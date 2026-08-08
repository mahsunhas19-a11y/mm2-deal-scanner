from datetime import datetime, timezone
from urllib.request import Request, urlopen
from xml.etree import ElementTree


ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
FALLBACK_USD_TO_EUR = 0.88


def get_usd_to_eur_rate(timeout=10):
    """Return USD->EUR from ECB (ECB publishes USD per EUR)."""
    try:
        request = Request(ECB_DAILY_URL, headers={"User-Agent": "MM2-Scanner/1.0"})
        with urlopen(request, timeout=timeout) as response:
            root = ElementTree.fromstring(response.read())
        usd_node = next(node for node in root.iter() if node.attrib.get("currency") == "USD")
        usd_per_eur = float(usd_node.attrib["rate"])
        return 1.0 / usd_per_eur, "ECB daily reference rate", datetime.now(timezone.utc).isoformat()
    except Exception:
        return FALLBACK_USD_TO_EUR, "offline fallback", datetime.now(timezone.utc).isoformat()
