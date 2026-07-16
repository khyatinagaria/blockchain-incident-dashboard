# save as fix_blockchain_var.py in root folder
import glob

files = glob.glob('scrapers/*.py')
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content
    # Fix: rename blockchain_tag to blockchain in the unpacking line
    content = content.replace(
        'theme_tags, blockchain, tech = parse_footer_tags(footer)',
        'theme_tags, blockchain, tech = parse_footer_tags(footer)'
    )
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed: {filepath}')
    else:
        print(f'No change: {filepath}')
