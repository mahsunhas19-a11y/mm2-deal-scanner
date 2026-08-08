import unittest

from discord_notify import build_payload


class DiscordNotificationTests(unittest.TestCase):
    def test_alert_and_best_deals_are_included(self):
        deals = [
            {
                "name": "Vampire's Edge",
                "website": "BuyBlox",
                "eur_per_100_from_usd": "1.4700",
                "ratio_usd_per_100": "1.6700",
            },
            {
                "name": "Heat",
                "website": "Bloxxer",
                "eur_per_100_from_usd": "1.6700",
                "ratio_usd_per_100": "1.9000",
            },
        ]
        payload = build_payload(deals, "success", "https://example.test/run")
        embed = payload["embeds"][0]
        self.assertIn("DEAL-ALARM", embed["title"])
        self.assertIn("1 Deal(s) unter €1.50", embed["description"])
        self.assertIn("Vampire's Edge", embed["fields"][0]["name"])
        self.assertIn("buyblox.gg", embed["fields"][0]["value"])
        self.assertIn("Heat", embed["fields"][1]["name"])

    def test_failed_scan_never_reports_old_deals(self):
        deals = [{
            "name": "Old result",
            "website": "Luger",
            "eur_per_100_from_usd": "0.1000",
            "ratio_usd_per_100": "0.1100",
        }]
        payload = build_payload(deals, "failure", "https://example.test/run")
        self.assertIn("fehlgeschlagen", payload["content"])
        self.assertNotIn("Old result", payload["content"])

    def test_discord_embed_contains_at_most_25_deal_fields(self):
        deals = [{
            "name": f"Deal {index}",
            "website": "Luger",
            "eur_per_100_from_usd": f"{1.5 + index / 100:.4f}",
            "ratio_usd_per_100": f"{1.7 + index / 100:.4f}",
            "price_usd": "0.25",
        } for index in range(40)]
        payload = build_payload(deals, "success", "https://example.test/run")
        self.assertEqual(len(payload["embeds"][0]["fields"]), 25)


if __name__ == "__main__":
    unittest.main()
