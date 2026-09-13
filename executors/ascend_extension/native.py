"""Native pipe codec and paired message authenticator; no process launch/registry/socket operations."""
import hashlib
import hmac
import json
import math
import re
import secrets
import struct

MAX_BYTES = 65536


def canonical(value):
    # JSON has one numeric type. JS parses 1.0 as Number(1), and JSON.stringify emits
    # "1" (also "0" for -0.0). Match that representation before MAC signing, without
    # rounding fractional timestamps or accepting an alternative MAC on verification.
    def json_numbers(item):
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError('native_numeric_invalid')
            if item.is_integer() and abs(item) <= 9007199254740991:
                return int(item)
        if isinstance(item, dict):
            return {key: json_numbers(nested) for key, nested in item.items()}
        if isinstance(item, (list, tuple)):
            return [json_numbers(nested) for nested in item]
        return item
    return json.dumps(json_numbers(value), sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def encode_message(value: dict) -> bytes:
    # Framing preserves JSON scalar types for strict protocol validation on input.
    # Numeric normalization belongs to the MAC representation, not the wire decoder.
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')
    if len(body) > MAX_BYTES:
        raise ValueError('native_message_bound')
    return struct.pack('<I', len(body)) + body


def decode_message(frame: bytes) -> dict:
    if len(frame) < 4:
        raise ValueError('native_frame_invalid')
    size, = struct.unpack('<I', frame[:4])
    if size > MAX_BYTES or len(frame) != size + 4:
        raise ValueError('native_frame_invalid')
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate_json_key')
                result[key] = value
            return result
        result = json.loads(frame[4:], object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise ValueError('native_json_invalid') from None
    if not isinstance(result, dict):
        raise ValueError('native_shape_invalid')
    return result


class NativeAuthenticator:
    """Injected private pairing key. Browser allowlist alone is not an app-level authentication proof.

    Owner-run pairing protects the host key with CurrentUser DPAPI; tests inject ephemeral fixture keys.
    Native stdio is local to the launched process; do not treat argv as protection against same-user malware.
    """
    def __init__(self, extension_id: str, key: bytes):
        if not re.fullmatch('[a-p]{32}', extension_id) or len(key) < 32:
            raise ValueError('pairing_invalid')
        self.origin = f'chrome-extension://{extension_id}/'
        self._key = key
        self.session_id = secrets.token_hex(16)
        self._incoming = 0
        self._outgoing = 0
        self._authenticated = False

    def challenge(self, caller_origin: str) -> dict:
        if caller_origin != self.origin or self._authenticated:
            raise PermissionError('native_origin_or_session_denied')
        return {'session_id': self.session_id, 'extension_origin': self.origin,
            'tenant_id': 'booking-logistics', 'actor': 'FreightDesk/Avery'}

    def authenticate(self, caller_origin: str, proof: str):
        challenge = self.challenge(caller_origin)
        expected = hmac.new(self._key, canonical(challenge), hashlib.sha256).hexdigest()
        if not isinstance(proof, str) or not hmac.compare_digest(expected, proof):
            raise PermissionError('native_pairing_proof_invalid')
        self._authenticated = True

    def sign(self, body: dict) -> dict:
        if not self._authenticated:
            raise PermissionError('native_pairing_required')
        self._outgoing += 1
        message = {'session_id': self.session_id, 'sequence': self._outgoing, 'body': body, 'direction': 'host_to_extension'}
        return dict(message, mac=hmac.new(self._key, canonical(message), hashlib.sha256).hexdigest())

    def verify(self, caller_origin: str, message: dict) -> dict:
        if not self._authenticated or caller_origin != self.origin:
            raise PermissionError('native_pairing_required')
        if set(message) != {'session_id', 'sequence', 'body', 'mac', 'direction'}:
            raise PermissionError('native_envelope_invalid')
        signed = {k: message[k] for k in ('session_id', 'sequence', 'body', 'direction')}
        expected = hmac.new(self._key, canonical(signed), hashlib.sha256).hexdigest()
        if (message['direction'] != 'extension_to_host' or message['session_id'] != self.session_id or type(message['sequence']) is not int or
            message['sequence'] != self._incoming + 1 or not isinstance(message['mac'], str) or
            not hmac.compare_digest(expected, message['mac'])):
            raise PermissionError('native_authentication_or_replay_failure')
        self._incoming += 1
        if not isinstance(message['body'], dict) or len(canonical(message['body'])) > MAX_BYTES:
            raise ValueError('native_body_invalid')
        return message['body']


class NativeBridgeInterface:
    """Fail-closed integration point until a separately approved pairing/host is installed."""
    async def exchange(self, command: dict) -> dict:
        raise PermissionError('production_extension_bridge_disabled')
