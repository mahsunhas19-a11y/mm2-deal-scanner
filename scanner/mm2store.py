from playwright.sync_api import sync_playwright

from catalog_matching import match_catalog
from scanner.browser import launch_chromium
from scanner.common import card_is_unavailable, card_title, extract_card_price, first_product_url, save_match_audit


def scan_mm2store(valid_names=None, show_items=False):
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        try:
            valid_set = set(valid_names) if valid_names is not None else None
            raw_items = []

            sections = [
                ("Knives", "https://mm2store.com/collections/knives?page="),
                ("Guns", "https://mm2store.com/collections/gun?page="),
            ]

            for section_name, base_url in sections:
                print(f"Lade {section_name}...")
                seen_urls = set()
                for page_number in range(1, 51):
                    print(f"Öffne Seite {page_number}...")
                    page.goto(
                        f"{base_url}{page_number}",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    page.wait_for_timeout(3000)

                    cards = page.locator("product-card")
                    if cards.count() == 0:
                        cards = page.locator(".product-card")
                    if cards.count() == 0:
                        cards = page.locator(".grid__item")
                    print(f"{section_name} Seite {page_number}: {cards.count()} Karten")

                    page_urls = set()
                    for card_number in range(cards.count()):
                        url = first_product_url(cards.nth(card_number))
                        if url:
                            page_urls.add(url.split("?", 1)[0])
                    if not page_urls or page_urls.issubset(seen_urls):
                        print(f"{section_name}: keine neue Seite mehr nach Seite {page_number - 1}.")
                        break
                    seen_urls.update(page_urls)

                    for i in range(cards.count()):
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
                        except Exception:
                            continue

            weapons, audit_rows = match_catalog("MM2Store", raw_items, valid_set or {x["shop_title"] for x in raw_items})
            save_match_audit("mm2store", audit_rows)
            if show_items:
                print()
                print("=" * 60)
                print("SHOP: MM2STORE")
                print("=" * 60)
                print()
                for name, price in weapons:
                    print(f"{name:<35} | {price}")
                print()
            print(f"MM2Store insgesamt: {len(weapons)}")
            return weapons
        finally:
            browser.close()
