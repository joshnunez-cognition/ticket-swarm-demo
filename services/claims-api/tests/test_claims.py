from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ALICE = {"Authorization": "Bearer token-alice"}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_requires_token():
    assert client.get("/claims/1001").status_code == 401


def test_get_own_claim():
    resp = client.get("/claims/1001", headers=ALICE)
    assert resp.status_code == 200
    assert resp.json()["member_id"] == "m-100"


def test_search_returns_only_member_claims():
    resp = client.get("/claims/search", params={"q": "Lab"}, headers=ALICE)
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["id"] for r in results] == [1002]


def test_missing_claim_404():
    assert client.get("/claims/9999", headers=ALICE).status_code == 404
