def merge_data(luger, mm2store, buyblox, bloxxer, supreme, lolga=None, starpets=None):
    """Scanner liefern bereits offizielle Supreme-Namen; hier wird nur noch zusammengeführt."""
    items = {
        name: {"name": name, "value": value, "prices": {}}
        for name, value in supreme
    }

    for shop_name, data in (
        ("Luger", luger),
        ("MM2Store", mm2store),
        ("BuyBlox", buyblox),
        ("Bloxxer", bloxxer),
        ("LOLGA", lolga or []),
        ("StarPets", starpets or []),
    ):
        for name, price in data:
            if name in items:
                items[name]["prices"][shop_name] = price

    return items
