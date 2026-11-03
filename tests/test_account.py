from datetime import datetime, timezone

from app.db.models import Goal, Holding, Investor, InvestorProfile, Recommendation, RecommendationEvaluation
from app.security import create_password_reset_token, hash_password, password_version

PASSWORD = "original-pass"


def seed(db, email="a@example.com"):
    investor = Investor(email=email, hashed_password=hash_password(PASSWORD))
    db.add(investor)
    db.commit()
    return investor


def login(client, email="a@example.com", password=PASSWORD):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_change_password_rotates_credentials(client, db_session, auth_headers):
    investor = seed(db_session)
    old_refresh = login(client).json()["refresh_token"]

    wrong = client.post("/auth/change-password", headers=auth_headers(investor.id),
                        json={"current_password": "nope-nope", "new_password": "brand-new-pass"})
    assert wrong.status_code == 400

    ok = client.post("/auth/change-password", headers=auth_headers(investor.id),
                     json={"current_password": PASSWORD, "new_password": "brand-new-pass"})
    assert ok.status_code == 200 and ok.json()["refresh_token"]

    assert login(client).status_code == 401
    assert login(client, password="brand-new-pass").status_code == 200
    # refresh tokens issued before the change are revoked; the new one works
    assert client.post("/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": ok.json()["refresh_token"]}).status_code == 200


def test_change_password_enforces_minimum_length(client, db_session, auth_headers):
    investor = seed(db_session)
    response = client.post("/auth/change-password", headers=auth_headers(investor.id),
                           json={"current_password": PASSWORD, "new_password": "short"})
    assert response.status_code == 422


def test_forgot_password_returns_503_without_smtp(client, db_session, monkeypatch):
    monkeypatch.setattr("app.config.settings.smtp_host", "")
    seed(db_session)
    assert client.post("/auth/forgot-password", json={"email": "a@example.com"}).status_code == 503
    assert client.get("/auth/features").json() == {"password_reset_email": False}


def test_forgot_password_sends_link_only_for_known_accounts(client, db_session, monkeypatch):
    monkeypatch.setattr("app.config.settings.smtp_host", "smtp.example.com")
    monkeypatch.setattr("app.config.settings.smtp_from", "noreply@example.com")
    sent = []
    monkeypatch.setattr("app.services.account.send_password_reset_email", lambda to, token: sent.append((to, token)))
    seed(db_session)

    known = client.post("/auth/forgot-password", json={"email": "A@Example.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()  # no account enumeration
    assert [to for to, _ in sent] == ["a@example.com"]


def test_reset_password_link_is_single_use(client, db_session):
    investor = seed(db_session)
    token = create_password_reset_token(str(investor.id), password_version(investor.hashed_password))

    first = client.post("/auth/reset-password", json={"token": token, "new_password": "after-reset-1"})
    assert first.status_code == 200
    assert login(client, password="after-reset-1").status_code == 200

    again = client.post("/auth/reset-password", json={"token": token, "new_password": "after-reset-2"})
    assert again.status_code == 400


def test_reset_password_rejects_other_token_types(client, db_session):
    investor = seed(db_session)
    refresh = login(client).json()["refresh_token"]
    assert client.post("/auth/reset-password", json={"token": refresh, "new_password": "whatever-123"}).status_code == 400
    assert investor.id


def test_delete_account_removes_everything_and_only_for_that_user(client, db_session, auth_headers, monkeypatch):
    removed = []
    monkeypatch.setattr(
        "app.services.chroma_client.get_reflection_collection",
        lambda: type("C", (), {"delete": lambda self, ids: removed.extend(ids)})(),
    )
    investor = seed(db_session)
    other = seed(db_session, "b@example.com")
    for owner in (investor, other):
        db_session.add(InvestorProfile(investor_id=owner.id, risk_cadence="Balanced"))
        db_session.add(Goal(investor_id=owner.id, category="Home", target_amount=1, target_date=datetime.now(timezone.utc)))
        db_session.add(Holding(investor_id=owner.id, ticker="VTI", quantity=1))
        rec = Recommendation(investor_id=owner.id, payload={})
        db_session.add(rec)
        db_session.flush()
        db_session.add(RecommendationEvaluation(recommendation_id=rec.id, deviation={}, assumptions_held=True))
    db_session.commit()

    assert client.post("/auth/delete-account", headers=auth_headers(investor.id), json={"password": "wrong-pass"}).status_code == 400
    assert client.post("/auth/delete-account", headers=auth_headers(investor.id), json={"password": PASSWORD}).status_code == 204

    db_session.expire_all()
    assert db_session.get(Investor, investor.id) is None
    for model in (InvestorProfile, Goal, Holding, Recommendation):
        assert db_session.query(model).filter(model.investor_id == investor.id).count() == 0
        assert db_session.query(model).filter(model.investor_id == other.id).count() == 1
    assert db_session.query(RecommendationEvaluation).count() == 1
    assert len(removed) == 1 and removed[0].startswith("evaluation:")
    assert login(client).status_code == 401
