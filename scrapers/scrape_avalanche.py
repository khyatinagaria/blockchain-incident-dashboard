"""
scrape_avalanche_web3.py  (FIXED)
Fetches ALL Avalanche entries from web3isgoinggreat.com using Playwright.

Fixes:
  - theme_tags: clean comma-separated tag names only (e.g. "Hack or scam, Bug")
  - links: JSON array of URLs only, no labels/text
  - image_link: new column — URL of entry image if present
  - Empty row fixes: fuller description parsing, better link extraction
  - Scroll logic: Added wiggle and higher stale tolerance to fetch entire timeline
"""

import csv
import re
import json
import asyncio
from datetime import datetime
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

BASE = "https://www.web3isgoinggreat.com"
URL = f"{BASE}/?blockchain=avalanche"

CATEGORY_PATTERNS = [
    (r"\bflash loan\b",
     "Flash Loan Attack"),
    (r"manipulat\w* (?:the )?(?:price )?oracle|oracle manipulat\w*",
     "Oracle Manipulation"),
    (r"governance attack|malicious proposal|achieve quorum",
     "Governance Attack"),
    (r"insider trading|front[- ]running",
     "Insider Trading"),
    (r"\bponzi\b|exit scam",
     "Exit Scam / Ponzi"),
    (r"dns hijack|domain registrar",
     "DNS Hijacking"),
    (r"address poisoning",
     "Address Poisoning"),
    (r"supply chain|malicious (?:browser extension|npm package)",
     "Supply Chain Attack"),
    (r"social engineering|impersonat\w+ (?:a |an )?(?:customer support)",
     "Social Engineering"),
    (r"phishing|seed phrase.{0,50}(?:enter|reveal|gave)|fake .{0,60}(?:wallet )?app", "Phishing"),
    (r"private key.{0,50}(?:compromis|stol|leak)|compromised.{0,30}(?:laptop|device)",
     "Private Key/Wallet Compromise"),
    (r"\brug[- ]?pull\b",
     "Rug Pull"),
    (r"\bbridge\b.{0,80}(?:exploit|hack|drain|steal)|(?:exploit|hack).{0,80}\bbridge\b", "Bridge Exploit"),
    (r"smart contract.{0,80}(?:bug|exploit|vulnerab|flaw)|exploit\w* a bug|flaw in.{0,50}(?:code|contract|protocol)",
     "Smart Contract Exploit"),
]


def classify_attack_type(title, description, theme_tags):
    text = f"{title} {description}".lower()
    if "rug pull" in theme_tags.lower():
        return "Rug Pull"
    for pattern, label in CATEGORY_PATTERNS:
        if re.search(pattern, text):
            return label
    if "hack or scam" in theme_tags.lower():
        return "Unclear from text — review manually"
    return ""


def parse_date(text):
    try:
        return datetime.strptime(text.strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def clean_theme_tags(footer):
    """Extract only the tag values from div.tag-list.theme e.g. 'Hack or scam, Bug'."""
    if not footer:
        return ""

    theme_list = footer.select_one("div.tag-list.theme")
    if not theme_list:
        return ""

    LABEL = re.compile(r"^(theme|blockchain|tech)\s*tags?\s*:?\s*", re.I)
    ONLY_LABEL = re.compile(r"^(theme|blockchain|tech)\s*tags?\s*:?$", re.I)

    # Try child elements — skip pure label nodes, strip label prefix from values
    children = theme_list.find_all(True, recursive=False)
    if children:
        seen = set()
        tags = []
        for el in children:
            t = el.get_text(strip=True)
            if not t or ONLY_LABEL.match(t):
                continue
            t = LABEL.sub("", t).strip()
            if t and t not in seen:
                seen.add(t)
                tags.append(t)
        if tags:
            return ", ".join(tags)

    # Fallback: text directly inside the div
    raw = theme_list.get_text(strip=True)
    raw = LABEL.sub("", raw).strip()
    raw = re.split(r"Blockchain\s*tags?:", raw,
                   flags=re.I)[0].strip().strip(",")
    return raw


def parse_footer_tags(footer):
    """Returns (theme_tags_clean, blockchain, tech)"""
    if not footer:
        return "", "", ""

    blockchain = ""
    tech = ""

    bc_els = footer.select('[class*="blockchain"]')
    if bc_els:
        blockchain = ", ".join(el.get_text(strip=True) for el in bc_els)

    tech_els = footer.select('[class*="tech"]')
    if tech_els:
        tech = ", ".join(el.get_text(strip=True) for el in tech_els)

    footer_text = footer.get_text(" ", strip=True)
    if not blockchain:
        m = re.search(
            r"Blockchain\s*(?:tags?)?\s*[:\|]?\s*([A-Za-z, ]+?)(?=\s*(?:Tech|DeFi|NFT|#|\||$))",
            footer_text, re.I)
        if m:
            blockchain = m.group(1).strip().strip(",")
    if not tech:
        m = re.search(
            r"(?:[\|]|Tech\s*(?:tags?)?\s*:)\s*([A-Za-z, ]+)$", footer_text, re.I)
        if m:
            tech = m.group(1).strip().strip(",")

    theme_tags = clean_theme_tags(footer)
    return theme_tags, blockchain, tech


def extract_links(entry_div):
    """Return a JSON array string of unique absolute URLs only (no labels).
    Excludes: internal anchors, ?id= permalinks, /attribution, /archive paths,
    and footer tag/attribution links."""
    footer_el = entry_div.select_one("div.entry-footer")
    seen = set()
    urls = []

    for a in entry_div.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or "?id=" in href:
            continue
        # Skip internal-only paths that are not real external links
        if href in ("/attribution",) or href.startswith("/archive"):
            continue
        # Skip footer elements (tag links)
        if footer_el and footer_el in a.parents:
            continue
        # Make relative URLs absolute
        if href.startswith("/"):
            href = BASE + href
        if href in seen:
            continue
        # Only keep http(s) URLs
        if not href.startswith("http"):
            continue
        seen.add(href)
        urls.append(href)

    return json.dumps(urls)


def extract_image_link(entry_div):
    """Return the src URL of the entry image (logo/illustration) if present."""
    # The image is inside div.captioned-image
    img_container = entry_div.select_one("div.captioned-image img")
    if img_container:
        src = img_container.get("src", "").strip()
        if src:
            if src.startswith("//"):
                src = "https:" + src
            return src
    return ""


def parse_entry(entry_div):
    wrapper = entry_div.select_one("div.entry-wrapper")
    if not wrapper:
        return None

    # Date
    ts_div = wrapper.select_one("div.timestamp-and-link-icons")
    date_text = ts_div.get_text(" ", strip=True) if ts_div else ""
    date_match = re.search(r"[A-Za-z]+ \d{1,2}, \d{4}", date_text)
    date_obj = parse_date(date_match.group(0)) if date_match else None

    # article_url — permalink directly from the Permalink button's data-url attribute
    article_url = ""
    permalink_btn = entry_div.select_one('button[title="Permalink"][data-url]')
    if permalink_btn:
        article_url = permalink_btn.get("data-url", "").strip()

    # source_url — original extraction logic (merged into links, NOT article_url)
    slug = ""
    for a in entry_div.find_all("a", href=True):
        href = a.get("href", "")
        id_match = re.search(r"\?id=([^&]+)", href)
        if id_match:
            slug = id_match.group(1)
            break
    if not slug:
        for a in entry_div.find_all("a", href=True):
            frag = urlparse(a.get("href", "")).fragment
            if frag:
                slug = frag
                break
    source_url = f"{BASE}/?id={slug}" if slug else ""

    # Title
    h2 = wrapper.select_one("h2")
    title = h2.get_text(strip=True) if h2 else ""

    # Description — try multiple known wrapper selectors, then fall back to
    # any p/li inside the wrapper that aren't inside the footer
    BODY_SELECTORS = [
        "div.timeline-body-text-wrapper",
        "div.entry-body",
        "div.body-text",
        "div.entry-content",
        "div.content",
    ]
    body = None
    for sel in BODY_SELECTORS:
        body = wrapper.select_one(sel)
        if body:
            break

    description = ""
    if body:
        # Remove captioned-image divs (thumbnails) so their alt text doesn't bleed in
        body_copy = BeautifulSoup(str(body), "html.parser")
        for img_div in body_copy.select("div.captioned-image"):
            img_div.decompose()
        # get_text with separator preserves spacing between inline elements (links, spans)
        # but collapses everything into one continuous string — which matches the site's
        # prose layout where text flows across spans, anchors, and <p> tags.
        raw = body_copy.get_text(" ", strip=False)
        # Normalise whitespace: collapse runs of spaces/newlines into single spaces,
        # then restore paragraph breaks (double-newlines → blank line).
        # collapse horizontal whitespace
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)        # max one blank line
        # trailing spaces before newline
        raw = re.sub(r" \n", "\n", raw)
        description = raw.strip()
    else:
        # Fallback: grab all <p> in wrapper, skip footer/timestamp
        footer_el = entry_div.select_one("div.entry-footer")
        ts_el = wrapper.select_one("div.timestamp-and-link-icons")
        parts = []
        for el in wrapper.find_all("p"):
            if footer_el and footer_el in el.parents:
                continue
            if ts_el and ts_el in el.parents:
                continue
            t = el.get_text(" ", strip=True)
            if t:
                parts.append(t)
        description = "\n\n".join(parts)

    # Links — clean URL-only JSON array
    links_list = json.loads(extract_links(entry_div))

    # Merge source_url into links (if present and not already included)
    if source_url and source_url not in links_list:
        links_list.append(source_url)
    links = json.dumps(links_list)

    # Image link
    image_link = extract_image_link(entry_div)

    # Footer tags
    footer = entry_div.select_one("div.entry-footer")
    theme_tags, blockchain, tech = parse_footer_tags(footer)

    return {
        "date":                       date_obj.isoformat() if date_obj else "",
        "title":                      title,
        "theme_tags":                 theme_tags,
        "type_of_malicious_activity": classify_attack_type(title, description, theme_tags),
        "blockchain":                 blockchain,
        "tech":                       tech,
        "description":                description,
        "links":                      links,
        "image_link":                 image_link,
        "article_url":                article_url,
        "extraction_timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


async def get_all_html_async():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        print(f"Opening browser → {URL}")
        # Increased timeout to 90s to ensure initial payload has time to load
        await page.goto(URL, wait_until="networkidle", timeout=90000)

        prev_count = 0
        stale_rounds = 0
        while True:
            # Scroll to the bottom of the page
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            # Give more time for the network request to process
            await asyncio.sleep(3)

            current_count = await page.locator("div.timeline-entry").count()
            print(f"  Entries visible: {current_count}")

            if current_count == prev_count:
                # Scroll wiggle: scroll up slightly, then back down to force lazy-loaders
                await page.evaluate("window.scrollBy(0, -500)")
                await asyncio.sleep(1)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # Check count again after wiggle
                current_count = await page.locator("div.timeline-entry").count()

                if current_count == prev_count:
                    stale_rounds += 1
                    # Increased to 6 rounds (~30 seconds of retries) before declaring completion
                    if stale_rounds >= 6:
                        print("  All entries loaded.")
                        break
                else:
                    stale_rounds = 0
            else:
                stale_rounds = 0

            prev_count = current_count

        html = await page.content()
        await browser.close()
        return html


def get_all_html():
    try:
        loop = asyncio.get_running_loop()
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(get_all_html_async())
    except RuntimeError:
        return asyncio.run(get_all_html_async())


def main():
    html = get_all_html()

    soup = BeautifulSoup(html, "html.parser")
    entries = soup.select("div.timeline-entry")
    print(f"\nTotal entries in HTML: {len(entries)}")

    results = []
    seen_titles = set()

    for entry_div in entries:
        row = parse_entry(entry_div)
        if not row:
            continue
        if not row["title"]:
            continue
        if row["title"] in seen_titles:
            continue
        seen_titles.add(row["title"])
        results.append(row)

    print(f"Entries collected: {len(results)}")

    if not results:
        print("No entries collected.")
        return

    output_file = "avalanche.csv"
    fieldnames = [
        "date", "title", "theme_tags", "type_of_malicious_activity",
        "blockchain", "tech", "description", "links", "image_link",
        "article_url", "extraction_timestamp",
    ]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved → {output_file}  ({len(results)} rows)")
    print("\nEntries saved:")
    for r in results:
        print(f"  {r['date']}  {r['title'][:70]}")
        print(f"    theme_tags: {r['theme_tags']}")
        print(f"    image_link: {r['image_link']}")
        print(f"    links: {r['links'][:100]}")


main()
