class Settings:
    """存储游戏《外星人入侵》中所有设置的类"""
    def __init__(self):
        """初始化游戏的设置"""
        # 屏幕设置
        self.screen_width = 1200
        self.screen_height = 800
        self.bg_color = (230, 230, 230)

        # 飞船设置
        self.ship_speed = 1.5
        self.ship_limit = 3

        # 子弹设置
        self.bullet_speed = 2.5
        self.bullet_width = 3
        self.bullet_height = 15
        self.bullet_color = (60, 60, 60)
        self.bullet_allowed = 3

        # 外星人设置
        self.alien_speed = 1.0
        self.fleet_drop_speed = 10
        # fleet_direction 为1表示向右移动，为-1表示向左移动
        self.fleet_direction = 1

        # 粒子（爆炸效果）设置
        self.particle_count = 20        # 每次爆炸生成的粒子数
        self.particle_min_size = 2      # 粒子最小尺寸
        self.particle_max_size = 5      # 粒子最大尺寸
        self.particle_lifetime = 30     # 粒子存活帧数（60帧/秒 ≈ 0.5秒）
        self.particle_gravity = 0.05   # 粒子向下的重力加速度
        self.particle_colors = [        # 爆炸颜色（黄→橙→红→金）
            (255, 200, 0),
            (255, 100, 0),
            (255, 50, 0),
            (255, 255, 0),
        ]
