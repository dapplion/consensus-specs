# Consolidation operation -- The Beacon Chain

## Introduction

Adds a new operation to consolidate the balance of a validator into another validator. This operation makes the target validator liable for the source validator's slashings.

## Constants

| Name | Value |
| - | - |
| `UNSET_CONSOLIDATED_INDEX` | `uint64(2**64 - 1)` |

#### Modified `Validator`

Note: The modifier pointers could be added in a new list to the beacon state.

Some other data could be re-purposed, for example:
- set `activation_eligibility_epoch` to point to consolidated target index. Using a prefix `CONSOLIDATED_PREFIX` for the first byte of 8
- set `withdrawal_credentials` to `CONSOLIDATED_PREFIX` + `uint_to_bytes(consolidation.target_index)`. However handling lingering rewards becomes more difficult. TODO: Is there any downside from losing the identity of the withdrawal id? Any future feature that may break?

```python
class Validator(phase0.Validator):
    consolidated: ValidatorIndex
```

#### `Consolidation`

```python
class Consolidation(Container):
    source_index: ValidatorIndex
    target_index: ValidatorIndex
    source_signature: TBD
    target_signature: BLSSignature
    
```

#### Process consolidation

```python
def is_consolidated(validator: Validator) -> bool:
   validator.consolidated != UNSET_CONSOLIDATED_INDEX
```

```python
def process_consolidation(state: BeaconState, consolidation: Consolidation) -> None:
    epoch = get_current_epoch(state)
    target_validator = state[consolidation.target_index]
    source_validator = state[consolidation.source_index]

    # target is active, not slashed, not consolidated
    assert is_active_validator(target_validator) and
        not target_validator.slashed and
        not is_consolidated(target_validator)

    # source is (active?), not slashed, not consolidated
    assert not source_validator.slashed and not is_consolidated(source_validator)

    # TODO: source validator must authenticate with their withdrawal credentials
    #       Must handle the case of withdrawal credentials being 0x01
    assert is_valid_signature(consolidation.source_signature)

    # TODO: target validator must authenticate with their voting key
    #       The target validator should be able to authorize with the voting key
    #       since it already has the capacity to slash itself. With this action
    #       it relegates the capacity to suffer slashing penalties to another
    #       entity. While increasing the potential damage it does not grant new
    #       capabilities.
    assert is_valid_signature(consolidation.target_signature)

    # Transfer all balance
    state.balances[consolidation.target_index] += state.balances[consolidation.source_index]
    state.balances[consolidation.source_index] = 0

    # effective balance must be immediatelly updated too in case a slashing is processed before the epoch transition
    # TODO: Those this adhoc transfer break hysteresis?
    target_validator.effective_balance += source_validator.effective_balance
    source_validator.effective_balance = 0

    # Update source validator record to point to target
    # TODO: May re-use an existing property to persist the target index
    validator.consolidated = consolidation.target_index

    # source validator should no longer be active:
    # `is_active_validator() == False`, so MUST validator.exit_epoch <= epoch
    #
    # ## `exit_epoch` usage:
    # - Condition for voluntary exit: `validator.exit_epoch == FAR_FUTURE_EPOCH`
    # - Condition for is active at epoch: `epoch < validator.exit_epoch`
    #   - if active, is selected for `get_active_validator_indices`
    #     - candidate for committee, proposer or sync committee
    #   - if active, is selected for `get_eligible_validator_indices`
    #     - candidate for inactivity penalties
    #   - if active + low effective balance -> initiate_validator_exit() 
    # - Used to compute the queue churn
    #
    # ## `withdrawable_epoch` usage:
    # - To post-punish slashings in `process_slashings`
    # - Condition for is_slashable_validator: `epoch < validator.withdrawable_epoch`
    # - Condition for `get_eligible_validator_indices`: `v.slashed and previous_epoch + 1 < v.withdrawable_epoch`
    # - Condition for `is_fully_withdrawable_validator`: `validator.withdrawable_epoch <= epoch and balance > 0`
    source_validator.exit_epoch = epoch
    source_validator.withdrawable_epoch = epoch

    # TODO: Should the inactivity scores by merged too?
    # TODO: What about lingering rewards attributed to this validator?
    #       Should they be forwarded to the target validator eventually?
    # TODO: What if there's a top-up to the consolidated validator?
```

#### Slashings

`process_slashings` should not be modified since the slashed status is forwarded to the target validator.

```python
def slash_validator(state: BeaconState,
                    slashed_index: ValidatorIndex,
                    whistleblower_index: ValidatorIndex=None) -> None:
    slashed_index = resolve_slashed_index(state, slashed_index)
    phase0.slash_validator(state, slashed_index, whistleblower_index)
```

```python
def resolve_slashed_index(state: BeaconState, index: ValidatorIndex) -> ValidatorIndex:
    if is_consolidated(state.validators[index]):
        # Recursively resolve consolidated index
        index = bytes_to_uint64(state.validators[index].withdrawal_credentials[26:])
        return resolve_slashed_index(state, index)
    else:
        return index
```
