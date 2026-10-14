from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)
ALICE = {"Authorization": "Bearer token-alice"}


def search_ids(q: str) -> tuple[int, list[int]]:
    resp = client.get("/claims/search", params={"q": q}, headers=ALICE)
    ids = [r["id"] for r in resp.json()["results"]] if resp.status_code == 200 else []
    return resp.status_code, ids


def test_boolean_injection_does_not_return_other_members_claims():
    for payload in ("' OR '1'='1", "%' OR 1=1 --", "' OR 1=1 --"):
        status, ids = search_ids(payload)
        assert status == 200, payload
        assert ids == [], payload


def test_union_injection_is_treated_as_literal_text():
    status, ids = search_ids("' UNION SELECT 1, name, sql, 4, 5, 6 FROM sqlite_master --")
    assert status == 200
    assert ids == []


def test_apostrophe_in_search_term_does_not_500():
    assert search_ids("O'Neill") == (200, [])


def test_search_still_scoped_and_matches_substring():
    assert search_ids("visit") == (200, [1001])
    assert search_ids("") == (200, [1002, 1001])
