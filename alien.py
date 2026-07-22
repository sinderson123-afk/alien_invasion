import random
import pygame
from pygame.sprite import Sprite
from settings import resource_path

class Alien(Sprite):
    """表示外星人的类：向飞船聚拢、缓慢下沉，并按调度发起俯冲"""

    def __init__(self,ai_game):
        """初始化外星人并设置其起始位置"""
        super().__init__()
        self.ai_game = ai_game            # 用于访问 meteors 等精灵组
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        # 保存飞船引用，用于聚拢目标和俯冲锁定
        self.ship = ai_game.ship
        self.stats = ai_game.stats

        # 根据当前关卡计算血量
        self.max_hp = self.settings.alien_base_hp + (
            self.stats.level - 1) * self.settings.alien_hp_per_level
        self.hp = self.max_hp

        # 加载外星人图像并缩放
        self.image = pygame.image.load(resource_path('resource/images/alien.bmp'))
        original_width, original_height = self.image.get_size()
        # 将外星人宽度缩放到屏幕宽度的 6%
        new_width = int(ai_game.screen.get_rect().width * 0.06)
        new_height = int(original_height * (new_width / original_width))
        self.image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.image.get_rect()

        # 每个外星人最初都在屏幕的左上角附近
        self.rect.x = self.rect.width
        self.rect.y = self.rect.height

        # 存储外星人的精确位置
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # 状态机：'swarm'（聚拢缓降）/ 'dive'（俯冲）/ 'climb'（爬升返回）
        self.state = 'swarm'
        # 个人聚集偏移：目标是飞船x加上该偏移，避免所有外星人叠成一列
        self.gather_offset = random.uniform(-self.settings.alien_gather_offset_range,
                                            self.settings.alien_gather_offset_range)
        # 爬升返回的目标高度
        self.cruise_y = random.uniform(self.settings.alien_cruise_y_min,
                                       self.settings.alien_cruise_y_max)
        # 俯冲速度向量（预警结束时锁定）和预警倒计时
        self.dive_velocity = None
        self.windup = 0

        # 受击闪烁计时器（帧数）
        self.flash_frames = 0

    def update(self):
        """按当前状态更新位置，并处理闪烁效果"""
        # 闪烁：每6帧切换透明度
        if self.flash_frames > 0:
            self.flash_frames -= 1
            if (self.flash_frames // 6) % 2 == 0:
                self.image.set_alpha(60)
            else:
                self.image.set_alpha(255)
        else:
            self.image.set_alpha(255)

        if self.state == 'swarm':
            self._update_swarm()
        elif self.state == 'dive':
            self._update_dive()
        elif self.state == 'climb':
            self._update_climb()

        self.rect.x = self.x
        self.rect.y = self.y

    def take_damage(self, amount):
        """受到伤害，返回True表示外星人死亡"""
        self.hp -= amount
        if self.hp <= 0:
            self.kill()
            return True
        return False

    def draw_hp_bar(self):
        """在外星人上方绘制血量条（仅在受伤后显示）"""
        if self.hp >= self.max_hp:
            return

        bar_width = self.settings.hp_bar_width
        bar_height = self.settings.hp_bar_height
        # 血条中心对齐外星人顶部
        bar_x = self.rect.centerx - bar_width // 2
        bar_y = self.rect.top - self.settings.hp_bar_offset_y

        # 背景（深灰）
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, (40, 40, 40), bg_rect)

        # 当前血量（绿→黄→红渐变）
        ratio = self.hp / self.max_hp
        if ratio > 0.5:
            color = (int(255 * (1 - ratio) * 2), 255, 0)   # 绿→黄
        else:
            color = (255, int(255 * ratio * 2), 0)           # 黄→红
        hp_rect = pygame.Rect(bar_x, bar_y, int(bar_width * ratio), bar_height)
        pygame.draw.rect(self.screen, color, hp_rect)

    def start_dive(self):
        """进入俯冲预警状态：静止若干帧后锁定飞船位置发起俯冲"""
        self.state = 'dive'
        self.windup = self.settings.alien_dive_windup
        self.dive_velocity = None

    def _update_swarm(self):
        """水平限速趋近飞船上方的个人偏移点，轨迹规避陨石，同时无条件缓降"""
        speed = self.settings.alien_speed
        target_x = self.ship.rect.centerx + self.gather_offset - self.rect.width / 2
        dx = target_x - self.x

        # ---- 陨石轨迹规避 ----
        threat_detected = False
        avoid_force = 0.0
        safety_margin = self.rect.width * 2  # 轨迹碰撞安全距离
        ax, ay = self.rect.centerx, self.rect.centery

        for meteor in self.ai_game.meteors:
            mx, my = meteor.rect.centerx, meteor.rect.centery

            # 只关心上方的陨石（可能撞到本外星人），已飞过的忽略
            if my >= ay:
                continue

            # 预测陨石到达本外星人高度时的 x 位置
            dy = ay - my
            if meteor.velocity_y <= 0:
                continue  # 陨石不下落，跳过
            time_to_reach = dy / meteor.velocity_y
            predicted_x = mx + meteor.velocity_x * time_to_reach

            # 预测位置在安全范围内 → 轨迹威胁
            if abs(predicted_x - ax) < safety_margin:
                threat_detected = True
                # 强规避：横向逃离陨石轨迹
                escape_dir = 1.0 if (predicted_x - ax) >= 0 else -1.0
                avoid_force += escape_dir * speed * 1.5
            else:
                # 不在轨迹上但仍较近 → 弱排斥
                dist_sq = (mx - ax) ** 2 + (my - ay) ** 2
                if dist_sq < self.settings.meteor_avoid_radius ** 2 and dist_sq > 0:
                    dist = dist_sq ** 0.5
                    force = (1.0 - dist / self.settings.meteor_avoid_radius) * 0.5
                    avoid_force += (ax - mx) / dist * force * speed

        # 水平移动：有威胁时规避优先（聚拢权重降到 0.2），无威胁时正常聚拢
        if threat_detected:
            self.x += max(-speed * 1.5, min(speed * 1.5, dx * 0.2 + avoid_force))
        else:
            self.x += max(-speed, min(speed, dx + avoid_force))

        # 钳制在屏幕内
        self.x = max(0.0, min(self.x, self.settings.screen_width - self.rect.width))
        # 群体压迫：持续缓慢下沉
        self.y += speed * self.settings.alien_descend_factor

    def _update_dive(self):
        """预警静止若干帧，随后沿锁定方向直线俯冲，到拉起线后转为爬升"""
        if self.windup > 0:
            self.windup -= 1
            if self.windup == 0:
                # 预警结束时才锁定飞船当前位置，给玩家留出躲避窗口
                desired = (pygame.math.Vector2(self.ship.rect.center)
                           - pygame.math.Vector2(self.rect.center))
                if desired.length_squared() == 0:
                    desired = pygame.math.Vector2(0, 1)
                self.dive_velocity = desired.normalize() * (
                    self.settings.alien_speed * self.settings.alien_dive_speed_factor)
            return

        self.x += self.dive_velocity.x
        self.y += self.dive_velocity.y
        # 钳制在屏幕内，防止高速俯冲冲出屏幕底部
        self.y = min(self.y, self.settings.screen_height - self.rect.height)

        # 到达拉起线：转为爬升，重掷巡航高度
        pullup_y = self.settings.screen_height - self.settings.alien_pullup_margin
        if self.y + self.rect.height >= pullup_y:
            self.state = 'climb'
            self.cruise_y = random.uniform(self.settings.alien_cruise_y_min,
                                           self.settings.alien_cruise_y_max)

    def _update_climb(self):
        """竖直爬升，回到巡航高度后重新加入蜂群"""
        self.y -= self.settings.alien_speed * self.settings.alien_climb_factor
        if self.y <= self.cruise_y:
            self.state = 'swarm'
            # 重掷聚集偏移，避免多次俯冲后叠成一列
            self.gather_offset = random.uniform(-self.settings.alien_gather_offset_range,
                                                self.settings.alien_gather_offset_range)
