"""Gem management tab (rendered inside the shop panel)."""
import pygame
from gem import ALL_STATS, STAT_LABELS, STAT_FORMATS, COLORS, upgrade_gem, get_gem_bonuses

gem_tab_buttons = []


def draw_gem_tab(screen, stats, settings, panel_rect):
    """Draw the gem equipment/storage tab. Returns button list for click handling."""
    global gem_tab_buttons
    gem_tab_buttons = []

    white = (255, 255, 255)
    gray = (160, 160, 160)
    gold_color = (255, 215, 0)
    green = (100, 220, 100)
    red = (220, 80, 80)

    px, py = panel_rect.topleft
    panel_w = panel_rect.width

    font_title = pygame.font.SysFont(None, 28)
    font_text = pygame.font.SysFont(None, 22)
    font_small = pygame.font.SysFont(None, 18)

    # ── Section: Equipped Gems (top row) ──
    slot_y = py + 48
    slot_info = font_title.render("Equipped Gems (5 slots)", True, white)
    screen.blit(slot_info, (px + 20, slot_y))

    slot_start_x = px + 20
    slot_w = 112
    slot_h = 62
    slot_gap = 8

    for i in range(5):
        sx = slot_start_x + i * (slot_w + slot_gap)
        sy = slot_y + 26
        gem = stats.equipped_gems[i] if (
            isinstance(stats.equipped_gems, list)
            and i < len(stats.equipped_gems)
        ) else None

        slot_rect = pygame.Rect(sx, sy, slot_w, slot_h)
        if gem:
            mst = gem['main_stat']
            color = COLORS.get(mst[0], (180, 180, 180))
            pygame.draw.rect(screen, (50, 50, 70), slot_rect)
            pygame.draw.rect(screen, color, slot_rect, 2)
            name_img = font_text.render(gem['name'][:8], True, color)
            screen.blit(name_img, (sx + 4, sy + 4))
            stat_str = f"{STAT_LABELS[mst[0]]} {STAT_FORMATS[mst[0]](mst[1])}"
            stat_img = font_small.render(stat_str, True, white)
            screen.blit(stat_img, (sx + 4, sy + 26))
            lv_img = font_small.render(f"Lv.{gem['level']}", True, gold_color)
            screen.blit(lv_img, (sx + 4, sy + 42))
            gem_tab_buttons.append(('unequip_gem', i, 0, slot_rect))
        else:
            pygame.draw.rect(screen, (35, 35, 50), slot_rect)
            pygame.draw.rect(screen, gray, slot_rect, 1)
            empty_img = font_text.render("Empty", True, gray)
            empty_rect = empty_img.get_rect(center=slot_rect.center)
            screen.blit(empty_img, empty_rect)
            gem_tab_buttons.append(('equip_slot', i, 0, slot_rect))

    # ── Section: Storage (grouped by main stat, sorted by level desc) ──
    storage_y = slot_y + 28 + slot_h + 16
    storage_title = font_title.render("Storage", True, white)
    screen.blit(storage_title, (px + 20, storage_y))

    storage_start_y = storage_y + 30
    item_h = 36
    header_h = 20
    visible_count = 5
    storage_area_h = visible_count * item_h

    if not isinstance(stats.gem_storage, list):
        stats.gem_storage = []

    # Build display rows: ('header', stat_type) or ('gem', storage_idx, gem)
    display_rows = []
    for stat_type in ALL_STATS:
        group = [(i, g) for i, g in enumerate(stats.gem_storage)
                 if g and g['main_stat'][0] == stat_type]
        if not group:
            continue
        display_rows.append(('header', stat_type))
        group.sort(key=lambda x: x[1]['level'], reverse=True)
        display_rows.extend(('gem', i, g) for i, g in group)

    total_rows = len(display_rows)

    gem_tab_buttons.append(('storage_scroll_up', None, 0,
                             pygame.Rect(px + panel_w - 40, storage_start_y, 32, 22)))
    gem_tab_buttons.append(('storage_scroll_down', None, 0,
                             pygame.Rect(px + panel_w - 40, storage_start_y + storage_area_h - 2, 32, 22)))

    scroll_offset = getattr(stats, '_gem_scroll', 0)
    if scroll_offset < 0:
        scroll_offset = 0
    max_scroll = max(0, total_rows - visible_count)
    if scroll_offset > max_scroll:
        scroll_offset = max_scroll
    stats._gem_scroll = scroll_offset

    for j in range(visible_count):
        row_idx = scroll_offset + j
        if row_idx >= total_rows:
            break
        row = display_rows[row_idx]
        iy = storage_start_y + j * item_h

        if row[0] == 'header':
            # Group header row
            stat_type = row[1]
            color = COLORS.get(stat_type, (180, 180, 180))
            count = sum(1 for g in stats.gem_storage
                        if g and g['main_stat'][0] == stat_type)
            hdr_rect = pygame.Rect(px + 20, iy, panel_w - 60, header_h)
            pygame.draw.rect(screen, (22, 28, 46), hdr_rect, border_radius=4)
            hdr = font_small.render(f"{STAT_LABELS[stat_type]}  ({count})", True, color)
            screen.blit(hdr, (px + 26, iy + 2))
        else:
            # Gem row
            _, idx, gem = row
            mst = gem['main_stat']
            color = COLORS.get(mst[0], (180, 180, 180))
            item_rect = pygame.Rect(px + 20, iy, panel_w - 60, item_h)
            sel_marker = getattr(stats, '_selected_gem_idx', None)
            if sel_marker == idx:
                pygame.draw.rect(screen, (60, 70, 100), item_rect)
                pygame.draw.rect(screen, gold_color, item_rect, 1)
            else:
                pygame.draw.rect(screen, (40, 40, 55), item_rect)
                pygame.draw.rect(screen, (70, 70, 90), item_rect, 1)

            name_img = font_text.render(gem['name'], True, color)
            screen.blit(name_img, (px + 26, iy + 3))
            stat_str = f"{STAT_LABELS[mst[0]]} {STAT_FORMATS[mst[0]](mst[1])}"
            stat_img = font_small.render(stat_str, True, white)
            screen.blit(stat_img, (px + 140, iy + 6))
            lv_img = font_small.render(f"Lv.{gem['level']}", True, gold_color)
            screen.blit(lv_img, (px + panel_w - 100, iy + 6))
            gem_tab_buttons.append(('select_gem', idx, 0, item_rect))

    # ── Scroll arrows ──
    up_color = white if scroll_offset > 0 else gray
    up_img = font_small.render("Up", True, up_color)
    screen.blit(up_img, (px + panel_w - 34, storage_start_y))

    down_color = white if scroll_offset < max_scroll else gray
    down_img = font_small.render("Dn", True, down_color)
    screen.blit(down_img, (px + panel_w - 34, storage_start_y + storage_area_h - 2))

    # ── Detail panel (right side of storage) ──
    detail_bottom = py + panel_rect.height - 40
    if (hasattr(stats, '_selected_gem_idx')
            and stats._selected_gem_idx is not None
            and stats._selected_gem_idx < len(stats.gem_storage)):
        gem = stats.gem_storage[stats._selected_gem_idx]
        mst = gem['main_stat']
        color = COLORS.get(mst[0], (180, 180, 180))

        detail_y = storage_start_y + storage_area_h + 8

        d_name = font_title.render(f"{gem['name']}  Lv.{gem['level']}", True, color)
        screen.blit(d_name, (px + 20, detail_y))

        main_str = f"  {STAT_LABELS[mst[0]]}: {STAT_FORMATS[mst[0]](mst[1])} (Main)"
        main_img = font_text.render(main_str, True, gold_color)
        screen.blit(main_img, (px + 20, detail_y + 24))

        for k, (st, val) in enumerate(gem['sub_stats']):
            sub_str = f"  {STAT_LABELS[st]}: {STAT_FORMATS[st](val)}"
            sub_img = font_small.render(sub_str, True, white)
            screen.blit(sub_img, (px + 20, detail_y + 48 + k * 18))

        upgrade_cost = (gem['level']) * settings.gem_upgrade_cost_base
        can_upgrade = stats.coins >= upgrade_cost
        up_text = f"Upgrade (${upgrade_cost})"
        up_img = font_text.render(up_text, True, (0, 0, 0))
        up_bg = pygame.Surface((up_img.get_width() + 20, up_img.get_height() + 10))
        up_bg.fill(green if can_upgrade else (80, 80, 80))
        up_rect = up_bg.get_rect(topleft=(px + 20, detail_y + 90))
        screen.blit(up_bg, up_rect)
        screen.blit(up_img, (up_rect.x + 10, up_rect.y + 5))
        if can_upgrade:
            gem_tab_buttons.append(('upgrade_gem', stats._selected_gem_idx,
                                    upgrade_cost, up_rect))

        del_text = "Discard"
        del_img = font_text.render(del_text, True, (0, 0, 0))
        del_bg = pygame.Surface((del_img.get_width() + 20, del_img.get_height() + 10))
        del_bg.fill(red)
        del_rect = del_bg.get_rect(topleft=(up_rect.right + 10, detail_y + 90))
        screen.blit(del_bg, del_rect)
        screen.blit(del_img, (del_rect.x + 10, del_rect.y + 5))
        gem_tab_buttons.append(('discard_gem', stats._selected_gem_idx, 0, del_rect))

    # ── Gem stat summary ──
    summary_y = detail_bottom - 50
    bonuses = get_gem_bonuses(stats.equipped_gems)
    summary_str = "Bonus: "
    first = True
    for st in ['hp', 'defense', 'damage', 'crit_rate', 'crit_dmg', 'gold', 'penetration']:
        v = bonuses.get(st, 0)
        if v > 0:
            if not first:
                summary_str += " | "
            summary_str += f"{STAT_LABELS[st]}+{v:.1f}"
            first = False
    if not first:
        summary_img = font_small.render(summary_str, True, (200, 200, 220))
        screen.blit(summary_img, (px + 20, summary_y))

    return gem_tab_buttons


def handle_gem_tab_click(mouse_pos, stats, settings, ai_game):
    """Process clicks in the gem tab. Returns (changed, action)."""
    for action, key, cost, rect in gem_tab_buttons:
        if rect.collidepoint(mouse_pos):
            if action == 'equip_slot':
                sel = getattr(stats, '_selected_gem_idx', None)
                if sel is not None and sel < len(stats.gem_storage):
                    gem = stats.gem_storage.pop(sel)
                    if key < len(stats.equipped_gems):
                        old = stats.equipped_gems[key]
                        if old:
                            stats.gem_storage.insert(sel if sel < len(stats.gem_storage) else len(stats.gem_storage), old)
                        stats.equipped_gems[key] = gem
                    stats._selected_gem_idx = None
                    stats._gem_scroll = 0
                    stats.save_player_data()
                    ai_game._apply_gems()
                    return (True, 'gem_action')
            elif action == 'unequip_gem':
                if key < len(stats.equipped_gems) and stats.equipped_gems[key]:
                    gem = stats.equipped_gems[key]
                    stats.gem_storage.append(gem)
                    stats.equipped_gems[key] = None
                    stats.save_player_data()
                    ai_game._apply_gems()
                    return (True, 'gem_action')
            elif action == 'select_gem':
                stats._selected_gem_idx = key
            elif action == 'storage_scroll_up':
                stats._gem_scroll = max(0, getattr(stats, '_gem_scroll', 0) - 1)
            elif action == 'storage_scroll_down':
                stats._gem_scroll = getattr(stats, '_gem_scroll', 0) + 1
            elif action == 'upgrade_gem':
                if (stats.coins >= cost and key < len(stats.gem_storage)):
                    stats.coins -= cost
                    upgrade_gem(stats.gem_storage[key], settings)
                    stats.save_player_data()
                    ai_game._apply_gems()
                    return (True, 'gem_action')
            elif action == 'discard_gem':
                if key < len(stats.gem_storage):
                    stats.gem_storage.pop(key)
                    stats._selected_gem_idx = None
                    stats._gem_scroll = 0
                    stats.save_player_data()
                    return (True, 'gem_action')
            break
    return (False, None)
