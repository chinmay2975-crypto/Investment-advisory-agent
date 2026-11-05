"""Create or update the Hugging Face Space and deploy the app to it, from this machine.

    .venv/Scripts/python.exe scripts/deploy_hf.py [--space investad] [--secrets-only] [--no-wait]

Reads HF_TOKEN (a Hugging Face token with Write access) and the app's keys from .env, then:
  1. creates the Docker Space <your-hf-username>/<space> if it doesn't exist (public, so the
     .hf.space URL opens without a Hugging Face login; the app has its own sign-in);
  2. stores DATABASE_URL, the API keys, a fresh JWT_SECRET and APP_BASE_URL as Space *secrets*;
  3. uploads only what the Docker build needs and waits until the Space is running;
  4. checks /api/health/deep, which proves the Space can reach the database.
Nothing secret is printed. Later deploys happen automatically from GitHub (deploy-hf.yml).
"""

import argparse
import secrets
import shutil
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
COPIED_SECRETS = ["DATABASE_URL", "GEMINI_API_KEY", "GROQ_API_KEY", "FRED_API_KEY", "NEWSAPI_KEY",
                  "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"]
SPACE_README = """---
title: InvestAd
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
short_description: Country-aware investment advisory agent
---

Deployed from GitHub. General information only, not licensed financial advice.
"""


def assemble(target: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "dist", "tsconfig.tsbuildinfo")
    for name in ("app", "alembic", "frontend"):
        shutil.copytree(ROOT / name, target / name, ignore=ignore)
    for name in ("alembic.ini", "requirements.txt", "Dockerfile", ".dockerignore"):
        shutil.copy2(ROOT / name, target / name)
    (target / "README.md").write_text(SPACE_README, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--space", default="investad", help="Space name (default: investad)")
    parser.add_argument("--secrets-only", action="store_true", help="update secrets, don't upload code")
    parser.add_argument("--no-wait", action="store_true", help="don't wait for the build")
    args = parser.parse_args()

    env = dotenv_values(ROOT / ".env")
    token = env.get("HF_TOKEN")
    if not token:
        sys.exit("Add HF_TOKEN=<your Hugging Face write token> to .env first.")
    database_url = env.get("DATABASE_URL") or ""
    if ".supabase.co" in database_url and "pooler.supabase.com" not in database_url:
        sys.exit("DATABASE_URL uses Supabase's direct host (IPv6-only). Use the Session pooler URI "
                 "(Supabase > Connect > Session pooler) so the Space can reach the database.")
    missing = [k for k in ("GEMINI_API_KEY", "GROQ_API_KEY") if not env.get(k)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")

    api = HfApi(token=token)
    user = api.whoami()["name"]
    space_id = f"{user}/{args.space}"
    url = f"https://{user.lower().replace('_', '-')}-{args.space.lower().replace('_', '-')}.hf.space"

    api.create_repo(space_id, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    print(f"Space: https://huggingface.co/spaces/{space_id}")

    for key in COPIED_SECRETS:
        if env.get(key):
            api.add_space_secret(space_id, key, env[key])
    api.add_space_secret(space_id, "APP_BASE_URL", url)
    # A production-only signing key, different from the local one. Secrets can't be read back from
    # Hugging Face, so it is kept in .env as HF_JWT_SECRET; reusing it keeps users signed in across deploys.
    jwt_secret = env.get("HF_JWT_SECRET")
    if not jwt_secret:
        jwt_secret = secrets.token_hex(32)
        with open(ROOT / ".env", "a", encoding="utf-8") as f:
            f.write("\n# Production JWT signing key used by the Hugging Face Space (scripts/deploy_hf.py)\n"
                    f"HF_JWT_SECRET={jwt_secret}\n")
    api.add_space_secret(space_id, "JWT_SECRET", jwt_secret)
    print("Secrets set: " + ", ".join([k for k in COPIED_SECRETS if env.get(k)] + ["APP_BASE_URL", "JWT_SECRET"]))
    if args.secrets_only:
        return

    with tempfile.TemporaryDirectory() as tmp:
        assemble(Path(tmp))
        api.upload_folder(repo_id=space_id, repo_type="space", folder_path=tmp,
                          commit_message="Deploy from local checkout", delete_patterns=["*"])
    print("Code uploaded; Hugging Face is building the image (about 5 minutes the first time).")
    if args.no_wait:
        print(f"App URL: {url}")
        return

    stage, deadline = None, time.time() + 20 * 60
    while time.time() < deadline:
        new_stage = api.get_space_runtime(space_id).stage
        if new_stage != stage:
            print(f"  {time.strftime('%H:%M:%S')}  {new_stage}")
            stage = new_stage
        if stage in ("RUNNING", "BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            break
        time.sleep(15)
    if stage != "RUNNING":
        sys.exit(f"Space is {stage}. See the Logs tab: https://huggingface.co/spaces/{space_id}?logs=container")

    for _ in range(20):
        try:
            response = httpx.get(f"{url}/api/health/deep", timeout=30)
            if response.status_code == 200:
                print(f"Database reachable from the Space: {response.json()}")
                break
            print(f"  health check: HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            print(f"  health check: {type(exc).__name__}")
        time.sleep(10)
    else:
        sys.exit("The Space runs but can't reach the database. Check the Logs tab; if it's a timeout, "
                 "outbound port 5432 is blocked and Render is the fallback (docs/DEPLOY.md).")
    print(f"\nLive: {url}")


if __name__ == "__main__":
    main()
