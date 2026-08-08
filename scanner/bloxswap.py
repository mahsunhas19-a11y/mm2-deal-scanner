from playwright.sync_api import sync_playwright
import re

from scanner.browser import launch_chromium


def parse_value(value):

    value = value.upper().replace(",", "").strip()

    if value.endswith("K"):
        return int(float(value[:-1]) * 1000)

    if value.endswith("M"):
        return int(float(value[:-1]) * 1000000)

    return int(float(value))


def scan_bloxswap():

    with sync_playwright() as p:

        browser = launch_chromium(p)

        page = browser.new_page(
            viewport={"width": 1500, "height": 1000}
        )

        page.goto(
            "https://bloxswaps.com/trade-mm2",
            wait_until="networkidle"
        )

        page.wait_for_timeout(5000)

        print("BloxSwap geöffnet.\n")

        print("Lade Items...\n")

        # komplette Itemliste
        cards = page.locator(
            "button.h-full.w-full.text-start.relative.overflow-hidden.cursor-pointer"
        )

        cards.first.wait_for(timeout=10000)

        print(f"Gefundene Items: {cards.count()}\n")

        weapons = []

        for i in range(cards.count()):

            card = cards.nth(i)

            try:

                # Bereiche "Your Offer" / "Your Receive" ignorieren
                if card.locator("text=Your Offer").count():
                    continue

                if card.locator("text=Your Receive").count():
                    continue

                name = card.locator(
                    "p.text-\\[11px\\].font-semibold.text-white\\/90"
                ).first.inner_text().strip()

                value_text = card.locator(
                    "span.text-\\[11px\\].font-medium.text-white\\/70"
                ).first.inner_text().strip()

                value = parse_value(value_text)

                weapons.append((name, value))

            except Exception:
                continue

        print("=" * 60)
        print("BLOXSWAP VALUES")
        print("=" * 60)
        print()

        for name, value in weapons:
            print(f"{name:<35} | {value}")

        print()
        print(f"Insgesamt gefunden: {len(weapons)}")

        browser.close()

        return weapons
