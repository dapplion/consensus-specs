# L1HEADERS -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Helpers](#helpers)
    - [Modified `Store`](#modified-store)
    - [Modified `filter_block_tree`](#modified-filter_block_tree)
    - [New `get_upstream_canonical_block`](#new-get_upstream_canonical_block)
  - [Handlers](#handlers)
    - [New `on_upstream_head`](#new-on_upstream_head)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the L1HEADERS feature

## Fork choice

### Helpers

#### Modified `Store`

*Note*: `Store` is modified to track the upstream chain canonical blocks

```python
@dataclass
class Store(object):
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: Set[ValidatorIndex]
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    block_timeliness: Dict[Root, boolean] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    # [New in L1HEADERS]
    upstream_canonical_blocks: List[BeaconBlockHeader] = field(default_factory=Set)
```

#### Modified `filter_block_tree`

*Note*: External calls to `filter_block_tree` (i.e., any calls that are not made by the recursive logic in this function) MUST set `block_root` to `store.justified_checkpoint`.

```python
def filter_block_tree(store: Store, block_root: Root, blocks: Dict[Root, BeaconBlock]) -> bool:
    block = store.blocks[block_root]
    children = [
        root for root in store.blocks.keys()
        if store.blocks[root].parent_root == block_root
    ]

    # If any children branches contain expected finalized/justified checkpoints,
    # add to filtered block-tree and signal viability to parent.
    if any(children):
        filter_block_tree_result = [filter_block_tree(store, child, blocks) for child in children]
        if any(filter_block_tree_result):
            blocks[block_root] = block
            return True
        return False

    current_epoch = get_current_store_epoch(store)
    voting_source = get_voting_source(store, block_root)

    # The voting source should be either at the same height as the store's justified checkpoint or
    # not more than two epochs ago
    correct_justified = (
        store.justified_checkpoint.epoch == GENESIS_EPOCH
        or voting_source.epoch == store.justified_checkpoint.epoch
        or voting_source.epoch + 2 >= current_epoch
    )

    finalized_checkpoint_block = get_checkpoint_block(
        store,
        block_root,
        store.finalized_checkpoint.epoch,
    )

    correct_finalized = (
        store.finalized_checkpoint.epoch == GENESIS_EPOCH
        or store.finalized_checkpoint.root == finalized_checkpoint_block
    )

    # [New in L1HEADERS]
    upstream_is_canonical = store.upstream_canonical_blocks.has(block.body.upstream_head)

    # If expected finalized/justified, add to viable block-tree and signal viability to parent.
    if correct_justified and correct_finalized and upstream_is_canonical:
        blocks[block_root] = block
        return True

    # Otherwise, branch not viable
    return False
```

#### New `get_upstream_canonical_block`

```python
def get_target_upstream_canonical_block(store: Store, slot: Root):
    for block in reversed(store.upstream_canonical_blocks):
        if compute_upstream_timestamp_at_slot(block.body.upstream_head.slot) <= compute_timestamp_at_slot(slot):
            return block
    # Should always return a value
```

### Handlers

#### New `on_upstream_head`

`on_upstream_head` is called every time the upstream chain head changes, either due to a new block or a re-org.

```python
def on_upstream_head(store: Store) -> None:
    # `retrieve_upstream_canonical_blocks` is implementation dependent. It returns all the upstream block
    # between genesis and the head in ascending slot order.
    #
    # *Note*: that only upstream blocks with a slot >= than 
    # `blocks[store.finalized_checkpoint.root].body.upstream_head.slot` are relevant.
    store.upstream_canonical_blocks = retrieve_upstream_canonical_blocks()
```
