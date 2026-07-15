import pygame

class Ship:
    """管理飞船的类"""
    def __init__(self,ai_game):
        """初始化飞船并设置其初始位置"""
        self.screen = ai_game.screen
        self.screen_rect = ai_game.screen.get_rect()

        # 加载飞船图像并缩放
        self.image = pygame.image.load("images/ship.bmp")
        original_width, original_height = self.image.get_size()
        # 将飞船宽度缩放到屏幕宽度的 8%
        new_width = int(self.screen_rect.width * 0.08)
        new_height = int(original_height * (new_width / original_width))
        self.image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.image.get_rect()

        # 每艘新飞船都放在屏幕底部的中央
        self.rect.midbottom =self.screen_rect.midbottom

        # 移动标志
        self.moving_right = False

    def update(self):
        if self.moving_right:
            self.rect.x += 1

    def blitme(self):
        """在指定位置绘制飞船"""
        self.screen.blit(self.image,self.rect)