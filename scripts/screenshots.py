"""Capture README screenshots of the running app as the demo account (run scripts/seed_demo.py first).

    .venv/Scripts/python.exe scripts/screenshots.py [--base http://localhost:5173] [--skip-advice]

Saves PNGs to docs/screenshots/. The advice shot runs one real suggestion (one LLM call).
"""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
EMAIL, PASSWORD = "demo@investad.app", "demo-investad-2026"

PAGES = [("dashboard", "/dashboard", "Performance vs"), ("portfolio", "/portfolio", None),
         ("goals", "/goals", None), ("tax", "/tax", None), ("self-assessment", "/self-assessment", None)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:5173")
    parser.add_argument("--skip-advice", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(base_url=args.base, viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.goto("/login")
        page.screenshot(path=OUT / "login.png")
        page.get_by_label("Email").first.fill(EMAIL)
        page.get_by_label("Password").first.fill(PASSWORD)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_url("**/dashboard")

        for name, path, wait_text in PAGES:
            page.goto(path)
            expect(page.locator("h1").first).to_be_visible(timeout=30_000)
            if wait_text:
                expect(page.get_by_text(wait_text).first).to_be_visible(timeout=60_000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1200)  # let charts finish animating
            page.screenshot(path=OUT / f"{name}.png")
            print("saved", name)

        if not args.skip_advice:
            page.goto("/advice")
            page.get_by_role("button", name="Get suggestion").click()
            expect(page.get_by_text("Saved as suggestion")).to_be_visible(timeout=180_000)
            page.wait_for_timeout(800)
            page.screenshot(path=OUT / "advice.png")
            print("saved advice")
        browser.close()


if __name__ == "__main__":
    main()
