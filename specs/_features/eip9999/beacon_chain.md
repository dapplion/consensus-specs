# EIP-9999 -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [State list lengths](#state-list-lengths)
  - [Gwei values](#gwei-values)
- [Containers](#containers)
  - [New Containers](#new-containers)
    - [`PendingWithdrawal`](#pendingwithdrawal)
  - [Changed Containers](#changed-containers)
    - [`ExecutionPayload`](#executionpayload)
  - [Extended Containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)
    - [Modified `process_withdrawals`](#modified-process_withdrawals)
    - [New `process_withdrawals`](#new-process_withdrawals)
    - [Modified `apply_deposit`](#modified-apply_deposit)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to prevent front running of deposits for distinct withdrawal credentials, [EIP-9999](https://github.com/ethereum/EIPs/pull/9999).

*Note:* This specification is built upon [Electra](../../electra/beacon_chain.md) and is under active development.

## Preset

### State list lengths

| Name | Value |
| - | - |
| `PENDING_WITHDRAWALS_LIMIT` | `uint64(2**13)` (= 8,192) |
| `MAX_WITHDRAWALS_PER_PAYLOAD` | `uint64(2**13)` (= 8,192) |

### Gwei values

| Name | Value |
| - | - |
| `RETURN_DEPOSIT_PENALTY` | `Gwei(2**0 * 10**9)` (= 1,000,000,000) |

## Containers

### New Containers

#### `PendingWithdrawal`

```python
class PendingWithdrawal(Container):
    validator_index: ValidatorIndex
    address: ExecutionAddress
    amount: Gwei
```

### Changed Containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress  # 'beneficiary' in the yellow paper
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32  # 'difficulty' in the yellow paper
    block_number: uint64  # 'number' in the yellow paper
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]  # [Modified in EIP-9999]
```

### Extended Containers

#### `BeaconState`

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    # [New in Electra:EIP6110]
    deposit_receipts_start_index: uint64
    # [New in EIP-9999]
    pending_withdrawals: List[PendingWithdrawal, PENDING_WITHDRAWALS_LIMIT]
```

## Beacon chain state transition function

### Block processing

#### Modified `get_expected_withdrawals`

```python
def get_expected_withdrawals(state: BeaconState) -> Sequence[Withdrawal]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []

    # [New in EIP-9999]
    for pending_withdrawal in state.pending_withdrawals:
        withdrawals.push(Withdrawal(
            index=withdrawal_index,
            validator_index=pending_withdrawal.validator_index,
            address=pending_withdrawal.address,
            amount=pending_withdrawal.amount,
        ))
        withdrawal_index += WithdrawalIndex(1)

    bound = min(
        len(state.validators),
        saturating_sub(MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - len(withdrawals))
    )
    for _ in range(bound):
        validator = state.validators[validator_index]
        balance = state.balances[validator_index]
        if is_fully_withdrawable_validator(validator, balance, epoch):
            withdrawals.append(Withdrawal(
                index=withdrawal_index,
                validator_index=validator_index,
                address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                amount=balance,
            ))
            withdrawal_index += WithdrawalIndex(1)
        elif is_partially_withdrawable_validator(validator, balance):
            withdrawals.append(Withdrawal(
                index=withdrawal_index,
                validator_index=validator_index,
                address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                amount=balance - MAX_EFFECTIVE_BALANCE,
            ))
            withdrawal_index += WithdrawalIndex(1)
        if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
            break
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
    return withdrawals
```

#### Modified `process_withdrawals`

#### New `process_withdrawals`

```python
def process_withdrawals(state: BeaconState, payload: ExecutionPayload) -> None:
    expected_withdrawals = get_expected_withdrawals(state)
    assert len(payload.withdrawals) == len(expected_withdrawals)
    state.pending_withdrawals = []  # [New in EIP-9999]

    for expected_withdrawal, withdrawal in zip(expected_withdrawals, payload.withdrawals):
        assert withdrawal == expected_withdrawal
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)

    # Update the next withdrawal index if this block contained withdrawals
    if len(expected_withdrawals) != 0:
        latest_withdrawal = expected_withdrawals[-1]
        state.next_withdrawal_index = WithdrawalIndex(latest_withdrawal.index + 1)

    # Update the next validator index to start the next withdrawal sweep
    if len(expected_withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = ValidatorIndex((expected_withdrawals[-1].validator_index + 1) % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        next_validator_index = ValidatorIndex(next_index % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index
```

#### Modified `apply_deposit`

```python
def apply_deposit(state: BeaconState,
                  pubkey: BLSPubkey,
                  withdrawal_credentials: Bytes32,
                  amount: uint64,
                  signature: BLSSignature) -> None:
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        deposit_message = DepositMessage(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            amount=amount,
        )
        domain = compute_domain(DOMAIN_DEPOSIT)  # Fork-agnostic domain since deposits are valid across forks
        signing_root = compute_signing_root(deposit_message, domain)
        if bls.Verify(pubkey, signing_root, signature):
            add_validator_to_registry(state, pubkey, withdrawal_credentials, amount)
    else:
        # Increase balance by deposit amount
        index = ValidatorIndex(validator_pubkeys.index(pubkey))

        # [New in EIP-9999]
        if (
            withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
            and withdrawal_credentials[12:] != state.validators[index].withdrawal_credentials[12:]
        ):
            state.pending_withdrawals.push(PendingWithdrawal(
                validator_index=index,
                address=ExecutionAddress(withdrawal_credentials[12:]),
                amount=amount - RETURN_DEPOSIT_PENALTY
            ))
        else:
            increase_balance(state, index, amount)
```

