"""Run the DA3 synthetic authentication and posting CRUD smoke test.

The script targets a running API only when invoked by the owner. It retains
tokens in memory, does not print them, and writes sanitized results under
docs/da3/results/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests


REQUEST_TIMEOUT_SECONDS = 10
RESULTS_DIRECTORY = Path(__file__).resolve().parents[1] / "results"


@dataclass
class CheckResult:
    step: str
    expected: str
    actual: str
    passed: bool
    status_code: int | None = None
    response_detail: str | None = None


class SmokeRunner:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.results: list[CheckResult] = []
        self.session = requests.Session()
        self.posting_id: str | None = None
        self.recruiter_headers: dict[str, str] | None = None

    def add_result(
        self,
        step: str,
        expected: str,
        actual: str,
        passed: bool,
        status_code: int | None = None,
        response_detail: str | None = None,
    ) -> bool:
        self.results.append(
            CheckResult(
                step=step,
                expected=expected,
                actual=actual,
                passed=passed,
                status_code=status_code,
                response_detail=response_detail,
            )
        )
        return passed

    @staticmethod
    def sanitized_error_detail(response: requests.Response) -> str:
        """Return useful FastAPI error details without echoing submitted values."""
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            return "non-JSON error response"

        if isinstance(detail, list):
            messages: list[str] = []
            for item in detail:
                if not isinstance(item, dict):
                    continue
                location = item.get("loc")
                message = item.get("msg")
                if isinstance(location, list) and isinstance(message, str):
                    messages.append(f"{'.'.join(map(str, location))}: {message}")
            return "; ".join(messages)[:500] or "validation detail present"

        if isinstance(detail, str):
            sanitized = re.sub(
                r"(?i)\\b(password|token|authorization|secret|api[_ -]?key|jwt)\\b[^,;\\s]*",
                "[redacted]",
                detail,
            )
            return sanitized[:500]

        return "error detail present but not safe to display"

    def request(
        self,
        step: str,
        expected: str,
        method: str,
        path: str,
        *,
        expected_status: int,
        **kwargs: Any,
    ) -> requests.Response | None:
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=REQUEST_TIMEOUT_SECONDS,
                **kwargs,
            )
        except requests.RequestException as exc:
            self.add_result(
                step,
                expected,
                f"request error: {type(exc).__name__}",
                False,
            )
            return None

        passed = response.status_code == expected_status
        response_detail = None if passed else self.sanitized_error_detail(response)
        actual = f"HTTP {response.status_code}"
        if response_detail:
            actual = f"{actual}; detail: {response_detail}"
        self.add_result(
            step,
            expected,
            actual,
            passed,
            response.status_code,
            response_detail,
        )
        return response

    def blocked(self, step: str, expected: str) -> None:
        self.add_result(step, expected, "not run: prerequisite failed", False)

    @staticmethod
    def token_from(response: requests.Response) -> str | None:
        try:
            token = response.json().get("access_token")
        except ValueError:
            return None
        return token if isinstance(token, str) and token else None

    @staticmethod
    def posting_id_from(response: requests.Response) -> str | None:
        try:
            posting_id = response.json().get("id")
        except ValueError:
            return None
        return posting_id if isinstance(posting_id, str) and posting_id else None

    def add_payload_check(
        self,
        step: str,
        expected: str,
        response: requests.Response | None,
        field: str,
        expected_value: str,
    ) -> bool:
        if response is None or response.status_code < 200 or response.status_code >= 300:
            return self.add_result(step, expected, "not run: request did not succeed", False)
        try:
            actual_value = response.json().get(field)
        except ValueError:
            actual_value = None
        return self.add_result(
            step,
            expected,
            f"{field} {'matched' if actual_value == expected_value else 'did not match'}",
            actual_value == expected_value,
            response.status_code,
        )

    def cleanup_posting(self) -> None:
        if self.posting_id is None or self.recruiter_headers is None:
            return
        try:
            response = self.session.delete(
                f"{self.base_url}/postings/{self.posting_id}",
                headers=self.recruiter_headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            self.add_result(
                "Cleanup synthetic posting",
                "HTTP 204 or 404",
                f"request error: {type(exc).__name__}",
                False,
            )
            return

        self.add_result(
            "Cleanup synthetic posting",
            "HTTP 204 or 404",
            f"HTTP {response.status_code}",
            response.status_code in {204, 404},
            response.status_code,
        )

    def run(self) -> bool:
        run_id = str(time.time_ns())
        recruiter_email = f"da3-smoke-recruiter-{run_id}@example.com"
        candidate_email = f"da3-smoke-candidate-{run_id}@example.com"
        password = f"Da3Smoke-{run_id}!"
        posting_payload = {
            "title": "DA3 synthetic smoke posting",
            "description": "Synthetic record used only for the DA3 smoke test.",
            "required_skills": ["Python", "FastAPI"],
        }
        update_payload = {
            "title": "DA3 synthetic smoke posting updated",
            "description": "Updated synthetic record used only for the DA3 smoke test.",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        }

        recruiter_signup = self.request(
            "Register synthetic recruiter",
            "HTTP 201",
            "POST",
            "/auth/signup",
            expected_status=201,
            json={"email": recruiter_email, "password": password, "role": "recruiter"},
        )
        if recruiter_signup is None or recruiter_signup.status_code != 201:
            return False

        candidate_signup = self.request(
            "Register synthetic candidate",
            "HTTP 201",
            "POST",
            "/auth/signup",
            expected_status=201,
            json={"email": candidate_email, "password": password, "role": "candidate"},
        )
        if candidate_signup is None or candidate_signup.status_code != 201:
            return False

        recruiter_login = self.request(
            "Log in synthetic recruiter",
            "HTTP 200 and access token",
            "POST",
            "/auth/login",
            expected_status=200,
            json={"email": recruiter_email, "password": password},
        )
        recruiter_token = self.token_from(recruiter_login) if recruiter_login else None
        if not recruiter_token:
            self.add_result(
                "Validate recruiter login token",
                "non-empty access token",
                "access token missing",
                False,
                recruiter_login.status_code if recruiter_login else None,
            )
            return False
        self.add_result(
            "Validate recruiter login token",
            "non-empty access token",
            "access token received and retained only in memory",
            True,
            recruiter_login.status_code,
        )
        self.recruiter_headers = {"Authorization": f"Bearer {recruiter_token}"}

        candidate_login = self.request(
            "Log in synthetic candidate",
            "HTTP 200 and access token",
            "POST",
            "/auth/login",
            expected_status=200,
            json={"email": candidate_email, "password": password},
        )
        candidate_token = self.token_from(candidate_login) if candidate_login else None
        if not candidate_token:
            self.add_result(
                "Validate candidate login token",
                "non-empty access token",
                "access token missing",
                False,
                candidate_login.status_code if candidate_login else None,
            )
            return False
        self.add_result(
            "Validate candidate login token",
            "non-empty access token",
            "access token received and retained only in memory",
            True,
            candidate_login.status_code,
        )
        candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

        create_response = self.request(
            "Recruiter creates posting",
            "HTTP 201 and posting id",
            "POST",
            "/postings",
            expected_status=201,
            headers=self.recruiter_headers,
            json=posting_payload,
        )
        self.posting_id = self.posting_id_from(create_response) if create_response else None
        if not self.posting_id:
            self.add_result(
                "Validate created posting",
                "non-empty posting id",
                "posting id missing",
                False,
                create_response.status_code if create_response else None,
            )
            return False
        self.add_result(
            "Validate created posting",
            "non-empty posting id",
            "posting id received",
            True,
            create_response.status_code,
        )

        try:
            recruiter_read = self.request(
                "Recruiter reads posting",
                "HTTP 200 with matching id",
                "GET",
                f"/postings/{self.posting_id}",
                expected_status=200,
                headers=self.recruiter_headers,
            )
            self.add_payload_check(
                "Validate recruiter read response",
                "response id matches created posting",
                recruiter_read,
                "id",
                self.posting_id,
            )

            candidate_read = self.request(
                "Candidate reads posting",
                "HTTP 200 with matching id",
                "GET",
                f"/postings/{self.posting_id}",
                expected_status=200,
                headers=candidate_headers,
            )
            self.add_payload_check(
                "Validate candidate read response",
                "response id matches created posting",
                candidate_read,
                "id",
                self.posting_id,
            )

            self.request(
                "Candidate create posting is rejected",
                "HTTP 403",
                "POST",
                "/postings",
                expected_status=403,
                headers=candidate_headers,
                json=posting_payload,
            )
            self.request(
                "Candidate update posting is rejected",
                "HTTP 403",
                "PUT",
                f"/postings/{self.posting_id}",
                expected_status=403,
                headers=candidate_headers,
                json=update_payload,
            )
            self.request(
                "Candidate delete posting is rejected",
                "HTTP 403",
                "DELETE",
                f"/postings/{self.posting_id}",
                expected_status=403,
                headers=candidate_headers,
            )

            recruiter_update = self.request(
                "Recruiter updates posting",
                "HTTP 200 with updated title",
                "PUT",
                f"/postings/{self.posting_id}",
                expected_status=200,
                headers=self.recruiter_headers,
                json=update_payload,
            )
            self.add_payload_check(
                "Validate recruiter update response",
                "response title matches update",
                recruiter_update,
                "title",
                update_payload["title"],
            )

            delete_response = self.request(
                "Recruiter deletes posting",
                "HTTP 204",
                "DELETE",
                f"/postings/{self.posting_id}",
                expected_status=204,
                headers=self.recruiter_headers,
            )
            deleted = delete_response is not None and delete_response.status_code == 204

            self.request(
                "Deleted posting is not found",
                "HTTP 404",
                "GET",
                f"/postings/{self.posting_id}",
                expected_status=404,
                headers=self.recruiter_headers,
            )
            if deleted:
                self.posting_id = None
        finally:
            self.cleanup_posting()

        return all(result.passed for result in self.results)


def parse_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise argparse.ArgumentTypeError(
            "--base-url must be an HTTP(S) origin without credentials, query, or fragment"
        )
    return value.rstrip("/")


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_results(base_url: str, results: list[CheckResult]) -> None:
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    overall = "PASS" if results and all(result.passed for result in results) else "FAIL"
    payload = {
        "script": "docs/da3/scripts/smoke_api.py",
        "base_url": base_url,
        "overall": overall,
        "steps": [asdict(result) for result in results],
    }
    (RESULTS_DIRECTORY / "04-smoke.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    rows = [
        "# DA3 Step 4 API Smoke Test",
        "",
        f"Overall: **{overall}**",
        "",
        "| step | expected | actual |",
        "| --- | --- | --- |",
    ]
    rows.extend(
        "| {step} | {expected} | {actual} |".format(
            step=markdown_cell(result.step),
            expected=markdown_cell(result.expected),
            actual=markdown_cell(result.actual),
        )
        for result in results
    )
    (RESULTS_DIRECTORY / "04-smoke.md").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    print("\n".join(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        type=parse_base_url,
        default="http://localhost:8000",
        help="API origin to test (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    runner = SmokeRunner(args.base_url)
    try:
        runner.run()
    except Exception as exc:  # Ensure sanitized result artifacts exist on unexpected failure.
        runner.add_result(
            "Smoke test execution",
            "script completes without an unexpected exception",
            f"unexpected error: {type(exc).__name__}",
            False,
        )
    finally:
        write_results(args.base_url, runner.results)

    return 0 if runner.results and all(result.passed for result in runner.results) else 1


if __name__ == "__main__":
    sys.exit(main())
