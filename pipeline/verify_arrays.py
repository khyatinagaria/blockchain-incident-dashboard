import sqlite3
import json
conn = sqlite3.connect('data/ReportedCases_web3isgoinggreat.db')

# Check arrays look correct
rows = conn.execute('''
    SELECT overall_theme_tags, blockchain, technology_used 
    FROM ReportedCases_web3isgoinggreat 
    WHERE overall_theme_tags LIKE "%,%"
    LIMIT 5
''').fetchall()
for r in rows:
    print('tags:', r[0])
    print('chain:', r[1])
    print('tech:', r[2])
    print()

# Test querying by tag
bug_rows = conn.execute('''
    SELECT COUNT(*) FROM ReportedCases_web3isgoinggreat
    WHERE overall_theme_tags LIKE "%Bug%"
''').fetchone()[0]
print(f'Rows with Bug tag: {bug_rows}')

# Check donation addresses
rows = conn.execute(
    "SELECT COUNT(*) FROM ExtractedAddresses WHERE metadata LIKE '%donation%'").fetchall()
print('Donation addresses in DB:', rows[0][0])

# Check total
total = conn.execute("SELECT COUNT(*) FROM ExtractedAddresses").fetchone()[0]
print('Total addresses in DB:', total)

# Check what source_urls exist in ExtractedAddresses
print("\n=== Source URLs in ExtractedAddresses ===")
rows = conn.execute("""
    SELECT DISTINCT source_url, COUNT(*) as count 
    FROM ExtractedAddresses 
    WHERE source_url IS NOT NULL
    GROUP BY source_url
""").fetchall()
for r in rows:
    print(f"  {r[1]} addresses from: {r[0]}")
