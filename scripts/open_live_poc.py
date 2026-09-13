"""Private local dashboard launcher. Grant stays out of terminal output unless privately orchestrated."""
import json
import sys
import webbrowser

from app.core.runtime import RuntimePaths
from app.services.live_access import issue_grant
from app.services.store import Store

paths = RuntimePaths.from_environment()
store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
try:
    url = "http://localhost:8787/#live-grant=" + issue_grant(store, "booking-logistics")
finally:
    store.close()
if "--private-orchestration" in sys.argv:
    # Caller must consume internally; do not display this single-use launch URL.
    print(json.dumps({"url": url}))
else:
    webbrowser.open(url)
