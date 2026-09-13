"""Windows-local installation and expiring pairing state; never print configuration/key material."""
import ctypes
import json
import re
import secrets
import sqlite3
import time
from ctypes import wintypes
from contextlib import contextmanager
from datetime import datetime, timezone

from app.core.runtime import RuntimePaths

HOST_NAME = 'com.freightdesk.ascend_x1'
TENANT = 'booking-logistics'
ACTOR = 'FreightDesk/Avery'
PROTOCOL = 1


def windows_sid():
    advapi, kernel = ctypes.WinDLL('advapi32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token, size, result = wintypes.HANDLE(), wintypes.DWORD(), wintypes.LPWSTR()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise PermissionError('windows_identity_unavailable')
    try:
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, buf, size, ctypes.byref(size)):
            raise PermissionError('windows_identity_unavailable')
        if not advapi.ConvertSidToStringSidW(ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.byref(result)):
            raise PermissionError('windows_identity_unavailable')
        try:
            return result.value
        finally:
            kernel.LocalFree(result)
    finally:
        kernel.CloseHandle(token)


def dpapi(data: bytes, *, decrypt=False) -> bytes:
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    crypt, kernel = ctypes.WinDLL('crypt32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, output = Blob(len(data), buffer), Blob()
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise PermissionError('pairing_protection_failed')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class PairingRepository:
    def __init__(self, paths=None, *, sid=windows_sid, protect=dpapi, clock=time.time):
        self.paths = paths or RuntimePaths.from_environment()
        self.sid, self.protect, self.clock = sid, protect, clock

    def path(self, name):
        return self.paths.path('Data', TENANT, 'ascend-native', name)

    def secret_path(self):
        return self.paths.path('Secrets', 'ascend-native-pairing.dpapi')

    def config(self):
        data = json.loads(self.path('installation.json').read_text(encoding='utf-8'))
        if (set(data) != {'extension_id','installation_id','windows_sid','protocol','tenant_id','actor','runtime_root'} or
            not re.fullmatch('[a-p]{32}', data['extension_id']) or
            not re.fullmatch('[a-f0-9]{32}', data['installation_id']) or
            type(data['protocol']) is not int or data['protocol'] != PROTOCOL or
            data['tenant_id'] != TENANT or data['actor'] != ACTOR or data['windows_sid'] != self.sid() or
            data['runtime_root'] != r'C:\FreightDeskRuntime'):
            raise PermissionError('installation_binding_invalid')
        return data

    def capture(self, extension_id):
        if not re.fullmatch('[a-p]{32}', extension_id):
            raise ValueError('extension_id_invalid')
        if self.path('installation.json').exists():
            raise PermissionError('installation_exists_reset_required')
        self.path('installation.json').parent.mkdir(parents=True, exist_ok=True)
        data = {'extension_id':extension_id, 'installation_id':secrets.token_hex(16), 'windows_sid':self.sid(),
            'protocol':PROTOCOL, 'tenant_id':TENANT, 'actor':ACTOR, 'runtime_root':r'C:\FreightDeskRuntime'}
        self.path('installation.json').write_text(json.dumps(data), encoding='utf-8')
        manifest = {'name':HOST_NAME, 'description':'FreightDesk Ascend read-only native host',
            'path':str(self.path('FreightDeskAscendHost.exe')), 'type':'stdio',
            'allowed_origins':[f'chrome-extension://{extension_id}/']}
        self.path('host-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    def load_pairing(self):
        encrypted = self.secret_path().read_bytes()
        try:
            decrypted = self.protect(encrypted, decrypt=True)
        except Exception:
            raise PermissionError('pairing_protection_failed') from None
        data = json.loads(decrypted)
        config = self.config()
        if (set(data) != {'extension_id','installation_id','protocol','tenant_id','actor','generation','key','expires_at'} or
            any(data[k] != config[k] for k in ('extension_id','installation_id','protocol','tenant_id','actor')) or
            type(data['protocol']) is not int or type(data['expires_at']) is not int or
            not re.fullmatch('[a-f0-9]{32}', data['generation']) or not re.fullmatch('[a-f0-9]{64}', data['key'])):
            raise PermissionError('stale_pairing')
        if self.clock() >= data['expires_at']:
            raise PermissionError('pairing_expired')
        if data['expires_at'] > self.clock() + 601:
            raise PermissionError('stale_pairing')
        return data

    def begin_pairing(self):
        config = self.config()
        now = self.clock()
        package = {k:config[k] for k in ('extension_id','installation_id','protocol','tenant_id','actor')}
        package.update(generation=secrets.token_hex(16), key=secrets.token_hex(32), expires_at=int(now+600))
        self.secret_path().parent.mkdir(parents=True, exist_ok=True)
        self.secret_path().write_bytes(self.protect(json.dumps(package).encode()))
        self.path('pairing-bootstrap.json').write_text(json.dumps(package), encoding='utf-8')
        return self.path('pairing-bootstrap.json')

    def claim(self, generation):
        pairing = self.load_pairing()
        if pairing['generation'] != generation:
            raise PermissionError('stale_pairing')
        with self.database() as db:
            try:
                db.execute('INSERT INTO consumed(kind,id) VALUES (?,?)', ('pairing',generation))
            except sqlite3.IntegrityError:
                raise PermissionError('pairing_already_used') from None
        self.path('pairing-bootstrap.json').unlink(missing_ok=True)

    def is_consumed(self, generation: str) -> bool:
        with self.database() as db:
            return db.execute('SELECT 1 FROM consumed WHERE kind=? AND id=?', ('pairing', generation)).fetchone() is not None

    def pairing_audit(self, metadata: dict) -> None:
        from executors.ascend_extension.diagnostics import FLAGS, validate_metadata
        safe = validate_metadata(metadata)
        with self.database() as db:
            db.execute('INSERT INTO pairing_attempts VALUES (?,?,?,?,?,?)',
                (datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                *(safe.get(k) for k in FLAGS), safe['handshake_stage'], safe['result_code']))

    @contextmanager
    def database(self):
        # Runtime availability and path/reparse validation are mandatory before any host message.
        self.config()
        db = sqlite3.connect(self.path('bridge.sqlite3'), timeout=2)
        db.execute('CREATE TABLE IF NOT EXISTS consumed(kind TEXT,id TEXT,PRIMARY KEY(kind,id))')
        db.execute('CREATE TABLE IF NOT EXISTS audit(at INTEGER,operation TEXT,outcome TEXT,tenant TEXT,actor TEXT)')
        db.execute('''CREATE TABLE IF NOT EXISTS pairing_attempts(timestamp TEXT,extension_id_match INTEGER,
            bootstrap_expired INTEGER,bootstrap_consumed INTEGER,handshake_stage TEXT,result_code TEXT)''')
        for table in ('consumed', 'audit', 'pairing_attempts'):
            for operation in ('UPDATE', 'DELETE'):
                db.execute(f'CREATE TRIGGER IF NOT EXISTS {table}_no_{operation} BEFORE {operation} ON {table} '
                    "BEGIN SELECT RAISE(ABORT, 'append_only_native_ledger'); END")
        try:
            with db:
                yield db
        finally:
            db.close()

    def consume_request(self, request_id):
        if not re.fullmatch('[a-f0-9]{32}', request_id):
            raise ValueError('request_id_invalid')
        with self.database() as db:
            try:
                db.execute('INSERT INTO consumed VALUES (?,?)', ('request',request_id))
            except sqlite3.IntegrityError:
                raise PermissionError('duplicate_request') from None

    def audit(self, operation, outcome):
        from executors.ascend_extension.contracts import OPERATIONS
        safe_operation = operation if operation in OPERATIONS else 'CONTROL'
        safe_outcome = outcome if outcome in {'PAIRING_REQUIRED','PAIRED','READ_RELEASE_REQUIRED','STOPPED'} else 'STOPPED'
        with self.database() as db:
            db.execute('INSERT INTO audit VALUES (?,?,?,?,?)',
                (int(self.clock()),safe_operation,safe_outcome,TENANT,ACTOR))

    def reset(self):
        self.config()
        enrollment_path = self.paths.path('Secrets', 'ascend-x1-enrollment.dpapi')
        if enrollment_path.exists():
            from executors.ascend_extension.enrollment import EnrollmentRepository
            # The existing explicit owner Reset also revokes durable enrollment and its lease.
            # Neither legacy consumed entries nor persistent enrollment/lease audits are deleted.
            EnrollmentRepository(self).revoke(owner_authorized=True)
        self.secret_path().unlink(missing_ok=True)
        self.path('pairing-bootstrap.json').unlink(missing_ok=True)
        # Preserve the duplicate-request ledger and audit history across all resets.
