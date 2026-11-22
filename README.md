# CSV Data Cleaner

A small command-line utility that checks customer CSV records, applies a few explicit normalizations, retains rows with quality issues, and writes a report column alongside the data. It uses only Python's standard library.

## Features

- Reads comma-separated UTF-8 CSV files, including files with a UTF-8 BOM.
- Requires `Customer_ID`, `Name`, `Email`, and `City` headers (case-insensitive; surrounding header whitespace is ignored).
- Trims surrounding whitespace from every cell and lowercases email addresses.
- Reports missing required fields, basic email syntax failures, and repeated non-empty customer IDs.
- Retains records with quality issues and writes their reasons in `Data_Quality_Issues`.
- Preserves additional columns and their order after the four standard columns.
- Rejects duplicate normalized headers and malformed records with too few or too many fields.
- Uses spreadsheet-safe CSV output by default and supports an explicit raw-value mode.
- Writes to a temporary file and replaces the destination only after a complete successful run.

Duplicate-ID detection is not complete-record duplicate detection. Two otherwise identical records with different IDs are retained and are not reported as duplicates.

## Requirements and installation

- Python 3.10 or later.
- No third-party packages are required; there is nothing to install.

Download or clone this repository, then run commands from the project root (the directory containing `src/`, `data/`, and this README).

## Usage

Run the included sample using the default paths:

```bash
python src/csv_cleaner.py
```

Choose input and output paths:

```bash
python src/csv_cleaner.py --input data/custom.csv --output output/cleaned_custom.csv
```

The default spreadsheet-safe mode prefixes values beginning with `=`, `+`, `-`, or `@` with an apostrophe so spreadsheet applications import them as text. It also checks for a leading BOM or common zero-width characters before those formula markers. To preserve source values exactly, use:

```bash
python src/csv_cleaner.py --input data/custom.csv --output output/raw.csv --raw-values
```

Raw-value mode can expose spreadsheet users to formula injection if untrusted values are opened as a spreadsheet. Use it only when exact value preservation is required and the recipient will handle the file safely.

The default input and output paths are `data/custom.csv` and `output/cleaned_custom.csv`, resolved relative to the project directory. An explicit relative path is resolved from the current working directory. The program refuses input/output path collisions. A successful run replaces an existing output file. A failed run leaves an existing output untouched.

## Input format and behavior

The input must have one header row and the four required columns. Column order and header capitalization do not matter. Other columns are carried through after the standard columns. All values, including extra-column values, have leading and trailing whitespace stripped; email values are lowercased. Other fields are not otherwise reformatted.

Every data record must have exactly as many fields as the header. A short or extra-width record aborts the run with a line-specific error; the program does not write a partial replacement. Blank rows are malformed records. Quoted commas, quotes, and embedded newlines are supported through Python's CSV parser.

Email checking is a basic syntax heuristic. It does not implement the complete email standard and does not verify that a mailbox exists. Empty emails are reported as missing rather than also marked invalid. Repeated non-empty customer IDs are compared after trimming, case-sensitively; blank IDs are not duplicate keys. Invalid and incomplete records remain in the output.

## Output

The output contains these columns, in order:

1. `Customer_ID`
2. `Name`
3. `Email`
4. `City`
5. Any additional input columns, in their input order
6. `Data_Quality_Issues`

The generated `Data_Quality_Issues` header is reserved and cannot also appear in the input. Rows with no detected issue contain `No issues`; otherwise the column lists all detected reasons separated by semicolons. Spreadsheet-safe mode changes formula-leading values in every exported field, including additional columns. The raw-value mode disables this transformation.

On success, the program prints record counts and the output path, then exits with status `0`. Input, CSV-structure, encoding, and file-access errors are printed to stderr and return a non-zero status. The destination is replaced only after all rows have been read and written successfully.

## Tests

Run the standard-library test suite from the project root:

```bash
python -m unittest discover -s tests -v
```

The tests use temporary directories and fictional data. They cover input validation, CSV edge cases, output safety, formula handling, and command-line behavior.

## Project structure

```text
CSV-Data-Cleaner/
├── data/
│   └── custom.csv              # Fictional example input
├── src/
│   └── csv_cleaner.py          # CLI and cleaning logic
├── tests/
│   └── test_csv_cleaner.py     # Automated tests
├── .gitignore
└── README.md
```

The generated `output/` directory is created when needed and is Git-ignored; it is not part of a fresh checkout.

## Sample run

The included sample has 9 data rows. Expected counts are 9 total records, 2 with missing required values, 1 invalid email, 0 repeated customer IDs, and 6 rows without issues. Although two records share the same name/email/city values, their customer IDs differ, so they are not duplicate IDs.

## Limitations

- Intended for small and medium files that fit ordinary local disk and runtime constraints; processing is row-oriented, but no performance benchmark is provided.
- Delimiter is comma; delimiter auto-detection is not provided.
- Formula neutralization is designed for common spreadsheet formula prefixes and leading invisible characters, not every spreadsheet application's import behavior. Use raw mode only when appropriate.
- No mailbox verification, complete record deduplication, schema inference, or automatic correction of invalid data is performed.
- Output files are plain text; users remain responsible for appropriate storage and handling of customer data.

## Sample data and license

`data/custom.csv` contains fictional sample records intended only for demonstration and testing; it is not intended to contain real personal information. No license file is included in this snapshot, so reuse and redistribution rights are not specified here.
