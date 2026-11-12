import json
import os
import re
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field, StringConstraints

from study_data import EXAMPLE_NOTES, RELATED

DB_PATH = Path(os.getenv("DATABASE_PATH", "data/studybuddy.db"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, subject TEXT NOT NULL, content TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY)")
        marker = db.execute("INSERT OR IGNORE INTO settings VALUES ('seeded')")
        if marker.rowcount:
            db.executemany(
                "INSERT INTO notes (title, subject, content) VALUES (?, ?, ?)",
                EXAMPLE_NOTES,
            )
    yield


app = FastAPI(title="StudyBuddy AI", lifespan=lifespan, docs_url="/api/docs",
              openapi_url="/api/openapi.json", redoc_url=None)


class Note(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]


class Message(BaseModel):
    role: Literal["user", "model"]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class Chat(BaseModel):
    messages: Annotated[list[Message], Field(min_length=1, max_length=11)]


@app.get("/api/health")
def health():
    with database() as db:
        db.execute("SELECT 1 FROM notes LIMIT 1")
    return {"status": "ok"}


@app.get("/api/notes")
def list_notes():
    with database() as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM notes ORDER BY updated_at DESC, id DESC"
        )]


def find_note(db, note_id):
    row = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Note not found.")
    return dict(row)


@app.get("/api/notes/{note_id}")
def get_note(note_id: int):
    with database() as db:
        return find_note(db, note_id)


@app.post("/api/notes", status_code=201)
def create_note(note: Note):
    with database() as db:
        cursor = db.execute("INSERT INTO notes (title, subject, content) VALUES (?, ?, ?)",
                            (note.title, note.subject, note.content))
        return find_note(db, cursor.lastrowid)


@app.put("/api/notes/{note_id}")
def update_note(note_id: int, note: Note):
    with database() as db:
        db.execute("""UPDATE notes SET title = ?, subject = ?, content = ?,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                   (note.title, note.subject, note.content, note_id))
        return find_note(db, note_id)


@app.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: int):
    with database() as db:
        if not db.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount:
            raise HTTPException(404, "Note not found.")
    return Response(status_code=204)


@app.get("/api/search")
def search(q: Annotated[str, Query(max_length=120)] = ""):
    notes = list_notes()
    query = q.strip().casefold()
    if not query:
        return notes

    def rank(note):
        title, subject, content = (note[field].casefold() for field in ("title", "subject", "content"))
        if query in (title, subject):
            return 4
        if re.search(r"(?<!\w)" + re.escape(query) + r"(?!\w)", " ".join((title, subject, content))):
            return 3
        if query in title or query in subject:
            return 2
        if all(word in " ".join((title, subject, content)) for word in query.split()):
            return 1
        return 0

    ranked = [(rank(note), note) for note in notes]
    return [note for score, note in sorted(ranked, key=lambda item: -item[0]) if score]


@app.get("/api/recommendations")
def recommendations(subject: Annotated[list[str] | None, Query()] = None):
    suggestions = {}
    for name in (subject or [])[:8]:
        for topic, description in RELATED.get(name.strip().casefold(), []):
            suggestions.setdefault(topic, {"topic": topic, "description": description, "subject": name})
    return list(suggestions.values())[:6]


@app.get("/api/chat/status")
def chat_status():
    return {"configured": bool(os.getenv("GEMINI_API_KEY", "").strip())}


@app.post("/api/chat")
def chat(request: Chat):
    if [message.role for message in request.messages] != [
        "user" if index % 2 == 0 else "model" for index in range(len(request.messages))
    ] or request.messages[-1].role != "user":
        raise HTTPException(422, "Send alternating user and model messages ending with a question.")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "Set GEMINI_API_KEY on the backend to enable chat.")
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", GEMINI_MODEL):
        raise HTTPException(503, "Check the GEMINI_MODEL backend setting.")

    payload = {
        "systemInstruction": {"parts": [{"text": "You are StudyBuddy, a tutor for beginners. Explain clearly, with short paragraphs and one practical example when useful. Use plain text with simple lists."}]},
        "contents": [{"role": message.role, "parts": [{"text": message.text}]}
                     for message in request.messages],
        "generationConfig": {"maxOutputTokens": 1200},
    }
    upstream = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    try:
        with urlopen(upstream, timeout=40) as result:
            data = json.load(result)
    except HTTPError as error:
        if error.code == 429:
            raise HTTPException(429, "Gemini's quota or rate limit was reached. Try again later.") from None
        if error.code in (400, 401, 403, 404):
            raise HTTPException(502, "Gemini rejected the request. Check the backend API key and model access.") from None
        raise HTTPException(502, "Gemini is temporarily unavailable.") from None
    except (TimeoutError, URLError, ValueError):
        raise HTTPException(502, "Gemini could not be reached or returned an invalid response.") from None

    candidates = data.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    reply = "\n".join(part["text"] for part in parts if part.get("text") and not part.get("thought")).strip()
    if not reply:
        raise HTTPException(502, "Gemini returned no answer. Try rephrasing your question.")
    return {"reply": reply}
