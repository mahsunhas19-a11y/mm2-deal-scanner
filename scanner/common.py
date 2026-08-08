import csv
import re
from pathlib import Path


MONEY_RE = re.compile(r"([0-9][0-9.,]*)")


def parse_money(text: str | None) -> float | None:
    if not text:
        return None
    match = MONEY_RE.search(text.replace("\u00a0", " "))
    if not match:
        return None
    number = match.group(1)
    if "," in number and "." in number:
        number = (number.replace(",", "") if number.rfind(".") > number.rfind(",")
                  else number.replace(".", "").replace(",", "."))
    elif "," in number:
        number = number.replace(",", ".") if len(number.rsplit(",", 1)[-1]) == 2 else number.replace(",", "")
    try:
        return float(number)
    except ValueError:
        return None


def usd_from_price_data(text: str | None, usd_cents: str | None = None,
                        price_cents: str | None = None,
                        original: str | None = None) -> float | None:
    """Return USD only; never relabel a visible EUR amount as dollars."""
    for cents in (usd_cents, price_cents):
        if cents:
            try:
                return float(cents) / 100
            except ValueError:
                pass
    if original:
        value = parse_money(original)
        if value is not None:
            return value
    normalized = (text or "").upper()
    if "$" in normalized or "USD" in normalized:
        return parse_money(text)
    # EUR without an embedded USD value is intentionally rejected. This is
    # safer than using a stale exchange rate or silently changing the symbol.
    return None


def _locator_usd_value(locator) -> float | None:
    node = locator.first
    nested_money = node.locator(".money")
    if nested_money.count():
        node = nested_money.first
    usd_cents = node.get_attribute("doubly-currency-usd")
    price_cents = node.get_attribute("data-price-cents")
    if not price_cents:
        price_cents = node.evaluate(
            "el => el.closest('[data-price-cents]')?.getAttribute('data-price-cents') || null"
        )
    original = node.get_attribute("bucks-original")
    return usd_from_price_data(node.inner_text().strip(), usd_cents, price_cents, original)


def extract_card_price(card) -> str | None:
    """Extract the payable unit price normalized to real USD."""
    for selector in (".mcp-card-price", ".price__sale .money", ".price-item--sale",
                     ".price__regular .money", ".price-item--regular", "sale-price .money",
                     "span.money"):
        locator = card.locator(selector)
        if locator.count():
            value = _locator_usd_value(locator)
            if value is not None:
                return f"${value:.2f}"
    return None


def card_is_unavailable(card) -> bool:
    text = card.inner_text().lower()
    return any(marker in text for marker in ("sold out", "out of stock", "ausverkauft"))


def first_product_url(card) -> str | None:
    links = card.locator('a[href*="/products/"]')
    return links.first.get_attribute("href") if links.count() else None


def card_title(card) -> str | None:
    for selector in (".mcp-card-title", ".product-card__title", "a.bold"):
        locator = card.locator(selector)
        if locator.count():
            title = locator.first.inner_text().strip()
            if title:
                return title
    return None


def save_match_audit(shop: str, rows: list[dict]) -> None:
    output = Path("scan_results")
    output.mkdir(exist_ok=True)
    path = output / f"{shop.lower()}_all_items.csv"
    fields = ("shop_title", "supreme_match", "confidence", "status", "reason",
              "available", "price", "source_price", "source_currency", "rarity",
              "year", "item_type", "chroma", "product_url")
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
