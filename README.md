# MM2 Deal Scanner

Der Scanner vergleicht Supreme Values mit Luger, MM2Store, BuyBlox,
Bloxxer, LOLGA und StarPets. GitHub Actions startet den vollständigen Scan
automatisch jede Stunde, auch wenn der eigene Rechner ausgeschaltet ist.

Nach jedem Lauf sendet der Workflow die Top 25 als Discord-Nachricht. Deals
unter EUR 1,50 pro 100 Value werden als Alarm markiert. Wenn ein Shop ausfällt,
meldet Discord stattdessen den fehlgeschlagenen Scan und keine alten Deals.

## Ergebnisse

- `scan_results/top_300_deals.csv`: aktuelle Top-300-Rangliste
- Unter **Actions > MM2 Deal Scan** enthält jeder Lauf zusätzlich alle
  Audit-CSVs und das vollständige Laufprotokoll als Download.

## Manueller Cloud-Start

Unter **Actions > MM2 Deal Scan > Run workflow** kann jederzeit ein zusätzlicher
Scan gestartet werden.

## Lokaler Start

```powershell
pip install -r requirements.txt
playwright install chromium
python main.py
```

Die normalen Shops laufen in GitHub unsichtbar. LOLGA wird wegen der
Cloudflare-Sperre für native Headless-Browser in einer virtuellen Anzeige
gestartet; dafür ist auf dem eigenen Rechner keine zusätzliche Einrichtung nötig.
