import csv
from pathlib import Path
from statistics import median


EXTREME_RATIO = 0.80
OUTLIER_FACTOR = 0.45


def price_to_float(price):
    if price is None:
        return None
    try:
        return float(price.replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def find_deals(items, max_price_per_100=None, min_price_per_100=0.0):
    """Return every valid shop price, ranked by dollars per 100 value."""
    deals = []
    for item in items.values():
        value = item["value"]
        if value is None or value <= 0:
            continue

        numeric_prices = {
            website: price_to_float(price)
            for website, price in item["prices"].items()
        }
        valid_prices = [price for price in numeric_prices.values() if price is not None]
        shop_median = median(valid_prices) if len(valid_prices) >= 2 else None

        for website, price_float in numeric_prices.items():
            if price_float is None:
                continue
            price_per_100 = (price_float / value) * 100
            if price_per_100 < min_price_per_100:
                continue
            if max_price_per_100 is not None and price_per_100 >= max_price_per_100:
                continue

            is_extreme = price_per_100 < EXTREME_RATIO
            is_outlier = bool(shop_median and price_float < shop_median * OUTLIER_FACTOR)
            deals.append({
                "ratio": price_per_100,
                "website": website,
                "name": item["name"],
                "price": price_float,
                "value": value,
                "median_price": shop_median,
                "needs_check": is_extreme,
                "flags": "EXTREM < $0.80/100" if is_extreme else "",
                "price_outlier_hint": is_outlier,
            })

    deals.sort(key=lambda row: (row["ratio"], row["price"], row["name"].lower()))
    return deals


def save_deals_report(deals, usd_to_eur_rate, fx_source, fx_timestamp,
                      path="scan_results/all_ranked_deals.csv"):
    output = Path(path)
    output.parent.mkdir(exist_ok=True)
    fields = ("rank", "ratio_usd_per_100", "website", "name", "price_usd",
              "value", "needs_check", "flags", "price_outlier_hint",
              "cross_shop_median_usd", "eur_per_100_from_usd", "usd_to_eur_rate",
              "fx_source", "fx_timestamp")
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, deal in enumerate(deals, 1):
            writer.writerow({
                "rank": rank,
                "ratio_usd_per_100": f"{deal['ratio']:.4f}",
                "website": deal["website"],
                "name": deal["name"],
                "price_usd": f"{deal['price']:.2f}",
                "value": deal["value"],
                "needs_check": deal["needs_check"],
                "flags": deal["flags"],
                "price_outlier_hint": deal["price_outlier_hint"],
                "cross_shop_median_usd": (
                    f"{deal['median_price']:.2f}" if deal["median_price"] is not None else ""
                ),
                "eur_per_100_from_usd": f"{deal['ratio'] * usd_to_eur_rate:.4f}",
                "usd_to_eur_rate": f"{usd_to_eur_rate:.8f}",
                "fx_source": fx_source,
                "fx_timestamp": fx_timestamp,
            })
