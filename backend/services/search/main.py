import json
import os
import re
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from services.shared.security import get_current_user

NOTES_SERVICE_URL = os.getenv("NOTES_SERVICE_URL", "http://studybuddy-notes:8000")

app = FastAPI(title="StudyBuddy Search Service", docs_url=None, redoc_url=None)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/search")
def search(
    user: Annotated[dict, Depends(get_current_user)],
    authorization: Annotated[str | None, Header()] = None,
    q: Annotated[str, Query(max_length=120)] = "",
):
    request = Request(
        f"{NOTES_SERVICE_URL}/api/notes",
        headers={"Authorization": authorization or ""},
    )
    try:
        with urlopen(request, timeout=8) as response:
            notes = json.load(response)
    except HTTPError as error:
        raise HTTPException(502, "Notes service rejected the search request.") from error
    except (TimeoutError, URLError, ValueError):
        raise HTTPException(502, "Notes service is unavailable.") from None

    query = q.strip().casefold()
    if not query:
        return notes

    def rank(note):
        title, subject, content = (note[field].casefold() for field in ("title", "subject", "content"))
        searchable = " ".join((title, subject, content))
        if query in (title, subject):
            return 4
        if re.search(r"(?<!\w)" + re.escape(query) + r"(?!\w)", searchable):
            return 3
        if query in title or query in subject:
            return 2
        if all(word in searchable for word in query.split()):
            return 1
        return 0

    return [note for score, note in sorted(
        ((rank(note), note) for note in notes), key=lambda item: -item[0]
    ) if score]
