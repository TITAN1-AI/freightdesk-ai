"""Explicit local owner setup; never invoked by the extension or the native message command path."""
import argparse

from executors.ascend_extension.pairing import PairingRepository


def setup(action, repo=None, prompt=input):
    repo = repo or PairingRepository()
    if action == 'capture':
        extension_id = prompt('Paste the installed extension ID from edge://extensions (local input only): ').strip()
        repo.capture(extension_id)
        return 'Exact installed extension ID captured; host manifest prepared. Registry unchanged.'
    if action == 'pair':
        repo.begin_pairing()
        return 'Pairing bootstrap prepared locally; valid for 10 minutes and one connection. Import it using the extension popup.'
    if action == 'reset':
        repo.reset()
        return 'Pairing revoked. Consumed request IDs and audit history preserved.'
    raise ValueError('setup_action_invalid')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['capture','pair','reset'])
    parser.add_argument('--owner-executed',action='store_true',required=True)
    args=parser.parse_args()
    try:
        print(setup(args.action))
    except Exception:
        raise SystemExit('Native setup stopped. Verify local ID/runtime/install state; private details omitted.') from None
