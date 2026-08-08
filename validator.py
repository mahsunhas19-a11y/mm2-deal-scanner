import csv
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


SHOP_FILES = {
    "Luger": "luger_all_items.csv",
    "MM2Store": "mm2store_all_items.csv",
    "BuyBlox": "buyblox_all_items.csv",
    "Bloxxer": "bloxxer_all_items.csv",
    "LOLGA": "lolga_all_items.csv",
    "StarPets": "starpets_all_items.csv",
}
SHOP_BASES = {
    "Luger": "https://luger.gg",
    "MM2Store": "https://mm2store.com",
    "BuyBlox": "https://buyblox.gg",
    "Bloxxer": "https://bloxxer.gg",
    "LOLGA": "https://www.lolga.com",
    "StarPets": "https://starpets.gg",
}


def _audit_index(directory="scan_results"):
    index = {}
    for shop, filename in SHOP_FILES.items():
        path = Path(directory) / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") == "MATCHED":
                    index[(shop, row.get("supreme_match"))] = row
    return index


def _shopify_json_url(product_url, base_url):
    absolute = urljoin(base_url, product_url)
    parsed = urlparse(absolute)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}.js"


def _available_price_usd(payload):
    variants = payload.get("variants") or []
    prices = [float(variant["price"]) / 100 for variant in variants
              if variant.get("available") and variant.get("price") is not None]
    if prices:
        return min(prices)
    if payload.get("available") and payload.get("price") is not None:
        return float(payload["price"]) / 100
    return None


def recheck_extreme_deals(deals, audit_directory="scan_results"):
    """Revalidate only <$0.80/100 rows through the product JSON endpoint."""
    if not deals:
        return []
    audit = _audit_index(audit_directory)
    checked = []
    with sync_playwright() as playwright:
        request = playwright.request.new_context(
            extra_http_headers={"Accept": "application/json", "User-Agent": "MM2-Scanner/1.0"}
        )
        try:
            for deal in deals:
                row = audit.get((deal["website"], deal["name"]))
                result = dict(deal)
                result["recheck_price"] = None
                result["product_url"] = row.get("product_url", "") if row else ""
                if not row or not result["product_url"]:
                    result["recheck_status"] = "KEIN PRODUKTLINK"
                    checked.append(result)
                    continue
                if deal["website"] in {"LOLGA", "StarPets"}:
                    result["recheck_status"] = f"{deal['website'].upper()}-LISTING; KEIN SHOPIFY-ENDPOINT"
                    checked.append(result)
                    continue
                try:
                    json_url = _shopify_json_url(result["product_url"], SHOP_BASES[deal["website"]])
                    response = request.get(json_url, timeout=30000)
                    if not response.ok:
                        result["recheck_status"] = f"HTTP {response.status}"
                    else:
                        price = _available_price_usd(response.json())
                        result["recheck_price"] = price
                        if price is None:
                            result["recheck_status"] = "AUSVERKAUFT/KEINE VARIANTE"
                        elif abs(price - deal["price"]) <= max(0.02, deal["price"] * 0.05):
                            result["recheck_status"] = "BESTÄTIGT"
                        else:
                            result["recheck_status"] = "PREIS WEICHT AB"
                except Exception as error:
                    result["recheck_status"] = f"PRÜFUNG FEHLER: {type(error).__name__}"
                checked.append(result)
        finally:
            request.dispose()
    return checked
