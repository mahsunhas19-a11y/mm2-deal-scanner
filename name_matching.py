import re
from difflib import SequenceMatcher
from urllib.parse import urlparse


SHOP_ALIASES = {
    "Luger": {
        "BattleAxe Knife": "Battleaxe", "Battle Axe 2 Knife": "Battleaxe II",
        "Chroma Constellation Gun": "C. Constellation",
        "Chroma Elderwood Blade Knife": "C. Elderwood Blade",
        "Chroma Traveler Gun": "C. Traveler's Gun",
        "Chroma Vampire's Gun": "C. Vampire's Gun",
        "Hallows Blade": "Hallow's Blade", "Hallow Gun": "Hallowgun",
        "Makeshift Gun - Halloween 2022": "Makeshift",
        "Eternal 2 Knife": "Eternal II", "Eternal 3 Knife": "Eternal III",
        "Eternal 4 Knife": "Eternal IV", "Logchopper Knife": "Logchopper",
        "Bloom Knife": "Bloom", "Chroma Lightbringer Gun": "Chroma Lightbringer",
        "Chroma Laser Gun": "Chroma Laser", "Laser Disint Gun (Vintage)": "Laser",
        "Heart Wand Knife": "Heart Wand", "Spectre Gun": "Spectre",
        "Chroma Heart Wand Knife": "Chroma Heart Wand",
        "Chroma Ornament Knife": "Chroma Ornament",
    },
    "MM2Store": {
        "BattleAxe II": "Battleaxe II", "Hallows Blade": "Hallow's Blade",
        "JingleGun": "Jinglegun", "Winters Edge": "Winter's Edge",
        "Eternal 2": "Eternal II", "Eternal 3": "Eternal III", "Eternal 4": "Eternal IV",
        "Soul Gun": "Soul",
    },
    "BuyBlox": {
        "BattleAxe II": "Battleaxe II", "Hallows Blade": "Hallow's Blade",
        "JingleGun": "Jinglegun", "Winters Edge": "Winter's Edge",
        "Eternal 2": "Eternal II", "Eternal 3": "Eternal III", "Eternal 4": "Eternal IV",
    },
    "Bloxxer": {
        "BattleAxe I": "Battleaxe", "BattleAxe II": "Battleaxe II",
        "Hallows Blade": "Hallow's Blade", "Hallows Edge": "Hallow's Edge",
        "Hallow Scythe": "Hallowscythe", "Hallow Gun": "Hallowgun",
        "Jingle Gun": "Jinglegun", "Winters Edge": "Winter's Edge",
        "Eternal 2": "Eternal II", "Eternal 3": "Eternal III", "Eternal 4": "Eternal IV",
        "Traveler Gun": "Traveler's Gun", "Traveler Axe": "Traveler's Axe",
        "Chroma Traveler Gun": "C. Traveler's Gun",
        "Chroma Vampire's Gun": "C. Vampire's Gun",
        "Chroma Constellation": "C. Constellation",
        "Chroma Elderwood Blade": "C. Elderwood Blade",
    },
    "LOLGA": {
        "BattleAxe Knife": "Battleaxe", "BattleAxe II Knife": "Battleaxe II",
        "Battle Axe 2 Knife": "Battleaxe II", "Xeno Knife": "Xenoknife",
        "Hallows Blade Knife": "Hallow's Blade", "Hallows Edge Knife": "Hallow's Edge",
        "Hallow Scythe Knife": "Hallowscythe", "Hallow Gun": "Hallowgun",
        "Jingle Gun": "Jinglegun", "Winters Edge Knife": "Winter's Edge",
        "Eternal 2 Knife": "Eternal II", "Eternal 3 Knife": "Eternal III",
        "Eternal 4 Knife": "Eternal IV", "Soul Gun": "Soul",
        "Chroma Traveler's Gun": "C. Traveler's Gun",
        "Chroma Vampire's Gun": "C. Vampire's Gun",
        "Chroma Constellation Gun": "C. Constellation",
        "Chroma Elderwood Blade Knife": "C. Elderwood Blade",
    },
    "StarPets": {
        "Chroma Constellation": "C. Constellation",
        "Chroma Elderwood Blade": "C. Elderwood Blade",
        "Chroma Traveler's Gun": "C. Traveler's Gun",
        "Chroma Vampire's Gun": "C. Vampire's Gun",
    },
}

# These routes identify the real high-value item.  The shops also sell cheap
# collectibles with the same visible title, so title-only matching is unsafe.
PRODUCT_ALIASES = {
    "Luger": {"blossom": "Blossom", "ornament-knife-1": "Ornament",
              "bat-knife-halloween-2022": "Bat", "heart-wand-knife": "Heart Wand",
              "spectre-gun-halloween-2022": "Spectre", "candy": "Candy"},
    "MM2Store": {"ornament-knife-1": "Ornament", "soul-gun": "Soul"},
    "BuyBlox": {"blossom-1": "Blossom", "ornament-knife-1": "Ornament"},
    "Bloxxer": {"blossom": "Blossom"},
}

BLOCKED_ROUTES = {
    "blossom", "blossom-knife", "ornament", "ornament-knife", "ornament-gun",
    "ornament2-gun", "ornament-2-knife", "ornament-set", "ornament-2-set",
}


def normalize_name(name: str) -> str:
    text = name.strip().lower().replace("’", "'").replace("'", "")
    text = text.replace("&", " and ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _candidate_keys(shop_name: str) -> list[str]:
    base = normalize_name(shop_name)
    candidates = [base]
    replacements = {
        "battle axe": "battleaxe", "jingle gun": "jinglegun",
        "hallow scythe": "hallowscythe", "hallow blade": "hallows blade",
    }
    changed = base
    for old, new in replacements.items():
        changed = changed.replace(old, new)
    if changed not in candidates:
        candidates.append(changed)
    return candidates


def build_name_index(valid_names) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for name in valid_names:
        index.setdefault(normalize_name(name), []).append(name)
    return index


def _product_slug(product_url: str | None) -> str:
    if not product_url:
        return ""
    return urlparse(product_url).path.rstrip("/").rsplit("/", 1)[-1].lower()


def resolve_name(shop: str, shop_name: str, valid_names, name_index=None,
                 product_url: str | None = None) -> str | None:
    valid_set = valid_names if isinstance(valid_names, set) else set(valid_names)
    slug = _product_slug(product_url)
    route_alias = PRODUCT_ALIASES.get(shop, {}).get(slug)
    aliased = route_alias or SHOP_ALIASES.get(shop, {}).get(shop_name, shop_name)
    if aliased in valid_set:
        return aliased
    name_index = name_index or build_name_index(valid_set)
    for key in _candidate_keys(aliased):
        matches = name_index.get(key, [])
        if len(matches) == 1:
            return matches[0]
    # Every scraped shop item is assigned to its closest Supreme entry. Exact
    # aliases/routes still win, after which the highest similarity always wins.
    source = normalize_name(aliased)
    source_tokens = set(source.split())
    ranked = []
    for key, names in name_index.items():
        key_tokens = set(key.split())
        sequence = SequenceMatcher(None, source, key).ratio()
        overlap = len(source_tokens & key_tokens) / max(len(source_tokens | key_tokens), 1)
        score = 0.72 * sequence + 0.28 * overlap
        # Shop type/bundle words carry meaning and must not silently disappear.
        semantic_extras = source_tokens - key_tokens
        if semantic_extras & {"set", "bundle", "pack"}:
            score -= 0.30
        if semantic_extras & {"knife", "gun"}:
            score -= 0.10
        for name in names:
            ranked.append((score, name))
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked else None


def price_to_number(price: str) -> float | None:
    if not price:
        return None
    cleaned = re.sub(r"[^0-9.,]", "", price).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def keep_safest_price(results: dict[str, str], name: str, price: str) -> None:
    """For ambiguous duplicate titles, keep the conservative (higher) price.

    Shops reuse weapon names for cheap collectibles.  Choosing the cheapest
    duplicate manufactures false deals; choosing the higher one fails closed.
    """
    current = results.get(name)
    if current is None:
        results[name] = price
        return
    current_number = price_to_number(current)
    new_number = price_to_number(price)
    if new_number is not None and (current_number is None or new_number > current_number):
        results[name] = price
