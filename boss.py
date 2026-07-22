import pygame
from pygame.sprite import Sprite
from settings import resource_path


class Boss(Sprite):
    """Boss 外星人：高血量、左右移动、周期性发射红色子弹"""

    def __init__(self, ai_game):
        """初始化 Boss 并设置起始位置"""
        super().__init__()
        self.ai_game = ai_game
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.stats = ai_game.stats
        # 保存 boss_bullets 编组引用，用于发射子弹
        self.boss_bullets = ai_game.boss_bullets

        # 加载 Boss 图像并缩放
        self.image = pygame.image.load(resource_path('resource/images/boss.bmp'))
        original_width, original_height = self.image.get_size()
        new_width = int(ai_game.screen.get_rect().width * 0.15)
        new_height = int(original_height * (new_width / original_width))
        self.image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.image.get_rect()

        # 初始位置：屏幕顶部居中
        self.rect.midtop = ai_game.screen.get_rect().midtop
        self.rect.y = 80
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # Boss 血量 = 同关外星人血量 × 20
        base_hp = self.settings.alien_base_hp + (
            self.stats.level - 1) * self.settings.alien_hp_per_level
        self.max_hp = base_hp * self.settings.boss_hp_multiplier
        self.hp = self.max_hp

        # 移动方向：1 向右，-1 向左
        self.direction = 1
        # 射击计时器
        self.fire_timer = self.settings.boss_fire_interval

        # 闪烁计时器（飞船碰撞时使用）
        self.flash_frames = 0

        # 死亡动画状态
        self.dying = False              # 是否处于死亡动画中
        self.death_timer = 0            # 死亡动画倒计时
        self._death_exploded = False    # 是否已触发爆炸（防止重复）

    def update(self):
        """左右移动并周期性发射子弹（死亡动画期间只运行闪烁）"""
        if self.dying:
            self._update_death_animation()
            return

        # 闪烁处理
        if self.flash_frames > 0:
            self.flash_frames -= 1
            if (self.flash_frames // 6) % 2 == 0:
                self.image.set_alpha(60)
            else:
                self.image.set_alpha(255)
        else:
            self.image.set_alpha(255)

        # 水平移动
        speed = self.settings.alien_speed * self.settings.boss_speed_factor
        self.x += speed * self.direction
        self.rect.x = int(self.x)

        # 碰到屏幕边缘反弹（必须在 rect 更新后检查）
        if self.rect.right >= self.settings.screen_width:
            self.direction = -1
        elif self.rect.left <= 0:
            self.direction = 1

        # 射击
        self.fire_timer -= 1
        if self.fire_timer <= 0:
            self._fire()
            self.fire_timer = self.settings.boss_fire_interval

    def _update_death_animation(self):
        """死亡动画：悬停 → 加速闪烁 → 最终爆炸"""
        self.death_timer -= 1

        elapsed = self.settings.boss_death_flash_frames - self.death_timer

        if elapsed < self.settings.boss_death_slow_frames:
            # 悬停阶段：保持可见，不闪
            self.image.set_alpha(255)
        else:
            # 加速闪烁：每 3 帧切换（正常是每 6 帧）
            if (self.death_timer // 3) % 2 == 0:
                self.image.set_alpha(40)
            else:
                self.image.set_alpha(255)

    def _fire(self):
        """从 Boss 底部中央发射一颗子弹"""
        from boss_bullet import BossBullet
        bullet = BossBullet(self.ai_game, self.rect.centerx, self.rect.bottom)
        self.boss_bullets.add(bullet)

    def take_damage(self, amount):
        """受到伤害，返回True表示 Boss 被击杀（进入死亡动画）"""
        self.hp -= amount
        if self.hp <= 0 and not self.dying:
            self.hp = 0
            self.dying = True
            self.death_timer = self.settings.boss_death_flash_frames
            self._death_exploded = False
            return True
        return False

    def draw_hp_bar(self):
        """在 Boss 上方绘制血量条"""
        bar_width = self.settings.boss_hp_bar_width
        bar_height = self.settings.boss_hp_bar_height
        bar_x = self.rect.centerx - bar_width // 2
        bar_y = self.rect.top - self.settings.boss_hp_bar_offset_y

        # 背景
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, (40, 40, 40), bg_rect)

        # 当前血量（绿→黄→红）
        ratio = self.hp / self.max_hp
        if ratio > 0.5:
            color = (int(255 * (1 - ratio) * 2), 255, 0)
        else:
            color = (255, int(255 * ratio * 2), 0)
        hp_rect = pygame.Rect(bar_x, bar_y, int(bar_width * ratio), bar_height)
        pygame.draw.rect(self.screen, color, hp_rect)
