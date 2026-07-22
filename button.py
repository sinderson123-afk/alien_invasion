"""菜单按钮组件：支持悬停高亮、圆角、文字阴影和自定义尺寸"""

import pygame


class Button:
    """为游戏创建按钮的类（增强版：hover、圆角、可变尺寸）"""

    def __init__(self, ai_game, msg, width=200, height=50,
                 button_color=(0, 135, 0), text_color=(255, 255, 255),
                 font_size=48, border_radius=10, hover_color=None):
        """初始化按钮的属性"""
        self.screen = ai_game.screen
        self.screen_rect = ai_game.screen.get_rect()

        # 按钮尺寸和样式
        self.width = width
        self.height = height
        self.button_color = button_color
        self.text_color = text_color
        self.shadow_color = (20, 20, 20)
        self.border_radius = border_radius
        self.font = pygame.font.SysFont(None, font_size)
        self.hover_color = hover_color or self._brighten(button_color)
        self.msg = msg  # 保存文字用于重渲染阴影

        # 创建按钮的rect对象，并使其居中
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.rect.center = self.screen_rect.center

        # 当前是否悬停
        self._hovered = False

        # 预渲染按钮标签
        self._prep_msg(msg)

    @staticmethod
    def _brighten(color, factor=0.2):
        """将颜色提亮指定比例"""
        return tuple(min(255, int(c * (1 + factor))) for c in color)

    def _prep_msg(self, msg):
        """将msg渲染为图像，并使其在按钮上居中"""
        # 文字不带背景色（透明背景），方便叠加在按钮颜色上
        self.msg_image = self.font.render(msg, True, self.text_color)
        self.msg_image_rect = self.msg_image.get_rect()
        self.msg_image_rect.center = self.rect.center

        # 阴影文字（暗色偏移版本）
        self.shadow_image = self.font.render(msg, True, self.shadow_color)
        self.shadow_rect = self.shadow_image.get_rect()
        self.shadow_rect.center = (self.rect.centerx + 1, self.rect.centery + 1)

    def check_hover(self, mouse_pos):
        """更新悬停状态，返回是否悬停"""
        self._hovered = self.rect.collidepoint(mouse_pos)
        return self._hovered

    def is_clicked(self, mouse_pos):
        """检测按钮是否被点击"""
        return self.rect.collidepoint(mouse_pos)

    def draw_button(self, mouse_pos=None):
        """绘制按钮（支持hover高亮、圆角和文字阴影）"""
        if mouse_pos is not None:
            self.check_hover(mouse_pos)

        color = self.hover_color if self._hovered else self.button_color

        # 绘制按钮主体（圆角矩形）
        pygame.draw.rect(self.screen, color, self.rect,
                         border_radius=self.border_radius)

        # 绘制边框（稍亮）
        border_color = self._brighten(color, 0.25)
        pygame.draw.rect(self.screen, border_color, self.rect,
                         width=2, border_radius=self.border_radius)

        # 绘制文字阴影（右下偏移1px）
        self.screen.blit(self.shadow_image, self.shadow_rect)

        # 绘制文字
        self.screen.blit(self.msg_image, self.msg_image_rect)
