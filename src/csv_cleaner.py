
"""
Project: CSV Data Cleaner
Purpose: Clean, validate and analyze customer CSV records.
"""

import csv
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(BASE_DIR, "data", "custom.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "output", "cleaned_custom.csv")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


def validate_email(email):
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return bool(re.fullmatch(pattern, email))


def clean_csv():

    total_records = 0
    missing_records = 0
    invalid_emails = 0
    duplicate_records = 0
    clean_records = 0

    seen_customer_ids = set()

    print("\nCSV DATA CLEANER STARTED")
    print("-" * 45)

    try:
        with open(INPUT_FILE, "r", newline="", encoding="utf-8-sig") as input_file:

            reader = csv.DictReader(input_file)

            if not reader.fieldnames:
                print("ERROR: CSV file is empty or has no headers.")
                return

            # Normalize headers
            original_headers = reader.fieldnames
            normalized_headers = {
                header.strip().lower(): header
                for header in original_headers
            }

            required_columns = [
                "customer_id",
                "name",
                "email",
                "city"
            ]

            missing_headers = [
                column for column in required_columns
                if column not in normalized_headers
            ]

            if missing_headers:
                print("ERROR: Required columns missing:", missing_headers)
                return

            output_headers = [
                "Customer_ID",
                "Name",
                "Email",
                "City",
                "Data_Quality_Issues"
            ]

            with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as output_file:

                writer = csv.DictWriter(
                    output_file,
                    fieldnames=output_headers
                )

                writer.writeheader()

                for row in reader:

                    total_records += 1

                    # Normalize input fields
                    cleaned = {
                        key.strip().lower(): (value.strip() if value else "")
                        for key, value in row.items()
                        if key is not None
                    }

                    record = {
                        "Customer_ID": cleaned.get("customer_id", ""),
                        "Name": cleaned.get("name", ""),
                        "Email": cleaned.get("email", "").lower(),
                        "City": cleaned.get("city", "")
                    }

                    issues = []

                    # Missing value detection
                    for column, value in record.items():
                        if not value:
                            issues.append(f"Missing {column}")

                    if issues:
                        missing_records += 1

                    # Email validation
                    email = record["Email"]

                    if email and not validate_email(email):
                        issues.append("Invalid email format")
                        invalid_emails += 1

                    # Duplicate ID detection
                    customer_id = record["Customer_ID"]

                    if customer_id:
                        if customer_id in seen_customer_ids:
                            issues.append("Duplicate Customer_ID")
                            duplicate_records += 1
                        else:
                            seen_customer_ids.add(customer_id)

                    if not issues:
                        clean_records += 1

                    record["Data_Quality_Issues"] = (
                        "; ".join(issues) if issues else "No issues"
                    )

                    writer.writerow(record)

        print("\nCSV CLEANING COMPLETED SUCCESSFULLY!")
        print("-" * 45)
        print("Total records:", total_records)
        print("Records with missing values:", missing_records)
        print("Invalid emails:", invalid_emails)
        print("Duplicate customer IDs:", duplicate_records)
        print("Records without issues:", clean_records)
        print("\nOutput saved at:")
        print(OUTPUT_FILE)
        print("-" * 45)

    except FileNotFoundError:
        print("ERROR: Input CSV file not found.")

    except PermissionError:
        print("ERROR: File access denied.")

    except Exception as error:
        print("UNEXPECTED ERROR:", error)


if __name__ == "__main__":
    clean_csv()
