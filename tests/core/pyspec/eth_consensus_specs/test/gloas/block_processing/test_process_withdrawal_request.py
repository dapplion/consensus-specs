from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.electra.block_processing.test_process_withdrawal_request import (
    run_withdrawal_request_processing,
)
from eth_consensus_specs.test.helpers.withdrawals import set_builder_withdrawal_credential


def prepare_validator_with_builder_credentials(spec, state, address, excess_balance=0):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    set_builder_withdrawal_credential(spec, state, validator_index, address=address)
    state.validators[validator_index].effective_balance = spec.MIN_ACTIVATION_BALANCE
    state.balances[validator_index] = spec.MIN_ACTIVATION_BALANCE + excess_balance
    return validator_index


@with_gloas_and_later
@spec_state_test
def test_full_exit_request_validator_with_builder_credentials(spec, state):
    """
    A validator with builder (0xB0) withdrawal credentials can exit with a
    withdrawal request from its execution address.
    """
    address = b"\x5b" * 20
    validator_index = prepare_validator_with_builder_credentials(spec, state, address)
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[validator_index].pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request)


@with_gloas_and_later
@spec_state_test
def test_full_exit_request_validator_with_builder_credentials_incorrect_source_address(spec, state):
    """
    A withdrawal request for a validator with builder (0xB0) withdrawal
    credentials from another address is ignored.
    """
    address = b"\x5b" * 20
    validator_index = prepare_validator_with_builder_credentials(spec, state, address)
    withdrawal_request = spec.WithdrawalRequest(
        source_address=b"\x33" * 20,
        validator_pubkey=state.validators[validator_index].pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request, success=False)


@with_gloas_and_later
@spec_state_test
def test_partial_withdrawal_request_validator_with_builder_credentials(spec, state):
    """
    As for 0x01 credentials, a partial withdrawal request for a validator with
    builder (0xB0) withdrawal credentials is ignored. Its excess balance is
    withdrawn by the sweep instead.
    """
    address = b"\x5b" * 20
    validator_index = prepare_validator_with_builder_credentials(
        spec, state, address, excess_balance=spec.EFFECTIVE_BALANCE_INCREMENT
    )
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[validator_index].pubkey,
        amount=spec.EFFECTIVE_BALANCE_INCREMENT,
    )

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request, success=False)
