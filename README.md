# Alien Invasion

基于 Pygame 的纵版射击游戏，集成邮箱验证码注册/登录、云端排行榜、游戏进度存档等功能。

---

## 架构

```text
桌面客户端 ── HTTPS ── logan-ai.org（la-vps）
                            │
                          Nginx
                            │
                      Flask + Gunicorn
                       ├─ SQLite：账号、验证码、排行榜
                       ├─ Redis：请求限流
                       ├─ Resend：验证码邮件
                       └─ 网页：排行榜、GitHub Releases 下载
```

已于 2026-09-19 完成 la-vps 数据迁移、TLS 和域名切换；旧 Cloud Run 地址保留兼容转发，详见部署文档。

---

## 本地运行

```bash
pip install pygame
python alien_invasion.py
```

> 首次启动弹出邮箱注册/登录界面。已认证用户跳过。  
> 游戏中按 **ESC** → Save Game 进度存档。主菜单 Resume Game 继续。

键盘不可用时，可点击战场指定飞船的横向目标位置（按原速度移动），点击顶部 **Fire** 切换持续射击；Missile / Magnet / Clover / Shop / Pause 按钮对应原键盘动作。射速、弹药限制和道具消耗不变。暂停、失去窗口焦点和返回菜单会停止输入；教程页点击任意位置返回。登录输入支持 IME 提交的文本。

---

## 打包 EXE

```bash
pip install pyinstaller pillow
python -c "from PIL import Image; img=Image.open('resource/images/cover.png'); img.save('icon.ico',format='ICO',sizes=[(256,256)])"
python -m PyInstaller AlienInvasion.spec --clean --noconfirm
```

产物：`dist/AlienInvasion.exe`（约 104MB 单文件）。

---

## 服务端部署

服务端迁往 la-vps：Nginx + Gunicorn + SQLite + Redis，保留 logan-ai.org。

安装步骤、数据迁移、TLS、备份和切换状态见 [web/DEPLOYMENT.md](web/DEPLOYMENT.md)。

---

## 项目结构

```
alien_invasion/
│
├── alien_invasion.py          # 主游戏入口 (1600+ 行)
├── settings.py                # 配置常量 + resource_path()
├── game_stats.py              # GameState 状态机 (7 状态)
├── player_data.py             # JSON 持久化 (金币/技能/token/email)
├── web_client.py              # HTTP 客户端 (stdlib only)
├── login_ui.py                # 登录/注册/重置 UI (5 步状态机)
│
├── 游戏实体 (Sprite)
│   ├── ship.py                # 玩家飞船 (无敌闪烁)
│   ├── alien.py               # 外星人 (HP/俯冲/爬升 AI)
│   ├── boss.py                # Boss (HP 条/射击/死亡动画)
│   ├── boss_bullet.py         # Boss 弹幕
│   ├── bullet.py              # 玩家子弹 (绿色能量弹)
│   ├── missile.py             # 追踪导弹 (AOE 爆炸)
│   ├── coin.py                # 金币 (掉落/悬停/闪烁)
│   ├── meteor.py              # 陨石 + 碎片
│   └── particle.py            # 爆炸粒子
│
├── 游戏系统
│   ├── menu.py                # 菜单/暂停/教程 (6 按钮)
│   ├── shop.py                # 商店/技能树 (磁铁/护盾/速度/弹药/生命)
│   ├── scoreboard.py          # HUD (心形/导弹/金币/分数)
│   ├── sound.py               # 音效 (文件 + 合成降级)
│   ├── scrolling_background.py # 3 图垂直滚动背景
│   ├── video_background.py    # 菜单视频背景 (CV2 降级)
│   └── button.py              # 可复用按钮组件
│
├── resource/
│   ├── images/                # 6 个 (飞船/外星人/Boss/3 背景/封面)
│   └── sounds/                # 12 个音效 + 1 个 BGM
│
├── web/                       # la-vps 网站与 API 服务端
│   ├── server.py              # Flask API (530 行)
│   ├── index.html             # 前端展板 (玻璃拟态仪表盘)
│   ├── requirements.txt       # 服务端依赖
│   └── Dockerfile             # 容器构建
│
├── AlienInvasion.spec         # PyInstaller 配置
├── requirements.txt           # 桌面端依赖 (pygame)
└── .gitignore
```

---

## API 接口

| 端点 | 方法 | 说明 | 限流 |
|------|------|------|------|
| `/api/auth/send-code` | POST | 发送邮箱验证码 | 5/min |
| `/api/auth/register` | POST | 注册 (验证码+用户名+密码) | 5/min |
| `/api/auth/login` | POST | 登录 (用户名/邮箱+密码) | 10/min |
| `/api/auth/reset-password` | POST | 重置密码 (验证码+新密码) | 5/min |
| `/api/stats` | POST | 上传战绩 (需 Bearer Token) | 30/min |
| `/api/leaderboard` | GET | 排行榜 Top 10 | 60/min |
| `/health` | GET | 健康检查 | — |

---

## 操作说明

脚本也可以通过本地 JSON 接口读取战况并游玩：`python alien_invasion.py --text-control`。参见[文本控制接口与左右巡航示例](TEXT_CONTROL.md)。

| 按键 | 功能 |
|------|------|
| A / D 或 ← / → | 移动飞船 |
| Space | 射击 |
| E | 发射追踪导弹 |
| M | 商店 / 技能树 |
| N | 激活磁铁 |
| ESC | 暂停（可存档 / 返回菜单） |
| F5 | 快速存档 |

---

## 技能树

| 技能 | 效果 | 满级 |
|------|------|------|
| Speed Boost | 飞船速度 +10%/级 | 5 |
| Ammo Capacity | 弹幕上限 +1/级 | 5 |
| Vitality | 最大生命 +1/级 | 5 |

---

## 许可证

MIT
