import sys
import os
from pathlib import Path


def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容 PyInstaller 单文件打包"""
    if hasattr(sys, '_MEIPASS'):
        return str(Path(sys._MEIPASS) / relative_path)
    return str(Path(relative_path))


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
        self.bullet_color = (0, 255, 80)        # 亮绿色
        self.bullet_allowed = 3

        # 外星人设置
        self.alien_speed = 1.0

        # 外星人集群行为设置（各速率均为alien_speed的倍率，随increase_speed整体缩放）
        self.aliens_per_wave = 22             # 每波外星人数量
        self.alien_spawn_y_min = 60           # 出生带（rect.y范围）
        self.alien_spawn_y_max = 240
        self.alien_descend_factor = 0.1       # 群体缓降速率倍率
        self.alien_dive_speed_factor = 5.0    # 俯冲速率倍率
        self.alien_climb_factor = 2.0         # 爬升速率倍率
        self.alien_gather_offset_range = 140  # 聚集目标 = 飞船x ± 随机偏移
        self.alien_cruise_y_min = 100         # 爬升返回的巡航高度带（rect.y，每次随机）
        self.alien_cruise_y_max = 280

        # 俯冲调度设置
        self.alien_cluster_radius = 90        # 密度判定半径（像素）
        self.alien_cluster_size = 3           # 半径内其他蜂群状态外星人的数量阈值
        self.alien_dive_cooldown = 180        # 两次俯冲触发的间隔帧数
        self.alien_dive_retry = 30            # 无合格集群时的重试间隔帧数
        self.alien_max_divers = 2             # 同时俯冲的外星人上限
        self.alien_dive_windup = 20           # 俯冲前的预警帧数（预警结束时锁定目标）
        self.alien_dive_max_start_y = 440     # 只有rect.bottom不低于此线的外星人可俯冲
        self.alien_pullup_margin = 40         # 俯冲拉起线 = screen_height - 此值

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

        # 导弹命中点粒子（比普通爆炸更大更亮）
        self.missile_particle_count = 35
        self.missile_particle_size_mult = 1.6
        self.missile_particle_speed_mult = 1.5
        self.missile_particle_colors = [
            (255, 80, 0), (255, 30, 0), (255, 180, 0), (255, 255, 100)
        ]

        # Boss 死亡粒子（华丽大型爆炸）
        self.boss_particle_count = 80
        self.boss_particle_size_mult = 2.5
        self.boss_particle_speed_mult = 2.0
        self.boss_particle_lifetime_mult = 2.0
        self.boss_particle_colors = [
            (255, 215, 0), (255, 100, 0), (255, 50, 0),
            (255, 255, 200), (255, 255, 50), (200, 100, 255)
        ]
        self.boss_secondary_count = 40        # 第二波粒子数
        self.boss_secondary_delay = 15        # 第二波延迟帧数

        # Boss 死亡动画
        self.boss_death_flash_frames = 90     # 死亡闪烁总帧数
        self.boss_death_slow_frames = 30      # 悬停不闪帧数（之后开始加速闪烁）

        # --- 陨石设置 ---
        self.meteor_spawn_interval = 180      # 生成间隔（帧，180=3秒）
        self.meteor_speed_min = 1.5           # 最小下落速度
        self.meteor_speed_max = 4.0           # 最大下落速度
        self.meteor_angle_range = 90          # 偏离垂直的角度范围（总共180°）
        self.meteor_size_min = 15             # 最小半径（像素）
        self.meteor_size_max = 38             # 最大半径（像素）
        self.meteor_hp = 3                    # 血量（子弹伤害=1，需3发击毁）
        self.meteor_alien_damage = 10         # 主陨石对外星人碰撞伤害（大量）
        self.meteor_boss_damage = 8           # 主陨石对Boss碰撞伤害（大量）
        self.meteor_fragment_damage = 3       # 碎片伤害（略大于子弹的1点）
        self.meteor_fragment_hp = 1           # 碎片血量（1发子弹即可摧毁）
        self.meteor_fragment_count = 12       # 破碎产生的碎片数
        self.meteor_fragment_lifetime = 90    # 碎片存活帧数（90帧=1.5秒）
        self.meteor_points = 25               # 摧毁陨石得分
        self.meteor_avoid_radius = 80         # 外星人规避检测半径
        self.meteor_avoid_strength = 1.5      # 规避力强度

        # 加速度设置
        self.speedup_scale = 1.1

        # 计分设置
        self.alien_points = 50
        self.boss_points = 500              # Boss 击杀分数

        # 导弹设置
        self.missile_score_step = 500   # 每得500分奖励一枚导弹
        self.missile_speed = 4.0        # 导弹飞行速度
        self.missile_turn_rate = 0.08   # 每帧向目标方向偏转的比例（越大转向越灵活）
        self.missile_blast_radius = 120 # 爆炸范围半径（像素）

        # 伤害与血量设置
        self.alien_base_hp = 1          # 第1关外星人血量
        self.alien_hp_per_level = 1     # 每关增加的血量
        self.bullet_damage = 1          # 子弹伤害
        self.missile_damage = 5         # 导弹爆炸伤害

        # 关卡设置
        self.kills_per_level = 30       # 每关需要的击杀数

        # 飞船受击闪烁设置
        self.invulnerable_duration = 60     # 闪烁/无敌/禁止俯冲的总帧数（60帧 = 1秒）

        # Boss 设置
        self.boss_hp_multiplier = 20        # Boss HP = 同关外星人HP × 此值
        self.boss_speed_factor = 0.5        # Boss 移速倍率（相对 alien_speed）
        self.boss_bullet_speed = 1.5        # Boss 子弹速度
        self.boss_bullet_radius = 6         # Boss 子弹半径（像素）
        self.boss_bullet_color = (220, 50, 50)  # 红色
        self.boss_fire_interval = 120       # Boss 射击间隔（帧，120=2秒）
        self.boss_hp_bar_width = 80         # Boss 血条宽度（像素）
        self.boss_hp_bar_height = 5         # Boss 血条高度
        self.boss_hp_bar_offset_y = 12      # Boss 血条距顶部的偏移

        # 金币设置
        self.coin_drop_rate = 0.3           # 击杀外星人掉落金币概率
        self.coin_fall_speed = 2.0          # 金币下落速度
        self.coin_hover_y_margin = 60       # 金币悬停位置距底部距离
        self.coin_hover_duration = 180      # 悬停帧数（3秒）
        self.coin_flash_duration = 60       # 闪烁帧数（1秒）
        self.coin_radius = 8                # 金币半径（像素）

        # 外星人血条设置
        self.hp_bar_width = 30              # 血条宽度（像素）
        self.hp_bar_height = 3              # 血条高度
        self.hp_bar_offset_y = 6            # 血条距外星人顶部的偏移

        # 道具价格
        self.magnet_item_cost = 5           # 磁铁购买价格
        self.shield_item_cost = 10          # 护盾购买价格
        self.magnet_duration = 600          # 磁铁持续时间（10秒）
        self.magnet_pickup_radius = 300     # 磁铁拾取半径

        # 技能费用（5级）
        self.skill_costs = {
            'speed':    [3, 6, 12, 24, 48],
            'ammo':     [5, 10, 20, 40, 80],
            'vitality': [8, 16, 32, 64, 128],
        }
        self.skill_max_level = 5

        # --- 菜单界面设置 ---
        self.menu_title_font_size = 72
        self.menu_button_font_size = 42
        self.menu_video_path = resource_path('resource/videos/gameplay.mp4')
        self.menu_blur_strength = 15          # 高斯模糊核大小（必须为奇数）
        self.menu_video_frame_skip = 3        # 每N帧读取一次视频帧
        self.menu_overlay_alpha = 100         # 菜单视频上的暗色叠加透明度（0-255）
        self.pause_overlay_alpha = 140        # 暂停遮罩透明度

        # 菜单按钮颜色 (R, G, B)
        self.menu_start_color = (40, 140, 60)
        self.menu_start_hover = (60, 180, 80)
        self.menu_shop_color = (60, 120, 200)
        self.menu_shop_hover = (90, 160, 240)
        self.menu_tutorial_color = (120, 80, 180)
        self.menu_tutorial_hover = (150, 110, 210)
        self.menu_resume_color = (40, 140, 60)
        self.menu_resume_hover = (60, 180, 80)
        self.menu_return_color = (180, 60, 60)
        self.menu_return_hover = (220, 80, 80)
        self.menu_quit_color = (120, 50, 50)
        self.menu_quit_hover = (160, 70, 70)

        # --- 音频设置 ---
        self.bgm_volume = 0.6              # 背景音乐正常音量 (0.0-1.0)
        self.bgm_pause_volume = 0.15       # 暂停时BGM降低到的音量
        self.sfx_volume = 0.8              # 音效音量

        # --- 背景滚动设置 ---
        self.bg_images = [
            resource_path('resource/images/bg_earth.png'),
            resource_path('resource/images/bg_moon.png'),
            resource_path('resource/images/bg_space.png'),
        ]
        self.bg_scroll_speed = 2

        # --- 动画持续时间 ---
        self.boss_warning_duration = 90     # Boss 出场警告横幅帧数
        self.ship_death_duration = 60       # 飞船死亡爆炸帧数
        self.fail_banner_duration = 90      # 失败横幅显示帧数

        # --- 存档设置 ---
        self._saves_dir = Path(os.path.dirname(sys.argv[0])) / "saves"
        self._saves_dir.mkdir(exist_ok=True)
        self.save_file = str(self._saves_dir / "savegame.dat")
        self.high_score_file = str(self._saves_dir / "high_score.dat")

        # --- 服务器设置 ---
        self.server_url = "https://alien-invasion-1018096304579.asia-east1.run.app"

        self.initialize_dynamic_settings()
        """初始化随游戏进行而变化的设置"""
        self.ship_speed = 1.5
        self.bullet_speed = 2.5
        self.alien_speed = 1.0

    def increase_speed(self):
        """提高速度设置的值"""
        self.ship_speed *= self.speedup_scale
        self.bullet_speed *= self.speedup_scale
        self.alien_speed *= self.speedup_scale
