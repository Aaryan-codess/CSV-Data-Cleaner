
# CSV Data Cleaner

A Python-based CSV data cleaning and validation tool designed to process customer records, standardize data, identify data-quality issues, and generate a cleaned CSV file.

## Features

- Reads customer data from CSV files.
- Removes unnecessary leading and trailing spaces.
- Converts email addresses to lowercase.
- Detects missing values.
- Validates email address formats.
- Identifies duplicate customer IDs.
- Preserves incomplete and invalid records.
- Adds a `Data_Quality_Issues` column.
- Generates a cleaned CSV output file.
- Includes basic error handling.

## Technologies Used

- Python 3
- CSV module
- OS module
- Regular Expressions (`re`)

No external Python packages are required.

## Project Structure

```text
Project-01-CSV-Cleaner/
│
├── src/
│   └── csv_cleaner.py
│
├── data/
│   └── custom.csv
│
├── output/
│   └── cleaned_custom.csv
│
└── README.md
```

## Installation

1. Install Python 3.
2. Clone or download this repository.
3. Place your input CSV file inside the `data` folder.
4. Name the input file `custom.csv`.

## Usage

Run the following command from the Mission50k directory:

```bash
python Project-01-CSV-Cleaner/src/csv_cleaner.py
```

## Input CSV Format

The input CSV must contain these columns:

- Customer_ID
- Name
- Email
- City

Column names are matched without case sensitivity.

## Output

The program generates:

`output/cleaned_custom.csv`

The output contains standardized customer information and a `Data_Quality_Issues` column.

## Sample Processing Results

Test dataset: 9 customer records.

- Total records processed: 9
- Records without issues: 6
- Records with missing values: 2
- Invalid email addresses: 1
- Duplicate customer IDs: 0

## Limitations

- Email validation uses basic format checking, not mailbox verification.
- Duplicate detection is based on Customer_ID.
- The program currently processes one input CSV file per execution.

## Sample Data Disclaimer

The CSV file included in this repository contains fictional sample customer data created exclusively for testing and demonstration.

No real personal information is intentionally included.

## Project Status

Core implementation and initial output verification completed.

## Author

Mission 50K — Portfolio Project 01
