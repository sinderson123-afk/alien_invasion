"""Shop and skill tree UI"""

import pygame


# Button area records (populated by draw_shop for click detection)
shop_buttons = []


def _get_armor_display_name(tier_key):
    if tier_key is None:
        return "None"
    return tier_key.capitalize()


def _calc_armor_upgrade_cost(stats, settings):
    """Calculate upgrade cost to next armor tier (with trade-in discount)"""
    current_tier = stats.armor_tier
    found = False
    for i, (key, name, pct, price) in enumerate(settings.armor_tiers):
        if current_tier is None:
            return (key, name, pct, price, price)
        if key == current_tier:
            found = True
            continue
        if found:
            discount = int(price - settings.armor_tiers[i - 1][3] * settings.armor_trade_in_ratio)
            return (key, name, pct, price, discount)
    return (None, None, None, None, None)


def _get_armor_pct(armor_tier, settings):
    """Return defense percentage for armor key"""
    if armor_tier is None:
        return 0.0
    for key, name, pct, price in settings.armor_tiers:
        if key == armor_tier:
            return pct
    return 0.0


def draw_shop(screen, stats, settings):
    """Draw shop/skill tree UI, return button list for click detection"""
    global shop_buttons
    shop_buttons = []

    # Semi-transparent overlay
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    # Center panel
    panel_w, panel_h = 640, 620
    panel = pygame.Surface((panel_w, panel_h))
    panel.fill((40, 40, 60))
    panel_rect = panel.get_rect(center=screen.get_rect().center)
    screen.blit(panel, panel_rect)

    font_title = pygame.font.SysFont(None, 44)
    font_section = pygame.font.SysFont(None, 32)
    font_text = pygame.font.SysFont(None, 26)
    font_small = pygame.font.SysFont(None, 22)
    gold_color = (255, 215, 0)
    white = (255, 255, 255)
    green = (100, 220, 100)
    gray = (160, 160, 160)
    blue = (100, 180, 255)

    px, py = panel_rect.topleft

    # Title + coins
    title = font_title.render("SHOP", True, gold_color)
    screen.blit(title, (px + 300, py + 12))

    coins_text = f"$ {stats.coins}"
    coins_img = font_section.render(coins_text, True, gold_color)
    screen.blit(coins_img, (px + panel_w - 120, py + 15))

    # --- Items section ---
    item_y = py + 55
    screen.blit(font_section.render("Items", True, white), (px + 30, item_y))

    items = [
        ('magnet', 'Magnet', '10s auto-pickup', settings.magnet_item_cost, 'N'),
        ('shield', 'Shield', 'Blocks one hit', settings.shield_item_cost, 'Passive'),
        ('clover', 'Clover', 'Push enemies upward', settings.clover_item_cost, 'C'),
    ]

    for i, (key, name, desc, price, hotkey) in enumerate(items):
        row_y = item_y + 30 + i * 50
        owned = stats.items.get(key, 0)

        screen.blit(font_text.render(f"{name}", True, white), (px + 35, row_y))
        screen.blit(font_small.render(desc, True, gray), (px + 35, row_y + 22))
        screen.blit(font_small.render(f"Owned: {owned}", True, gray),
                    (px + 260, row_y))
        btn_text = f"${price} Buy"
        btn_img = font_text.render(btn_text, True, (0, 0, 0))
        btn_bg = pygame.Surface((btn_img.get_width() + 20, btn_img.get_height() + 10))
        can_afford = stats.coins >= price
        btn_bg.fill(green if can_afford else (80, 80, 80))
        btn_rect = btn_bg.get_rect(topleft=(px + 420, row_y))
        screen.blit(btn_bg, btn_rect)
        screen.blit(btn_img, (btn_rect.x + 10, btn_rect.y + 5))
        if can_afford:
            shop_buttons.append(('buy_item', key, price, btn_rect))
        screen.blit(font_small.render(f"[{hotkey}]", True, gray), (px + 570, row_y))

    # --- Armor section ---
    armor_y = item_y + 30 + len(items) * 50 + 15
    screen.blit(font_section.render("Armor", True, white), (px + 30, armor_y))

    row_y = armor_y + 30
    current_name = _get_armor_display_name(stats.armor_tier)
    current_pct = _get_armor_pct(stats.armor_tier, settings)

    armor_status = f"{current_name} ({int(current_pct * 100)}%)"
    armor_color = blue if stats.armor_tier else gray
    screen.blit(font_text.render(armor_status, True, armor_color),
                (px + 35, row_y))

    next_key, next_name, next_pct, full_price, discounted_price = \
        _calc_armor_upgrade_cost(stats, settings)

    if next_key:
        row_y += 38
        screen.blit(font_small.render(
            f"Next: {next_name} ({int(next_pct * 100)}%)", True, white),
            (px + 35, row_y))

        if discounted_price < full_price:
            price_text = f"${discounted_price} Upgrade ({int(settings.armor_trade_in_ratio * 100)}% trade-in)"
        else:
            price_text = f"${full_price} Buy"
        btn_img = font_text.render(price_text, True, (0, 0, 0))
        btn_bg = pygame.Surface((btn_img.get_width() + 20, btn_img.get_height() + 10))
        can_afford = stats.coins >= discounted_price
        btn_bg.fill(green if can_afford else (80, 80, 80))
        btn_rect = btn_bg.get_rect(topleft=(px + 35, row_y + 24))
        screen.blit(btn_bg, btn_rect)
        screen.blit(btn_img, (btn_rect.x + 10, btn_rect.y + 5))
        if can_afford:
            shop_buttons.append(('buy_armor', next_key, discounted_price, btn_rect))
    else:
        row_y += 38
        screen.blit(font_small.render("MAX", True, gold_color), (px + 35, row_y))

    # --- Skills section ---
    skill_y = armor_y + 30 + 2 * 50 + 10
    screen.blit(font_section.render("Skills", True, white), (px + 30, skill_y))

    skills = [
        ('speed', 'Speed Boost', '+10% ship speed/lv', settings.skill_costs['speed']),
        ('ammo', 'Ammo Capacity', '+1 bullet/lv', settings.skill_costs['ammo']),
        ('vitality', 'Vitality', '+1 max life/lv', settings.skill_costs['vitality']),
    ]

    for i, (key, name, desc, costs) in enumerate(skills):
        row_y = skill_y + 30 + i * 50
        level = stats.skills.get(key, 0)

        screen.blit(font_text.render(f"{name}", True, white), (px + 35, row_y))
        screen.blit(font_small.render(desc, True, gray), (px + 35, row_y + 22))
        lv_color = gold_color if level >= settings.skill_max_level else white
        screen.blit(font_small.render(f"Lv.{level}/{settings.skill_max_level}", True, lv_color),
                    (px + 320, row_y))
        if level < settings.skill_max_level:
            cost = costs[level]
            btn_text = f"${cost} Up"
            btn_img = font_text.render(btn_text, True, (0, 0, 0))
            btn_bg = pygame.Surface((btn_img.get_width() + 20, btn_img.get_height() + 10))
            can_afford = stats.coins >= cost
            btn_bg.fill(green if can_afford else (80, 80, 80))
            btn_rect = btn_bg.get_rect(topleft=(px + 420, row_y))
            screen.blit(btn_bg, btn_rect)
            screen.blit(btn_img, (btn_rect.x + 10, btn_rect.y + 5))
            if can_afford:
                shop_buttons.append(('upgrade_skill', key, cost, btn_rect))
        else:
            screen.blit(font_small.render("MAX", True, gold_color), (px + 450, row_y))

    # Close button
    close_text = "Close"
    close_img = font_text.render(close_text, True, (255, 255, 255))
    close_bg = pygame.Surface((close_img.get_width() + 30, close_img.get_height() + 14))
    close_bg.fill((140, 50, 50))
    close_rect = close_bg.get_rect()
    close_rect.centerx = px + panel_w // 2
    close_rect.bottom = py + panel_h - 10
    screen.blit(close_bg, close_rect)
    screen.blit(close_img, (close_rect.x + 15, close_rect.y + 7))
    shop_buttons.append(('close_shop', None, 0, close_rect))

    hint = font_small.render("Press M or Esc to close", True, gray)
    screen.blit(hint, (px + panel_w // 2 - hint.get_width() // 2, close_rect.top - 22))

    return shop_buttons


def handle_shop_click(mouse_pos, stats, settings):
    """
    Handle click events in shop.
    Returns: (has_change: bool, action: str | None)
      action is 'purchase' for buy/upgrade, 'close' for close, None for no-op
    """
    for action, key, cost, rect in shop_buttons:
        if rect.collidepoint(mouse_pos):
            if action == 'close_shop':
                return (False, 'close')
            elif action == 'buy_item' and stats.coins >= cost:
                stats.coins -= cost
                stats.items[key] = stats.items.get(key, 0) + 1
                stats.save_player_data()
                return (True, 'purchase')
            elif action == 'buy_armor' and stats.coins >= cost:
                stats.coins -= cost
                stats.armor_tier = key
                stats.save_player_data()
                return (True, 'purchase')
            elif action == 'upgrade_skill' and stats.coins >= cost:
                stats.coins -= cost
                stats.skills[key] = stats.skills.get(key, 0) + 1
                if key == 'vitality':
                    stats.max_hp = stats._calc_max_hp()
                    stats.ship_hp = min(stats.ship_hp + stats.settings.ship_hp_multiplier,
                                        stats.max_hp)
                stats.save_player_data()
                return (True, 'purchase')
    return (False, None)
