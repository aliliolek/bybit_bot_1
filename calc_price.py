# calc_price.py

from pprint import pprint

import logging
logger = logging.getLogger(__name__)

def to_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# =======================================================================
# ДОПОМІЖНІ ФУНКЦІЇ ТА ПРАВИЛА ВАЛІДАЦІЇ
# =======================================================================

def _is_ad_acceptable(ad: dict, cfg: dict) -> bool:


    ALL_RULES = [
        {
            'name': 'Minimum Total Orders',
            'is_active': lambda ad, cfg: cfg.get('check_orderNum', False),
            'is_valid': lambda ad, cfg: to_float(ad.get('recentOrderNum', 0)) > to_float(cfg.get('min_total_orders', 0)),
            'ad_value': lambda ad, cfg: ad.get('recentOrderNum', 0),
            'cfg_value': lambda ad, cfg: cfg.get('min_total_orders', 0),
        },
        {
            'name': 'Payment Methods',
            'is_active': lambda ad, cfg: cfg.get('check_payment_methods', False),
            'is_valid': lambda ad, cfg: (
                len(
                    set(cfg.get('allowed_payment_types', [])).intersection(set(ad.get('payments', [])))
                ) >= min(
                    to_float(cfg.get('min_payment_matches', 1)),
                    len(cfg.get('allowed_payment_types', []))
                )
            ),
            'ad_value': lambda ad, cfg: ad.get('payments', []),
            'cfg_value': lambda ad, cfg: {
                'allowed_payment_types': cfg.get('allowed_payment_types', []),
                'min_payment_matches': cfg.get('min_payment_matches', 1),
            },
        },
        {
            'name': 'Minimum Balance',
            'is_active': lambda ad, cfg: cfg.get('check_min_balance', False),
            'is_valid': lambda ad, cfg: to_float(ad.get('lastQuantity')) >= to_float(cfg.get('min_amount_threshold', 0)),
            'ad_value': lambda ad, cfg: ad.get('lastQuantity'),
            'cfg_value': lambda ad, cfg: cfg.get('min_amount_threshold', 0),
        },
        {
            'name': 'Minimum Limit',
            'is_active': lambda ad, cfg: cfg.get('check_min_limit', False),
            'is_valid': lambda ad, cfg: to_float(ad.get('minAmount')) <= to_float(cfg.get('min_limit_threshold', float('inf'))),
            'ad_value': lambda ad, cfg: ad.get('minAmount'),
            'cfg_value': lambda ad, cfg: cfg.get('min_limit_threshold', float('inf')),
        },
        {
            'name': 'Limit Range',
            'is_active': lambda ad, cfg: cfg.get('check_limit_range', False),
            'is_valid': lambda ad, cfg: (to_float(ad.get('maxAmount')) - to_float(ad.get('minAmount'))) >= to_float(cfg.get('min_limit_range', 0)),
            'ad_value': lambda ad, cfg: to_float(ad.get('maxAmount')) - to_float(ad.get('minAmount')),
            'cfg_value': lambda ad, cfg: cfg.get('min_limit_range', 0),
        },
        {
            'name': 'Advertiser Register Time',
            'is_active': lambda ad, cfg: cfg.get('check_register_days', False) and ad.get('tradingPreferenceSet', {}).get('hasRegisterTime') == 1,
            'is_valid': lambda ad, cfg: to_float(ad.get('tradingPreferenceSet', {}).get('registerTimeThreshold')) <= to_float(cfg.get('min_register_days', float('inf'))),
            'ad_value': lambda ad, cfg: ad.get('tradingPreferenceSet', {}).get('registerTimeThreshold'),
            'cfg_value': lambda ad, cfg: cfg.get('min_register_days', float('inf')),
        },
        {
            'name': 'Advertiser Order Count',
            'is_active': lambda ad, cfg: cfg.get('check_min_orders', False) and ad.get('tradingPreferenceSet', {}).get('hasOrderFinishNumberDay30') == 1,
            'is_valid': lambda ad, cfg: to_float(ad.get('tradingPreferenceSet', {}).get('orderFinishNumberDay30')) <= to_float(cfg.get('min_order_count', float('inf'))),
            'ad_value': lambda ad, cfg: ad.get('tradingPreferenceSet', {}).get('orderFinishNumberDay30'),
            'cfg_value': lambda ad, cfg: cfg.get('min_order_count', float('inf')),
        },
        {
            'name': 'Country Whitelist',
            'is_active': lambda ad, cfg: cfg.get('check_country_whitelist', False),
            'is_valid': lambda ad, cfg: (
                ad.get('tradingPreferenceSet', {}).get('hasNationalLimit') != 1 or
                not set(cfg.get('country_whitelist', [])).isdisjoint(set(ad.get('tradingPreferenceSet', {}).get('nationalLimit', [])))
            ),
            'ad_value': lambda ad, cfg: ad.get('tradingPreferenceSet', {}).get('nationalLimit', []),
            'cfg_value': lambda ad, cfg: cfg.get('country_whitelist', []),
        },
        {
            'name': 'Remark Blacklist',
            'is_active': lambda ad, cfg: cfg.get('check_remark_blacklist', False),
            'is_valid': lambda ad, cfg: not any(
                word in ad.get('remark', '').lower()
                for word in cfg.get('remark_blacklist', [])
            ),
            'ad_value': lambda ad, cfg: ad.get('remark', ''),
            'cfg_value': lambda ad, cfg: cfg.get('remark_blacklist', []),
        },
        {
            'name': 'Nickname Blacklist',
            'is_active': lambda ad, cfg: cfg.get('check_exclude_nicknames', False),
            'is_valid': lambda ad, cfg: ad.get('nickName') not in cfg.get('exclude_nicknames', []),
            'ad_value': lambda ad, cfg: ad.get('nickName'),
            'cfg_value': lambda ad, cfg: cfg.get('exclude_nicknames', []),
        },
        {
            'name': 'Min Price Delta from BUY (SELL only)',
            'is_active': lambda ad, cfg: cfg.get('check_sell_vs_buy_gap', False) and cfg.get('side') == 'SELL',
            'is_valid': lambda ad, cfg: (
                to_float(ad.get("price", 0)) >= to_float(cfg.get("reference_buy_price", 0)) * (1 + to_float(cfg.get("min_gap_percent", 0.015)))
            ),
            'ad_value': lambda ad, cfg: ad.get('price'),
            'cfg_value': lambda ad, cfg: {
                'reference_buy_price': cfg.get('reference_buy_price', 0),
                'min_gap_percent': cfg.get('min_gap_percent', 0.015),
            },
        },
    ]


    for rule in ALL_RULES:
        if rule['is_active'](ad, cfg):
            if not rule['is_valid'](ad, cfg):
                ad_val = rule.get('ad_value', lambda a, c: None)(ad, cfg)
                cfg_val = rule.get('cfg_value', lambda a, c: None)(ad, cfg)
                logger.info(
                    "Rule '%s' failed: ad value=%s, config=%s",
                    rule['name'],
                    ad_val,
                    cfg_val,
                )
                return False
    return True

def _find_neighbor_price(ad, all_ads, gap, side_code):
    ad_price = float(ad['price'])
    ad_owner = ad['nickName']
    for neighbor in all_ads:
        if neighbor['nickName'] == ad_owner:
            continue
        neighbor_price = float(neighbor['price'])

        if side_code == 1:
            price_diff = neighbor_price - ad_price
            match = neighbor_price >= ad_price and price_diff <= gap
        else:
            price_diff = ad_price - neighbor_price
            match = neighbor_price <= ad_price and price_diff <= gap

        logger.info(
            "Neighbor check: %s vs %s | diff: %.8f | match: %s",
            ad_owner,
            neighbor['nickName'],
            price_diff,
            match,
        )
        if match:
            return True, neighbor
    return False, None


def _find_price_in_list(list_to_search, all_ads, gap, side_code):
    for ad in list_to_search:
        matched, neighbor = _find_neighbor_price(ad, all_ads, gap, side_code)
        if matched:
            logger.info(
                "Price returned from ad %s matched with neighbor %s",
                ad['nickName'],
                neighbor['nickName'],
            )
            return float(ad['price'])
    return None

def find_price_from_config(ads_list: list, side_config: dict, side_code: int, price_gap: float, fallback_price: float) -> float:
    filtered_ads = [ad for ad in ads_list if _is_ad_acceptable(ad, side_config)]

    logger.info(f"🧾 Filtered ads ({'BUY' if side_code == 0 else 'SELL'}):")
    for ad in filtered_ads:
        nickname = ad.get("nickName", "?")
        price = ad.get("price", "?")
        qty = ad.get("lastQuantity", "?")
        logger.info(f"  - {nickname} | price: {price} | qty: {qty}")

    if not filtered_ads:
      logger.warning("⚠️ No ads passed filtering, using fallback price")
      return fallback_price

    use_target = side_config.get("check_target_nicknames", False)
    use_neighbors = side_config.get("check_price_neighbors", True)

    if use_target:
        target_nicknames = side_config.get("target_nicknames", [])
        target_ads = [ad for ad in filtered_ads if ad['nickName'] in target_nicknames]
        other_ads = [ad for ad in filtered_ads if ad['nickName'] not in target_nicknames]

        if use_neighbors:
            price = _find_price_in_list(target_ads, filtered_ads, price_gap, side_code)
            if price is not None:
                return price
            price = _find_price_in_list(other_ads, filtered_ads, price_gap, side_code)
            if price is not None:
                return price
        else:
            if target_ads:
                return float(target_ads[0]['price'])
            if other_ads:
                return float(other_ads[0]['price'])
    else:
        if use_neighbors:
            price = _find_price_in_list(filtered_ads, filtered_ads, price_gap, side_code)
            if price is not None:
                return price
        else:
            return float(filtered_ads[0]['price'])

    return fallback_price
