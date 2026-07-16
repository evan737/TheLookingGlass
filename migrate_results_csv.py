import csv
from pathlib import Path

RESULTS_LOG = Path("paper_trade_results.csv")
BACKUP_LOG = Path("paper_trade_results_backup.csv")

NEW_FIELDNAMES = ["ticker", "decision", "entry_price", "result", "won", "profit", "fee", "settled_at"]

# The file has evolved through 3 different row shapes over the course of
# today as columns got added -- map each shape explicitly by how many
# fields the row actually has, rather than trusting the (outdated) header.
SIX_COL = ["ticker", "decision", "entry_price", "result", "won", "profit"]
SEVEN_COL = ["ticker", "decision", "entry_price", "result", "won", "profit", "settled_at"]
EIGHT_COL = ["ticker", "decision", "entry_price", "result", "won", "profit", "fee", "settled_at"]

if not RESULTS_LOG.exists():
    print("No paper_trade_results.csv found -- nothing to migrate.")
else:
    RESULTS_LOG.rename(BACKUP_LOG)
    print(f"Backed up original to {BACKUP_LOG}")

    rows = []
    skipped = 0
    with BACKUP_LOG.open("r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)  # skip the old header -- we're re-deriving field mapping per row

        for raw_row in reader:
            n = len(raw_row)
            if n == 6:
                row = dict(zip(SIX_COL, raw_row))
            elif n == 7:
                row = dict(zip(SEVEN_COL, raw_row))
            elif n == 8:
                row = dict(zip(EIGHT_COL, raw_row))
            else:
                print(f"  Skipping unrecognized row shape ({n} fields): {raw_row}")
                skipped += 1
                continue

            row.setdefault("fee", "0.0")
            row.setdefault("settled_at", "")
            rows.append(row)

    with RESULTS_LOG.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=NEW_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in NEW_FIELDNAMES})

    print(f"Migrated {len(rows)} rows to the new 8-column schema ({skipped} skipped).")
    print("Rows that predate fee tracking have fee=0.0 (genuinely unknown, not fabricated).")