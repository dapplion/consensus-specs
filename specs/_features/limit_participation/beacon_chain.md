# Limit participation -- The Beacon Chain


## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_committee_count_per_slot`](#get_committee_count_per_slot)
    - [`compute_committee`](#compute_committee)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This feature introduces a stronger disincentivize to active index count growth. A very large index count makes future roadmap items like SSF or ePBS very difficult to deliver. It also introduces direct incentives for validators to consolidate if MAX_EFFECTIVE_BALANCE is raised. 

*Note:* This specification is built upon [Capella](../../capella/beacon-chain.md) and is under active development.

## Configuration

| Name | Value |
| - | - |
| `MAX_PARTICIPANT_INDEX_COUNT` | uint64(18446744073709551615) **TBD** |

## Helper functions

### Beacon state accessors

#### `get_committee_count_per_slot`

```python
def get_committee_count_per_slot(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of committees in each slot for the given ``epoch``.
    """
    participant_index_count = min(MAX_PARTICIPANT_INDEX_COUNT, len(get_active_validator_indices(state, epoch)))
    return max(uint64(1), min(
        MAX_COMMITTEES_PER_SLOT,
        uint64(participant_index_count) // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
    ))
```

#### `compute_committee`

```python
def compute_committee(indices: Sequence[ValidatorIndex],
                      seed: Bytes32,
                      index: uint64,
                      count: uint64) -> Sequence[ValidatorIndex]:
    """
    Return the committee corresponding to ``indices``, ``seed``, ``index``, and committee ``count``.
    """
    participating_indices = min(MAX_PARTICIPANT_INDEX_COUNT, len(indices))
    start = (participating_indices * index) // count
    end = (participating_indices * uint64(index + 1)) // count
    return [indices[compute_shuffled_index(uint64(i), uint64(len(indices)), seed)] for i in range(start, end)]
```
