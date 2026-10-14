from .db import db


def search_claims(member_id: str, term: str) -> list[dict]:
    query = (
        "SELECT id, member_id, description, service_date, amount, status "
        "FROM claims WHERE member_id = ? AND description LIKE ? "
        "ORDER BY service_date DESC"
    )
    rows = db().execute(query, (member_id, f"%{term}%")).fetchall()
    return [dict(r) for r in rows]
