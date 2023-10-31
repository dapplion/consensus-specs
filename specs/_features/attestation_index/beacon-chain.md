# EIP-XXXX -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Time parameters](#time-parameters)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [`is_reusable_validator`](#is_reusable_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `get_index_for_new_validator`](#modified-get_index_for_new_validator)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to move the attestation committee index outside of the signed message.

*Note:* This specification is built upon [Deneb](../../deneb/beacon_chain.md) and is under active development.

## Preset

### Time parameters

| Name | Value | Unit | Duration |
| - | - | - | - |
| `SAFE_EPOCHS_TO_REUSE_INDEX` | `uint64(2**16)` (= 65,536) | epochs | ~0.8 year |

## Containers

### Extended containers

#### AttestationData

```python
class AttestationData(Container):
    slot: Slot
    beacon_block_root: Root
    source: Checkpoint
    target: Checkpoint
```

#### Attestation

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    index: CommitteeIndex  # [New in EIPXXXX]
    data: AttestationData
    signature: BLSSignature
```

## Helper functions

### Beacon state accessors

#### `get_attesting_indices`

```python
def get_attesting_indices(state: BeaconState, attestation: Attestation) -> Set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``data`` and ``bits``.
    """
    committee = get_beacon_committee(state, attestation.data.slot, attestation.index)
    return set(index for i, index in enumerate(committee) if attestation.aggregation_bits[i])
```

## Beacon chain state transition function

### Block processing

#### Modified `process_attestation`

*Note*: The function `process_attestation` is modified to expand valid slots for inclusion to those in both `target.epoch` epoch and `target.epoch + 1` epoch for EIP-7045. Additionally, it utilizes an updated version of `get_attestation_participation_flag_indices` to ensure rewards are available for the extended attestation inclusion range for EIP-7045.

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot  # [Modified in Deneb:EIP7045]
    assert attestation.index < get_committee_count_per_slot(state, data.target.epoch)

    committee = get_beacon_committee(state, data.slot, attestation.index)
    assert len(attestation.aggregation_bits) == len(committee)

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(state, data, state.slot - data.slot)

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Update epoch participation flags
    if data.target.epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(epoch_participation[index], flag_index):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight

    # Reward proposer
    proposer_reward_denominator = (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

#### Modified `get_index_for_new_validator`

```python
def get_index_for_new_validator(state: BeaconState) -> ValidatorIndex:
    for index, validator in enumerate(state.validators):
        if is_reusable_validator(validator, state.balances[index], get_current_epoch(state)):
            return ValidatorIndex(index)
    return ValidatorIndex(len(state.validators))
```
