import sys
from concurrent.futures import ThreadPoolExecutor

from calculator import find_deals, save_deals_report
from currency import get_usd_to_eur_rate
from matcher import merge_data
from scanner.bloxxer import scan_bloxxer
from scanner.buyblox import scan_buyblox
from scanner.luger import scan_luger
from scanner.lolga import scan_lolga
from scanner.mm2store import scan_mm2store
from scanner.starpets import scan_starpets
from scanner.supreme import scan_supreme
from validator import recheck_extreme_deals


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SHOP_LABELS = {
    "Luger": "luger.gg", "MM2Store": "mm2store.com",
    "BuyBlox": "buyblox.gg", "Bloxxer": "bloxxer.gg", "LOLGA": "lolga.com",
    "StarPets": "starpets.gg",
}

TOP_DEALS_LIMIT = 300


def print_usd_ranking(rows, title, show_rank=False):
    print("\n" + "=" * 125)
    print(title)
    print("=" * 125)
    rank_header = "Rang  " if show_rank else ""
    print(f"{rank_header}{'$/100':<10}{'Website':<16}{'Name':<34}{'Preis/Stück':<15}{'Value':>9}  Status")
    print("-" * 125)
    for position, deal in enumerate(rows, 1):
        website = SHOP_LABELS.get(deal["website"], deal["website"])
        prefix = f"{position:<6}" if show_rank else ""
        status = "[CHECK] " + deal["flags"] if deal["needs_check"] else "OK"
        print(f"{prefix}${deal['ratio']:<9.2f}{website:<16}{deal['name']:<34}"
              f"${deal['price']:<14.2f}{deal['value']:>9}  {status}")


def print_extreme_recheck(rows):
    print("\n" + "=" * 135)
    print("ECHTE ZWEITPRÜFUNG: NUR TREFFER UNTER $0.80 PRO 100 VALUE")
    print("=" * 135)
    print(f"{'$/100':<10}{'Website':<16}{'Name':<32}{'Scanpreis':<13}{'Produktpreis':<15}{'Value':>8}  Prüfung")
    print("-" * 135)
    if not rows:
        print("Keine Treffer unter $0.80/100 vorhanden.")
        return
    for deal in rows:
        website = SHOP_LABELS.get(deal["website"], deal["website"])
        product_price = (f"${deal['recheck_price']:.2f}"
                         if deal.get("recheck_price") is not None else "-")
        print(f"${deal['ratio']:<9.2f}{website:<16}{deal['name']:<32}"
              f"${deal['price']:<12.2f}{product_price:<15}{deal['value']:>8}  {deal['recheck_status']}")


def print_outlier_hints(rows):
    print("\n" + "=" * 120)
    print("INFORMATION: STARKE CROSS-SHOP-PREISUNTERSCHIEDE (KEIN FEHLERNACHWEIS)")
    print("=" * 120)
    if not rows:
        print("Keine starken Cross-Shop-Preisunterschiede gefunden.")
        return
    print(f"{'$/100':<10}{'Website':<16}{'Name':<34}{'Preis':<12}{'Shop-Median':<14}")
    print("-" * 120)
    for deal in rows:
        website = SHOP_LABELS.get(deal["website"], deal["website"])
        print(f"${deal['ratio']:<9.2f}{website:<16}{deal['name']:<34}"
              f"${deal['price']:<11.2f}${deal['median_price']:<13.2f}")


def print_eur_ranking(rows, usd_to_eur_rate, title):
    print("\n" + "=" * 105)
    print(title)
    print("=" * 105)
    print(f"{'Rang':<6}{'€/100':<10}{'Website':<16}{'Name':<34}{'$/100 Basis':<13}{'Value':>8}")
    print("-" * 105)
    for position, deal in enumerate(rows, 1):
        website = SHOP_LABELS.get(deal["website"], deal["website"])
        eur_ratio = deal["ratio"] * usd_to_eur_rate
        print(f"{position:<6}€{eur_ratio:<9.2f}{website:<16}{deal['name']:<34}"
              f"${deal['ratio']:<12.2f}{deal['value']:>8}")


def main():
    print("\n" + "=" * 90)
    print("STARTE MM2 SCANNER")
    print("=" * 90 + "\n")

    supreme = scan_supreme()
    valid_names = {name for name, _ in supreme}
    usd_to_eur_rate, fx_source, fx_timestamp = get_usd_to_eur_rate()
    print("\nStarte alle sechs Shops parallel...\n")
    scanners = {"luger": scan_luger, "mm2store": scan_mm2store,
                "buyblox": scan_buyblox, "bloxxer": scan_bloxxer,
                "lolga": scan_lolga,
                "starpets": lambda names: scan_starpets(names, usd_to_eur_rate)}
    with ThreadPoolExecutor(max_workers=len(scanners)) as pool:
        futures = {name: pool.submit(scanner, valid_names) for name, scanner in scanners.items()}
        results, failures = {}, {}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as error:
                results[name] = []
                failures[name] = str(error)

    items = merge_data(results["luger"], results["mm2store"], results["buyblox"],
                       results["bloxxer"], supreme, lolga=results["lolga"],
                       starpets=results["starpets"])
    all_ranked_deals = find_deals(items)
    ranking = all_ranked_deals[:TOP_DEALS_LIMIT]
    extremes = [deal for deal in ranking if deal["needs_check"]]
    outlier_hints = [deal for deal in ranking if deal["price_outlier_hint"]]
    checked_extremes = recheck_extreme_deals(extremes)
    save_deals_report(
        ranking,
        usd_to_eur_rate,
        fx_source,
        fx_timestamp,
        path="scan_results/top_300_deals.csv",
    )

    print_extreme_recheck(checked_extremes)
    print_outlier_hints(outlier_hints)
    print_usd_ranking(ranking, "TOP 300 $/100-RANGLISTE – BESTE BIS SCHLECHTESTE", show_rank=True)
    print_eur_ranking(
        ranking,
        usd_to_eur_rate,
        "TOP 300 €/100-RANGLISTE – AUS DER $/100-RANGLISTE UMGERECHNET",
    )

    print(f"\nUmrechnung: 1 USD = {usd_to_eur_rate:.6f} EUR ({fx_source}, {fx_timestamp})")
    print("Die €/100-Werte entstehen ausschließlich aus: $/100 × USD→EUR-Kurs.")
    print(
        f"Gezeigt/gespeichert: {len(ranking)} beste von "
        f"{len(all_ranked_deals)} verfügbaren Shoppreisen"
    )
    print(f"Unter $0.80/100 erneut geprüft: {len(checked_extremes)}")
    result_labels = {"luger": "luger.gg", "mm2store": "mm2store.com",
                     "buyblox": "buyblox.gg", "bloxxer": "bloxxer.gg",
                     "lolga": "lolga.com", "starpets": "starpets.gg"}
    print("Erfasste Preise pro Shop: " + ", ".join(
        f"{result_labels[name]}={len(rows)}" for name, rows in results.items()
    ))
    if failures:
        print("[WARN] Fehlgeschlagene Shops: " + ", ".join(sorted(failures)))
        for name, error in failures.items():
            print(f"  {name}: {error}")
    print("CSV: scan_results/top_300_deals.csv")
    print("=" * 125)
    # A partial scan must be visible as a failed cloud job. The audit files are
    # still available as an artifact, but an incomplete Top-300 must not be
    # treated or announced as a successful fresh result.
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
