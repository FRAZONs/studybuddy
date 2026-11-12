from typing import Annotated

from fastapi import Depends, FastAPI, Query

from services.shared.security import get_current_user
from study_data import RELATED

app = FastAPI(title="StudyBuddy Recommendations Service", docs_url=None, redoc_url=None)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/recommendations")
def recommendations(
    user: Annotated[dict, Depends(get_current_user)],
    subject: Annotated[list[str] | None, Query()] = None,
):
    suggestions = {}
    for name in (subject or [])[:8]:
        for topic, description in RELATED.get(name.strip().casefold(), []):
            suggestions.setdefault(
                topic, {"topic": topic, "description": description, "subject": name}
            )
    return list(suggestions.values())[:6]
