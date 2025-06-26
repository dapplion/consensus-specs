# L1HEADERS -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
- [Configuration](#configuration)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [New `compute_upstream_timestamp_at_slot`](#new-compute_upstream_timestamp_at_slot)
    - [New `compute_upstream_start_slot_at_epoch`](#new-compute_upstream_start_slot_at_epoch)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [New `process_upstream_chain`](#new-process_upstream_chain)
  - [Epoch processing](#epoch-processing)
    - [Modified `weigh_justification_and_finalization`](#modified-weigh_justification_and_finalization)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to make fork-choice conditional on an upstream chain.

*Note*: This specification is built upon [Electra](../../electra/beacon_chain.md) and is under active development.

## Preset

| Name | Value |
| - | - |
| `JUSTIFIED_EPOCHS_LIMIT` | `uint64(2**7)` (=128) |

## Configuration

| Name | Value | Unit |
| - | - | - |
| `UPSTREAM_GENESIS_SLOT`     | `0` | slots
| `UPSTREAM_GENESIS_TIME`     | `1606824023` | seconds
| `UPSTREAM_SECONDS_PER_SLOT` | `uint64(12)` | seconds
| `UPSTREAM_SLOTS_PER_EPOCH`  | `uint64(32)` | slots`

## Containers

### Modified containers

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: ExecutionRequests
    upstream_head: BeaconBlockHeader  # [New in L1HEADERS]
    upstream_justified_checkpoint: Checkpoint  # [New in L1HEADERS]
    upstream_finalized_checkpoint: Checkpoint  # [New in L1HEADERS]
```

*Note*: `upstream_head_root` is available to the EVM throught EIP-4788 (Beacon block root in the EVM) with a merkle proof from the beacon block root.

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
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justified_checkpoints: List[Checkpoint, JUSTIFIED_EPOCHS_LIMIT]  # [Modified in L1HEADERS]
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
    deposit_requests_start_index: uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: List[PendingDeposit, PENDING_DEPOSITS_LIMIT]
    pending_partial_withdrawals: List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]
    pending_consolidations: List[PendingConsolidation, PENDING_CONSOLIDATIONS_LIMIT]
    # [New in L1HEADERS]
    latest_upstream_head: BeaconBlockHeader
    latest_upstream_justified_checkpoint: Checkpoint
    latest_upstream_finalized_checkpoint: Checkpoint
```

## Helper functions

### Misc

#### New `compute_upstream_timestamp_at_slot`

```python
def compute_upstream_timestamp_at_slot(state: BeaconState, slot: Slot) -> uint64:
    slots_since_genesis = slot - UPSTREAM_GENESIS_SLOT
    return uint64(UPSTREAM_GENESIS_TIME + slots_since_genesis * UPSTREAM_SECONDS_PER_SLOT)
```


#### New `compute_upstream_start_slot_at_epoch`

```python
def compute_upstream_start_slot_at_epoch(epoch: Epoch) -> Slot:
    return Slot(epoch * UPSTREAM_SLOTS_PER_EPOCH)
```

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
    process_upstream_chain(state, block)
```

#### New `process_upstream_chain`

```python
def process_upstream_chain(state: BeaconState, block: BeaconBlock) -> None:
    # Point to an upstream block that's in the past
    assert compute_upstream_timestamp_at_slot(block.body.upstream_head.slot) <= compute_timestamp_at_slot(block.slot)

    # Ascending upstream slots
    assert block.body.upstream_head.slot >= state.latest_upstream_head.slot
    # Reject distinct blocks with equal slots, expect for the first post-fork state
    if (
        block.body.upstream_head.slot == state.latest_upstream_head.slot
        and state.latest_upstream_head.slot != BeaconBlockHeader()
    ):
        assert block.body.upstream_head == state.latest_upstream_head

    # TODO: Verify inclusion proofs of the upstream checkpoints
    state.latest_upstream_finalized_checkpoint = block.body.upstream_finalized_checkpoint;
    state.latest_upstream_justified_checkpoint = block.body.upstream_finalized_checkpoint;
```

### Epoch processing

#### Modified `weigh_justification_and_finalization`

*Note*: The function `weigh_justification_and_finalization` is modified to make justification and finalization checkpoint updates conditional on the upstream chain.

```python
def weigh_justification_and_finalization(state: BeaconState,
                                         total_active_balance: Gwei,
                                         previous_epoch_target_balance: Gwei,
                                         current_epoch_target_balance: Gwei) -> None:
    previous_epoch = get_previous_epoch(state)
    current_epoch = get_current_epoch(state)

    # Process justifications
    # Register that this epoch received enough votes to justify. But don't update the justified
    # checkpoint until the upstream chain justified it.
    if previous_epoch_target_balance * 3 >= total_active_balance * 2:
        state.justified_checkpoints.append(Checkpoint(epoch=previous_epoch,
                                                      root=get_block_root(state, previous_epoch))
    if current_epoch_target_balance * 3 >= total_active_balance * 2:
        state.justified_checkpoints.append(Checkpoint(epoch=current_epoch,
                                                      root=get_block_root(state, current_epoch))
        
    # We can only justify a checkpoint if its block point to an upstream block that is upstream justified.
    # We know that all ancestor blocks of this chain point to upstream canonical blocks.
    # We can justify only epochs in `voted_justified_epochs` set whose block points to an upstream block with
    # a slot <= than the slot of the upstream justified epoch.
    for checkpoint in reversed(state.justified_checkpoints):
        # `epoch` is in the L2 chain's time
        # The justified block of `epoch` has a timestamp <= than `timestamp(start_slot(epoch))`
        # `state.upstream_justified_block_timestamp` is in the upstream chain's time
        # Any L2 block must point to an upstream block that has <= timestamp
        checkpoint_block_timestamp = compute_timestamp_at_slot(compute_start_slot_at_epoch(checkpoint.epoch))
        upstream_justified_block_timestamp = compute_upstream_timestamp_at_slot(
            compute_upstream_start_slot_at_epoch(state.upstream_justified_checkpoint.epoch)
        )
        if checkpoint_block_timestamp <= upstream_justified_block_timestamp:
            # The block `checkpoint.root` must point to an upstream block that is justified
            state.current_justified_checkpoint = checkpoint
            break
# you cannot justified something uynless its l1 finalized, since there's still a risk that it will reorg

    # Process finalizations
    # Gasper paper: https://arxiv.org/pdf/2003.03052
    # Apply Definition 4.9 with K <= 3 to epochs prior to the upstream finalized checkpoint timestamp
    #
    # `satisfy_finality` must check if the epochs prior to Ethereum finality
    # satisfy the k-finalized condition. Because of the upper bound with
    # Ethereum's finality there's this set of epochs may not be recent
    #
    # First k-finalized conditions, used in Beacon chain today:
    # The 2nd/3rd/4th most recent epochs are justified, the 2nd using the 4th as source
    # The 2nd/3rd most recent epochs are justified, the 2nd using the 3rd as source
    # The 1st/2nd/3rd most recent epochs are justified, the 1st using the 3rd as source
    # The 1st/2nd most recent epochs are justified, the 1st using the 2nd as source
    finalized_checkpoint = satisfy_finality(
        state.upstream_finalized_checkpoint,
        state.justified_checkpoints
    )
    if finalized_checkpoint is not None:
        state.finalized_checkpoint = finalized_checkpoint
        # Prune `justified_checkpoints` that are too old
        state.justified_checkpoints = [
            cp for cp in state.justified_checkpoints
            if cp.epoch > finalized_checkpoint.epoch
        ]
# This is not good, because the votes still exist, and people cannot change to another chain. Here we just ignoring reality by not aknowliedging the votes that exist
```


