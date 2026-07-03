"""
extract_addresses.py - Task 2
Extracts crypto addresses from:
1. Etherscan transaction URLs (via API)
2. rekt.news articles (via scraping)
"""

import sqlite3
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

DB_PATH = "data/ReportedCases_web3isgoinggreat.db"
ETHERSCAN_KEY = "Z6N54WT7A2NBYPD9W6AMJ2BEH29DD2IWPT"
TEST_MODE = False
TEST_LIMIT = 100

ETH_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
TX_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{64}\b')

# ── ETHERSCAN: get tx details ────────────────────────────


def get_tx_addresses(tx_hash):
    try:
        url = (f"https://api.etherscan.io/v2/api"
               f"?chainid=1&module=proxy&action=eth_getTransactionByHash"
               f"&txhash={tx_hash}&apikey={ETHERSCAN_KEY}")
        r = requests.get(url, timeout=10).json()
        result = r.get("result", {})  # V2 returns result directly
        if not result:
            return []

        from_addr = result.get("from", "")
        to_addr = result.get("to", "")
        addresses = []
        if from_addr:
            addresses.append(
                (from_addr, "ETH", json.dumps(["sender", "transaction"])))
        if to_addr:
            meta = get_contract_label(to_addr)
            addresses.append((to_addr, "ETH", meta))

        time.sleep(0.25)
        return addresses
    except Exception as e:
        print(f"  TX lookup error: {e}")
        return []


def get_contract_label(address):
    try:
        url = (f"https://api.etherscan.io/v2/api"
               f"?chainid=1&module=contract&action=getsourcecode"
               f"&address={address}&apikey={ETHERSCAN_KEY}")
        r = requests.get(url, timeout=10).json()
        if r.get("status") == "1":
            name = r["result"][0].get("ContractName", "")
            if name:
                return json.dumps([name, "contract"])
        time.sleep(0.25)
        return json.dumps(["malicious", "involved in incident"])
    except:
        return json.dumps(["unknown"])

# ── REKT.NEWS: scrape and extract addresses ──────────────


def scrape_rekt(url, scam_category):
    """Fetch rekt.news article and extract ETH addresses."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (research; khyatinagaria098@gmail.com)"}
        r = requests.get(url, timeout=15, headers=headers)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        addresses = []
        for addr in set(ETH_PATTERN.findall(text)):
            # Skip if it looks like a tx hash (too long)
            if len(addr) != 42:
                continue
            meta = get_contract_label(addr)
            if "malicious" in meta:
                meta = json.dumps(["malicious", scam_category])
            addresses.append((addr, "ETH", meta))

        time.sleep(1)
        return addresses
    except Exception as e:
        print(f"  rekt scrape error: {e}")
        return []

# ── MAIN ────────────────────────────────────────────────


def extract_addresses():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ExtractedAddresses (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id      TEXT REFERENCES ReportedCases_web3isgoinggreat(report_id),
            source_url     TEXT,
            crypto_address TEXT,
            address_type   TEXT,
            metadata       TEXT,
            is_malicious   INTEGER DEFAULT 0,
            UNIQUE(report_id, crypto_address)
        );
    """)
    conn.commit()

    query = """SELECT report_id, report_related_links, scam_category
               FROM ReportedCases_web3isgoinggreat"""
    if TEST_MODE:
        query += f" LIMIT {TEST_LIMIT}"

    rows = cursor.execute(query).fetchall()
    print(f"Processing {len(rows)} rows | TEST_MODE={TEST_MODE}\n")

    total = 0

    for i, (report_id, links_str, scam_category) in enumerate(rows):
        try:
            links = json.loads(links_str) if links_str else []
        except:
            links = []

        found_this_row = 0

        for url in links:
            domain = urlparse(url).netloc.lower()
            results = []

            # ── Etherscan TX page ──
            if "etherscan.io" in domain and "/tx/" in url:
                tx_hash = url.split("/tx/")[-1].split("?")[0]
                print(f"  [ETH-TX] {tx_hash[:16]}...")
                results = get_tx_addresses(tx_hash)

            # ── rekt.news article ──
            elif "rekt.news" in domain:
                print(f"  [REKT] {url}")
                results = scrape_rekt(url, str(scam_category))

            for (addr, addr_type, metadata) in results:
                is_malicious = 1 if "malicious" in metadata else 0
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO ExtractedAddresses
                        (report_id, source_url, crypto_address,
                         address_type, metadata, is_malicious)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (report_id, url, addr, addr_type, metadata, is_malicious))
                    total += 1
                    found_this_row += 1
                    print(f"    ✅ {addr[:20]}... | {metadata}")
                except:
                    pass

        if found_this_row:
            conn.commit()
            print(
                f"[{i+1}/{len(rows)}] {report_id[:12]}... → {found_this_row} addresses\n")

    final = cursor.execute(
        "SELECT COUNT(*) FROM ExtractedAddresses").fetchone()[0]
    print(f"\n✅ Done! Total addresses in DB: {final}")
    conn.close()


if __name__ == "__main__":
    extract_addresses()
