import sys
import random
import pygame

from settings import Settings
from ship import Ship
from bullet import Bullet
from missile import Missile
from alien import Alien
from particle import Particle
from game_stats import GameStats, GameState
from scoreboard import Scoreboard
from sound import SoundManager
from boss import Boss
from coin import Coin
from video_background import VideoBackground
from menu import MenuSystem
from meteor import Meteor, MeteorFragment
import shop

class AlienInvasion:
    """管理游戏资源和行为的类"""
    def __init__(self):
        """初始化游戏并创建游戏资源"""
        pygame.init()
        # 关闭SDL文本输入模式，防止中文输入法拦截按键
        # （否则按E会唤起输入法组词，之后的方向键被候选框吃掉）
        pygame.key.stop_text_input()
        self.sound = SoundManager()
        self.clock = pygame.time.Clock()
        self.settings = Settings()
        self.screen = pygame.display.set_mode((self.settings.screen_width, self.settings.screen_height))
        pygame.display.set_caption("Alien Invasion")

        self.stats = GameStats(self)
        self.sb = Scoreboard(self)

        self.ship = Ship(self)
        self.bullets = pygame.sprite.Group()
        self.missiles = pygame.sprite.Group()
        self.aliens = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()
        self.boss_bullets = pygame.sprite.Group()
        self.coins = pygame.sprite.Group()
        self.meteors = pygame.sprite.Group()
        self.meteor_fragments = pygame.sprite.Group()
        self.boss = None                    # Boss 引用（Boss关卡时非None）

        # 状态机（替代原有的 game_active 和 shop_open）
        self.state = GameState.MENU
        self.previous_state = GameState.MENU

        # 菜单系统
        self.menu_bg = VideoBackground(self)
        self.menu_system = MenuSystem(self)

        self.hit_cooldown = 0          # 受击后的冷却帧数（期间禁止俯冲和二次碰撞）
        self.flashing_alien = None     # 正在闪烁的外星人（冷却结束后消失）
        self.flashing_alien_pos = None # 记录碰撞发生时的位置（爆炸用）
        self.levelup_anim_frames = 0   # 升级动画剩余帧数
        self.magnet_active = False        # 磁铁是否激活
        self.magnet_timer = 0             # 磁铁剩余时间
        self._boss_secondary_burst = None # Boss 第二波爆炸 (x, y, delay)
        self.meteor_timer = 0              # 陨石生成倒计时

        # 开始播放背景音乐
        self.sound.play_bgm()

    def run_game(self):
        """开始游戏的主循环"""
        while True:
            self._check_events()

            if self.state == GameState.PLAYING:
                if self.hit_cooldown > 0:
                    # 冷却期间：更新外星人（含闪烁动画）、Boss子弹和粒子，不触发碰撞检测
                    self.aliens.update()
                    self._update_boss_bullets()
                    if self.boss is not None:
                        self.boss.update()
                    self.coins.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self.meteors.update()
                    self.meteor_fragments.update()
                    self._update_meteor_collisions(skip_ship=True)
                    self._spawn_meteor()
                    self.particles.update()
                    self.hit_cooldown -= 1
                    if self.hit_cooldown == 0:
                        # 闪烁结束：消灭碰撞的外星人（在碰撞位置爆炸，而非当前位置）
                        if self.flashing_alien is not None and self.flashing_alien.alive():
                            explosion_pos = (self.flashing_alien_pos
                                             if self.flashing_alien_pos
                                             else self.flashing_alien.rect.center)
                            self._create_explosion(explosion_pos)
                            self._maybe_drop_coin(*explosion_pos)
                            self.flashing_alien.kill()
                            self.sound.play_explosion()
                            self._award_points(1)
                        self.flashing_alien = None
                        self.flashing_alien_pos = None
                else:
                    self.ship.update()
                    self._update_bullets()
                    self._update_missiles()
                    self._update_boss_bullets()
                    if self.boss is not None:
                        self.boss.update()
                    self._update_aliens()
                    self.coins.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self.meteors.update()
                    self.meteor_fragments.update()
                    self._update_meteor_collisions(skip_ship=False)
                    self._spawn_meteor()
                    self.particles.update()

                    # Boss 第二波爆炸
                    if self._boss_secondary_burst is not None:
                        bx, by, delay = self._boss_secondary_burst
                        delay -= 1
                        if delay <= 0:
                            s = self.settings
                            for _ in range(s.boss_secondary_count):
                                p = Particle(self, bx, by,
                                             size_mult=s.boss_particle_size_mult * 0.7,
                                             speed_mult=s.boss_particle_speed_mult * 1.2,
                                             lifetime_mult=s.boss_particle_lifetime_mult * 0.7,
                                             colors=s.boss_particle_colors)
                                self.particles.add(p)
                            self._boss_secondary_burst = None
                        else:
                            self._boss_secondary_burst = (bx, by, delay)

            elif self.state == GameState.MENU:
                self.menu_bg.update()

            elif self.state == GameState.TUTORIAL:
                self.menu_bg.update()

            elif self.state == GameState.SHOP:
                # 从菜单进入商店时继续更新背景；从游戏进入则冻结
                if self.previous_state == GameState.MENU:
                    self.menu_bg.update()

            # PAUSED: 不更新任何实体

            self._update_screen()
            self.clock.tick(60)

    def _check_events(self):
        """响应按键和鼠标事件（按当前状态路由）"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit_game()
            elif event.type == pygame.KEYDOWN:
                self._check_keydown_events(event)
            elif event.type == pygame.KEYUP:
                self._check_keyup_events(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                self._check_mouse_click(mouse_pos)

    def _check_mouse_click(self, mouse_pos):
        """根据当前状态路由鼠标点击事件"""
        if self.state == GameState.MENU:
            action = self.menu_system.handle_menu_click(mouse_pos)
            if action == 'start':
                self._start_new_game()
            elif action == 'shop':
                self.previous_state = GameState.MENU
                self.state = GameState.SHOP
            elif action == 'tutorial':
                self.state = GameState.TUTORIAL

        elif self.state == GameState.PAUSED:
            action = self.menu_system.handle_pause_click(mouse_pos)
            if action == 'resume':
                self.state = GameState.PLAYING
                self.ship.moving_right = False
                self.ship.moving_left = False
                self.sound.set_bgm_volume(self.settings.bgm_volume)
            elif action == 'quit_to_menu':
                self._return_to_menu()
            elif action == 'exit':
                self._quit_game()

        elif self.state == GameState.SHOP:
            changed, action = shop.handle_shop_click(
                mouse_pos, self.stats, self.settings)
            if action == 'close':
                self.state = self.previous_state
            elif changed:
                self.sb.prep_coins()
                self._apply_skills()

        elif self.state == GameState.TUTORIAL:
            action = self.menu_system.handle_tutorial_click(mouse_pos)
            if action == 'back':
                self.state = GameState.MENU

        # PLAYING 状态下鼠标点击暂不处理

    def _apply_skills(self):
        """根据技能等级调整游戏设置（在 initialize_dynamic_settings 之后调用）"""
        skills = self.stats.skills
        s = self.settings
        s.ship_speed *= (1 + skills['speed'] * 0.1)
        s.bullet_allowed = 3 + skills['ammo']
        # vitality（生命上限）已在 GameStats.reset_stats 中处理

    def _quit_game(self):
        """保存最高分和玩家数据并退出游戏"""
        self.sound.stop_bgm()
        self.stats.save_high_score()
        self.stats.save_player_data()
        sys.exit()

    def _start_new_game(self):
        """开始一场新游戏：重置所有游戏状态并切换到 PLAYING"""
        self.settings.initialize_dynamic_settings()
        self.stats.reset_stats()
        self._apply_skills()
        self.hit_cooldown = 0
        self.flashing_alien = None
        self.flashing_alien_pos = None
        self.sb.prep_score()
        self.sb.prep_hearts()
        self.sb.prep_missiles()
        self.sb.prep_level()
        self.sb.prep_coins()

        # 清空所有游戏实体
        self.bullets.empty()
        self.missiles.empty()
        self.aliens.empty()
        self.boss_bullets.empty()
        self.meteors.empty()
        self.meteor_fragments.empty()
        self.meteor_timer = self.settings.meteor_spawn_interval
        self.boss = None

        # 创建舰队，放置飞船
        self._create_fleet()
        self.ship.center_ship()

        # 切换到游戏状态
        self.state = GameState.PLAYING
        self.sound.set_bgm_volume(self.settings.bgm_volume)

    def _return_to_menu(self):
        """返回主菜单：保存数据，清理游戏实体，切换状态"""
        self.stats.save_high_score()
        self.bullets.empty()
        self.missiles.empty()
        self.aliens.empty()
        self.boss_bullets.empty()
        self.meteors.empty()
        self.meteor_fragments.empty()
        self.boss = None
        self.state = GameState.MENU
        self.sound.set_bgm_volume(self.settings.bgm_volume)

    def _check_keydown_events(self, event):
        """响应按键按下（按当前状态路由）"""
        # ---------- 全状态通用 ----------
        if event.key == pygame.K_q:
            self._quit_game()

        # ---------- MENU 状态 ----------
        elif self.state == GameState.MENU:
            if event.key == pygame.K_ESCAPE:
                self._quit_game()

        # ---------- PLAYING 状态 ----------
        elif self.state == GameState.PLAYING:
            if event.key == pygame.K_ESCAPE:
                # 暂停并清除移动标志
                self.ship.moving_right = False
                self.ship.moving_left = False
                self.state = GameState.PAUSED
                self.sound.set_bgm_volume(self.settings.bgm_pause_volume)
            elif event.key == pygame.K_RIGHT:
                self.ship.moving_right = True
            elif event.key == pygame.K_LEFT:
                self.ship.moving_left = True
            elif event.key == pygame.K_SPACE:
                self._fire_bullet()
            elif event.key == pygame.K_e:
                self._fire_missile()
            elif event.key == pygame.K_m:
                self.previous_state = GameState.PLAYING
                self.state = GameState.SHOP
            elif event.key == pygame.K_n:
                self._activate_magnet()

        # ---------- PAUSED 状态 ----------
        elif self.state == GameState.PAUSED:
            if event.key == pygame.K_ESCAPE:
                self.state = GameState.PLAYING
                self.sound.set_bgm_volume(self.settings.bgm_volume)

        # ---------- SHOP 状态 ----------
        elif self.state == GameState.SHOP:
            if event.key in (pygame.K_m, pygame.K_ESCAPE):
                self.state = self.previous_state

        # ---------- TUTORIAL 状态 ----------
        elif self.state == GameState.TUTORIAL:
            if event.key == pygame.K_ESCAPE:
                self.state = GameState.MENU

    def _check_keyup_events(self, event):
        """响应按键释放（仅 PLAYING 状态下处理移动键）"""
        if self.state == GameState.PLAYING:
            if event.key == pygame.K_RIGHT:
                self.ship.moving_right = False
            elif event.key == pygame.K_LEFT:
                self.ship.moving_left = False

    def _update_bullets(self):
        """更新子弹的位置并删除已消失的子弹"""
        # 更新子弹的位置
        self.bullets.update()

        # 删除已消失的子弹
        for bullet in self.bullets.copy():
            if bullet.rect.bottom <= 0:
                self.bullets.remove(bullet)

        self._check_bullet_alien_collisions()
        self._check_bullet_boss_collisions()

    def _check_bullet_alien_collisions(self):
        """响应子弹和外星人的碰撞：扣血，死则爆炸并计分"""
        # dokill1=False: 不再直接移除，改为伤害系统
        collisions = pygame.sprite.groupcollide(self.aliens, self.bullets, False, True)
        for alien, bullets in collisions.items():
            # 同一帧内多颗子弹命中则伤害累加
            total_damage = self.settings.bullet_damage * len(bullets)
            if alien.take_damage(total_damage):
                self._create_explosion(alien.rect.center)
                self._maybe_drop_coin(*alien.rect.center)
                self.sound.play_explosion()
                self._award_points(1)
            else:
                self.sound.play_hurt()

        self._check_fleet_cleared()

    def _update_missiles(self):
        """更新导弹的位置并删除已飞出屏幕的导弹"""
        self.missiles.update()

        # 删除已飞出屏幕的导弹
        screen_rect = self.screen.get_rect()
        for missile in self.missiles.copy():
            if not screen_rect.colliderect(missile.rect):
                self.missiles.remove(missile)

        self._check_missile_alien_collisions()
        self._check_missile_boss_collisions()

    def _update_boss_bullets(self):
        """更新Boss子弹位置并删除已飞出屏幕的子弹"""
        self.boss_bullets.update()
        for bullet in self.boss_bullets.copy():
            if bullet.rect.top > self.settings.screen_height:
                self.boss_bullets.remove(bullet)

    def _check_missile_alien_collisions(self):
        """响应导弹和外星人的碰撞：对爆炸范围内的外星人造成范围伤害"""
        collisions = pygame.sprite.groupcollide(self.missiles, self.aliens, True, False)
        for missile in collisions:
            self._explode_missile(missile.rect.center)

        self._check_fleet_cleared()

    def _explode_missile(self, center):
        """对爆炸半径内的外星人和Boss造成伤害，阵亡的生成爆炸粒子并计分"""
        # 导弹命中点的大型爆炸粒子
        self._create_missile_explosion(center)

        blast_center = pygame.math.Vector2(center)
        destroyed = 0
        for alien in self.aliens.sprites():
            if blast_center.distance_to(alien.rect.center) <= self.settings.missile_blast_radius:
                if alien.take_damage(self.settings.missile_damage):
                    self._create_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    destroyed += 1
                    self.sound.play_explosion()
                else:
                    self.sound.play_hurt()
        # 同时检查Boss是否在爆炸范围内
        if self.boss is not None and self.boss.hp > 0:
            if blast_center.distance_to(self.boss.rect.center) <= self.settings.missile_blast_radius:
                if self.boss.take_damage(self.settings.missile_damage):
                    self._create_explosion(self.boss.rect.center)
                    self._maybe_drop_coin(*self.boss.rect.center)
                    destroyed += 1
                    self.sound.play_explosion()
                else:
                    self.sound.play_hurt()
        if destroyed:
            self._award_points(destroyed)

    def _award_points(self, alien_count):
        """按击落的外星人数量累加得分并更新相关显示"""
        self.stats.score += self.settings.alien_points * alien_count
        self.stats.kills += alien_count
        self.sb.prep_score()
        self.sb.check_high_score()
        self._check_missile_award()
        self._check_level_up()

    def _check_missile_award(self):
        """每当分数跨过missile_score_step的新整数倍，就奖励相应数量的导弹"""
        earned = self.stats.score // self.settings.missile_score_step
        if earned > self.stats.missiles_awarded:
            self.stats.missiles += earned - self.stats.missiles_awarded
            self.stats.missiles_awarded = earned
            self.sb.prep_missiles()

    def _check_level_up(self):
        """检测击杀数是否跨过升关门槛，若升级则更新记分牌并启动动画"""
        if self.stats.level > self.sb.last_displayed_level:
            self.sb.prep_level()
            self.levelup_anim_frames = 60   # 1秒动画
            self.sound.play_levelup()

    def _draw_levelup_animation(self):
        """在屏幕中央绘制渐隐放大的升级文字"""
        self.levelup_anim_frames -= 1
        ratio = self.levelup_anim_frames / 60

        # 计算透明度（前80%不透明，最后20%渐隐）
        alpha = 255 if ratio > 0.2 else int(255 * ratio / 0.2)

        # 计算缩放比例（1.0 → 1.5 逐渐放大）
        scale = 1.0 + (1 - ratio) * 0.5

        font = pygame.font.SysFont(None, int(72 * scale))
        level_str = f"Level {self.stats.level}!"
        text_image = font.render(level_str, True, (255, 215, 0))
        text_image.set_alpha(alpha)
        text_rect = text_image.get_rect(center=self.screen.get_rect().center)
        # 向上偏移，避免遮挡游戏画面中央
        text_rect.y -= 40
        self.screen.blit(text_image, text_rect)

    def _check_missile_boss_collisions(self):
        """检测导弹爆炸是否伤到了Boss"""
        if self.boss is None or self.boss.hp <= 0:
            return
        # 导弹直接撞击Boss本体
        for missile in self.missiles.sprites():
            # 导弹碰到Boss
            if missile.rect.colliderect(self.boss.rect):
                if self.boss.take_damage(self.settings.missile_damage):
                    self._create_explosion(self.boss.rect.center)
                    self._maybe_drop_coin(*self.boss.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
                else:
                    self.sound.play_hurt()
                self.missiles.remove(missile)
                self._check_fleet_cleared()
                break

    def _check_bullet_boss_collisions(self):
        """检测子弹是否击中了Boss"""
        if self.boss is None or self.boss.hp <= 0:
            return
        for bullet in self.bullets.sprites():
            if bullet.rect.colliderect(self.boss.rect):
                self.bullets.remove(bullet)
                if self.boss.take_damage(self.settings.bullet_damage):
                    self._create_explosion(self.boss.rect.center)
                    self._maybe_drop_coin(*self.boss.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
                    self._check_fleet_cleared()
                else:
                    self.sound.play_hurt()
                break  # 每帧只处理一次命中

    def _check_boss_bullet_ship_collisions(self):
        """检测Boss子弹是否击中了飞船"""
        if self.ship.invulnerable_frames > 0:
            return
        for bullet in self.boss_bullets.sprites():
            if bullet.rect.colliderect(self.ship.rect):
                self.boss_bullets.remove(bullet)
                self._ship_hit(None)
                break

    def _check_fleet_cleared(self):
        """在整支舰队（或Boss）被消灭后开始新的一波"""
        if self.boss is not None:
            # Boss关：Boss HP归零进入死亡动画，动画结束后清关
            if self.boss.dying and self.boss.death_timer <= 0:
                # 触发爆炸和音效
                self.sound.play_boss_destroy()
                self._create_boss_explosion(self.boss.rect.center)
                self._maybe_drop_coin(*self.boss.rect.center)
                self.boss.kill()
                self.boss = None
                # Boss击杀奖励：补足分数和击杀数以退出本关
                self.stats.score += self.settings.boss_points
                threshold = self.stats.level * self.settings.kills_per_level
                if self.stats.kills < threshold:
                    self.stats.kills = threshold
                self.sb.prep_score()
                self.sb.check_high_score()
                self._check_missile_award()
                self._check_level_up()
                self.bullets.empty()
                self.boss_bullets.empty()
                self._create_fleet()
                self.settings.increase_speed()
        elif not self.aliens:
            # 普通关：外星人全灭即清关
            self.bullets.empty()
            self._create_fleet()
            self.settings.increase_speed()


    def _fire_bullet(self):
        """创建一颗子弹，并将其编入bullets"""
        if len(self.bullets) < self.settings.bullet_allowed:
            new_bullet = Bullet(self)
            self.bullets.add(new_bullet)
            self.sound.play_shoot()

    def _fire_missile(self):
        """若还有导弹库存，就发射一枚追踪导弹"""
        if self.state == GameState.PLAYING and self.stats.missiles > 0:
            self.missiles.add(Missile(self))
            self.stats.missiles -= 1
            self.sound.play_missile()
            self.sb.prep_missiles()

    def _create_fleet(self):
        """在屏幕上方随机散布一波外星舰队（Boss关只生成Boss）"""
        # Boss关：每5关一次
        if self.stats.level % 5 == 0:
            self.boss = Boss(self)
            self.sound.play_alarm()
        else:
            self.boss = None
            alien = Alien(self)
            alien_width = alien.rect.width
            for _ in range(self.settings.aliens_per_wave):
                x_position = random.randint(0, self.settings.screen_width - alien_width)
                y_position = random.randint(self.settings.alien_spawn_y_min,
                                            self.settings.alien_spawn_y_max)
                self._create_alien(x_position, y_position)

        # 每波开始时重置俯冲调度计时器
        self.dive_timer = self.settings.alien_dive_cooldown

    def _create_alien(self,x_position, y_position):
        """在指定位置创建一个外星人"""
        new_alien = Alien(self)
        new_alien.x = float(x_position)
        new_alien.y = float(y_position)
        new_alien.rect.x = x_position
        new_alien.rect.y = y_position
        self.aliens.add(new_alien)

    def _activate_magnet(self):
        """激活磁铁道具"""
        if self.stats.items.get('magnet', 0) > 0 and not self.magnet_active:
            self.stats.items['magnet'] -= 1
            self.magnet_active = True
            self.magnet_timer = self.settings.magnet_duration
            self.stats.save_player_data()

    def _update_magnet(self):
        """更新磁铁状态：计时 + 吸引附近金币"""
        if not self.magnet_active:
            return
        self.magnet_timer -= 1
        if self.magnet_timer <= 0:
            self.magnet_active = False
            return
        # 吸引半径内的金币飞向飞船
        ship_center = pygame.math.Vector2(self.ship.rect.center)
        for coin in self.coins.sprites():
            dist = ship_center.distance_to(coin.rect.center)
            if dist <= self.settings.magnet_pickup_radius:
                # 金币飞向飞船
                direction = ship_center - pygame.math.Vector2(coin.rect.center)
                if direction.length_squared() > 0:
                    direction.normalize_ip()
                    coin.y += direction.y * 5
                    coin.rect.y = int(coin.y)
                    coin.rect.x += int(direction.x * 5)

    def _check_coin_pickup(self):
        """检测飞船是否拾取了金币"""
        picked = pygame.sprite.spritecollide(self.ship, self.coins, True)
        if picked:
            self.stats.coins += len(picked)
            self.sb.prep_coins()

    def _maybe_drop_coin(self, x, y):
        """按概率在指定位置掉落金币"""
        if random.random() < self.settings.coin_drop_rate:
            self.coins.add(Coin(self, x, y))

    # ------------------------------------------------------------------
    # 陨石系统
    # ------------------------------------------------------------------

    def _spawn_meteor(self):
        """计时器归零时在屏幕顶部生成新陨石"""
        self.meteor_timer -= 1
        if self.meteor_timer <= 0:
            self.meteors.add(Meteor(self))
            self.meteor_timer = self.settings.meteor_spawn_interval

    def _update_meteor_collisions(self, skip_ship=False):
        """检测陨石和碎片与所有实体的碰撞"""
        s = self.settings

        # ---- 陨石 ↔ 飞船 ----
        if not skip_ship and self.ship.invulnerable_frames <= 0:
            hit = pygame.sprite.spritecollideany(self.ship, self.meteors)
            if hit:
                self._meteor_break(hit)
                self._ship_hit(None)

        # ---- 碎片 ↔ 飞船 ----
        if not skip_ship and self.ship.invulnerable_frames <= 0:
            hit_frag = pygame.sprite.spritecollideany(self.ship, self.meteor_fragments)
            if hit_frag:
                hit_frag.kill()
                self._ship_hit(None)

        # ---- 陨石 + 碎片 ↔ 外星人 ----
        for meteor in self.meteors:
            collisions = pygame.sprite.spritecollide(meteor, self.aliens, False)
            for alien in collisions:
                self._meteor_break(meteor)
                if alien.take_damage(s.meteor_alien_damage):
                    self._create_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
                else:
                    self.sound.play_hurt()
                break  # 陨石已碎，跳出内层循环
            else:
                continue
            break  # 陨石已碎，跳出外层循环

        for frag in self.meteor_fragments:
            collisions = pygame.sprite.spritecollide(frag, self.aliens, False)
            for alien in collisions:
                frag.kill()
                if alien.take_damage(s.meteor_fragment_damage):
                    self._create_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
                else:
                    self.sound.play_hurt()
                break

        # ---- 陨石 + 碎片 ↔ Boss ----
        if self.boss is not None and not self.boss.dying:
            for meteor in self.meteors:
                if meteor.rect.colliderect(self.boss.rect):
                    self._meteor_break(meteor)
                    self.boss.take_damage(s.meteor_boss_damage)
                    self.sound.play_hurt()
                    break

            for frag in self.meteor_fragments:
                if frag.rect.colliderect(self.boss.rect):
                    frag.kill()
                    self.boss.take_damage(s.meteor_fragment_damage)
                    self.sound.play_hurt()
                    break

        # ---- 陨石 ↔ 子弹 ----
        for meteor in self.meteors:
            bullet_hits = pygame.sprite.spritecollide(meteor, self.bullets, True)
            if bullet_hits and meteor.take_damage(len(bullet_hits)):
                self._meteor_break(meteor)
                self.stats.score += s.meteor_points
                self.sb.prep_score()
                self.sb.check_high_score()

        # ---- 碎片 ↔ 子弹 ----
        pygame.sprite.groupcollide(
            self.meteor_fragments, self.bullets, True, True)

        # ---- 陨石 ↔ 导弹爆炸 ----
        for missile in self.missiles:
            for meteor in self.meteors:
                if missile.rect.colliderect(meteor.rect):
                    if meteor.take_damage(s.missile_damage):
                        self._meteor_break(meteor)
                        self.stats.score += s.meteor_points
                        self.sb.prep_score()
                        self.sb.check_high_score()

    def _meteor_break(self, meteor):
        """陨石碎裂：生成碎片 + 粒子火花 + 音效"""
        cx, cy = meteor.rect.center
        s = self.settings

        # 生成碎片
        for _ in range(s.meteor_fragment_count):
            self.meteor_fragments.add(MeteorFragment(self, cx, cy))

        # 粒子火花
        rock_colors = [(180, 140, 100), (150, 120, 80), (200, 160, 120), (120, 90, 60)]
        for _ in range(s.particle_count):
            p = Particle(self, cx, cy,
                         size_mult=1.5, speed_mult=1.2,
                         colors=rock_colors)
            self.particles.add(p)

        self.sound.play_explosion()
        meteor.kill()

    # ------------------------------------------------------------------
    # 爆炸
    # ------------------------------------------------------------------

    def _create_explosion(self, position):
        """在指定位置生成爆炸粒子（子弹击杀用）"""
        for _ in range(self.settings.particle_count):
            particle = Particle(self, position[0], position[1])
            self.particles.add(particle)

    def _create_missile_explosion(self, position):
        """在导弹命中点生成大型爆炸粒子"""
        s = self.settings
        for _ in range(s.missile_particle_count):
            p = Particle(self, position[0], position[1],
                         size_mult=s.missile_particle_size_mult,
                         speed_mult=s.missile_particle_speed_mult,
                         colors=s.missile_particle_colors)
            self.particles.add(p)

    def _create_boss_explosion(self, position):
        """Boss 击杀爆炸：主爆炸 + 延迟第二波"""
        s = self.settings
        # 主爆炸
        for _ in range(s.boss_particle_count):
            p = Particle(self, position[0], position[1],
                         size_mult=s.boss_particle_size_mult,
                         speed_mult=s.boss_particle_speed_mult,
                         lifetime_mult=s.boss_particle_lifetime_mult,
                         colors=s.boss_particle_colors)
            self.particles.add(p)
        # 记录第二波延迟爆发
        self._boss_secondary_burst = (position[0], position[1],
                                       s.boss_secondary_delay)

    def _draw_game_scene(self):
        """绘制所有游戏实体（不包括暂停/菜单覆盖层）"""
        self.screen.fill(self.settings.bg_color)
        for bullet in self.bullets.sprites():
            bullet.draw_bullet()
        self.missiles.draw(self.screen)
        self.ship.blitme()
        self.aliens.draw(self.screen)
        for alien in self.aliens.sprites():
            alien.draw_hp_bar()
        self.boss_bullets.draw(self.screen)
        if self.boss is not None:
            self.screen.blit(self.boss.image, self.boss.rect)
            self.boss.draw_hp_bar()
        self.coins.draw(self.screen)
        self.meteors.draw(self.screen)
        self.meteor_fragments.draw(self.screen)
        self.particles.draw(self.screen)

        # 显示得分信息
        self.sb.show_score()

        # 升级动画
        if self.levelup_anim_frames > 0:
            self._draw_levelup_animation()

    def _update_screen(self):
        """更新屏幕上的图像（按当前状态路由渲染）"""
        if self.state == GameState.MENU:
            self.menu_bg.draw()
            self.menu_system.draw_start_screen(pygame.mouse.get_pos())

        elif self.state in (GameState.PLAYING, GameState.PAUSED):
            self._draw_game_scene()
            if self.state == GameState.PAUSED:
                self.menu_system.draw_pause_overlay(pygame.mouse.get_pos())

        elif self.state == GameState.SHOP:
            # 商店背景：来自游戏则显示冻结画面，来自菜单则显示视频背景
            if self.previous_state == GameState.PLAYING:
                self._draw_game_scene()
            else:
                self.menu_bg.draw()
            shop.draw_shop(self.screen, self.stats, self.settings)

        elif self.state == GameState.TUTORIAL:
            self.menu_bg.draw()
            self.menu_system.draw_tutorial(pygame.mouse.get_pos())

        pygame.display.flip()

    def _update_aliens(self):
        """更新所有外星人的位置，并调度俯冲攻击"""
        self.aliens.update()
        self._update_alien_dives()

        # 检测 Boss 子弹和飞船的碰撞
        self._check_boss_bullet_ship_collisions()

        # 检测外星人和飞船之间的碰撞（无敌期间不触发）
        if self.ship.invulnerable_frames == 0:
            colliding_alien = pygame.sprite.spritecollideany(self.ship, self.aliens)
            if colliding_alien:
                self._ship_hit(colliding_alien)

        # 检查是否有外星人到达了屏幕的下边缘
        self._check_aliens_bottom()

    def _update_alien_dives(self):
        """密度调度：冷却结束后让最密集集群中位置最低的外星人发起俯冲"""
        # 受击冷却期间禁止俯冲
        if self.hit_cooldown > 0:
            return
        self.dive_timer -= 1
        if self.dive_timer > 0:
            return

        # 同时俯冲的外星人达到上限时，稍后重试
        divers = sum(1 for alien in self.aliens.sprites() if alien.state == 'dive')
        if divers >= self.settings.alien_max_divers:
            self.dive_timer = self.settings.alien_dive_retry
            return

        # 只有蜂群状态、且位于俯冲高度线以上的外星人才有资格俯冲
        swarm = [alien for alien in self.aliens.sprites() if alien.state == 'swarm']
        eligible = [alien for alien in swarm
                    if alien.rect.bottom <= self.settings.alien_dive_max_start_y]

        # 找出邻域内其他蜂群外星人最多的合格外星人
        radius_sq = self.settings.alien_cluster_radius ** 2
        best_alien, best_neighbors = None, []
        for alien in eligible:
            center = pygame.math.Vector2(alien.rect.center)
            neighbors = [other for other in swarm if other is not alien
                         and center.distance_squared_to(other.rect.center) <= radius_sq]
            if best_alien is None or len(neighbors) > len(best_neighbors):
                best_alien, best_neighbors = alien, neighbors

        if best_alien is not None and len(best_neighbors) >= self.settings.alien_cluster_size:
            # 该集群中位置最低的合格成员发起俯冲
            cluster = [best_alien] + [alien for alien in best_neighbors
                                      if alien in eligible]
            diver = max(cluster, key=lambda alien: alien.rect.bottom)
            diver.start_dive()
            self.dive_timer = self.settings.alien_dive_cooldown
        else:
            # 没有达到密度阈值的集群，稍后重试
            self.dive_timer = self.settings.alien_dive_retry

    def _ship_hit(self, colliding_alien=None):
        """响应飞船和外星人（或Boss子弹）的碰撞"""
        # 护盾拦截：消耗一个护盾，免疫本次伤害
        if self.stats.items.get('shield', 0) > 0:
            self.stats.items['shield'] -= 1
            self.stats.save_player_data()
            self.ship.invulnerable_frames = self.settings.invulnerable_duration
            self.sound.play_hit()
            return

        if self.stats.ship_left > 0:
            # 将ship_left减1，并更新剩余生命显示
            self.stats.ship_left -= 1
            self.sb.prep_hearts()

            # 启动飞船闪烁
            self.ship.invulnerable_frames = self.settings.invulnerable_duration

            # 碰撞源闪烁（Boss子弹命中时无碰撞源，仅飞船闪烁+重置舰队）
            if colliding_alien is not None:
                colliding_alien.flash_frames = self.settings.invulnerable_duration
                self.flashing_alien = colliding_alien
                self.flashing_alien_pos = colliding_alien.rect.center
                # 进入冷却（期间禁止俯冲和二次碰撞，舰队保持原样）
                self.hit_cooldown = self.settings.invulnerable_duration
            else:
                # Boss子弹命中：仅扣命+闪烁，不重置Boss和舰队
                self.flashing_alien = None
                self.hit_cooldown = self.settings.invulnerable_duration

            self.sound.play_hit()

        else:
            self._return_to_menu()

    def _check_aliens_bottom(self):
        """检查是否有蜂群状态的外星人达到了屏幕下边缘"""
        # 俯冲/爬升中的外星人由拉起线管理，不触发触底判定
        for alien in self.aliens.sprites():
            if alien.state == 'swarm' and alien.rect.bottom >= self.settings.screen_height:
                # 外星人触底：舰队重置（与碰撞闪烁不同）
                self._aliens_reached_bottom()
                break

    def _aliens_reached_bottom(self):
        """外星人触底：扣命并重置舰队"""
        if self.stats.ship_left > 0:
            self.stats.ship_left -= 1
            self.sb.prep_hearts()
            self.ship.invulnerable_frames = self.settings.invulnerable_duration

            self.bullets.empty()
            self.missiles.empty()
            self.aliens.empty()
            self._create_fleet()
            self.ship.center_ship()
        else:
            self._return_to_menu()

if __name__ == "__main__":
    # 创建游戏实例并运行游戏
    ai = AlienInvasion()
    ai.run_game()
