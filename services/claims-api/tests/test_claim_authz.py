import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ALICE = {"Authorization": "Bearer token-alice"}  # m-100 owns 1001, 1002
BOB = {"Authorization": "Bearer token-bob"}  # m-200 owns 1003, 1004
ADJUSTER = {"Authorization": "Bearer token-adjuster"}


@pytest.mark.parametrize(
    "headers,claim_id",
    [(ALICE, 1003), (ALICE, 1004), (ALICE, 1005), (BOB, 1001), (BOB, 1002), (BOB, 1005)],
)
def test_member_cannot_read_other_members_claim(headers, claim_id):
    resp = client.get(f"/claims/{claim_id}", headers=headers)
    assert resp.status_code == 404
    assert resp.json() == client.get("/claims/9999", headers=headers).json()


def test_member_enumeration_returns_only_own_claims():
    readable = [i for i in range(1001, 1006) if client.get(f"/claims/{i}", headers=BOB).status_code == 200]
    assert readable == [1003, 1004]


def test_adjuster_can_read_any_claim():
    for claim_id in range(1001, 1006):
        assert client.get(f"/claims/{claim_id}", headers=ADJUSTER).status_code == 200
