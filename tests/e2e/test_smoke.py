"""Browser smoke test of the real app (UI + API + database). No LLM calls, so it is cheap and stable.

Skipped unless E2E_BASE_URL points at a running app, e.g.
    E2E_BASE_URL=http://localhost:5173 .venv/Scripts/python.exe -m pytest tests/e2e -q
Needs `pip install playwright` and `python -m playwright install chromium`.
It creates a throwaway account and deletes it again through the UI.
"""

import os
import re
import uuid

import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="set E2E_BASE_URL to run browser smoke tests")

playwright_api = pytest.importorskip("playwright.sync_api")
expect = playwright_api.expect

PAGES = [  # (nav label, path, heading)
    ("Dashboard", "/dashboard", None),
    ("Portfolio", "/portfolio", None),
    ("Advice", "/advice", None),
    ("Suggestions", "/recommendations", None),
    ("Goals", "/goals", None),
    ("Scenarios", "/scenarios", None),
    ("Tax notes", "/tax", None),
    ("Market data", "/market", None),
    ("Self-assessment", "/self-assessment", None),
    ("Profile & country", "/onboarding", "Profile & country"),
    ("Account", "/account", "Account"),
]


@pytest.fixture(scope="module")
def account():
    """A fresh investor with a profile, created through the API."""
    import httpx

    email, password = f"e2e-{uuid.uuid4().hex[:10]}@example.com", "e2e-password-1"
    with httpx.Client(base_url=f"{BASE_URL}/api", timeout=30) as api:
        investor = api.post("/investors/", json={"email": email, "password": password, "full_name": "E2E Bot"})
        investor.raise_for_status()
        token = api.post("/auth/login", data={"username": email, "password": password}).json()["access_token"]
        api.put(
            f"/investors/{investor.json()['id']}/profile",
            json={"risk_cadence": "Balanced", "horizon_years": 10, "country": "IN", "base_currency": "INR"},
            headers={"Authorization": f"Bearer {token}"},
        ).raise_for_status()
    return {"email": email, "password": password}


@pytest.fixture(scope="module")
def page(account):
    with playwright_api.sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(base_url=BASE_URL)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.errors = errors
        yield page
        browser.close()


def login(page, email, password):
    page.goto("/login")
    page.get_by_label("Email").first.fill(email)
    page.get_by_label("Password").first.fill(password)
    page.get_by_role("button", name="Log in").click()


def test_login_shows_dashboard(page, account):
    login(page, account["email"], account["password"])
    expect(page).to_have_url(re.compile(r"/dashboard$"), timeout=20_000)


@pytest.mark.parametrize("label,path,heading", PAGES)
def test_every_page_renders(page, label, path, heading):
    page.get_by_role("link", name=label).first.click()
    expect(page).to_have_url(re.compile(re.escape(path) + "$"))
    h1 = page.locator("h1").first
    expect(h1).to_be_visible(timeout=20_000)
    if heading:
        expect(h1).to_have_text(heading)
    assert not page.errors, f"uncaught JS errors on {path}: {page.errors}"


def test_change_password_then_log_back_in(page, account):
    page.goto("/account")
    page.get_by_label("Current password").fill(account["password"])
    page.get_by_label("New password", exact=True).fill("e2e-password-2")
    page.get_by_label("Confirm new password").fill("e2e-password-2")
    page.get_by_role("button", name="Update password").click()
    expect(page.get_by_text("Password changed")).to_be_visible(timeout=15_000)
    account["password"] = "e2e-password-2"

    page.get_by_role("button", name="Log out").first.click()
    expect(page).to_have_url(re.compile(r"/login$"))
    login(page, account["email"], account["password"])
    expect(page).to_have_url(re.compile(r"/dashboard$"), timeout=20_000)


def test_delete_account_cleans_up(page, account):
    page.goto("/account")
    page.locator("#delete-password").fill(account["password"])
    page.locator("#delete-phrase").fill("DELETE")
    page.get_by_role("button", name="Delete my account").click()
    expect(page).to_have_url(re.compile(r"/login$"), timeout=15_000)

    login(page, account["email"], account["password"])
    expect(page.get_by_text("Incorrect email or password")).to_be_visible(timeout=15_000)
