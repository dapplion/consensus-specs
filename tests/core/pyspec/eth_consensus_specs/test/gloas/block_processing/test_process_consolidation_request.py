from eth_consensus_specs.test.context import (
    default_activation_threshold,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.electra.block_processing.test_process_consolidation_request import (
    run_consolidation_processing,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.withdrawals import (
    set_builder_withdrawal_credential,
    set_compounding_withdrawal_credential,
)


@with_gloas_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_consolidation_source_validator_with_builder_credentials(spec, state):
    """
    A validator with builder (0xB0) withdrawal credentials can consolidate into
    a compounding validator with a request from its execution address.
    """
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for consolidation
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    source_address = b"\x5b" * 20
    set_builder_withdrawal_credential(spec, state, source_index, address=source_address)
    set_compounding_withdrawal_credential(spec, state, target_index)
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    yield from run_consolidation_processing(spec, state, consolidation)


@with_gloas_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_consolidation_target_validator_with_builder_credentials(spec, state):
    """
    A validator with builder (0xB0) withdrawal credentials is not compounding,
    so it cannot be a consolidation target.
    """
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for consolidation
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    source_address = b"\x22" * 20
    set_compounding_withdrawal_credential(spec, state, source_index, address=source_address)
    set_builder_withdrawal_credential(spec, state, target_index)
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    yield from run_consolidation_processing(spec, state, consolidation, success=False)


@with_gloas_and_later
@spec_state_test
def test_switch_to_compounding_validator_with_builder_credentials(spec, state):
    """
    A validator with builder (0xB0) withdrawal credentials can switch to
    compounding (0x02) credentials for the same execution address, and its
    excess balance is queued as a pending deposit.
    """
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    source_address = b"\x5b" * 20
    excess_balance = spec.EFFECTIVE_BALANCE_INCREMENT
    set_builder_withdrawal_credential(spec, state, source_index, address=source_address)
    state.validators[source_index].effective_balance = spec.MIN_ACTIVATION_BALANCE
    state.balances[source_index] = spec.MIN_ACTIVATION_BALANCE + excess_balance
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[source_index].pubkey,
    )
    pre_pending_deposits = state.pending_deposits.copy()
    pre_pending_consolidations = state.pending_consolidations.copy()

    yield "pre", state
    yield "consolidation_request", consolidation

    spec.process_consolidation_request(state, consolidation)

    yield "post", state

    validator = state.validators[source_index]
    assert validator.withdrawal_credentials == (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + source_address
    )
    assert state.balances[source_index] == spec.MIN_ACTIVATION_BALANCE
    assert list(state.pending_deposits) == list(pre_pending_deposits) + [
        spec.PendingDeposit(
            pubkey=validator.pubkey,
            withdrawal_credentials=validator.withdrawal_credentials,
            amount=excess_balance,
            signature=spec.G2_POINT_AT_INFINITY,
            slot=spec.GENESIS_SLOT,
        )
    ]
    assert list(state.pending_consolidations) == list(pre_pending_consolidations)
