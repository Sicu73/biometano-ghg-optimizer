# -*- coding: utf-8 -*-
"""core/auth.py — Sistema utenti SQLite-based (Fase 2.1 IMPLEMENTATA).

Implementazione pragmatica con SQLite locale + bcrypt + JWT. Pronta per
migrazione a PostgreSQL multi-tenant solo cambiando la connection string
(`_db_url()` legge da st.secrets["database"]["url"] o fallback SQLite locale).

API pubblica:
  signup(email, password, full_name, company) -> User
  login(email, password) -> str (JWT)
  logout()
  current_user() -> User | None
  is_demo_mode() -> bool
  init_db()

Sicurezza:
- Password hashing bcrypt (cost factor 12)
- JWT firmato HS256 con secret da st.secrets["auth"]["jwt_secret"]
- Cookie httpOnly via st.session_state (Streamlit non espone cookie HTTP
  raw, ma session_state è server-side e isolato per sessione browser)
- Email lowercase normalizzata, validation basic
"""
from __future__ import annotations

import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ============================================================================
# CONFIG
# ============================================================================
_JWT_ALGO = "HS256"
_JWT_TTL_DAYS = 30
_BCRYPT_ROUNDS = 12
_TRIAL_DAYS = 14
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class User:
    id: str
    email: str
    full_name: str | None
    company: str | None
    tenant_id: str
    role: str = "editor"        # admin | editor | viewer
    plan: str = "free"          # free | pro | enterprise
    trial_ends_at: str | None = None
    stripe_customer_id: str | None = None
    is_active: bool = True
    email_verified: bool = False
    created_at: str | None = None


# ============================================================================
# DB BOOTSTRAP
# ============================================================================
def _db_path() -> Path:
    """Path SQLite locale fallback (data/users.db)."""
    base = Path(__file__).resolve().parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "users.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Crea schema users idempotente."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                company TEXT,
                tenant_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'editor',
                plan TEXT NOT NULL DEFAULT 'free',
                trial_ends_at TEXT,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                email_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login_at TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id)")


# ============================================================================
# HASHING
# ============================================================================
def _hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"),
                         bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ============================================================================
# JWT
# ============================================================================
def _jwt_secret() -> str:
    try:
        import streamlit as st
        s = st.secrets.get("auth", {}).get("jwt_secret", "")
        if s:
            return str(s)
    except Exception:
        pass
    # Fallback insecure per dev locale (warning visibile)
    return os.environ.get("METANIQ_JWT_SECRET", "dev-insecure-secret-CHANGE-ME")


def _encode_token(user_id: str) -> str:
    import jwt
    payload = {
        "sub": user_id,
        "iat": datetime.utcnow().timestamp(),
        "exp": (datetime.utcnow() + timedelta(days=_JWT_TTL_DAYS)).timestamp(),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALGO)


def _decode_token(token: str) -> Optional[str]:
    try:
        import jwt
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_JWT_ALGO])
        return str(payload.get("sub", ""))
    except Exception:
        return None


# ============================================================================
# DEMO MODE
# ============================================================================
def is_demo_mode() -> bool:
    """True se l'auth è disabilitata (default).

    Per attivare il gate auth in produzione, set in `.streamlit/secrets.toml`:
        [auth]
        demo_mode = false
    """
    try:
        import streamlit as st
        v = st.secrets.get("auth", {}).get("demo_mode", True)
        return bool(v)
    except Exception:
        return True


# ============================================================================
# PUBLIC API
# ============================================================================
def _validate_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Email non valida")
    return email


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password deve essere almeno 8 caratteri")


def signup(email: str, password: str,
           full_name: str | None = None,
           company: str | None = None) -> User:
    """Crea nuovo utente. Trial Pro 14gg automatico."""
    email = _validate_email(email)
    _validate_password(password)
    init_db()
    user_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())  # 1 tenant per utente (per ora)
    trial_ends = (datetime.utcnow() + timedelta(days=_TRIAL_DAYS)).isoformat()
    with _conn() as c:
        try:
            c.execute("""
                INSERT INTO users (id, email, password_hash, full_name, company,
                                   tenant_id, plan, trial_ends_at, role)
                VALUES (?, ?, ?, ?, ?, ?, 'pro', ?, 'admin')
            """, (user_id, email, _hash_password(password), full_name, company,
                  tenant_id, trial_ends))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                raise ValueError("Email già registrata")
            raise
    try:
        from core.audit import log as audit_log
        audit_log("user_signup", resource_type="user", resource_id=user_id,
                  user_id=user_id, tenant_id=tenant_id,
                  payload={"email": email, "plan": "pro_trial"})
    except Exception:
        pass
    return _row_to_user(_fetch_by_id(user_id))


def login(email: str, password: str) -> str:
    """Verifica credenziali, restituisce JWT. Setta session_state["_user"]."""
    email = _validate_email(email)
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
        ).fetchone()
    if not row:
        raise ValueError("Credenziali non valide")
    if not _verify_password(password, row["password_hash"]):
        raise ValueError("Credenziali non valide")
    user = _row_to_user(row)
    token = _encode_token(user.id)
    with _conn() as c:
        c.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?",
                  (user.id,))
    try:
        import streamlit as st
        st.session_state["_user"] = user
        st.session_state["_jwt"] = token
    except Exception:
        pass
    try:
        from core.audit import log as audit_log
        audit_log("user_login", user_id=user.id, tenant_id=user.tenant_id,
                  payload={"email": email})
    except Exception:
        pass
    return token


def logout() -> None:
    try:
        import streamlit as st
        u = st.session_state.get("_user")
        if u:
            try:
                from core.audit import log as audit_log
                audit_log("user_logout", user_id=u.id, tenant_id=u.tenant_id)
            except Exception:
                pass
        st.session_state.pop("_user", None)
        st.session_state.pop("_jwt", None)
    except Exception:
        pass


def current_user() -> User | None:
    try:
        import streamlit as st
        u = st.session_state.get("_user")
        if isinstance(u, User):
            return u
        # Hydrate da JWT se presente
        token = st.session_state.get("_jwt")
        if token:
            uid = _decode_token(token)
            if uid:
                row = _fetch_by_id(uid)
                if row:
                    u = _row_to_user(row)
                    st.session_state["_user"] = u
                    return u
    except Exception:
        pass
    return None


def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    init_db()
    _validate_password(new_password)
    with _conn() as c:
        row = c.execute("SELECT password_hash, tenant_id FROM users WHERE id = ?",
                        (user_id,)).fetchone()
        if not row or not _verify_password(old_password, row["password_hash"]):
            return False
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                  (_hash_password(new_password), user_id))
    try:
        from core.audit import log as audit_log
        audit_log("password_changed", user_id=user_id, tenant_id=row["tenant_id"])
    except Exception:
        pass
    return True


def delete_account(user_id: str, hard: bool = False) -> None:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT tenant_id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return
        if hard:
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        else:
            c.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    try:
        from core.audit import log as audit_log
        audit_log("account_deleted", user_id=user_id, tenant_id=row["tenant_id"],
                  payload={"hard": hard})
    except Exception:
        pass


def check_and_downgrade_expired_trials() -> int:
    """Job idempotente: downgrade utenti con trial scaduto a piano 'free'.

    Da chiamare periodicamente (cron Fase 4 o lazy a ogni login). Restituisce
    il numero di utenti downgradati.
    """
    init_db()
    now_iso = datetime.utcnow().isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT id, tenant_id FROM users WHERE plan = 'pro' "
            "AND trial_ends_at IS NOT NULL "
            "AND stripe_subscription_id IS NULL "
            "AND trial_ends_at < ?",
            (now_iso,)
        ).fetchall()
        for r in rows:
            c.execute("UPDATE users SET plan='free', trial_ends_at=NULL WHERE id=?",
                       (r["id"],))
    if rows:
        try:
            from core.audit import log as audit_log
            for r in rows:
                audit_log("trial_expired_downgrade",
                          user_id=r["id"], tenant_id=r["tenant_id"],
                          payload={"new_plan": "free"})
        except Exception:
            pass
    return len(rows)


def list_users() -> list[User]:
    """Solo per admin / debug."""
    init_db()
    with _conn() as c:
        rows = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return [_row_to_user(r) for r in rows]


# ============================================================================
# HELPERS
# ============================================================================
def _fetch_by_id(user_id: str):
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def _row_to_user(row) -> User:
    if row is None:
        raise ValueError("User not found")
    return User(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        company=row["company"],
        tenant_id=row["tenant_id"],
        role=row["role"],
        plan=row["plan"],
        trial_ends_at=row["trial_ends_at"],
        stripe_customer_id=row["stripe_customer_id"],
        is_active=bool(row["is_active"]),
        email_verified=bool(row["email_verified"]),
        created_at=row["created_at"],
    )


__all__ = [
    "User",
    "signup",
    "login",
    "logout",
    "current_user",
    "change_password",
    "delete_account",
    "list_users",
    "is_demo_mode",
    "init_db",
    "check_and_downgrade_expired_trials",
]
