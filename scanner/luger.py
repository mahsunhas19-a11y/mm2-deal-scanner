from playwright.sync_api import sync_playwright

from catalog_matching import match_catalog
from scanner.browser import launch_chromium
from scanner.common import card_is_unavailable, card_title, extract_card_price, first_product_url, save_match_audit


def scan_luger(valid_names=None, show_items=False):
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        try:
            page.goto(
                "https://luger.gg/collections/murder-mystery-2",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(3000)
            print("Luger geöffnet.")

            last_height = 0
            unchanged_rounds = 0
            while unchanged_rounds < 2:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    unchanged_rounds += 1
                else:
                    unchanged_rounds = 0
                    last_height = new_height

            print("Scrollen beendet.\n")
            cards = page.locator("#mcpFullGrid .mcp-grid-card")
            card_count = cards.count()
            print(f"Gefundene Produktkarten: {card_count}\n")

            valid_set = set(valid_names) if valid_names is not None else None
            raw_items = []

            for i in range(card_count):
                card = cards.nth(i)
                try:
                    original_name = card_title(card)
                    if not original_name:
                        continue
                    product_url = first_product_url(card)

                    unavailable = card_is_unavailable(card)
                    price = extract_card_price(card)
                    raw_items.append({"shop_title": original_name, "price": price or "UNKNOWN",
                                      "available": not unavailable,
                                      "product_url": product_url or ""})
                except Exception as error:
                    print(f"Fehler bei Karte {i + 1}: {error}")

            weapons, audit_rows = match_catalog("Luger", raw_items, valid_set or {x["shop_title"] for x in raw_items})
            save_match_audit("luger", audit_rows)

            if show_items:
                print("=" * 60)
                print("SHOP: LUGER")
                print("=" * 60)
                print()
                for name, price in weapons:
                    print(f"{name:<35} | {price}")
                print()
            print(f"Luger insgesamt: {len(weapons)}")
            return weapons
        finally:
            browser.close()
