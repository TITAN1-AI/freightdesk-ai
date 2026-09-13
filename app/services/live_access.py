"""One-use owner launch grant -> separate HttpOnly historical-view session."""
import hashlib
import secrets
import json
import sqlite3
from datetime import datetime, timedelta

from app.models.domain import utcnow


def digest(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def issue_grant(store, tenant):
    # Only a local private launcher can issue grants. There is no HTTP grant-issuance route.
    store.get(tenant, "live_poc", "001")
    grant = secrets.token_urlsafe(48)
    with store.transaction():
        store.put(tenant, "live_view_grant", digest(grant),
                  {"expires_at": (utcnow() + timedelta(minutes=3)).isoformat(), "consumed": False})
    return grant


def redeem_grant(store, tenant, grant):
    with store.transaction():
        value = store.get(tenant, "live_view_grant", digest(grant))
        if value["consumed"] or datetime.fromisoformat(value["expires_at"]) <= utcnow():
            raise PermissionError("Owner launch link expired or already used")
        value["consumed"] = True
        store.put(tenant, "live_view_grant", digest(grant), value)
        session = secrets.token_urlsafe(48)
        store.put(tenant, "live_view_session", digest(session),
                  {"expires_at": (utcnow() + timedelta(hours=8)).isoformat()})
    return session


def session_valid(store, tenant, session):
    if not session:
        return False
    try:
        value = store.get(tenant, "live_view_session", digest(session))
        return datetime.fromisoformat(value["expires_at"]) > utcnow()
    except KeyError:
        return False


def session_valid_readonly(path, tenant, session):
    """Verify the existing dedicated owner session without opening or mutating provider records."""
    if not session:
        return False
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            row = db.execute("SELECT body FROM records WHERE tenant=? AND kind=? AND id=?",
                             (tenant, "live_view_session", digest(session))).fetchone()
        return bool(row) and datetime.fromisoformat(json.loads(row[0])["expires_at"]) > utcnow()
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        return False
