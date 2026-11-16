from eth_consensus_specs.test.context import spec_state_test, with_gloas_and_later
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.withdrawals import set_builder_withdrawal_credential


@with_gloas_and_later
@spec_state_test
def test_effective_balance_capped_validator_with_builder_credentials(spec, state):
    """
    A validator with builder (0xB0) withdrawal credentials is not compounding,
    so its effective balance stays capped at MIN_ACTIVATION_BALANCE.
    """
    validator_index = 0
    set_builder_withdrawal_credential(spec, state, validator_index)
    state.validators[validator_index].effective_balance = spec.MIN_ACTIVATION_BALANCE
    state.balances[validator_index] = (
        spec.MIN_ACTIVATION_BALANCE + 8 * spec.EFFECTIVE_BALANCE_INCREMENT
    )

    yield from run_epoch_processing_with(spec, state, "process_effective_balance_updates")

    assert state.validators[validator_index].effective_balance == spec.MIN_ACTIVATION_BALANCE
