"""菜单背景视频播放器：循环播放游戏录像并应用高斯模糊"""

import random
import math
import pygame


class VideoBackground:
    """在菜单背景循环播放游戏录像，应用高斯模糊。
    优先使用 opencv-python 播放视频文件，加载失败时降级为程序化模拟背景。"""

    def __init__(self, ai_game):
        """初始化视频背景播放器"""
        self.ai_game = ai_game
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.width = self.settings.screen_width
        self.height = self.settings.screen_height

        self.use_video = False          # 是否成功加载视频
        self.cap = None                 # cv2.VideoCapture 对象
        self.blurred_frame = None       # 当前模糊帧（Pygame Surface）
        self.frame_counter = 0          # 帧计数器（用于隔帧读取）

        # 尝试加载视频
        self._init_video()

        # 如果视频加载失败，初始化程序化背景
        if not self.use_video:
            self._init_fallback()

    # ------------------------------------------------------------------
    # 视频背景
    # ------------------------------------------------------------------

    def _init_video(self):
        """尝试用 OpenCV 加载视频文件"""
        try:
            import cv2
        except ImportError:
            print("⚠ opencv-python 未安装，使用程序化菜单背景")
            return

        path = self.settings.menu_video_path
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"⚠ 无法打开视频文件: {path}，使用程序化菜单背景")
            return

        self.cap = cap
        self.use_video = True
        self._cv2 = cv2
        print(f"✓ 菜单背景视频已加载: {path}")

    def _update_video(self):
        """从视频读取下一帧并应用高斯模糊"""
        if self.cap is None or not self.use_video:
            return

        self.frame_counter += 1
        if self.frame_counter % self.settings.menu_video_frame_skip != 0:
            return  # 隔帧跳过，降低开销

        ret, frame = self.cap.read()
        if not ret:
            # 视频播放完毕，循环到开头
            self.cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                self.use_video = False
                return

        # 缩放到屏幕尺寸
        frame = self._cv2.resize(frame, (self.width, self.height))

        # 高斯模糊
        k = self.settings.menu_blur_strength
        if k % 2 == 0:
            k += 1  # 确保核大小为奇数
        blurred = self._cv2.GaussianBlur(frame, (k, k), 0)

        # BGR → RGB
        rgb = self._cv2.cvtColor(blurred, self._cv2.COLOR_BGR2RGB)

        # 转成 Pygame Surface
        self.blurred_frame = pygame.image.frombuffer(
            rgb.tobytes(), (self.width, self.height), 'RGB')

    # ------------------------------------------------------------------
    # 程序化 Fallback 背景
    # ------------------------------------------------------------------

    def _init_fallback(self):
        """初始化程序化模拟背景（视频不可用时）"""
        # 低分辨率渲染目标（缩小再放大 = 天然模糊）
        self.fb_scale = 4
        self.fb_small_w = self.width // self.fb_scale
        self.fb_small_h = self.height // self.fb_scale
        self.fb_surface = pygame.Surface((self.fb_small_w, self.fb_small_h))
        self.fb_cache = None       # 缓存的模糊结果
        self.fb_update_every = 3   # 每N帧更新一次
        self.fb_counter = 0

        # 加载精灵（低透明度）
        self.fb_alien_img = self._fb_load_sprite('resource/images/alien.bmp', 0.06, 0.35)
        self.fb_ship_img = self._fb_load_sprite('resource/images/ship.bmp', 0.08, 0.30)
        self.fb_boss_img = self._fb_load_sprite('resource/images/boss.bmp', 0.12, 0.25)

        # 背景装饰实体
        self.fb_aliens = []
        self._fb_spawn_aliens(14)

        self.fb_ship_x = float(self.fb_small_w // 2)
        self.fb_ship_vx = 0.15

        self.fb_boss = None
        self.fb_boss_timer = random.randint(180, 360)

        self.fb_particles = []
        self.fb_particle_colors = [
            (255, 200, 0), (255, 100, 0),
            (255, 50, 0),  (255, 255, 0),
        ]

    def _fb_load_sprite(self, path, size_ratio, alpha):
        """加载精灵图像，缩放到小渲染面的比例并设置透明度"""
        img = pygame.image.load(path)
        w = int(self.fb_small_w * size_ratio)
        ratio = w / img.get_width()
        h = int(img.get_height() * ratio)
        img = pygame.transform.scale(img, (w, h))
        img.set_alpha(int(255 * alpha))
        return img

    def _fb_spawn_aliens(self, count):
        """在小型渲染面上随机生成背景外星人"""
        for _ in range(count):
            self.fb_aliens.append({
                'x': random.uniform(0, self.fb_small_w - self.fb_alien_img.get_width()),
                'y': random.uniform(5, self.fb_small_h * 0.45),
                'vx': random.uniform(0.1, 0.4) * random.choice([-1, 1]),
                'vy': random.uniform(0.02, 0.08),
            })

    def _fb_spawn_particles(self, x, y, count=5):
        """在指定位置生成一波粒子"""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.2, 1.0)
            self.fb_particles.append({
                'x': float(x), 'y': float(y),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': random.randint(15, 30),
                'max_life': 30,
                'color': random.choice(self.fb_particle_colors),
            })

    def _fb_update_entities(self):
        """更新所有程序化背景实体的位置"""
        # 外星人位移（边界反弹）
        for a in self.fb_aliens:
            a['x'] += a['vx']
            a['y'] += a['vy']
            aw = self.fb_alien_img.get_width()
            if a['x'] <= 0 or a['x'] >= self.fb_small_w - aw:
                a['vx'] *= -1
            if a['y'] <= 5 or a['y'] >= self.fb_small_h * 0.45:
                a['vy'] *= -1

        # 飞船水平漂移
        self.fb_ship_x += self.fb_ship_vx
        sw = self.fb_ship_img.get_width()
        if self.fb_ship_x <= 30 or self.fb_ship_x >= self.fb_small_w - 30:
            self.fb_ship_vx *= -1

        # Boss 定时巡游
        self.fb_boss_timer -= 1
        if self.fb_boss_timer <= 0:
            if self.fb_boss is None:
                self.fb_boss = {
                    'x': float(random.randint(30, self.fb_small_w - 80)),
                    'vx': random.uniform(0.15, 0.3) * random.choice([-1, 1]),
                }
            else:
                self.fb_boss = None
            self.fb_boss_timer = random.randint(180, 360)

        if self.fb_boss is not None:
            self.fb_boss['x'] += self.fb_boss['vx']
            bw = self.fb_boss_img.get_width()
            if self.fb_boss['x'] <= 0 or self.fb_boss['x'] >= self.fb_small_w - bw:
                self.fb_boss['vx'] *= -1

        # 更新粒子
        for p in self.fb_particles[:]:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 1
            if p['life'] <= 0:
                self.fb_particles.remove(p)

        # 随机生成粒子爆发
        if random.random() < 0.04:
            x = random.randint(20, self.fb_small_w - 20)
            y = random.randint(10, self.fb_small_h // 2)
            self._fb_spawn_particles(x, y, random.randint(3, 8))

    def _fb_render(self):
        """渲染程序化背景到小Surface，再放大到全屏（模糊效果）"""
        self.fb_surface.fill((10, 10, 25))

        # 绘制外星人
        for a in self.fb_aliens:
            self.fb_surface.blit(self.fb_alien_img, (int(a['x']), int(a['y'])))

        # 绘制飞船
        ship_y = self.fb_small_h - 50
        self.fb_surface.blit(
            self.fb_ship_img,
            (int(self.fb_ship_x - self.fb_ship_img.get_width() / 2), ship_y))

        # 绘制 Boss
        if self.fb_boss is not None:
            self.fb_surface.blit(self.fb_boss_img, (int(self.fb_boss['x']), 20))

        # 绘制粒子
        for p in self.fb_particles:
            alpha = int(255 * (p['life'] / p['max_life']))
            color = (*p['color'], alpha)
            r = 2
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (r, r), r)
            self.fb_surface.blit(surf, (int(p['x'] - r), int(p['y'] - r)))

        # 缩小再放大产生模糊
        self.fb_cache = pygame.transform.smoothscale(
            self.fb_surface, (self.width, self.height))

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------

    def update(self):
        """每帧调用，更新背景帧"""
        if self.use_video:
            self._update_video()
        else:
            self.fb_counter += 1
            self._fb_update_entities()
            if self.fb_counter >= self.fb_update_every:
                self.fb_counter = 0
                self._fb_render()

    def draw(self):
        """绘制模糊背景到屏幕"""
        if self.use_video and self.blurred_frame is not None:
            self.screen.blit(self.blurred_frame, (0, 0))
        elif not self.use_video and self.fb_cache is not None:
            self.screen.blit(self.fb_cache, (0, 0))
        else:
            # 首次调用时还没有帧，填充深色背景
            self.screen.fill((10, 10, 25))

        # 暗色半透明蒙版（提升文字可读性）
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, self.settings.menu_overlay_alpha))
        self.screen.blit(overlay, (0, 0))
