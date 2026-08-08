import os

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from catalog_matching import match_catalog
from scanner.browser import launch_chromium
from scanner.common import save_match_audit


LOLGA_URL = "https://www.lolga.com/murder-mystery-2-items"


def _enabled(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes", "on"}


def _launch_lolga_browser(playwright):
    """Use a normal browser for LOLGA when the cloud workflow provides Xvfb.

    LOLGA currently returns a Cloudflare 403 page to Chromium's native
    headless mode, while the same public page loads normally in a regular
    browser. Other shops remain headless.
    """
    if _enabled("MM2_LOLGA_HEADED"):
        return playwright.chromium.launch(
            headless=False,
            args=["--disable-dev-shm-usage"],
        )
    return launch_chromium(playwright)


def _blocked_by_cloudflare(page) -> bool:
    title = page.title().strip().lower()
    if "attention required" in title or "cloudflare" in title:
        return True
    body = page.locator("body")
    if not body.count():
        return False
    text = body.inner_text().lower()
    return "you have been blocked" in text or "cloudflare ray id" in text


def _wait_for_catalog(page, wait_timeout=45000) -> None:
    prices = page.locator("ul.product_list span.sell_price")
    try:
        # Attached is sufficient for extraction and avoids false timeouts when
        # a responsive layout briefly keeps the grid outside the viewport.
        prices.first.wait_for(state="attached", timeout=wait_timeout)
    except PlaywrightTimeoutError as error:
        if _blocked_by_cloudflare(page):
            raise RuntimeError(
                "LOLGA blockiert den Headless-Browser mit Cloudflare (HTTP 403)"
            ) from error
        raise RuntimeError("LOLGA-Produktkatalog wurde nicht geladen") from error


def _open_catalog(page) -> None:
    last_error = None
    for attempt in range(3):
        response = page.goto(LOLGA_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000 + attempt * 2000)
        try:
            _wait_for_catalog(page)
            return
        except RuntimeError as error:
            last_error = error
            if _blocked_by_cloudflare(page):
                break
            if attempt < 2:
                page.wait_for_timeout(2000)
    raise last_error or RuntimeError("LOLGA konnte nicht geöffnet werden")


def _prices_are_usd(page, wait_timeout=45000) -> bool:
    """Verify rendered card prices instead of trusting the currency switcher."""
    prices = page.locator("ul.product_list span.sell_price")
    prices.first.wait_for(state="attached", timeout=wait_timeout)
    for index in range(min(prices.count(), 5)):
        if "$" in prices.nth(index).locator("..").inner_text():
            return True
    return False


def _select_usd(page) -> None:
    """Force LOLGA to render USD so EUR/GBP is never mislabeled as dollars."""
    # Headless/cloud layouts can omit the visible switcher while already
    # rendering USD. The actual product prices are the authoritative check.
    if _prices_are_usd(page):
        return

    currency = page.locator("div[x-data='currency']:visible").first
    if not currency.count():
        raise RuntimeError("LOLGA is not in USD and no visible currency switcher exists")
    selected = currency.locator("span[x-text='switcher.selected']").first
    selected_text = selected.inner_text().strip().upper() if selected.count() else ""
    if selected_text != "USD":
        currency.locator("p").first.click()
        usd_option = currency.locator("li").filter(has_text="USD").first
        usd_option.wait_for(state="visible", timeout=10000)
        usd_option.click()
        page.wait_for_function(
            """() => [...document.querySelectorAll(
                "div[x-data='currency'] span[x-text='switcher.selected']"
            )].some(el => el.offsetParent !== null && el.textContent.trim() === 'USD')""",
            timeout=15000,
        )

    # A visible USD label alone is not enough: verify that the product prices
    # were re-rendered too before collecting the catalog.
    if not _prices_are_usd(page):
        raise RuntimeError("LOLGA currency switch did not update product prices to USD")


def _load_complete_catalog(page) -> int:
    """Scroll until LOLGA's lazy-loaded card count is stable."""
    cards = page.locator("ul.product_list > li[data-good-id]")
    previous_count = -1
    stable_rounds = 0
    for _ in range(60):
        count = cards.count()
        if count == previous_count:
            stable_rounds += 1
        else:
            previous_count = count
            stable_rounds = 0
        if stable_rounds >= 5:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
    return cards.count()


def _card_price_usd(card) -> str | None:
    price = card.locator("span.sell_price")
    if not price.count():
        return None
    price_box = price.first.locator("..")
    if "$" not in price_box.inner_text():
        return None
    try:
        value = float(price.first.inner_text().strip().replace(",", ""))
    except ValueError:
        return None
    return f"${value:.2f}"


def scan_lolga(valid_names=None, show_items=False):
    with sync_playwright() as playwright:
        browser = _launch_lolga_browser(playwright)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            _open_catalog(page)
            _select_usd(page)
            card_count = _load_complete_catalog(page)
            print(f"LOLGA geöffnet. Gefundene Produktkarten: {card_count}\n")

            cards = page.locator("ul.product_list > li[data-good-id]")
            raw_items = []
            for index in range(card_count):
                card = cards.nth(index)
                try:
                    title = card.locator("h3.product_name").first.inner_text().strip()
                    good_id = card.get_attribute("data-good-id") or str(index)
                    price = _card_price_usd(card)
                    unavailable = "notify me" in card.inner_text().lower() or price is None
                    raw_items.append({
                        "shop_title": title,
                        "price": price or "UNKNOWN",
                        "available": not unavailable,
                        "product_url": f"{LOLGA_URL}#good-{good_id}",
                    })
                except (PlaywrightTimeoutError, ValueError) as error:
                    print(f"Fehler bei LOLGA-Karte {index + 1}: {error}")

            valid_set = set(valid_names) if valid_names is not None else {
                item["shop_title"] for item in raw_items
            }
            weapons, audit_rows = match_catalog("LOLGA", raw_items, valid_set)
            save_match_audit("lolga", audit_rows)

            if show_items:
                print("=" * 60)
                print("SHOP: LOLGA")
                print("=" * 60)
                print()
                for name, price in weapons:
                    print(f"{name:<35} | {price}")
                print()
            print(f"LOLGA insgesamt: {len(weapons)}")
            return weapons
        finally:
            browser.close()
