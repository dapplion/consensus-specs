# Churn top-ups -- The Beacon Chain

## Introduction

Adding churn to deposit topups is a minimal security increase for current spec, but a valuable UX improvement for MaxEB https://ethresear.ch/t/increase-the-max-effective-balance-a-modest-proposal/15801

#### `PendingBalanceDeposit`

```python
class PendingBalanceDeposit(Container):
    index: ValidatorIndex
    amount: GWei
```

#### `BeaconState`

```python
class BeaconState(capella.BeaconState):
    pending_balance_deposits: PendingBalanceDeposit  # [New in Churn top-ups]
```

## Beacon chain state transition function

### Epoch processing

*Note*: Adds `process_pending_balance_deposits` before updating effective balances.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_balance_deposits(state)  # [New in Churn top-ups]
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```

#### `process_pending_balance_deposits`

```python
def process_pending_balance_deposits(state: BeaconState) -> None:
    epoch_churn = get_validator_churn_limit(state) * MAX_EFFECTIVE_BALANCE
    next_pending_deposit_index = 0
    for pending_balance_deposit in state.pending_balance_deposits:
        # Process up to churn
        if pending_balance_deposit.amount > epoch_churn:
            break

        increase_balance(state, pending_balance_deposit.index, pending_balance_deposit.amount)
        epoch_churn -= pending_balance_deposit.amount
        next_pending_deposit_index += 1

    state.pending_balance_deposits = state.pending_balance_deposits[next_pending_deposit_index:]
```

### Block processing

#### Modified `add_validator_to_registry`

*Note*: The function `add_validator_to_registry` is modified to not set effective_balance

```python
def get_validator_from_deposit(pubkey: BLSPubkey, withdrawal_credentials: Bytes32) -> Validator:
    return Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=0,  # [Modified in Churn top-ups]
    )
```

#### Modified `add_validator_to_registry`

*Note*: The function `add_validator_to_registry` is modified to not credit `balances`

```python
def add_validator_to_registry(state: BeaconState,
                              pubkey: BLSPubkey,
                              withdrawal_credentials: Bytes32,
                              amount: uint64) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, 0)
    # [New in Altair]
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, uint64(0))
    state.pending_balance_deposits.append(PendingBalanceDeposit(index, amount)) # [Modified in Churn top-ups]
```

#### Modified `apply_deposit`

*Note*: The function `apply_deposit` is modified to not credit `balances` on top-ups

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
        state.pending_balance_deposits.append(PendingBalanceDeposit(index, amount))  # [New in Churn top-ups]
```