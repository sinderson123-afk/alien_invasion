import pygame
import pygame.font

from missile import create_missile_image

class Scoreboard:
    """显示得分信息的类"""

    def __init__(self, ai_game):
        """初始化显示得分涉及的属性"""
        self.ai_game = ai_game
        self.screen = ai_game.screen
        self.screen_rect = self.screen.get_rect()
        self.settings = ai_game.settings
        self.stats = ai_game.stats

        # 显示得分信息时使用的字体设置
        self.text_color = (30, 30, 30)
        self.font = pygame.font.SysFont(None, 48)
        self.small_font = pygame.font.SysFont(None, 32)

        # 表示剩余生命的爱心图像和导弹库存图标只需绘制一次
        self.heart_image = self._create_heart_image(24)
        self.missile_icon = create_missile_image(10, 22)

        # 记录上次显示的关卡，用于检测升级
        self.last_displayed_level = 1

        # 准备初始的得分、最高分、剩余生命和导弹库存图像
        self.prep_score()
        self.prep_high_score()
        self.prep_hearts()
        self.prep_missiles()
        self.prep_level()
        self.prep_coins()

    def _create_heart_image(self, size):
        """用两个圆和一个三角形在透明Surface上绘制一颗红心"""
        heart = pygame.Surface((size, size), pygame.SRCALPHA)
        color = (220, 30, 60)
        r = size // 4
        # 上半部分：两个圆
        pygame.draw.circle(heart, color, (r, r + 1), r)
        pygame.draw.circle(heart, color, (3 * r, r + 1), r)
        # 下半部分：一个倒三角形
        pygame.draw.polygon(heart, color,
                            [(0, r + 2), (size, r + 2), (size // 2, size - 1)])
        return heart

    def prep_score(self):
        """将得分渲染为图像"""
        score_str = f"{self.stats.score:,}"
        self.score_image = self.font.render(score_str, True,
                                            self.text_color, self.settings.bg_color)

        # 在屏幕右上角显示得分
        self.score_rect = self.score_image.get_rect()
        self.score_rect.right = self.screen_rect.right - 20
        self.score_rect.top = 20

    def prep_high_score(self):
        """将最高分渲染为图像"""
        high_score_str = f"{self.stats.high_score:,}"
        self.high_score_image = self.font.render(high_score_str, True,
                                                 self.text_color, self.settings.bg_color)

        # 将最高分放在屏幕顶部的中央
        self.high_score_rect = self.high_score_image.get_rect()
        self.high_score_rect.centerx = self.screen_rect.centerx
        self.high_score_rect.top = self.score_rect.top

    def prep_hearts(self):
        """根据剩余生命数准备爱心的位置"""
        self.heart_rects = []
        heart_width = self.heart_image.get_width()
        for heart_number in range(self.stats.ship_left):
            rect = self.heart_image.get_rect()
            rect.x = 20 + heart_number * (heart_width + 10)
            rect.y = 20
            self.heart_rects.append(rect)

    def prep_missiles(self):
        """将导弹库存渲染为图标加数量（位于爱心下方）"""
        self.missile_icon_rect = self.missile_icon.get_rect()
        self.missile_icon_rect.topleft = (20, 54)

        count_str = f"x {self.stats.missiles}"
        self.missile_count_image = self.small_font.render(count_str, True,
                                                          self.text_color, self.settings.bg_color)
        self.missile_count_rect = self.missile_count_image.get_rect()
        self.missile_count_rect.midleft = (self.missile_icon_rect.right + 8,
                                           self.missile_icon_rect.centery)

    def prep_coins(self):
        """将金币数渲染为图像（位于导弹库存下方）"""
        coins_str = f"$ {self.stats.coins}"
        self.coins_image = self.small_font.render(coins_str, True,
                                                    (218, 165, 32), self.settings.bg_color)
        self.coins_rect = self.coins_image.get_rect()
        self.coins_rect.topleft = (20, 78)

    def prep_level(self):
        """将关卡渲染为图像"""
        self.last_displayed_level = self.stats.level
        level_str = f"Level {self.stats.level}"
        self.level_image = self.small_font.render(level_str, True,
                                                    self.text_color, self.settings.bg_color)
        # 放在得分下方
        self.level_rect = self.level_image.get_rect()
        self.level_rect.right = self.screen_rect.right - 20
        self.level_rect.top = self.score_rect.bottom + 5

    def check_high_score(self):
        """检查是否诞生了新的最高分"""
        if self.stats.score > self.stats.high_score:
            self.stats.high_score = self.stats.score
            self.prep_high_score()

    def show_score(self):
        """在屏幕上显示得分、最高分、剩余生命、导弹库存、金币、道具状态"""
        self.screen.blit(self.score_image, self.score_rect)
        self.screen.blit(self.high_score_image, self.high_score_rect)
        for rect in self.heart_rects:
            self.screen.blit(self.heart_image, rect)
        self.screen.blit(self.missile_icon, self.missile_icon_rect)
        self.screen.blit(self.missile_count_image, self.missile_count_rect)
        self.screen.blit(self.level_image, self.level_rect)
        self.screen.blit(self.coins_image, self.coins_rect)

        # 护盾图标（如果有）
        if self.stats.items.get('shield', 0) > 0:
            shield_img = self.small_font.render(
                f"Shield: {self.stats.items['shield']}", True,
                (100, 200, 255), self.settings.bg_color)
            self.screen.blit(shield_img, (20, 100))

        # 磁铁计时（如果激活）
        if self.ai_game.magnet_active:
            mag_img = self.small_font.render(
                f"Magnet: {self.ai_game.magnet_timer // 60 + 1}s", True,
                (255, 200, 100), self.settings.bg_color)
            self.screen.blit(mag_img, (20, 120))
