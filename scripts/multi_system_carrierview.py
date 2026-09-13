"""Owner-executed tenant DPAPI entry point; no other phase or credential fallback."""
from scripts.multi_system_ops import execute

if __name__=='__main__':
    execute('carrierview')
