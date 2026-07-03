import sqlite3
import pandas as pd
import glob
import json
import hashlib

DB_PATH = "data/ReportedCases_web3isgoinggreat.db"


def create_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ReportedCases_web3isgoinggreat (
            report_id                   TEXT PRIMARY KEY,
            date_of_report              TEXT,
            report_title                TEXT NOT NULL,
            overall_theme_tags          TEXT,
            scam_category               TEXT,
            blockchain                  TEXT,
            blockchain_id               TEXT,
            technology_used             TEXT,
            report_description          TEXT,
            report_related_links        TEXT,
            report_related_image_link   TEXT,
            report_url                  TEXT,
            report_extraction_timestamp TEXT
        );
    """)

    # Read master.csv directly — already has 1241 clean rows
    df = pd.read_csv("data/master.csv")
    print(f"Reading master.csv: {len(df)} rows")

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        url = str(row.get("article_url", "")).strip()
        date = str(row.get("date", "")).strip()
        source = str(row.get("source_file", "")).strip()

        if not title:
            skipped += 1
            continue

        # Unique ID: title + url + source_file (handles cross-chain duplicates)
        unique_str = f"{title}|{url}|{source}"
        report_id = hashlib.md5(unique_str.encode()).hexdigest()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO ReportedCases_web3isgoinggreat (
                    report_id, date_of_report, report_title,
                    overall_theme_tags, scam_category,
                    blockchain, blockchain_id, technology_used,
                    report_description, report_related_links,
                    report_related_image_link, report_url,
                    report_extraction_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                date,
                title,
                str(row.get("theme_tags", "")),
                str(row.get("type_of_malicious_activity", "")),
                str(row.get("blockchain", "")),
                "[]",   # blockchain_id — will populate after schema update
                str(row.get("tech", "")),
                str(row.get("description", "")),
                str(row.get("links", "[]")),
                str(row.get("image_link", "")),
                url,
                str(row.get("extraction_timestamp", "")),
            ))
            inserted += 1
        except Exception as e:
            print(f"  Error: {e}")
            skipped += 1

    conn.commit()

    count = cursor.execute(
        "SELECT COUNT(*) FROM ReportedCases_web3isgoinggreat"
    ).fetchone()[0]

    print(f"✅ Database created: {DB_PATH}")
    print(
        f"   Inserted: {inserted} | Skipped: {skipped} | Total in DB: {count}")

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_date       ON ReportedCases_web3isgoinggreat(date_of_report);")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_blockchain ON ReportedCases_web3isgoinggreat(blockchain);")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scam       ON ReportedCases_web3isgoinggreat(scam_category);")
    conn.commit()
    conn.close()
    print("   Indexes created ✅")


if __name__ == "__main__":
    create_db()
