# save as fix_output_path.py in root
import glob

files = glob.glob('scrapers/*.py')
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content
    # Fix output file path to save into data/ folder
    import re
    content = re.sub(
        r'output_file = "(\w+)\.csv"',
        r'output_file = "data/\1.csv"',
        content
    )
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed: {filepath}')
    else:
        print(f'No change: {filepath}')
