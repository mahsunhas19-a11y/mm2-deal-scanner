import csv
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


ALERT_EUR_PER_100 = 1.50
TOP_DEALS_COUNT = 25
REPORT_PATH = Path("scan_results/top_300_deals.csv")
SHOP_LABELS = {
    "Luger": "luger.gg",
    "MM2Store": "mm2store.com",
    "BuyBlox": "buyblox.gg",
    "Bloxxer": "bloxxer.gg",
    "LOLGA": "lolga.com",
    "StarPets": "starpets.gg",
}


def read_deals(path=REPORT_PATH):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: float(row["eur_per_100_from_usd"]))
    return rows


def build_payload(deals, status, run_url):
    if status != "success":
        return {
            "username": "MM2 Deal Scanner",
            "content": (
                "❌ **MM2-Scan fehlgeschlagen**\n"
                "Es werden keine möglicherweise alten Deal-Daten gemeldet.\n"
                f"[Fehler in GitHub öffnen]({run_url})"
            ),
            "allowed_mentions": {"parse": []},
        }

    alerts = [
        row for row in deals
        if float(row["eur_per_100_from_usd"]) < ALERT_EUR_PER_100
    ]
    if alerts:
        title = "🚨 MM2 DEAL-ALARM"
        description = (
            f"**{len(alerts)} Deal(s) unter €{ALERT_EUR_PER_100:.2f}/100 Value gefunden!**"
        )
        color = 0xED4245
    else:
        title = "✅ MM2-Scan abgeschlossen"
        description = f"Kein Deal unter €{ALERT_EUR_PER_100:.2f}/100 Value."
        color = 0x57F287

    fields = []
    for position, row in enumerate(deals[:TOP_DEALS_COUNT], 1):
        eur_ratio = float(row["eur_per_100_from_usd"])
        usd_ratio = float(row["ratio_usd_per_100"])
        website = SHOP_LABELS.get(row["website"], row["website"])
        marker = "🚨 " if eur_ratio < ALERT_EUR_PER_100 else ""
        unit_price = row.get("price_usd", "")
        unit_text = f" • Stück: ${float(unit_price):.2f}" if unit_price else ""
        fields.append({
            "name": f"{position}. {marker}{row['name']}",
            "value": (
                f"**€{eur_ratio:.2f}/100** • ${usd_ratio:.2f}/100 • "
                f"{website}{unit_text}"
            ),
            "inline": False,
        })

    if len(alerts) > TOP_DEALS_COUNT:
        description += (
            f"\nDavon liegen {len(alerts) - TOP_DEALS_COUNT} weitere "
            "unter dem Alarmwert."
        )

    return {
        "username": "MM2 Deal Scanner",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": title,
            "description": description,
            "url": run_url,
            "color": color,
            "fields": fields,
            "footer": {
                "text": (
                    f"Top {min(TOP_DEALS_COUNT, len(deals))} • "
                    f"Alarmgrenze: unter €{ALERT_EUR_PER_100:.2f}/100 Value"
                )
            },
        }],
    }


def send_discord(webhook_url, payload):
    encoded_payload = json.dumps(payload).encode("utf-8")
    request = Request(
        webhook_url,
        data=encoded_payload,
        headers={"Content-Type": "application/json", "User-Agent": "MM2-Scanner/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        if response.status not in {200, 204}:
            raise RuntimeError(f"Discord webhook returned HTTP {response.status}")


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("Discord-Benachrichtigung übersprungen: Secret fehlt.")
        return

    status = os.environ.get("JOB_STATUS", "failure").strip().lower()
    run_url = os.environ.get("RUN_URL", "https://github.com").strip()
    deals = read_deals() if status == "success" and REPORT_PATH.exists() else []
    if status == "success" and not deals:
        status = "failure"
    send_discord(webhook_url, build_payload(deals, status, run_url))
    print("Discord-Benachrichtigung gesendet.")


if __name__ == "__main__":
    main()
