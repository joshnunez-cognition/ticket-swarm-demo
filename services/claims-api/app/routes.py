from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import current_user
from .db import db
from .search import search_claims

router = APIRouter(prefix="/claims")

CLAIM_READ_ALL_ROLES = {"adjuster"}


def can_read_claim(user: dict, row) -> bool:
    return user["role"] in CLAIM_READ_ALL_ROLES or row["member_id"] == user["user_id"]


@router.get("/search")
def search(q: str = Query(default="", max_length=200), user: dict = Depends(current_user)):
    return {"results": search_claims(user["user_id"], q)}


@router.get("/{claim_id}")
def get_claim(claim_id: int, user: dict = Depends(current_user)):
    row = db().execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    # Same 404 for missing and not-yours so ids can't be probed for existence.
    if row is None or not can_read_claim(user, row):
        raise HTTPException(status_code=404, detail="claim not found")
    return dict(row)
