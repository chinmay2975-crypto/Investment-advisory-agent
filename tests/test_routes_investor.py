from app.db.models import Investor


def test_get_profile_404_when_not_set(client, db_session, auth_headers):
    investor = Investor(email="noprofile@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()

    response = client.get(f"/investors/{investor.id}/profile", headers=auth_headers(investor.id))
    assert response.status_code == 404


def test_upsert_then_get_profile(client, db_session, auth_headers):
    investor = Investor(email="withprofile@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()
    headers = auth_headers(investor.id)

    client.put(
        f"/investors/{investor.id}/profile",
        json={"risk_cadence": "Balanced", "horizon_years": 12},
        headers=headers,
    )

    response = client.get(f"/investors/{investor.id}/profile", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_cadence"] == "Balanced"
    assert body["horizon_years"] == 12
