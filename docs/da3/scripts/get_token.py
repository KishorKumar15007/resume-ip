"""Print one seeded-candidate access token for a DA3 load-test stack."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LOADTEST_ENV_PATH = REPOSITORY_ROOT / "backend" / ".env.loadtest"
SEEDED_CANDIDATE_EMAIL = "da3-seed-candidate-1@example.com"
REQUEST_TIMEOUT_SECONDS = 10
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def parse_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.hostname not in LOOPBACK_HOSTS
    ):
        raise argparse.ArgumentTypeError(
            "--base-url must be a loopback HTTP(S) origin"
        )
    return value.rstrip("/")


def load_credentials() -> tuple[str, str]:
    if not LOADTEST_ENV_PATH.is_file():
        raise RuntimeError("load-test configuration file is unavailable")

    values = dotenv_values(LOADTEST_ENV_PATH)
    if values.get("DA3_LOADTEST_BRANCH") != "da3-loadtest":
        raise RuntimeError("load-test branch sentinel is invalid")

    password = values.get("DA3_SEED_PASSWORD")
    if not password:
        raise RuntimeError("load-test seed password is unavailable")

    return SEEDED_CANDIDATE_EMAIL, password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        type=parse_base_url,
        default="http://localhost:8080",
        help="load-balancer origin (default: http://localhost:8080)",
    )
    args = parser.parse_args()

    try:
        email, password = load_credentials()
        response = requests.post(
            f"{args.base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except (OSError, requests.RequestException, RuntimeError):
        print("token helper could not complete the login request", file=sys.stderr)
        return 1

    if response.status_code != 200:
        print(f"token helper received HTTP {response.status_code}", file=sys.stderr)
        return 1

    try:
        token = response.json().get("access_token")
    except ValueError:
        token = None

    if not isinstance(token, str) or not token:
        print("token helper response did not contain an access token", file=sys.stderr)
        return 1

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
