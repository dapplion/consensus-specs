# EIP-8025 -- Guest Program

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Guest inputs](#guest-inputs)
  - [New `PrivateInput`](#new-privateinput)
- [Guest processing](#guest-processing)
  - [New `verify_execution_payload_binding`](#new-verify_execution_payload_binding)
  - [New `verify_execution_transition`](#new-verify_execution_transition)
- [Execution engine](#execution-engine)
- [Builder signature](#builder-signature)

<!-- mdformat-toc end -->

## Introduction

This document defines the private input and the processing logic of the guest
program. Each run proves one execution payload and binds it to the beacon block
that committed to it. The public input it commits to is the `PublicInput`
defined in [beacon-chain.md](./beacon-chain.md).

The guest authenticates the post-state of the target block against that block's
root, and binds the payload to the `ExecutionPayloadBid` the state holds. The
bid commits to `block_hash`, which the execution engine recomputes from the
payload, so the bid determines the payload uniquely.

## Guest inputs

The guest inputs are implementation-level dataclasses, not consensus SSZ
containers.

### New `PrivateInput`

```python
@dataclass
class PrivateInput:
    state: BeaconState
    payload: ExecutionPayload
    execution_requests: ExecutionRequests
    execution_witness: Any
```

- `state` is the post-state of the target block, and `payload` with
  `execution_requests` are the contents of that block's payload envelope.
- `execution_witness` has the execution-specs type `ExecutionWitness`. The
  execution engine running in the guest is bound to it.

`state` is the step's beacon state witness. It is a post-block state, not
advanced by `process_slots`, so its `latest_block_header.state_root` is still
empty. Implementations SHOULD supply it as a partial SSZ tree whose root is the
full state root and in which only the fields read by the guest are expanded.
Reading a field that is not expanded MUST fail the proof.

## Guest processing

### New `verify_execution_payload_binding`

```python
def verify_execution_payload_binding(
    state: BeaconState,
    payload: ExecutionPayload,
    execution_requests: ExecutionRequests,
    execution_engine: ExecutionEngine,
) -> None:
    bid = state.latest_execution_payload_bid

    # Bind the payload to the bid committed to by the beacon block
    assert payload.block_hash == bid.block_hash
    assert hash_tree_root(execution_requests) == bid.execution_requests_root

    # Verify the payload against the beacon state
    assert payload.slot_number == state.slot
    assert payload.parent_hash == state.latest_block_hash
    assert payload.timestamp == compute_time_at_slot(state.genesis_time, state.slot)
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    # Gloas enforces these limits only in payload envelope gossip. The gossip
    # helper raises ``GossipReject``, which fails the proof like an assertion.
    verify_execution_requests_limits(execution_requests)
    assert len(payload.withdrawals) <= MAX_WITHDRAWALS_PER_PAYLOAD

    # Compute versioned hashes
    versioned_hashes = VersionedHashes()
    for commitment in bid.blob_kzg_commitments:
        versioned_hashes.append(kzg_commitment_to_versioned_hash(commitment))

    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=execution_requests,
        )
    )
```

### New `verify_execution_transition`

```python
def verify_execution_transition(
    execution_engine: ExecutionEngine,
    private_input: PrivateInput,
) -> PublicInput:
    state = private_input.state

    # Authenticate the post-state against the block root it commits to
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    beacon_block_root = hash_tree_root(header)

    # Bind the payload to the block and validate it statelessly
    verify_execution_payload_binding(
        state,
        private_input.payload,
        private_input.execution_requests,
        execution_engine,
    )

    return PublicInput(
        beacon_block_root=beacon_block_root,
        successful_validation=Boolean(True),
        chain_id=DEPOSIT_CHAIN_ID,
        schema_id=STATELESS_INPUT_SCHEMA_ID,
    )
```

Any failed assertion or raised exception fails the proof.

## Execution engine

Inside the guest, the execution engine has no execution state. Its
`verify_and_notify_new_payload` validates the payload statelessly against the
execution witness, with the guarantees the `ExecutionEngine` specification
requires of that function. It MUST validate the payload under the chain ID
`DEPOSIT_CHAIN_ID` and the fork rules the guest implements, and MUST reject a
payload whose timestamp falls outside that fork. The guest MUST NOT take the
chain ID or the fork schedule from its private input.

Validation MUST be equivalent to the execution-specs
`verify_stateless_new_payload` applied to a `StatelessInput` built from the
request, the execution witness and `DEPOSIT_CHAIN_ID`.

## Builder signature

The guest does not verify the envelope signature. The bid in the authenticated
state commits to `block_hash`, so the payload the guest proves is the payload
the beacon block committed to, whoever revealed it. The signature authenticates
the revealer, which consensus clients verify natively on the envelope gossip
topic.

The guest does not prove data availability, and a proof does not imply that the
payload was revealed.
