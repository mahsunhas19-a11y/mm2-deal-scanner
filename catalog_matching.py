from difflib import SequenceMatcher

from name_matching import PRODUCT_ALIASES, SHOP_ALIASES, _product_slug, normalize_name


# Verified shop routes that look like valuable Supreme items but are cheap
# collectibles.  They remain in the audit, but never enter the deal table.
DENIED_ROUTES = {
    "Luger": {"blossom-knife", "ornament", "ornament-knife", "ornament-gun",
              "ornament2-gun", "ornament-2-knife", "bats", "cotton-candy"},
    "MM2Store": {"blossom", "ornament-knife", "ornament-gun", "ornament2-gun"},
    "BuyBlox": {"blossom", "ornament-knife", "ornament-gun", "ornament2-gun"},
    # /products/blossom-1 is a different, cheap collectible.  The valuable
    # Supreme weapon is Bloxxer's /products/blossom product ("Blossom Gun").
    "Bloxxer": {"blossom-1"},
}


def _price_number(value):
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return -1.0


def _score(source: str, target: str) -> float:
    source_tokens = set(source.split())
    target_tokens = set(target.split())
    sequence = SequenceMatcher(None, source, target).ratio()
    overlap = len(source_tokens & target_tokens) / max(len(source_tokens | target_tokens), 1)
    score = 0.72 * sequence + 0.28 * overlap
    extras = source_tokens - target_tokens
    if extras & {"bundle", "set", "pack", "collection"}:
        score -= 0.32
    if extras & {"knife", "gun"}:
        score -= 0.08
    return score


def match_catalog(shop: str, raw_items: list[dict], valid_names) -> tuple[list[tuple[str, str]], list[dict]]:
    """Globally match a complete shop catalog to Supreme, one item per name."""
    valid_names = sorted(set(valid_names))
    normalized = {name: normalize_name(name) for name in valid_names}

    # The same URL may occur on several pagination/collection surfaces.
    deduplicated = {}
    for item in raw_items:
        key = item.get("product_url") or (item.get("shop_title"), item.get("price"))
        old = deduplicated.get(key)
        if old is None or _price_number(item.get("price")) > _price_number(old.get("price")):
            deduplicated[key] = item

    proposals = []
    audit = []
    for item in deduplicated.values():
        title = item.get("shop_title", "")
        slug = _product_slug(item.get("product_url"))
        base_audit = dict(item)
        if slug in DENIED_ROUTES.get(shop, set()):
            audit.append({**base_audit, "supreme_match": "", "confidence": "0.000",
                          "status": "REJECTED", "reason": "verified collectible route"})
            continue

        route_target = PRODUCT_ALIASES.get(shop, {}).get(slug)
        alias_target = SHOP_ALIASES.get(shop, {}).get(title)
        source = normalize_name(alias_target or title)
        ranked = sorted(((_score(source, key), name) for name, key in normalized.items()), reverse=True)
        exact_targets = [name for name, key in normalized.items() if key == source]
        typed_base = " ".join(source.split()[:-1]) if source.split()[-1:] and source.split()[-1] in {"knife", "gun"} else ""
        typed_targets = [name for name, key in normalized.items() if typed_base and key == typed_base]
        if route_target in normalized:
            best_score, best_name, reason = 1.25, route_target, "verified product route"
            margin = 1.0
        elif alias_target in normalized:
            best_score, best_name, reason = 1.20, alias_target, "verified title alias"
            margin = 1.0
        elif len(exact_targets) == 1:
            best_score, best_name, reason = 1.15, exact_targets[0], "exact normalized title"
            margin = 1.0
        elif len(typed_targets) == 1:
            best_score, best_name, reason = 1.10, typed_targets[0], "exact title plus item type"
            margin = 1.0
        else:
            best_score, best_name = ranked[0]
            margin = best_score - (ranked[1][0] if len(ranked) > 1 else 0.0)
            reason = "exact normalized title" if source == normalized[best_name] else "similarity"

        accepted = best_score >= 0.78 and (reason != "similarity" or margin >= 0.045)
        if not accepted:
            audit.append({**base_audit, "supreme_match": best_name,
                          "confidence": f"{best_score:.3f}", "status": "REVIEW",
                          "reason": f"{reason}; margin {margin:.3f}"})
            continue
        proposals.append((best_score, _price_number(item.get("price")), best_name, reason, margin, item))

    # Global one-to-one assignment prevents several cheap collectibles from
    # overwriting the actual product with the same Supreme name.
    proposals.sort(key=lambda row: (row[0], row[1]), reverse=True)
    claimed = set()
    found = {}
    for score, _, name, reason, margin, item in proposals:
        if name in claimed:
            audit.append({**item, "supreme_match": name, "confidence": f"{score:.3f}",
                          "status": "DUPLICATE", "reason": "stronger card already claimed this Supreme item"})
            continue
        claimed.add(name)
        audit.append({**item, "supreme_match": name, "confidence": f"{score:.3f}",
                      "status": "MATCHED", "reason": f"{reason}; margin {margin:.3f}"})
        if item.get("available", True) and _price_number(item.get("price")) >= 0:
            found[name] = item["price"]

    weapons = sorted(found.items(), key=lambda pair: pair[0].lower())
    audit.sort(key=lambda row: (row.get("status", ""), row.get("shop_title", "").lower()))
    return weapons, audit
