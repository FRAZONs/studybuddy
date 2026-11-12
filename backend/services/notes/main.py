import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, StringConstraints

from study_data import EXAMPLE_NOTES
from services.shared.security import get_current_user

DB_PATH = Path(os.getenv("DATABASE_PATH", "/data/notes.db"))


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL DEFAULT 'admin',
            title TEXT NOT NULL, subject TEXT NOT NULL, content TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(notes)")}
        if "owner_id" not in columns:
            db.execute("ALTER TABLE notes ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'admin'")
        db.execute("CREATE INDEX IF NOT EXISTS notes_owner_updated ON notes(owner_id, updated_at DESC)")
        if db.execute("SELECT 1 FROM notes LIMIT 1").fetchone() is None:
            db.executemany(
                "INSERT INTO notes (owner_id, title, subject, content) VALUES ('admin', ?, ?, ?)",
                EXAMPLE_NOTES,
            )
    yield


app = FastAPI(title="StudyBuddy Notes Service", lifespan=lifespan, docs_url=None, redoc_url=None)


class Note(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]


@app.get("/api/health")
def health():
    with database() as db:
        db.execute("SELECT 1 FROM notes LIMIT 1")
    return {"status": "ok"}


@app.get("/api/notes")
def list_notes(user: Annotated[dict, Depends(get_current_user)]):
    with database() as db:
        return [dict(row) for row in db.execute(
            "SELECT id, title, subject, content, updated_at FROM notes WHERE owner_id = ? ORDER BY updated_at DESC, id DESC",
            (user["id"],),
        )]


def find_note(db, note_id: int, owner_id: str):
    row = db.execute(
        "SELECT id, title, subject, content, updated_at FROM notes WHERE id = ? AND owner_id = ?",
        (note_id, owner_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Note not found.")
    return dict(row)


@app.get("/api/notes/{note_id}")
def get_note(note_id: int, user: Annotated[dict, Depends(get_current_user)]):
    with database() as db:
        return find_note(db, note_id, user["id"])


@app.post("/api/notes", status_code=201)
def create_note(note: Note, user: Annotated[dict, Depends(get_current_user)]):
    with database() as db:
        cursor = db.execute(
            "INSERT INTO notes (owner_id, title, subject, content) VALUES (?, ?, ?, ?)",
            (user["id"], note.title, note.subject, note.content),
        )
        return find_note(db, cursor.lastrowid, user["id"])


@app.put("/api/notes/{note_id}")
def update_note(note_id: int, note: Note, user: Annotated[dict, Depends(get_current_user)]):
    with database() as db:
        db.execute(
            """UPDATE notes SET title = ?, subject = ?, content = ?,
               updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_id = ?""",
            (note.title, note.subject, note.content, note_id, user["id"]),
        )
        return find_note(db, note_id, user["id"])


@app.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: int, user: Annotated[dict, Depends(get_current_user)]):
    with database() as db:
        if not db.execute(
            "DELETE FROM notes WHERE id = ? AND owner_id = ?", (note_id, user["id"])
        ).rowcount:
            raise HTTPException(404, "Note not found.")
    return Response(status_code=204)
