from app.db.models import Investor
from app.rate_limit import login_attempt_tracker
from app.security import hash_password


def test_create_investor_then_login_and_access_own_data(client, db_session):
    create_response = client.post(
        "/investors/", json={"email": "authflow@example.com", "password": "correct-password"}
    )
    assert create_response.status_code == 200
    investor_id = create_response.json()["id"]

    login_response = client.post(
        "/auth/login",
        data={"username": "authflow@example.com", "password": "correct-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        f"/investors/{investor_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "authflow@example.com"


def test_login_rejects_wrong_password(client, db_session):
    investor = Investor(email="wrongpass@example.com", hashed_password=hash_password("correct"))
    db_session.add(investor)
    db_session.commit()

    response = client.post(
        "/auth/login", data={"username": "wrongpass@example.com", "password": "incorrect"}
    )
    assert response.status_code == 401


def test_login_rejects_unknown_email(client, db_session):
    response = client.post(
        "/auth/login", data={"username": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401


def test_get_investor_without_token_is_rejected(client, db_session):
    investor = Investor(email="notoken@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()

    response = client.get(f"/investors/{investor.id}")
    assert response.status_code == 401


def test_get_investor_with_someone_elses_token_is_forbidden(client, db_session, auth_headers):
    investor = Investor(email="victim@example.com", hashed_password="x")
    attacker = Investor(email="attacker@example.com", hashed_password="x")
    db_session.add_all([investor, attacker])
    db_session.commit()

    response = client.get(f"/investors/{investor.id}", headers=auth_headers(attacker.id))
    assert response.status_code == 403


def test_invalid_token_is_rejected(client, db_session):
    investor = Investor(email="badtoken@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()

    response = client.get(
        f"/investors/{investor.id}", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_login_returns_refresh_token_which_issues_a_new_access_token(client, db_session):
    create_response = client.post(
        "/investors/", json={"email": "refresh@example.com", "password": "correct-password"}
    )
    investor_id = create_response.json()["id"]

    login_response = client.post(
        "/auth/login", data={"username": "refresh@example.com", "password": "correct-password"}
    )
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 200
    new_access_token = refresh_response.json()["access_token"]

    me_response = client.get(
        f"/investors/{investor_id}", headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert me_response.status_code == 200


def test_refresh_rejects_an_access_token_used_as_a_refresh_token(client, db_session, auth_headers):
    investor = Investor(email="accesstokenasrefresh@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()

    access_token = auth_headers(investor.id)["Authorization"].removeprefix("Bearer ")
    response = client.post("/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


def test_refresh_rejects_garbage_token(client, db_session):
    response = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_login_locks_out_after_too_many_failed_attempts(client, db_session):
    email = "lockout@example.com"
    login_attempt_tracker.reset(email)
    investor = Investor(email=email, hashed_password=hash_password("correct-password"))
    db_session.add(investor)
    db_session.commit()

    for _ in range(5):
        response = client.post("/auth/login", data={"username": email, "password": "wrong"})
        assert response.status_code == 401

    locked_response = client.post("/auth/login", data={"username": email, "password": "wrong"})
    assert locked_response.status_code == 429

    # Even the correct password is rejected while locked out.
    still_locked = client.post("/auth/login", data={"username": email, "password": "correct-password"})
    assert still_locked.status_code == 429

    login_attempt_tracker.reset(email)
