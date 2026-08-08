from playwright.sync_api import sync_playwright

from catalog_matching import match_catalog
from currency import get_usd_to_eur_rate
from scanner.browser import launch_chromium
from scanner.common import save_match_audit


STARPETS_URL = "https://starpets.gg/de/mm2"
SUPREME_RARITIES = {"godly", "ancient", "vintage", "unique"}

CARD_DATA_SCRIPT = """elements => elements.map(link => {
    const card = link.querySelector("article[itemtype='https://schema.org/Product']");
    const properties = {};
    for (const property of card?.querySelectorAll("[itemprop='additionalProperty']") || []) {
        const name = property.querySelector("meta[itemprop='name']")?.content;
        const value = property.querySelector("meta[itemprop='value']")?.content;
        if (name) properties[name] = value;
    }
    return {
        product_url: link.getAttribute("href") || "",
        name: card?.querySelector("meta[itemprop='name']")?.content || "",
        price: card?.querySelector("[itemprop='price']")?.getAttribute("content") || null,
        currency: card?.querySelector("meta[itemprop='priceCurrency']")?.content || null,
        properties,
    };
})"""


def _snapshot_cards(page) -> list[dict]:
    links = page.locator("main a[href*='/mm2/shop/']")
    return links.evaluate_all(CARD_DATA_SCRIPT)


def _load_complete_catalog(page) -> list[dict]:
    """Capture every batch, including StarPets' post-720 replacement pages."""
    page.locator("main a[href*='/mm2/shop/']").first.wait_for(
        state="attached", timeout=30000
    )
    seen: dict[str, dict] = {}
    stagnant_clicks = 0

    for _ in range(30):
        # The hydrated page can briefly replace one batch with another. Taking
        # several quick snapshots prevents transient cards from being lost.
        for _ in range(3):
            for item in _snapshot_cards(page):
                if item.get("product_url"):
                    seen[item["product_url"]] = item
            page.wait_for_timeout(250)

        load_more = page.locator("button[class*='_loadMoreButton_']:visible")
        if not load_more.count():
            break

        before = len(seen)
        load_more.first.click(force=True)
        last_signature = None
        stable_rounds = 0
        for _ in range(20):
            page.wait_for_timeout(250)
            batch = _snapshot_cards(page)
            for item in batch:
                if item.get("product_url"):
                    seen[item["product_url"]] = item
            signature = tuple(item.get("product_url") for item in batch)
            if signature == last_signature:
                stable_rounds += 1
            else:
                stable_rounds = 0
                last_signature = signature
            if stable_rounds >= 2 and len(seen) > before:
                break

        if len(seen) == before:
            stagnant_clicks += 1
            if stagnant_clicks >= 2:
                break
        else:
            stagnant_clicks = 0

    return list(seen.values())


def _usd_price(amount, currency, usd_to_eur_rate) -> str | None:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    currency = (currency or "").upper()
    if currency == "USD":
        usd = value
    elif currency == "EUR" and usd_to_eur_rate > 0:
        usd = value / usd_to_eur_rate
    else:
        return None
    return f"${usd:.2f}"


def _prepare_catalog(rows, usd_to_eur_rate):
    candidates = []
    excluded = []
    for row in rows:
        properties = row.get("properties") or {}
        item_type = (properties.get("type") or "").lower()
        rarity = (properties.get("rare") or "").lower()
        chroma = (properties.get("chroma") or "").lower() == "chroma"
        name = (row.get("name") or "").strip()
        title = f"Chroma {name}" if chroma else name
        price = _usd_price(row.get("price"), row.get("currency"), usd_to_eur_rate)
        base = {
            "shop_title": title,
            "price": price or "UNKNOWN",
            "available": price is not None,
            "product_url": row.get("product_url") or "",
            "source_price": row.get("price") or "",
            "source_currency": row.get("currency") or "",
            "rarity": rarity,
            "year": properties.get("year") or "",
            "item_type": item_type,
            "chroma": "yes" if chroma else "no",
        }
        if item_type != "weapon" or rarity not in SUPREME_RARITIES:
            excluded.append({
                **base,
                "supreme_match": "",
                "confidence": "0.000",
                "status": "REJECTED",
                "reason": f"non-Supreme type/rarity: {item_type or '?'} / {rarity or '?'}",
            })
        else:
            candidates.append(base)
    return candidates, excluded


def scan_starpets(valid_names=None, usd_to_eur_rate=None, show_items=False):
    if usd_to_eur_rate is None:
        usd_to_eur_rate = get_usd_to_eur_rate()[0]

    with sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            page.goto(STARPETS_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            catalog = _load_complete_catalog(page)
            candidates, excluded = _prepare_catalog(catalog, usd_to_eur_rate)
            print(
                f"StarPets geöffnet. Katalogkarten: {len(catalog)}, "
                f"Supreme-Kandidaten: {len(candidates)}\n"
            )

            valid_set = set(valid_names) if valid_names is not None else {
                item["shop_title"] for item in candidates
            }
            weapons, audit_rows = match_catalog("StarPets", candidates, valid_set)
            all_audit_rows = audit_rows + excluded
            all_audit_rows.sort(
                key=lambda row: (row.get("status", ""), row.get("shop_title", "").lower())
            )
            save_match_audit("starpets", all_audit_rows)

            if show_items:
                print("=" * 60)
                print("SHOP: STARPETS")
                print("=" * 60)
                print()
                for name, price in weapons:
                    print(f"{name:<35} | {price}")
                print()
            print(f"StarPets insgesamt: {len(weapons)}")
            return weapons
        finally:
            browser.close()
