"""Real Python/JS MAC agreement for the bridge's timestamp/count numeric domain."""

import copy
import hashlib
import hmac
import json
import subprocess
import time

import pytest

from executors.ascend_extension.native import NativeAuthenticator, canonical


NODE_ROUNDTRIP = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
let input='';process.stdin.on('data',chunk=>input+=chunk);
process.stdin.on('end',async()=>{
  try {
    const fixture=JSON.parse(input),context={crypto:webcrypto,TextEncoder,Uint8Array,Date};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync('extensions/ascend-x1/pairing.js','utf8'),context);
    const api=context.FreightDeskPairing;
    const pairing=await api.importBundle(fixture.bundle,fixture.bundle.extension_id);
    const proof=await api.proof(pairing,fixture.challenge);
    const body=await api.verify(pairing,fixture.host_envelopes[0]);
    assert.deepEqual(JSON.parse(JSON.stringify(body)),JSON.parse(JSON.stringify(fixture.client_body)));
    await assert.rejects(api.verify(pairing,fixture.host_envelopes[0]));
    const tampered=structuredClone(fixture.host_envelopes[1]);
    tampered.body.count=99;
    await assert.rejects(api.verify(pairing,tampered));
    await api.verify(pairing,fixture.host_envelopes[1]);
    const client_envelope=await api.sign(pairing,fixture.client_body);
    process.stdout.write(JSON.stringify({proof,client_envelope,host_tamper_rejected:true,host_replay_rejected:true}));
  } catch {process.stderr.write('Synthetic native numeric MAC regression failed.');process.exitCode=1;}
});
"""


def test_python_js_numeric_mac_roundtrip_preserves_tamper_and_replay_guards():
    key = bytes.fromhex("1" * 64)
    auth = NativeAuthenticator("a" * 32, key)
    challenge = auth.challenge(auth.origin)
    proof = hmac.new(key, canonical(challenge), hashlib.sha256).hexdigest()
    auth.authenticate(auth.origin, proof)
    body = {
        "count": 1.0,
        "command": {"lease_expires_at": 1789183969.0},
        "nested": [0.0, -0.0, 1789183969.125, 1789183969.000001],
        "safe_integer_edge": 9007199254740991.0,
        "unicode": "caf\u00e9 \U0001f69b",
    }
    fixture = {
        "bundle": {
            "extension_id": "a" * 32,
            "installation_id": "b" * 32,
            "protocol": 1,
            "tenant_id": "booking-logistics",
            "actor": "FreightDesk/Avery",
            "generation": "c" * 32,
            "key": key.hex(),
            "expires_at": int(time.time()) + 300,
        },
        "challenge": challenge | {
            "protocol": 1, "installation_id": "b" * 32, "generation": "c" * 32,
        },
        "host_envelopes": [auth.sign(body), auth.sign(body)],
        "client_body": body,
    }
    result = subprocess.run(
        ["node", "-e", NODE_ROUNDTRIP],
        input=json.dumps(fixture),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, "Synthetic Python/JS numeric MAC roundtrip failed."
    verified = json.loads(result.stdout)
    assert verified["proof"] == proof
    assert verified["host_tamper_rejected"] and verified["host_replay_rejected"]
    incoming = verified["client_envelope"]
    tampered = copy.deepcopy(incoming)
    tampered["body"]["count"] = 99
    with pytest.raises(PermissionError, match="native_authentication_or_replay_failure"):
        auth.verify(auth.origin, tampered)
    assert auth.verify(auth.origin, incoming) == body
    with pytest.raises(PermissionError, match="native_authentication_or_replay_failure"):
        auth.verify(auth.origin, incoming)


def test_integral_float_normalization_does_not_round_fractional_timestamps():
    assert canonical({"t": [1.0, -0.0, 1789183969.125]}) == b'{"t":[1,0,1789183969.125]}'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_native_numbers_fail_closed(value):
    with pytest.raises(ValueError, match="native_numeric_invalid"):
        canonical({"value": value})
