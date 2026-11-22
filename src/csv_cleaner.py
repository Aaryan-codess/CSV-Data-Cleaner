"""Clean and annotate customer CSV files using only the Python standard library."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REQUIRED_COLUMNS = ("customer_id", "name", "email", "city")
CANONICAL_HEADERS = {
    "customer_id": "Customer_ID",
    "name": "Name",
    "email": "Email",
    "city": "City",
}
ISSUES_HEADER = "Data_Quality_Issues"
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    )
FORMULA_PREFIXES = ("=", "+", "-", "@")


class CSVDataError(Exception):
    """Raised when a CSV's structure is ambiguous or inconsistent."""


@dataclass(frozen=True)
class Summary:
    total_records: int
    records_with_missing_values: int
    invalid_emails: int
    duplicate_customer_ids: int
    records_without_issues: int


def validate_email(email: str) -> bool:
    """Return whether email has the project's intentionally basic syntax shape."""
    return bool(EMAIL_PATTERN.fullmatch(email))


def _normalize_headers(headers: list[str]) -> tuple[list[str], dict[str, int]]:
    normalized = [header.strip().lower() for header in headers]
    duplicates = sorted({name for name in normalized if normalized.count(name) > 1})
    if duplicates:
        raise CSVDataError(f"Duplicate headers after normalization: {', '.join(repr(x) for x in duplicates)}")
    if any(not name for name in normalized):
        raise CSVDataError("CSV contains a blank header.")
    positions = {name: index for index, name in enumerate(normalized)}
    if "data_quality_issues" in positions:
        raise CSVDataError("Header 'Data_Quality_Issues' is reserved for the generated quality report.")
    missing = [name for name in REQUIRED_COLUMNS if name not in positions]
    if missing:
        raise CSVDataError("Missing required columns: " + ", ".join(missing))
    return normalized, positions


def _spreadsheet_safe(value: str) -> str:
    """Prefix formula-leading text so spreadsheet software imports it as text."""
    first_visible = value.lstrip("\ufeff\u200b\u200c\u200d")
    if first_visible.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _same_path(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    return first.exists() and second.exists() and os.path.samefile(first, second)


def clean_csv(input_path: Path | str, output_path: Path | str, *, spreadsheet_safe: bool = True) -> Summary:
    """Validate and annotate a CSV, atomically replacing output only on success.

    Malformed-width records reject the whole input. Other quality issues are
    annotated and retained. All cell values are trimmed and email is lowercased.
    """
    source = Path(input_path)
    destination = Path(output_path)
    if _same_path(source, destination):
        raise CSVDataError("Input and output paths resolve to the same file.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    counts = dict(total=0, missing=0, invalid=0, duplicates=0, clean=0)
    seen_customer_ids: set[str] = set()

    try:
        with source.open("r", newline="", encoding="utf-8-sig") as input_file:
            reader = csv.reader(input_file, strict=True)
            try:
                input_headers = next(reader)
            except StopIteration:
                raise CSVDataError("Input CSV is empty; expected a header row.") from None
            if not input_headers:
                raise CSVDataError("Input CSV has a blank header row.")

            normalized_headers, positions = _normalize_headers(input_headers)
            extra_indices = [i for i, name in enumerate(normalized_headers) if name not in REQUIRED_COLUMNS]
            output_headers = [CANONICAL_HEADERS[name] for name in REQUIRED_COLUMNS]
            extra_headers = [input_headers[i].strip() for i in extra_indices]
            output_headers.extend(extra_headers)
            output_headers.append(ISSUES_HEADER)

            with tempfile.NamedTemporaryFile(
                mode="w", newline="", encoding="utf-8", dir=destination.parent,
                prefix=f".{destination.name}.", suffix=".tmp", delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                writer = csv.writer(temporary_file)
                writer.writerow(output_headers)

                for row in reader:
                    line_number = reader.line_num
                    counts["total"] += 1
                    if len(row) != len(input_headers):
                        detail = "too few" if len(row) < len(input_headers) else "too many"
                        raise CSVDataError(
                            f"Malformed record ending at line {line_number}: {detail} fields "
                            f"(expected {len(input_headers)}, found {len(row)})."
                        )

                    values = [value.strip() for value in row]
                    record = {
                        "Customer_ID": values[positions["customer_id"]],
                        "Name": values[positions["name"]],
                        "Email": values[positions["email"]].lower(),
                        "City": values[positions["city"]],
                    }
                    extras = [values[index] for index in extra_indices]
                    issues: list[str] = []
                    for column, value in record.items():
                        if not value:
                            issues.append(f"Missing {column}")
                    if any(issue.startswith("Missing ") for issue in issues):
                        counts["missing"] += 1

                    email = record["Email"]
                    if email and not validate_email(email):
                        issues.append("Invalid email format")
                        counts["invalid"] += 1

                    customer_id = record["Customer_ID"]
                    if customer_id:
                        if customer_id in seen_customer_ids:
                            issues.append("Duplicate Customer_ID")
                            counts["duplicates"] += 1
                        else:
                            seen_customer_ids.add(customer_id)

                    if not issues:
                        counts["clean"] += 1
                    output_values = [record[CANONICAL_HEADERS[name]] for name in REQUIRED_COLUMNS]
                    output_values.extend(extras)
                    output_values.append("; ".join(issues) if issues else "No issues")
                    if spreadsheet_safe:
                        output_values = [_spreadsheet_safe(value) for value in output_values]
                    writer.writerow(output_values)

                temporary_file.flush()
                os.fsync(temporary_file.fileno())

        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return Summary(
        total_records=counts["total"],
        records_with_missing_values=counts["missing"],
        invalid_emails=counts["invalid"],
        duplicate_customer_ids=counts["duplicates"],
        records_without_issues=counts["clean"],
    )


def _default_paths() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "custom.csv", project_root / "output" / "cleaned_custom.csv"


def build_parser() -> argparse.ArgumentParser:
    default_input, default_output = _default_paths()
    parser = argparse.ArgumentParser(description="Validate and annotate a customer CSV file.")
    parser.add_argument("--input", type=Path, default=default_input, help=f"input CSV (default: {default_input})")
    parser.add_argument("--output", type=Path, default=default_output, help=f"output CSV (default: {default_output})")
    export = parser.add_mutually_exclusive_group()
    export.add_argument("--spreadsheet-safe", dest="spreadsheet_safe", action="store_true", default=True,
                        help="prefix values beginning with =, +, -, or @ with an apostrophe (default)")
    export.add_argument("--raw-values", dest="spreadsheet_safe", action="store_false",
                        help="preserve values exactly; output may execute formulas in spreadsheet software")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = clean_csv(args.input, args.output, spreadsheet_safe=args.spreadsheet_safe)
    except (CSVDataError, OSError, UnicodeError, csv.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("CSV CLEANING COMPLETED")
    print(f"Total records: {summary.total_records}")
    print(f"Records with missing values: {summary.records_with_missing_values}")
    print(f"Invalid emails: {summary.invalid_emails}")
    print(f"Duplicate customer IDs: {summary.duplicate_customer_ids}")
    print(f"Records without issues: {summary.records_without_issues}")
    print(f"Output saved at: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
