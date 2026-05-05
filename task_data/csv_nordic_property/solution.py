"""
Norwegian residential property transaction data processor.
Source: SSB 06726 - Omsetning av boligeiendommer med bygning i fritt salg, etter region og år
        (Residential property sales with building, by region and year)

File format: data.csv
  - Nordic CSV: semicolon (;) separated, all fields double-quoted, UTF-8 encoding
  - Line 1: descriptive title row — skip it
  - Line 2: column headers
  - Lines 3+: data rows (5 000 rows, 103 columns)
  - ".." means the value is not available; "0" means no transactions
  - Column layout: "region" + 3 columns per year (1992–2025):
      "YYYY Omsetninger (antall)"                          — transaction count
      "YYYY Samlet kjøpesum (1 000 kr)"                   — total purchase sum in 1 000 NOK
      "YYYY Gjennomsnittlig kjøpesum per omsetning (1 000 kr)" — avg price per transaction
"""
import csv
import sys
import statistics

DATA_FILE = "data.csv"


def load_data() -> tuple[list[str], list[dict]]:
    """Return (header, rows) parsed from the Nordic CSV file."""
    with open(DATA_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    # Line 0 is a descriptive title — skip it. Line 1 is the column header.
    header = [h.strip('"') for h in lines[1].strip().split(";")]
    rows = []
    for line in lines[2:]:
        vals = [v.strip('"') for v in line.strip().split(";")]
        if len(vals) == len(header):
            rows.append(dict(zip(header, vals)))
    return header, rows


def answer_questions(rows: list[dict]) -> list[str]:
    """
    Compute answers to 10 questions about the dataset.
    Return a list of exactly 10 strings, one answer per question, in order.

    Q1.  How many rows (regions) are in the dataset?

    Q2.  How many regions have a non-zero 2023 total purchase sum
         ("2023 Samlet kjøpesum (1 000 kr)")?
         (Treat "0" and ".." as no data.)

    Q3.  Name of the region with the highest 2023 total purchase sum?

    Q4.  Total national purchase sum across all regions in 2023
         (sum of "2023 Samlet kjøpesum (1 000 kr)" for all regions with data),
         expressed in 1 000 kr, as an integer.

    Q5.  Which year (1992–2023) had the highest total national transaction count?
         (Sum "YYYY Omsetninger (antall)" across all rows for each year, treating
         ".." and "0" as 0.  Return the 4-digit year as a string.)

    Q6.  How many region names contain the substring "(synt"?

    Q7.  How many regions had a 2023 total purchase sum strictly greater than
         1 000 000 (i.e. more than 1 billion NOK)?

    Q8.  How many regions had MORE transactions in 2023 than in 2010?
         (Only count regions that have non-zero data in BOTH years.)

    Q9.  Median 2023 total purchase sum among regions with 2023 data.
         Return as an integer (truncate if not whole).

    Q10. Name of the region with the highest absolute growth in total purchase sum
         from 2010 to 2023 (2023 value − 2010 value).
         Only consider regions with non-zero data in BOTH years.
    """
    raise NotImplementedError("answer_questions() is not yet implemented")


def transform(rows: list[dict]) -> None:
    """
    Select the bottom 25 % and top 25 % of regions by 2023 total purchase sum
    and write the result to output.csv in Nordic format.

    Selection (base: the 3 900 rows that have non-zero 2023 total purchase sum):
      • bottom 25 %:  the  975 rows with the SMALLEST 2023 total purchase sum
      • top    25 %:  the  975 rows with the LARGEST  2023 total purchase sum

    Output columns (7 columns):
      1. region
      2. 1992 Omsetninger (antall)
      3. 1992 Samlet kjøpesum (1 000 kr)
      4. 1992 Gjennomsnittlig kjøpesum per omsetning (1 000 kr)
      5. 2022 Omsetninger (antall)
      6. 2022 Samlet kjøpesum (1 000 kr)
      7. 2022 Gjennomsnittlig kjøpesum per omsetning (1 000 kr)

    Why 1992 and 2022?  Those are the years with the lowest and highest national
    total purchase sum (across 1992–2023), providing a historical contrast.

    Sort order: ascending by 2023 total purchase sum (smallest first).

    Output format: semicolon-separated, all fields double-quoted, UTF-8, with a
    header row.  Write to output.csv in the current directory.
    """
    raise NotImplementedError("transform() is not yet implemented")


if __name__ == "__main__":
    header, rows = load_data()
    answers = answer_questions(rows)
    with open("answers.txt", "w", encoding="utf-8") as f:
        for a in answers:
            f.write(str(a) + "\n")
    transform(rows)
    print("Done: answers.txt and output.csv written.")
