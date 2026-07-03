# pipeline/fill_blockchain_ids.py
import sqlite3
import json

BLOCKCHAIN_IDS = {
    "Ethereum": 1, "Bitcoin": 0, "BNB Chain": 56,
    "Polygon": 137, "Avalanche": 43114, "Fantom": 250,
    "Arbitrum": 42161, "Optimism": 10, "Tron": 728126428,
    "Celo": 42220, "Cosmos": None, "Terra": None,
    "Cardano": None, "Monero": None, "Litecoin": None,
    "XRP Ledger": None, "Tezos": None, "Flow": None,
    "WAX": None, "Sui": None, "Hyperliquid": None,
}


def get_ids(blockchain_str):
    if not blockchain_str:
        return "[]"
    chains = [b.strip() for b in blockchain_str.split(",")]
    ids = [BLOCKCHAIN_IDS[c] for c in chains
           if c in BLOCKCHAIN_IDS and BLOCKCHAIN_IDS[c] is not None]
    return json.dumps(ids)


conn = sqlite3.connect("data/ReportedCases_web3isgoinggreat.db")
cursor = conn.cursor()
rows = cursor.execute(
    "SELECT report_id, blockchain FROM ReportedCases_web3isgoinggreat"
).fetchall()

for report_id, blockchain in rows:
    ids = get_ids(str(blockchain))
    cursor.execute(
        "UPDATE ReportedCases_web3isgoinggreat SET blockchain_id=? WHERE report_id=?",
        (ids, report_id)
    )

conn.commit()

# Verify
sample = cursor.execute(
    "SELECT blockchain, blockchain_id FROM ReportedCases_web3isgoinggreat WHERE blockchain_id != '[]' LIMIT 5"
).fetchall()
for row in sample:
    print(row)
conn.close()
print("blockchain_id column populated ✅")
