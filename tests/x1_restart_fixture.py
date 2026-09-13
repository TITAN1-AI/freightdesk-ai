"""Subprocess-only synthetic restart probe. Never targets an installed host or live store."""
import json
import os
import socket
import sys
from pathlib import Path

from app.core.runtime import RuntimePaths
from executors.ascend_extension.enrollment import EnrollmentRepository
from executors.ascend_extension.mapping_orchestrator import MappingOrchestrator
from executors.ascend_extension.pairing import PairingRepository
from executors.ascend_extension.runtime import RuntimeController
from executors.webbridge_v2.runtime_bridge import install_offline


def main():
    root, mode, now = Path(sys.argv[1]).absolute(), sys.argv[2], float(sys.argv[3])
    relative = root.relative_to(RuntimePaths.from_environment().path('Data', 'TestRuns').absolute())
    assert RuntimePaths.from_environment().path('Data', 'TestRuns', *relative.parts) == root
    assert mode in {'commit_then_crash', 'recover'}
    def no_network(*args, **kwargs):
        raise AssertionError('OFFLINE_NETWORK_FORBIDDEN')
    socket.socket = no_network
    class Paths:
        def path(self, *parts):
            return root.joinpath(*parts)
    def protect(data, *, decrypt=False):
        assert decrypt and data.startswith(b'FIXTURE:')
        return data[8:]
    repo = PairingRepository(Paths(), sid=lambda: 'fixture-sid', protect=protect, clock=lambda: now)
    enrollment = EnrollmentRepository(repo, device=lambda: 'd' * 64)
    controller = RuntimeController(repo, clock=lambda: now, gate=lambda _: None, enrollment_guard=enrollment.load)
    install_offline(controller.access)
    if mode == 'commit_then_crash':
        controller.finish(json.loads((root / 'restart-result.json').read_text()))
        with controller.access.database(readonly=True) as db:
            assert db.execute('SELECT count(*) FROM runtime_v2_observations').fetchone()[0] == 1
        os._exit(23)  # Abrupt process death AFTER commit, BEFORE coordinator notification.
    result = MappingOrchestrator(controller.access).tick()
    assert result['stage'] == 'OWNER_REVIEW_REQUIRED' and result['cleanup_complete'], result
    assert controller.access.status()['read_access'] == 'REVOKED'
    with controller.access.database(readonly=True) as db:
        assert db.execute('SELECT count(*) FROM runtime_provider_maps').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM runtime_v2_observations').fetchone()[0] == 1
    print(json.dumps({'recovery': 'PASSED', 'maps': 1, 'cleanup': 'COMPLETE', 'reads_replayed': 0}))


if __name__ == '__main__':
    main()
