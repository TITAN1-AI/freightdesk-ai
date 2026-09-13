"""Closed vocabulary for pairing-only diagnostics. Never accept free-form errors or payloads."""
RESULTS = frozenset('''PAIRING_FILE_NOT_SELECTED PAIRING_FILE_SELECTED PAIRING_FILE_READ_FAILED
PAIRING_SCHEMA_INVALID PAIRING_EXPIRED PAIRING_ALREADY_CONSUMED EXTENSION_ID_MISMATCH
PAIRING_VALIDATING PAIRING_HANDSHAKE_PENDING HOST_HANDSHAKE_FAILED PAIRING_PROOF_REJECTED
PAIRING_DPAPI_FAILED PAIRING_BINDING_MISMATCH PAIRING_PERSIST_FAILED PAIRING_ACK_INVALID
PAIRING_INTERRUPTED PAIRING_REQUIRED HOST_REACHABLE PAIRING_SUCCESS PAIRING_DIAGNOSTIC_SAVED
COMMAND_NOT_ALLOWED'''.split())
STAGES = frozenset('''FILE_INPUT FILE_READ JSON_PARSE SCHEMA_VALIDATION EXTENSION_ID_VALIDATION
EXPIRY_VALIDATION NATIVE_CONNECT DPAPI_VALIDATION ONE_TIME_VALIDATION PROOF_VALIDATION
PAIRING_PERSIST ACK_VERIFICATION PAIRED LIFECYCLE'''.split())
FLAGS = ('extension_id_match', 'bootstrap_expired', 'bootstrap_consumed')


def validate_metadata(value: dict) -> dict:
    if (not isinstance(value, dict) or set(value) - {'handshake_stage', 'result_code', *FLAGS} or
        value.get('handshake_stage') not in STAGES or value.get('result_code') not in RESULTS or
        any(type(value[k]) is not bool for k in FLAGS if k in value)):
        raise ValueError('pairing_diagnostic_invalid')
    return dict(value)


def result_code(error: Exception) -> str:
    code = error.args[0] if len(error.args) == 1 and isinstance(error.args[0], str) else ''
    return {
        'extension_id_mismatch': 'EXTENSION_ID_MISMATCH', 'pairing_expired': 'PAIRING_EXPIRED',
        'native_session_expired': 'PAIRING_EXPIRED', 'stale_pairing': 'PAIRING_BINDING_MISMATCH',
        'pairing_already_used': 'PAIRING_ALREADY_CONSUMED', 'native_pairing_proof_invalid': 'PAIRING_PROOF_REJECTED',
        'pairing_protection_failed': 'PAIRING_DPAPI_FAILED', 'pairing_persist_failed': 'PAIRING_PERSIST_FAILED',
        'pairing_required': 'PAIRING_REQUIRED', 'installation_binding_invalid': 'PAIRING_BINDING_MISMATCH',
        'pairing_diagnostic_invalid': 'PAIRING_SCHEMA_INVALID'
    }.get(code, 'PAIRING_REQUIRED' if isinstance(error, FileNotFoundError) else 'HOST_HANDSHAKE_FAILED')
