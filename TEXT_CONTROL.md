# 游戏文本控制接口

这个接口把游戏画面中的战况表示成 JSON，让脚本可以读取战况、左右移动、持续射击和使用道具。游戏仍按原来的 60 FPS 实时运行，不提供单步推进、加速、修改分数/生命/金币/存档或直接上传战绩的指令。

## 启动与试用

在项目目录打开两个终端。第一个终端启动游戏，按原有流程登录：

```powershell
python alien_invasion.py --text-control
```

第二个终端读取状态并开始一局：

```powershell
python game_control.py state
python game_control.py act --action start
python game_control.py act --move left --fire on --lease-ms 1000
python game_control.py state
python game_control.py act --move right --fire on --lease-ms 1000
python game_control.py act --action pause
```

`start` 等同于菜单里的 Start Game，会按原有逻辑清除旧的局内存档。登录仍在游戏界面完成；接口不会返回账号、密码或登录令牌。

试用“左右移动同时射击”的示例：

```powershell
python game_control.py act --action resume
python text_patrol.py --seconds 30
```

示例每 100 ms 读取战况，在屏幕宽度的 20%～80% 之间往返，持续射击，每秒打印一次战况。30 秒后正常暂停；若中途阵亡则结束。它只使用下面的公开接口，不访问游戏对象、内存、存档或战绩上传 API。它是基础战术演示，还不会主动躲避陨石或使用道具。

## Python 接口

客户端仅用 Python 标准库，不需要 pygame：

```python
from game_control import GameClient

game = GameClient()
state = game.state()
if state['accepts_controls']:
    game.act(move='left', fire=True, lease_ms=500)
```

每次移动指令完整替换脚本的按住状态：省略 `move` 表示 `stop`，省略 `fire` 表示 `False`。`lease_ms` 默认 1000，范围 100～2000 ms。必须在期限内续发；超时后自动松开，不暂停游戏。服务器确认的是输入已经应用，实际移动和射击发生在后续游戏帧中。

动作指令 `game.act(action='missile')` 与移动指令分开发送，合法动作以返回的 `actions` 为准：

| 动作 | 条件与效果 |
| --- | --- |
| `start` | 主菜单，开始新一局 |
| `pause` / `resume` | 暂停当前游戏 / 继续暂停的游戏 |
| `menu` | 暂停菜单，按原有逻辑结算并回主菜单 |
| `back` | 退出教程、排行榜或商店 |
| `shop` | 主菜单或正常战斗中打开商店 |
| `purchase` | 仅在商店中，附带 `offer` 字段，购买当前可见且可负担的商品 |
| `missile` | 消耗一枚已有导弹 |
| `magnet` / `clover` | 消耗对应的已有道具 |

移动仍调用原来的飞船更新逻辑；持续射击共用原来的冷却和弹数上限。密集发请求不会增加速度或射速。死亡、过场与暂停期间拒绝战斗输入。键鼠操作和窗口失去焦点会撤销当前脚本输入；仍在运行的脚本可以通过下一条指令重新取得控制，手动接管前应停止脚本。

## 战况格式

`GET /state` 最多每秒更新 20 次；`frame` 是正常游戏循环的帧编号，`observed_at` 是 Unix 秒时间戳，可用于检测陈旧状态。暂停时帧编号仍增长，但战斗对象不更新。

- `state`：`login`、`menu`、`playing`、`paused`、`shop`、`tutorial` 或 `leaderboard`。
- `accepts_controls`：当前能否接受移动和射击。
- `actions`：当前可以执行的菜单/道具动作。
- `screen`：游戏内坐标尺寸，与 Windows DPI 缩放无关；原点在左上，x 向右、y 向下。
- `hud`：当前界面中的分数、生命、关卡、金币、导弹数量等。
- `ship` / `objects`：屏幕范围内的对象矩形，字段为 `id, kind, x, y, width, height`。坐标是矩形左上角；`id` 只在本次游戏进程中有效。离开屏幕的对象不返回，部分出界的矩形裁切到屏幕范围。
- `phase`：游戏场景中的 `active`、`transition`、`dying` 或 `game_over`。
- `control`：脚本的移动方向、射击开关和剩余有效毫秒数。

对象类型包括 `alien`、`boss`、`bullet`、`missile`、`hostile_bullet`、`hostile_missile`、`meteor`、`meteor_fragment`、`coin`、`gem`。不返回 AI 状态、目标坐标、随机数、未来出生位置或计时器。过场隐藏对象列表；菜单、登录及商店不导出战斗对象。敌人的速度可由相邻观测的位置差自行估算。

## 本地 HTTP 协议

商店返回 `shop.offers`（商品标识和价格）、当前技能等级、物品库存和护甲；购买示例：`game.act(action='purchase', offer='upgrade_skill:ammo')`。接口不接受客户端价格或数量，调用同一套商店按钮与扣款逻辑。神经网络训练和实战见 [NEURAL_PILOT.md](NEURAL_PILOT.md)。

默认仅监听 `127.0.0.1:8765`，普通启动不开启接口。可用 `--text-control 8766` 换端口，或传 `0` 自动分配端口。

游戏为每次启动生成独立 Bearer Token，把本地连接信息存入 `saves/text-control.dat`，沿用项目的文件编码方式，退出时清理。客户端自动读取。可通过游戏的 `--control-file PATH` 与客户端/示例的 `--session-file PATH` 指定同一个文件。连接文件供本机脚本使用，不要提交或分享。

- `GET /state` 返回 JSON 战况。
- `POST /action` 接收 JSON 控制对象或单一动作对象。
- 两者都需要 `Authorization: Bearer <本次启动的令牌>`，Host 必须是指定的本地地址；拒绝带 Origin 的浏览器请求。
- POST 请求体上限 2048 字节，不接受额外字段。
- `200` 已应用，`400` 参数错误，`403` 身份校验失败，`409` 当前不可执行，`408` 排队过期，`429` 队列满，`504` 游戏循环未及时响应。
- 发生超时不要自动重试导弹等一次性动作；先读状态。`504` 的 `cancelled=true` 表示排队指令已经取消，`false` 表示可能已开始执行。

这是桌面进程的本地接口，不依赖 la-vps，不需要开放服务器端口或修改网站服务。正常结算依然走游戏原来的上传流程。

## 验证

```powershell
python -m unittest discover -s tests -v
```

测试使用 SDL 虚拟显示和临时存档，禁用更新检查与战绩上传。覆盖真实游戏循环中的 HTTP 控制、原有移速/射速/弹数限制、输入超时、暂停、失焦、访问校验、非法修改请求、屏幕外对象过滤和过场隐藏，不读取玩家的真实存档。
