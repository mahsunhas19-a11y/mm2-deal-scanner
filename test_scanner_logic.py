import unittest
from unittest.mock import MagicMock, patch

from catalog_matching import match_catalog
from name_matching import build_name_index, resolve_name
from calculator import find_deals
from scanner.common import parse_money, usd_from_price_data
from validator import _available_price_usd, _shopify_json_url
from scanner.starpets import _prepare_catalog, _usd_price
from scanner.lolga import _launch_lolga_browser, _select_usd


class LolgaCloudTests(unittest.TestCase):
    def test_cloud_can_launch_lolga_in_virtual_display(self):
        playwright = MagicMock()
        expected_browser = playwright.chromium.launch.return_value
        with patch.dict("os.environ", {"MM2_LOLGA_HEADED": "1"}):
            browser = _launch_lolga_browser(playwright)

        self.assertIs(browser, expected_browser)
        playwright.chromium.launch.assert_called_once_with(
            headless=False,
            args=["--disable-dev-shm-usage"],
        )

    def test_existing_usd_prices_do_not_require_visible_switcher(self):
        page = MagicMock()
        prices = MagicMock()
        price = MagicMock()
        price.locator.return_value.inner_text.return_value = "$0.99"
        prices.count.return_value = 1
        prices.nth.return_value = price
        page.locator.return_value = prices

        _select_usd(page)

        page.locator.assert_called_once_with("ul.product_list span.sell_price")


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.names = {"Blossom", "Bloom", "Ornament", "Logchopper", "Chroma Darkbringer"}
        self.index = build_name_index(self.names)

    def resolve(self, shop, title, url):
        return resolve_name(shop, title, self.names, self.index, url)

    def test_every_item_gets_closest_match(self):
        self.assertEqual(self.resolve("Luger", "Blossom Knife", "/products/blossom-knife"), "Blossom")
        self.assertEqual(self.resolve("Luger", "Blossom", "/products/blossom"), "Blossom")
        self.assertEqual(self.resolve("MM2Store", "Blossom", "/products/blossom"), "Blossom")
        self.assertEqual(self.resolve("BuyBlox", "Blossom Gun", "/products/blossom-1"), "Blossom")

    def test_ornament_variants_get_closest_match(self):
        self.assertEqual(self.resolve("MM2Store", "Ornament Gun", "/products/ornament-gun"), "Ornament")
        self.assertEqual(self.resolve("BuyBlox", "Ornament Knife", "/products/ornament-knife"), "Ornament")
        self.assertEqual(self.resolve("BuyBlox", "Ornament Knife", "/products/ornament-knife-1"), "Ornament")

    def test_suffix_names_still_get_a_match(self):
        self.assertEqual(self.resolve("BuyBlox", "Blossom Knife", "/products/unknown"), "Blossom")
        self.assertEqual(self.resolve("Luger", "Logchopper Knife", "/products/log-chopper"), "Logchopper")

    def test_clear_best_fuzzy_match_is_accepted(self):
        self.assertEqual(self.resolve("Bloxxer", "Chromma Darkbringer", "/products/c-dark-bringer"),
                         "Chroma Darkbringer")

    def test_lolga_weapon_suffix_maps_to_supreme_item(self):
        names = {"Harvester", "Icepiercer", "Candy"}
        index = build_name_index(names)
        self.assertEqual(resolve_name("LOLGA", "Harvester Gun", names, index), "Harvester")
        self.assertEqual(resolve_name("LOLGA", "Candy Knife", names, index), "Candy")

    def test_lolga_chroma_alias_maps_to_c_abbreviation(self):
        names = {"C. Vampire's Gun", "Vampire's Gun"}
        index = build_name_index(names)
        self.assertEqual(
            resolve_name("LOLGA", "Chroma Vampire's Gun", names, index),
            "C. Vampire's Gun",
        )


class PriceTests(unittest.TestCase):
    def test_starpets_eur_price_is_converted_to_usd(self):
        self.assertEqual(_usd_price("0.88", "EUR", 0.88), "$1.00")
        self.assertEqual(_usd_price("1.25", "USD", 0.88), "$1.25")
        self.assertIsNone(_usd_price("1.25", "GBP", 0.88))

    def test_localized_prices(self):
        self.assertEqual(parse_money("$3.90"), 3.90)
        self.assertEqual(parse_money("€3,90"), 3.90)
        self.assertEqual(parse_money("$2,768.45"), 2768.45)

    def test_euro_text_uses_embedded_usd_cents(self):
        self.assertEqual(usd_from_price_data("€6.91 EUR", usd_cents="797"), 7.97)

    def test_euro_without_usd_source_is_rejected(self):
        self.assertIsNone(usd_from_price_data("€6.91 EUR"))

    def test_extreme_deal_is_kept_but_flagged(self):
        items = {"Soul": {"name": "Soul", "value": 615, "prices": {"MM2Store": "$0.19"}}}
        deals = find_deals(items)
        self.assertEqual(len(deals), 1)
        self.assertTrue(deals[0]["needs_check"])
        self.assertIn("EXTREM", deals[0]["flags"])

    def test_all_prices_are_returned_best_to_worst(self):
        items = {
            "Heat": {"name": "Heat", "value": 10, "prices": {"A": "$0.19"}},
            "Soul": {"name": "Soul", "value": 615, "prices": {"A": "$51.98"}},
        }
        deals = find_deals(items)
        self.assertEqual([deal["name"] for deal in deals], ["Heat", "Soul"])

    def test_cross_shop_outlier_is_flagged(self):
        items = {"Candy": {"name": "Candy", "value": 80,
                           "prices": {"A": "$0.75", "B": "$6.99", "C": "$4.48"}}}
        deals = find_deals(items)
        cheap = next(deal for deal in deals if deal["website"] == "A")
        self.assertTrue(cheap["price_outlier_hint"])
        self.assertFalse(cheap["needs_check"])

    def test_eur_ratio_is_derived_from_usd_ratio(self):
        usd_ratio = 2.50
        usd_to_eur = 0.88
        self.assertAlmostEqual(usd_ratio * usd_to_eur, 2.20)

    def test_product_recheck_uses_available_variant_price(self):
        payload = {"variants": [
            {"available": False, "price": 10},
            {"available": True, "price": 399},
            {"available": True, "price": 499},
        ]}
        self.assertEqual(_available_price_usd(payload), 3.99)

    def test_product_json_url_drops_query_string(self):
        url = _shopify_json_url("/products/heat?_pos=1", "https://bloxxer.gg")
        self.assertEqual(url, "https://bloxxer.gg/products/heat.js")


class CatalogTests(unittest.TestCase):
    def test_starpets_filters_collectible_collision_by_metadata(self):
        rows = [
            {"name": "Blossom", "price": "0.04", "currency": "EUR",
             "product_url": "/common", "properties": {
                 "type": "weapon", "rare": "uncommon", "year": "2026"}},
            {"name": "Blossom", "price": "38.24", "currency": "EUR",
             "product_url": "/godly", "properties": {
                 "type": "weapon", "rare": "godly", "year": "2023"}},
        ]
        candidates, excluded = _prepare_catalog(rows, 0.88)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["shop_title"], "Blossom")
        self.assertEqual(candidates[0]["price"], "$43.45")
        self.assertEqual(excluded[0]["status"], "REJECTED")

    def test_starpets_chroma_metadata_changes_identity(self):
        rows = [{"name": "Vampire's Gun", "price": "699.41", "currency": "EUR",
                 "product_url": "/chroma", "properties": {
                     "type": "weapon", "rare": "godly", "chroma": "chroma"}}]
        candidates, excluded = _prepare_catalog(rows, 0.88)
        self.assertFalse(excluded)
        self.assertEqual(candidates[0]["shop_title"], "Chroma Vampire's Gun")
        weapons, _ = match_catalog(
            "StarPets", candidates, {"C. Vampire's Gun", "Vampire's Gun"}
        )
        self.assertIn("C. Vampire's Gun", dict(weapons))

    def test_lolga_single_item_beats_bundle(self):
        rows = [
            {"shop_title": "Candy Bundle", "price": "$4.05", "product_url": "#good-1"},
            {"shop_title": "Candy Knife", "price": "$2.97", "product_url": "#good-2"},
        ]
        weapons, audit = match_catalog("LOLGA", rows, {"Candy"})
        self.assertEqual(dict(weapons)["Candy"], "$2.97")
        self.assertTrue(any(row["shop_title"] == "Candy Bundle" and
                            row["status"] == "REVIEW" for row in audit))

    def test_exact_gun_name_beats_stripped_base_name(self):
        rows = [
            {"shop_title": "Flowerwood Knife", "price": "$14.50", "product_url": "#good-1"},
            {"shop_title": "Flowerwood Gun", "price": "$14.50", "product_url": "#good-2"},
        ]
        weapons, _ = match_catalog("LOLGA", rows, {"Flowerwood", "Flowerwood Gun"})
        self.assertEqual(dict(weapons), {
            "Flowerwood": "$14.50",
            "Flowerwood Gun": "$14.50",
        })

    def test_verified_real_product_beats_collectible_collision(self):
        rows = [
            {"shop_title": "Blossom", "price": "$0.19", "product_url": "/products/blossom"},
            {"shop_title": "Blossom Gun", "price": "$72.30", "product_url": "/products/blossom-1"},
        ]
        weapons, audit = match_catalog("BuyBlox", rows, {"Blossom", "Bloom"})
        self.assertEqual(dict(weapons)["Blossom"], "$72.30")
        self.assertTrue(any(row["status"] == "REJECTED" for row in audit))

    def test_bloxxer_real_blossom_beats_collectible_collision(self):
        rows = [
            {"shop_title": "Blossom", "price": "$0.99", "available": True,
             "product_url": "/products/blossom-1"},
            {"shop_title": "Blossom Gun", "price": "$64.45", "available": True,
             "product_url": "/products/blossom"},
        ]
        weapons, audit = match_catalog("Bloxxer", rows, {"Blossom", "Bloom"})
        self.assertEqual(dict(weapons)["Blossom"], "$64.45")
        rejected = [row for row in audit if row.get("product_url") == "/products/blossom-1"]
        self.assertEqual(rejected[0]["status"], "REJECTED")

    def test_bloxxer_collectible_blossom_is_never_a_deal_by_itself(self):
        rows = [
            {"shop_title": "Blossom", "price": "$0.99", "available": True,
             "product_url": "/products/blossom-1"},
        ]
        weapons, audit = match_catalog("Bloxxer", rows, {"Blossom"})
        self.assertNotIn("Blossom", dict(weapons))
        self.assertEqual(audit[0]["reason"], "verified collectible route")

    def test_one_supreme_name_can_only_be_claimed_once(self):
        rows = [
            {"shop_title": "Logchopper", "price": "$0.39", "product_url": "/products/logchopper"},
            {"shop_title": "Logchopper", "price": "$0.20", "product_url": "/products/log-chopper-copy"},
        ]
        weapons, audit = match_catalog("MM2Store", rows, {"Logchopper"})
        self.assertEqual(len(weapons), 1)
        self.assertTrue(any(row["status"] == "DUPLICATE" for row in audit))

    def test_sold_out_real_item_blocks_available_collectible(self):
        rows = [
            {"shop_title": "Bat", "price": "$7.18", "available": False,
             "product_url": "/products/bat-knife-halloween-2022"},
            {"shop_title": "Bats", "price": "$0.19", "available": True,
             "product_url": "/products/bats"},
        ]
        weapons, audit = match_catalog("Luger", rows, {"Bat"})
        self.assertNotIn("Bat", dict(weapons))
        self.assertTrue(any(row["status"] == "REJECTED" for row in audit))


if __name__ == "__main__":
    unittest.main()
