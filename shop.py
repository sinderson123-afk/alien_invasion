"""商店与技能树 UI"""

import pygame


# 按钮区域记录（由 draw_shop 填充，供点击检测使用）
shop_buttons = []


def draw_shop(screen, stats, settings):
    """绘制商店/技能树界面，返回按钮列表供点击检测"""
    global shop_buttons
    shop_buttons = []

    # 半透明遮罩
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    # 中央面板
    panel_w, panel_h = 560, 420
    panel = pygame.Surface((panel_w, panel_h))
    panel.fill((40, 40, 60))
    panel_rect = panel.get_rect(center=screen.get_rect().center)
    screen.blit(panel, panel_rect)

    font_title = pygame.font.SysFont(None, 48)
    font_section = pygame.font.SysFont(None, 32)
    font_text = pygame.font.SysFont(None, 26)
    font_small = pygame.font.SysFont(None, 22)
    gold_color = (255, 215, 0)
    white = (255, 255, 255)
    green = (100, 220, 100)
    gray = (160, 160, 160)
    red = (220, 80, 80)

    px, py = panel_rect.topleft

    # 标题 + 金币
    title = font_title.render("SHOP", True, gold_color)
    screen.blit(title, (px + 240, py + 15))

    coins_text = f"$ {stats.coins}"
    coins_img = font_section.render(coins_text, True, gold_color)
    screen.blit(coins_img, (px + panel_w - 120, py + 20))

    # --- 道具区 ---
    item_y = py + 65
    screen.blit(font_section.render("Items", True, white), (px + 30, item_y))

    items = [
        ('magnet', 'Magnet', '10s auto-pickup', settings.magnet_item_cost, 'N'),
        ('shield', 'Shield', 'Blocks one hit', settings.shield_item_cost, 'Passive'),
    ]

    for i, (key, name, desc, price, hotkey) in enumerate(items):
        row_y = item_y + 30 + i * 50
        owned = stats.items.get(key, 0)

        # 名称
        screen.blit(font_text.render(f"{name}", True, white), (px + 35, row_y))
        # 描述
        screen.blit(font_small.render(desc, True, gray), (px + 35, row_y + 22))
        # 库存
        screen.blit(font_small.render(f"Owned: {owned}", True, gray),
                    (px + 210, row_y))
        # 购买按钮
        btn_text = f"${price} Buy"
        btn_img = font_text.render(btn_text, True, (0, 0, 0))
        btn_bg = pygame.Surface((btn_img.get_width() + 20, btn_img.get_height() + 10))
        can_afford = stats.coins >= price
        btn_bg.fill(green if can_afford else (80, 80, 80))
        btn_rect = btn_bg.get_rect(topleft=(px + 340, row_y))
        screen.blit(btn_bg, btn_rect)
        screen.blit(btn_img, (btn_rect.x + 10, btn_rect.y + 5))
        if can_afford:
            shop_buttons.append(('buy_item', key, price, btn_rect))
        # 快捷键
        screen.blit(font_small.render(f"[{hotkey}]", True, gray), (px + 490, row_y))

    # --- 技能区 ---
    skill_y = item_y + 30 + 2 * 50 + 20
    screen.blit(font_section.render("Skills", True, white), (px + 30, skill_y))

    skills = [
        ('speed', 'Speed Boost', '+10% ship speed/lv', settings.skill_costs['speed']),
        ('ammo', 'Ammo Capacity', '+1 bullet/lv', settings.skill_costs['ammo']),
        ('vitality', 'Vitality', '+1 max life/lv', settings.skill_costs['vitality']),
    ]

    for i, (key, name, desc, costs) in enumerate(skills):
        row_y = skill_y + 30 + i * 50
        level = stats.skills.get(key, 0)

        # 名称
        screen.blit(font_text.render(f"{name}", True, white), (px + 35, row_y))
        # 描述
        screen.blit(font_small.render(desc, True, gray), (px + 35, row_y + 22))
        # 等级
        lv_color = gold_color if level >= settings.skill_max_level else white
        screen.blit(font_small.render(f"Lv.{level}/{settings.skill_max_level}", True, lv_color),
                    (px + 260, row_y))
        # 升级按钮
        if level < settings.skill_max_level:
            cost = costs[level]
            btn_text = f"${cost} Up"
            btn_img = font_text.render(btn_text, True, (0, 0, 0))
            btn_bg = pygame.Surface((btn_img.get_width() + 20, btn_img.get_height() + 10))
            can_afford = stats.coins >= cost
            btn_bg.fill(green if can_afford else (80, 80, 80))
            btn_rect = btn_bg.get_rect(topleft=(px + 340, row_y))
            screen.blit(btn_bg, btn_rect)
            screen.blit(btn_img, (btn_rect.x + 10, btn_rect.y + 5))
            if can_afford:
                shop_buttons.append(('upgrade_skill', key, cost, btn_rect))
        else:
            screen.blit(font_small.render("MAX", True, gold_color), (px + 370, row_y))

    # 关闭按钮
    close_text = "Close"
    close_img = font_text.render(close_text, True, (255, 255, 255))
    close_bg = pygame.Surface((close_img.get_width() + 30, close_img.get_height() + 14))
    close_bg.fill((140, 50, 50))
    close_rect = close_bg.get_rect()
    close_rect.centerx = px + panel_w // 2
    close_rect.bottom = py + panel_h - 12
    screen.blit(close_bg, close_rect)
    screen.blit(close_img, (close_rect.x + 15, close_rect.y + 7))
    shop_buttons.append(('close_shop', None, 0, close_rect))

    # 提示
    hint = font_small.render("Press M or Esc to close", True, gray)
    screen.blit(hint, (px + panel_w // 2 - hint.get_width() // 2, close_rect.top - 22))

    return shop_buttons


def handle_shop_click(mouse_pos, stats, settings):
    """
    处理商店界面内的点击事件。
    返回: (has_change: bool, action: str | None)
      action 为 'purchase' 表示购买/升级操作, 'close' 表示关闭商店, None 表示无操作
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
            elif action == 'upgrade_skill' and stats.coins >= cost:
                stats.coins -= cost
                stats.skills[key] = stats.skills.get(key, 0) + 1
                stats.save_player_data()
                return (True, 'purchase')
    return (False, None)
