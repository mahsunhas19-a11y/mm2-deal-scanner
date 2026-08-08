import random
import re

from playwright.sync_api import sync_playwright

from scanner.browser import launch_chromium


EXCLUDED_ENTRIES = {
    ("Black Luger", 1000000),
    ("Batwing", 1000000),
    ("Laser", 8),
}


def scan_page(page, category):
    print(f"Lade {category}...")
    cards = page.locator("div.itemcolumn")
    cards.first.wait_for(timeout=15000)
    page.wait_for_timeout(500)
    print(f"{category}: {cards.count()} Karten")

    weapons = []
    for i in range(cards.count()):
        card = cards.nth(i)
        try:
            lines = [x.strip() for x in card.inner_text().split("\n") if x.strip()]
            if len(lines) < 2:
                continue
            name = lines[0]
            value = None
            for line in lines:
                if line.startswith("Value"):
                    match = re.search(r"([\d,]+)", line)
                    if match:
                        value = int(match.group(1).replace(",", ""))
                    break
            if value is None or (name, value) in EXCLUDED_ENTRIES:
                continue
            weapons.append((name, value))
        except Exception:
            continue
    return weapons


def scan_supreme(show_items=False):
    with sync_playwright() as p:
        browser = launch_chromium(p)
        try:
            categories = [
                ("Godlies", "https://supremevalues.com/mm2/godlies"),
                ("Chromas", "https://supremevalues.com/mm2/chromas"),
                ("Vintages", "https://supremevalues.com/mm2/vintages"),
                ("Ancients", "https://supremevalues.com/mm2/ancients"),
            ]
            pages = []
            print("Öffne Supreme Values...\n")

            for category, url in categories:
                page = browser.new_page()
                pages.append((category, page))
                print(f"Öffne {category}...")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                wait = random.randint(1500, 3000)
                print(f"Warte {wait} ms...\n")
                page.wait_for_timeout(wait)

            combined = []
            for category, page in pages:
                combined.extend(scan_page(page, category))

            # Doppelte identische Einträge entfernen; unterschiedliche Values bleiben sichtbar.
            weapons = sorted(set(combined), key=lambda item: (item[0].lower(), item[1]))

            if show_items:
                print()
                print("=" * 60)
                print("SUPREME VALUES")
                print("=" * 60)
                print()
                for name, value in weapons:
                    print(f"{name:<35} | {value}")
                print()
            print(f"Supreme Values insgesamt: {len(weapons)}")
            return weapons
        finally:
            browser.close()
