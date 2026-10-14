from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import current_user
from .db import db
from .search import search_claims

router = APIRouter(prefix="/claims")


@router.get("/search")
def search(q: str = Query(default="", max_length=200), user: dict = Depends(current_user)):
    return {"results": search_claims(user["user_id"], q)}


@router.get("/{claim_id}")
def get_claim(claim_id: int, user: dict = Depends(current_user)):
    row = db().execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return dict(row)
