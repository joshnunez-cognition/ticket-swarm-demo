from .db import db


def search_claims(member_id: str, term: str) -> list[dict]:
    query = (
        "SELECT id, member_id, description, service_date, amount, status "
        "FROM claims WHERE member_id = '%s' AND description LIKE '%%%s%%' "
        "ORDER BY service_date DESC" % (member_id, term)
    )
    rows = db().execute(query).fetchall()
    return [dict(r) for r in rows]
