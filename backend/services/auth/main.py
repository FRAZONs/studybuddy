import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, StringConstraints

from services.shared.security import create_token, get_current_user, require_admin

DB_PATH = Path(os.getenv("AUTH_DATABASE_PATH", "/data/auth.db"))
ITERATIONS = 310_000


@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"{ITERATIONS}${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        iterations, salt, digest = encoded.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest)
    except (ValueError, TypeError):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        username = os.getenv("AUTH_ADMIN_USERNAME", "").strip()
        password = os.getenv("AUTH_ADMIN_PASSWORD", "")
        if username and len(password) >= 12 and len(os.getenv("AUTH_TOKEN_SECRET", "").strip()) >= 32:
            db.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, role) VALUES (?, ?, ?, 'admin')",
                ("admin", username, hash_password(password)),
            )
    yield


app = FastAPI(title="StudyBuddy Auth Service", lifespan=lifespan, docs_url=None, redoc_url=None)


class Credentials(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class NewUser(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=80)]
    password: Annotated[str, StringConstraints(min_length=12, max_length=200)]


def user_view(row):
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


@app.get("/api/health")
def health():
    with database() as db:
        db.execute("SELECT 1 FROM users LIMIT 1")
    return {"status": "ok"}


@app.get("/api/auth/status")
def auth_status():
    ready = len(os.getenv("AUTH_TOKEN_SECRET", "").strip()) >= 32
    with database() as db:
        users_exist = db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    return {"configured": ready and users_exist, "bootstrap_required": ready and not users_exist}


@app.post("/api/auth/login")
def login(credentials: Credentials):
    if len(os.getenv("AUTH_TOKEN_SECRET", "").strip()) < 32:
        raise HTTPException(503, "Authentication is not configured. Set AUTH_TOKEN_SECRET.")
    with database() as db:
        row = db.execute("SELECT * FROM users WHERE username = ?", (credentials.username,)).fetchone()
    if row is None or not password_matches(credentials.password, row["password_hash"]):
        raise HTTPException(401, "Username or password is incorrect.")
    user = user_view(row)
    return {"token": create_token(user), "user": user}


@app.get("/api/auth/me")
def me(user: Annotated[dict, Depends(get_current_user)]):
    return user


@app.get("/api/auth/users")
def list_users(user: Annotated[dict, Depends(get_current_user)]):
    require_admin(user)
    with database() as db:
        rows = db.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()
    return [user_view(row) for row in rows]


@app.post("/api/auth/users", status_code=201)
def create_user(payload: NewUser, user: Annotated[dict, Depends(get_current_user)]):
    require_admin(user)
    with database() as db:
        try:
            cursor = db.execute(
                "INSERT INTO users (id, username, password_hash, role) VALUES (?, ?, ?, 'student')",
                (secrets.token_urlsafe(18), payload.username, hash_password(payload.password)),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "That username already exists.") from None
        row = db.execute(
            "SELECT id, username, role FROM users WHERE rowid = ?", (cursor.lastrowid,)
        ).fetchone()
    return user_view(row)
