"""
extract_addresses.py - Task 2 (Updated)
- Extracts crypto addresses from etherscan tx URLs and rekt.news articles
- Detects donation addresses from context
- Extracts tx hashes found within rekt.news articles
- Splits source_url vs txn_hashes properly
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

ETH_ADDR_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
ETH_TX_PATTERN = re.compile(r'\b0x[a-fA-F0-9]{64}\b')
ETHERSCAN_TX_URL = re.compile(
    r'https?://etherscan\.io/tx/(0x[a-fA-F0-9]{64})', re.I)

DONATION_KEYWORDS = re.compile(
    r'donat\w*|tip\s+us|support\s+us|buy\s+us\s+a|sponsor|contribute|fund\s+us',
    re.I
)

# Known site infrastructure addresses — appear on every page, not incident-related
KNOWN_NON_INCIDENT_ADDRESSES = {
    # rekt.news footer donation address
    "0x3c5c2f4bcec51a36494682f91dbc6ca7c63b514c",
}
# ── ETHERSCAN V2 API ─────────────────────────────────────


def get_tx_addresses(tx_hash):
    """Get from/to addresses for a tx hash via Etherscan V2 API."""
    try:
        url = (f"https://api.etherscan.io/v2/api"
               f"?chainid=1&module=proxy&action=eth_getTransactionByHash"
               f"&txhash={tx_hash}&apikey={ETHERSCAN_KEY}")
        r = requests.get(url, timeout=10).json()
        result = r.get("result", {})
        if not result:
            return []
        from_addr = result.get("from", "")
        to_addr = result.get("to", "")
        addresses = []
        if from_addr:
            addresses.append((from_addr, json.dumps(
                ["sender", "transaction"]), json.dumps([tx_hash])))
        if to_addr:
            meta = get_contract_label(to_addr)
            addresses.append((to_addr, meta, json.dumps([tx_hash])))
        time.sleep(0.25)
        return addresses
    except Exception as e:
        print(f"  TX lookup error: {e}")
        return []


def get_contract_label(address):
    """Check if address is a named contract on Etherscan V2."""
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


# ── CONTEXT-AWARE ADDRESS CLASSIFIER ────────────────────
def classify_address_from_context(address, surrounding_text):
    """
    Look at text around the address to determine metadata.
    Returns metadata JSON array.
    """
    # Get ~300 chars around address occurrence
    idx = surrounding_text.find(address)
    if idx == -1:
        return None
    context = surrounding_text[max(0, idx-300): idx+300].lower()

    if DONATION_KEYWORDS.search(context):
        return json.dumps(["donation", "rekt.news author address"])

    if re.search(r'attacker|hacker|exploit\w*|drain\w*|stole|stolen|malicious', context):
        return json.dumps(["malicious", "attacker address"])

    if re.search(r'victim|user|affected|lost\s+fund', context):
        return json.dumps(["victim", "affected address"])

    if re.search(r'contract|protocol|vault|pool|treasury', context):
        return json.dumps(["contract", "protocol address"])

    if re.search(r'exchange|binance|coinbase|kraken|huobi|okex', context):
        return json.dumps(["exchange", "centralized exchange"])

    return None  # fall through to API lookup


# ── REKT.NEWS SCRAPER ────────────────────────────────────
def scrape_rekt(url, scam_category):
    """
    Fetch rekt.news article.
    Returns list of (address, metadata, txn_hashes_json)
    Also extracts tx hashes found in article links.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (research; khyatinagaria098@gmail.com)"}
        r = requests.get(url, timeout=15, headers=headers)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        full_text = soup.get_text(" ", strip=True)

        # ── Extract tx hashes from etherscan links in article ──
        page_tx_hashes = list(set(ETHERSCAN_TX_URL.findall(r.text)))
        if page_tx_hashes:
            print(
                f"    Found {len(page_tx_hashes)} tx hashes in article links")

        # ── Extract ETH addresses ──
        addresses_found = list(set(ETH_ADDR_PATTERN.findall(full_text)))
        results = []

        for addr in addresses_found:
            # 1. Try context-based classification first
            if addr.lower() in KNOWN_NON_INCIDENT_ADDRESSES:
                print(
                    f"    ⏭ Skipping known non-incident address: {addr[:20]}...")
                continue
            metadata = classify_address_from_context(addr, full_text)

            # 2. If context didn't give us metadata, query Etherscan
            if metadata is None:
                metadata = get_contract_label(addr)
                # If still malicious default, keep scam_category
                if "malicious" in metadata and scam_category:
                    metadata = json.dumps(["malicious", str(scam_category)])

            is_malicious = 1 if "malicious" in metadata else 0

            # Attach any tx hashes found in the article to this address
            txn_hashes = json.dumps(page_tx_hashes) if page_tx_hashes else "[]"

            results.append((addr, metadata, txn_hashes, is_malicious))

        time.sleep(1)
        return results

    except Exception as e:
        print(f"  rekt scrape error: {e}")
        return []


# ── MAIN ─────────────────────────────────────────────────
def extract_addresses():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop and recreate table with new schema
    cursor.execute("DROP TABLE IF EXISTS ExtractedAddresses")
    cursor.execute("""
        CREATE TABLE ExtractedAddresses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id       TEXT REFERENCES ReportedCases_web3isgoinggreat(report_id),
            source_url      TEXT,
            crypto_address  TEXT,
            address_type    TEXT,
            metadata        TEXT,
            is_malicious    INTEGER DEFAULT 0,
            txn_hashes      TEXT DEFAULT '[]',
            UNIQUE(report_id, crypto_address)
        );
    """)
    conn.commit()
    print("ExtractedAddresses table recreated with txn_hashes column ✅")

    rows = cursor.execute("""
        SELECT report_id, report_related_links, scam_category
        FROM ReportedCases_web3isgoinggreat
    """).fetchall()
    print(f"Processing {len(rows)} rows\n")

    total = 0

    for i, (report_id, links_str, scam_category) in enumerate(rows):
        try:
            links = json.loads(links_str) if links_str else []
        except:
            links = []

        found_this_row = 0

        for url in links:
            domain = urlparse(url).netloc.lower()

            # ── Etherscan TX page → API lookup ──
            if "etherscan.io" in domain and "/tx/" in url:
                tx_hash = url.split("/tx/")[-1].split("?")[0]
                print(f"  [ETH-TX] {tx_hash[:20]}...")
                results = get_tx_addresses(tx_hash)

                for (addr, metadata, txn_hashes) in results:
                    is_malicious = 1 if "malicious" in metadata else 0
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO ExtractedAddresses
                            (report_id, source_url, crypto_address,
                             address_type, metadata, is_malicious, txn_hashes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (report_id, None, addr, "ETH",
                              metadata, is_malicious, txn_hashes))
                        total += 1
                        found_this_row += 1
                        print(
                            f"    ✅ {addr[:20]}... | {metadata} | txn: {txn_hashes[:40]}")
                    except Exception as e:
                        pass

            # ── rekt.news article → scrape + context classify ──
            elif "rekt.news" in domain:
                print(f"  [REKT] {url}")
                results = scrape_rekt(url, str(scam_category))

                for (addr, metadata, txn_hashes, is_malicious) in results:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO ExtractedAddresses
                            (report_id, source_url, crypto_address,
                             address_type, metadata, is_malicious, txn_hashes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (report_id, url, addr, "ETH",
                              metadata, is_malicious, txn_hashes))
                        total += 1
                        found_this_row += 1
                        print(
                            f"    ✅ {addr[:20]}... | {metadata} | txn: {txn_hashes[:40]}")
                    except:
                        pass

        if found_this_row:
            conn.commit()
            print(
                f"[{i+1}/{len(rows)}] {report_id[:12]}... → {found_this_row} addresses\n")

    final = cursor.execute(
        "SELECT COUNT(*) FROM ExtractedAddresses").fetchone()[0]
    print(f"\n✅ Done! Total addresses in DB: {final}")

    # Summary
    print("\nSample with txn_hashes:")
    for row in cursor.execute("""
        SELECT crypto_address, metadata, txn_hashes, source_url
        FROM ExtractedAddresses
        WHERE txn_hashes != '[]'
        LIMIT 5
    """).fetchall():
        print(
            f"  {row[0][:20]}... | {row[1]} | txns: {row[2][:60]} | src: {str(row[3])[:40]}")

    conn.close()


if __name__ == "__main__":
    extract_addresses()
