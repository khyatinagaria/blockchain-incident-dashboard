import glob

files = glob.glob('scrapers/*.py')
for f in files:
    with open(f, encoding='utf-8') as fp:
        content = fp.read()
    issues = []
    if "row['title']" in content or 'row["title"]' in content:
        issues.append('old title ref')
    if "row['date']" in content or 'row["date"]' in content:
        issues.append('old date ref')
    if "r['theme_tags']" in content or 'r["theme_tags"]' in content:
        issues.append('old theme_tags ref')
    if issues:
        print(f"ISSUES in {f}: {issues}")
    else:
        print(f"OK: {f}")
