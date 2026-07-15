# Save this as fix_scrapers.py in your project root and run it
import glob

files = glob.glob('scrapers/*.py')

fixes = [
    # main() dedup checks
    ("if not row[\"title\"]:", 'if not row["report_title"]:'),
    ("if row[\"title\"] in seen_titles:",
     'if row["report_title"] in seen_titles:'),
    ("seen_titles.add(row[\"title\"])",
     'seen_titles.add(row["report_title"])'),
    # print loop - double quotes version
    ("r['date_of_report']}  {r['report_title']", "r['date_of_report']}  {r['report_title']"),
    ("r['overall_theme_tags']}", "r['overall_theme_tags']}"),
    ("r['report_related_image_link']}", "r['report_related_image_link']}"),
    ("r['report_related_links'][:100]}", "r['report_related_links'][:100]}"),
    # double quote versions
    ('r["date_of_report"]}  {r["report_title"]', 'r["date_of_report"]}  {r["report_title"]'),
    ('r["overall_theme_tags"]}', 'r["overall_theme_tags"]}'),
    ('r["report_related_image_link"]}', 'r["report_related_image_link"]}'),
    ('r["report_related_links"][:100]}', 'r["report_related_links"][:100]}'),
]

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content
    for old, new in fixes:
        content = content.replace(old, new)
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed: {filepath}')
    else:
        print(f'No change: {filepath}')
