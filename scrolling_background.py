import pygame

class ScrollingBackground:
    """管理无缝滚动背景的类"""
    def __init__(self, ai_game, image_path, speed=2):
        self.screen = ai_game.screen
        self.screen_rect = self.screen.get_rect()
        
        # 加载背景图像并获取其矩形
        self.image = pygame.image.load(image_path).convert_alpha()
        self.rect = self.image.get_rect()
        
        # 确保图片宽度至少覆盖屏幕（高度可以比屏幕大）
        self.bg_height = self.rect.height
        
        # 设置两张图片的初始 y 坐标
        self.y1 = 0.0
        self.y2 = -float(self.bg_height)
        
        # 背景滚动速度
        self.speed = speed

    def update(self):
        """向下滚动背景"""
        self.y1 += self.speed
        self.y2 += self.speed

        # 如果图1超出了屏幕底部，把它拼接到图2的上方
        if self.y1 >= self.screen_rect.height:
            self.y1 = self.y2 - self.bg_height

        # 如果图2超出了屏幕底部，把它拼接到图1的上方
        if self.y2 >= self.screen_rect.height:
            self.y2 = self.y1 - self.bg_height

    def draw(self):
        """在屏幕上绘制两张背景图"""
        self.screen.blit(self.image, (0, self.y1))
        self.screen.blit(self.image, (0, self.y2))