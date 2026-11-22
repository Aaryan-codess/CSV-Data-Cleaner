import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
import csv_cleaner  # noqa: E402


class CSVToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "input.csv"
        self.destination = self.root / "nested" / "output.csv"

    def tearDown(self):
        self.temp.cleanup()

    def write_csv(self, headers, rows, *, encoding="utf-8", newline=""):
        with self.source.open("w", encoding=encoding, newline=newline) as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(headers)
            writer.writerows(rows)

    def read_output(self):
        with self.destination.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_email_syntax_examples(self):
        for email in ("a@example.com", "first.last+tag@sub.example.org"):
            with self.subTest(email=email):
                self.assertTrue(csv_cleaner.validate_email(email))
        for email in ("", "no-at.example.com", "a@localhost", "a@b.c", "a@@example.com"):
            with self.subTest(email=email):
                self.assertFalse(csv_cleaner.validate_email(email))

    def test_empty_file_and_header_only_file(self):
        self.source.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(csv_cleaner.CSVDataError, "empty"):
            csv_cleaner.clean_csv(self.source, self.destination)
        self.write_csv(["Customer_ID", "Name", "Email", "City"], [])
        summary = csv_cleaner.clean_csv(self.source, self.destination)
        self.assertEqual(summary.total_records, 0)
        self.assertEqual(self.read_output(), [])

    def test_missing_required_columns_rejected_and_old_output_preserved(self):
        self.write_csv(["Customer_ID", "Name", "Email"], [["1", "A", "a@b.com"]])
        self.destination.parent.mkdir(parents=True)
        self.destination.write_text("previous valid output\n", encoding="utf-8")
        with self.assertRaisesRegex(csv_cleaner.CSVDataError, "Missing required"):
            csv_cleaner.clean_csv(self.source, self.destination)
        self.assertEqual(self.destination.read_text(encoding="utf-8"), "previous valid output\n")

    def test_reordered_case_and_whitespace_headers_and_utf8_bom(self):
        self.write_csv([" City ", " eMaIl", "NAME", " CUSTOMER_ID "], [["Town", "A@EXAMPLE.COM", " Ada ", "7"]])
        raw = self.source.read_bytes()
        self.source.write_bytes(b"\xef\xbb\xbf" + raw)
        csv_cleaner.clean_csv(self.source, self.destination)
        row = self.read_output()[0]
        self.assertEqual((row["Customer_ID"], row["Name"], row["Email"], row["City"]),
                         ("7", "Ada", "a@example.com", "Town"))

    def test_duplicate_normalized_and_blank_headers_rejected(self):
        for headers, expected in [
            (["Customer_ID", "customer_id", "Name", "Email", "City"], "Duplicate headers"),
            (["Customer_ID", "Name", "Email", "City", "   "], "blank header"),
        ]:
            with self.subTest(headers=headers):
                self.write_csv(headers, [])
                with self.assertRaisesRegex(csv_cleaner.CSVDataError, expected):
                    csv_cleaner.clean_csv(self.source, self.destination)

    def test_missing_whitespace_values_invalid_email_and_multiple_issues_retained(self):
        self.write_csv(
            ["Customer_ID", "Name", "Email", "City"],
            [[" ", " ", "bad", "Town"], ["2", "B", " ", "Town"]],
        )
        summary = csv_cleaner.clean_csv(self.source, self.destination)
        self.assertEqual(summary.records_with_missing_values, 2)
        self.assertEqual(summary.invalid_emails, 1)
        rows = self.read_output()
        self.assertEqual(len(rows), 2)
        self.assertIn("Missing Customer_ID", rows[0]["Data_Quality_Issues"])
        self.assertIn("Missing Name", rows[0]["Data_Quality_Issues"])
        self.assertIn("Invalid email format", rows[0]["Data_Quality_Issues"])
        self.assertIn("Missing Email", rows[1]["Data_Quality_Issues"])

    def test_duplicate_ids_blank_ids_whitespace_and_case_semantics(self):
        self.write_csv(
            ["Customer_ID", "Name", "Email", "City"],
            [[" x ", "A", "a@b.com", "T"], ["x", "B", "b@b.com", "T"],
             ["", "C", "c@b.com", "T"], ["X", "D", "d@b.com", "T"]],
        )
        summary = csv_cleaner.clean_csv(self.source, self.destination)
        self.assertEqual(summary.duplicate_customer_ids, 1)
        rows = self.read_output()
        self.assertIn("Duplicate Customer_ID", rows[1]["Data_Quality_Issues"])
        self.assertIn("Missing Customer_ID", rows[2]["Data_Quality_Issues"])
        self.assertEqual(rows[3]["Data_Quality_Issues"], "No issues")

    def test_additional_columns_preserved_and_trimmed(self):
        self.write_csv(["Customer_ID", "Name", "Email", "City", " Notes ", "Loyalty"],
                       [["1", "A", "a@b.com", "T", "  note  ", " 42 "]])
        csv_cleaner.clean_csv(self.source, self.destination)
        row = self.read_output()[0]
        self.assertEqual(row["Notes"], "note")
        self.assertEqual(row["Loyalty"], "42")

    def test_reserved_quality_column_rejected(self):
        self.write_csv(["Customer_ID", "Name", "Email", "City", "Data_Quality_Issues"], [])
        with self.assertRaisesRegex(csv_cleaner.CSVDataError, "reserved"):
            csv_cleaner.clean_csv(self.source, self.destination)

    def test_short_and_extra_width_rows_fail_without_replacing_output(self):
        for row in (["1", "A", "a@b.com"], ["1", "A", "a@b.com", "T", "extra"]):
            with self.subTest(row=row):
                self.write_csv(["Customer_ID", "Name", "Email", "City"], [row])
                self.destination.parent.mkdir(parents=True, exist_ok=True)
                self.destination.write_text("old output", encoding="utf-8")
                with self.assertRaisesRegex(csv_cleaner.CSVDataError, "Malformed record"):
                    csv_cleaner.clean_csv(self.source, self.destination)
                self.assertEqual(self.destination.read_text(encoding="utf-8"), "old output")

    def test_quoted_commas_escaped_quotes_and_embedded_newlines(self):
        self.write_csv(["Customer_ID", "Name", "Email", "City", "Note"],
                       [["1", 'A "quoted", Name', "a@b.com", "New, Town", "line one\nline two"]])
        csv_cleaner.clean_csv(self.source, self.destination)
        row = self.read_output()[0]
        self.assertEqual(row["Name"], 'A "quoted", Name')
        self.assertEqual(row["City"], "New, Town")
        self.assertEqual(row["Note"], "line one\nline two")

    def test_formula_prefixes_are_neutralized_and_raw_mode_preserves(self):
        values = ["=1+1", "+SUM(A1:A2)", "-1+2", "@SUM(A1:A2)", "\ufeff=hidden"]
        self.write_csv(["Customer_ID", "Name", "Email", "City", "Value"],
                       [[str(i + 1), "A", "a@b.com", "T", value] for i, value in enumerate(values)])
        csv_cleaner.clean_csv(self.source, self.destination)
        safe_values = [row["Value"] for row in self.read_output()]
        self.assertEqual(safe_values, ["'" + value for value in values])
        csv_cleaner.clean_csv(self.source, self.destination, spreadsheet_safe=False)
        raw_values = [row["Value"] for row in self.read_output()]
        self.assertEqual(raw_values, values)

    def test_output_directory_created_and_existing_output_replaced(self):
        self.write_csv(["Customer_ID", "Name", "Email", "City"], [["1", "A", "a@b.com", "T"]])
        summary = csv_cleaner.clean_csv(self.source, self.destination)
        self.assertTrue(self.destination.exists())
        self.assertEqual(summary.total_records, 1)
        csv_cleaner.clean_csv(self.source, self.destination)
        self.assertEqual(len(self.read_output()), 1)

    def test_input_output_collision_is_rejected(self):
        self.write_csv(["Customer_ID", "Name", "Email", "City"], [])
        with self.assertRaisesRegex(csv_cleaner.CSVDataError, "same file"):
            csv_cleaner.clean_csv(self.source, self.source)

    def test_invalid_output_path_and_missing_input_preserve_existing_output(self):
        blocker = self.root / "not_a_directory"
        blocker.write_text("file", encoding="utf-8")
        with self.assertRaises(OSError):
            csv_cleaner.clean_csv(self.root / "missing.csv", blocker / "out.csv")

    def test_invalid_encoding_preserves_existing_output(self):
        self.source.write_bytes(b"Customer_ID,Name,Email,City\n1,\xff,A,a@b.com,T\n")
        self.destination.parent.mkdir(parents=True)
        self.destination.write_text("old", encoding="utf-8")
        with self.assertRaises(UnicodeDecodeError):
            csv_cleaner.clean_csv(self.source, self.destination)
        self.assertEqual(self.destination.read_text(encoding="utf-8"), "old")

    def test_cli_success_failure_exit_codes_and_stderr(self):
        self.write_csv(["Customer_ID", "Name", "Email", "City"], [["1", "A", "a@b.com", "T"]])
        script = PROJECT_ROOT / "src" / "csv_cleaner.py"
        ok = subprocess.run([sys.executable, str(script), "--input", str(self.source), "--output", str(self.destination)],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("CSV CLEANING COMPLETED", ok.stdout)
        failed = subprocess.run([sys.executable, str(script), "--input", str(self.root / "missing.csv"),
                                 "--output", str(self.destination)], capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertTrue(failed.stderr.startswith("ERROR:"))

    def test_documented_command_works_from_clean_project_copy(self):
        clean = self.root / "CSV-Data-Cleaner"
        (clean / "src").mkdir(parents=True)
        (clean / "data").mkdir()
        shutil.copy2(PROJECT_ROOT / "src" / "csv_cleaner.py", clean / "src" / "csv_cleaner.py")
        shutil.copy2(PROJECT_ROOT / "data" / "custom.csv", clean / "data" / "custom.csv")
        run = subprocess.run([sys.executable, "src/csv_cleaner.py"], cwd=clean, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue((clean / "output" / "cleaned_custom.csv").is_file())
        with (clean / "output" / "cleaned_custom.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 9)

    def test_importing_module_does_not_create_output_directory(self):
        clean = self.root / "fresh"
        (clean / "src").mkdir(parents=True)
        shutil.copy2(PROJECT_ROOT / "src" / "csv_cleaner.py", clean / "src" / "csv_cleaner.py")
        run = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import csv_cleaner"],
            cwd=clean, capture_output=True, text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse((clean / "output").exists())


if __name__ == "__main__":
    unittest.main()
