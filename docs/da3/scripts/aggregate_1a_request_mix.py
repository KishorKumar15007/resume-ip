"""Generate the DA3 1a request-mix table from declared scenario assumptions."""

from __future__ import annotations

import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIRECTORY = REPOSITORY_ROOT / "docs" / "da3" / "results"
INPUT_PATH = RESULTS_DIRECTORY / "07-request-mix-assumptions.json"
MARKDOWN_PATH = RESULTS_DIRECTORY / "07-request-mix-table.md"
CSV_PATH = RESULTS_DIRECTORY / "07-request-mix-table.csv"


def rounded(value: Decimal, places: int) -> str:
    quantum = Decimal("1").scaleb(-places)
    return format(value.quantize(quantum, rounding=ROUND_HALF_UP), f".{places}f")


def load_assumptions() -> dict:
    with INPUT_PATH.open(encoding="utf-8") as source:
        assumptions = json.load(source)

    if assumptions.get("label") != "assumptions_not_observations":
        raise ValueError("request-mix input must be labelled assumptions_not_observations")

    if not isinstance(assumptions.get("students"), int) or assumptions["students"] <= 0:
        raise ValueError("students must be a positive integer")
    if (
        not isinstance(assumptions.get("peak_window_seconds"), int)
        or assumptions["peak_window_seconds"] <= 0
    ):
        raise ValueError("peak_window_seconds must be a positive integer")

    requests = assumptions.get("per_student_requests")
    if not isinstance(requests, list) or not requests:
        raise ValueError("per_student_requests must be a non-empty list")

    for request in requests:
        if (
            not isinstance(request.get("method"), str)
            or not isinstance(request.get("path"), str)
            or not isinstance(request.get("category"), str)
            or not isinstance(request.get("count"), int)
            or request["count"] <= 0
        ):
            raise ValueError("each request-mix row must have valid endpoint metadata")

    return assumptions


def build_rows(assumptions: dict) -> tuple[list[dict], int, int]:
    students = assumptions["students"]
    total_requests = sum(row["count"] * students for row in assumptions["per_student_requests"])
    read_requests = sum(
        row["count"] * students
        for row in assumptions["per_student_requests"]
        if row["category"] == "read"
    )
    window = Decimal(assumptions["peak_window_seconds"])
    places_share = assumptions["rounding"]["shares_decimal_places"]
    places_rate = assumptions["rounding"]["rates_decimal_places"]

    rows = []
    for request in assumptions["per_student_requests"]:
        endpoint_total = request["count"] * students
        rows.append(
            {
                "method": request["method"],
                "path": request["path"],
                "category": request["category"],
                "per_student": request["count"],
                "total_requests": endpoint_total,
                "share_of_total_percent": rounded(
                    Decimal(endpoint_total) * Decimal("100") / Decimal(total_requests),
                    places_share,
                ),
                "average_requests_per_second": rounded(
                    Decimal(endpoint_total) / window,
                    places_rate,
                ),
            }
        )

    return rows, total_requests, read_requests


def write_outputs(assumptions: dict, rows: list[dict], total_requests: int, read_requests: int) -> None:
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    window = assumptions["peak_window_seconds"]
    places_share = assumptions["rounding"]["shares_decimal_places"]
    places_rate = assumptions["rounding"]["rates_decimal_places"]
    total_rate = rounded(Decimal(total_requests) / Decimal(window), places_rate)

    with CSV_PATH.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    markdown_rows = [
        "# DA3 1a Request Mix",
        "",
        "**Scenario assumptions, not observations.**",
        "",
        "| method | path | category | per student | total requests | share of total | average requests/s |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    markdown_rows.extend(
        "| {method} | `{path}` | {category} | {per_student} | {total_requests} | {share_of_total_percent}% | {average_requests_per_second} |".format(
            **row
        )
        for row in rows
    )
    markdown_rows.extend(
        [
            "",
            f"- Students: {assumptions['students']}",
            f"- Peak window: {window} seconds",
            f"- Read requests: {read_requests}",
            f"- Total HTTP requests: {total_requests}",
            f"- Average total request rate: {total_rate} requests/s",
            (
                "- Shares and rates are rounded with ROUND_HALF_UP to "
                f"{places_share} and {places_rate} decimal places respectively."
            ),
        ]
    )
    MARKDOWN_PATH.write_text("\n".join(markdown_rows) + "\n", encoding="utf-8")


def main() -> int:
    assumptions = load_assumptions()
    rows, total_requests, read_requests = build_rows(assumptions)
    write_outputs(assumptions, rows, total_requests, read_requests)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
