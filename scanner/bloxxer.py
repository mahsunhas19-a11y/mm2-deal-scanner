from playwright.sync_api import sync_playwright

from catalog_matching import match_catalog
from scanner.browser import launch_chromium
from scanner.common import card_is_unavailable, card_title, extract_card_price, first_product_url, save_match_audit


def load_all_lazy_products(page, cards, max_passes=80):
    """Traverse the page incrementally so every lazy-load sentinel is observed."""
    stable_passes = 0
    last_count = cards.count()
    last_height = page.evaluate("document.body.scrollHeight")
    position = 0

    for _ in range(max_passes):
        viewport = page.evaluate("window.innerHeight")
        height = page.evaluate("document.body.scrollHeight")
        position = min(position + max(int(viewport * 0.75), 600), height)
        page.evaluate("y => window.scrollTo(0, y)", position)
        page.wait_for_timeout(650)

        # At the bottom, move back across the final observer and enter it again.
        if position + viewport >= height - 100:
            page.mouse.wheel(0, -900)
            page.wait_for_timeout(350)
            page.mouse.wheel(0, 1400)
            page.wait_for_timeout(1400)

        current_count = cards.count()
        current_height = page.evaluate("document.body.scrollHeight")
        print(f"Geladene Produkte: {current_count}")
        if current_count > last_count or current_height > last_height:
            last_count, last_height = current_count, current_height
            stable_passes = 0
        elif position + viewport >= current_height - 100:
            stable_passes += 1

        if stable_passes >= 5:
            break
        if current_height > height:
            position = max(0, height - viewport)

    page.evaluate("window.scrollTo(0, 0)")
    return cards.count()


def scan_bloxxer(valid_names=None, show_items=False):
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            page.goto("https://bloxxer.gg/collections/mm2-godlys",
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            print("Bloxxer geöffnet.\n\nLade alle Produkte...\n")
            selector = "div.card.product-card.product-card--card"
            cards = page.locator(selector)
            total_cards = load_all_lazy_products(page, cards)
            print(f"Lazy Loading abgeschlossen: {total_cards} Produktkarten.\n")

            valid_set = set(valid_names) if valid_names is not None else None
            raw_items = []
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
                except Exception as error:
                    print(f"Fehler bei Karte {i + 1}: {error}")

            weapons, audit_rows = match_catalog("Bloxxer", raw_items, valid_set or {x["shop_title"] for x in raw_items})
            save_match_audit("bloxxer", audit_rows)
            if show_items:
                print("=" * 60 + "\nSHOP: BLOXXER\n" + "=" * 60 + "\n")
                for name, price in weapons:
                    print(f"{name:<35} | {price}")
                print()
            print(f"Bloxxer insgesamt: {len(weapons)}")
            return weapons
        finally:
            browser.close()
