# 神经网络玩家

`neural_pilot.py` 包含敌人位移预测、策略网络、离线训练、独立评测和实时挑战。输入只来自文本接口的可见战况与过去观测，不读取敌人内部 AI、随机数或未来生成位置。

## 安装与训练

普通游戏不需要以下可选依赖。第一轮的小型网络使用 CPU：训练 4 个线程，实时推理 1 个线程，没有使用 GPU 或付费云计算。

```powershell
python -m pip install pygame
python -m pip install -r requirements-training.txt --index-url https://download.pytorch.org/whl/cpu
python neural_pilot.py train --episodes 24 --steps 2500 --ppo 16 --output training_runs/pilot-v1.dat
```

训练分三步：

1. 用只看公开战况的示范策略采集数据，模仿左右扫射、避让、使用已有道具以及按可见价格购买装备/升级。
2. 用随后实际出现的观测学习约半秒后的敌人位移。预测器在匀速外推上学习修正，保留后 20% 时间段作验证，并报告相对匀速基线的误差。这是时间留出验证，不等同于独立关卡泛化评测。
3. 用 [PPO-Clip](https://spinningup.openai.com/en/latest/algorithms/ppo.html) 更新策略/价值网络。奖励来自实际得分增量、失血和死亡，并对拖延施加小惩罚。商店开关不产生得分奖励。

策略网络为两层各 128 个单元的 MLP，输出 23 个动作与状态价值。旧模型使用 90 维观测；瞄准/拾取纠错模型使用 110 维，额外保留精确目标偏移、估计射击交会位置、掉落物方向及沿途风险。预测器为两层 64/32 单元网络，输入连续可见位置、估计速度、上一速度、对象类型及自己的位置等 9 个数。依赖安装参见 [PyTorch 官方说明](https://pytorch.org/get-started/locally/)。

动作包含移动与射击组合、导弹、磁铁、四叶草、打开/关闭商店，以及三类消耗品、五级护甲、四类技能升级。不可执行或买不起的动作被屏蔽；商店最多每 300 个游戏循环帧打开一次。道具消耗、价格、技能上限、冷却和碰撞由原游戏决定。

## 独立评测

```powershell
python neural_pilot.py evaluate --episodes 5 --steps 6000 --seed 1000 --output training_runs/pilot-v1.dat
python neural_pilot.py evaluate --episodes 5 --steps 6000 --seed 1000 --baseline --output training_runs/pilot-v1.dat
```

训练保存最终 PPO 模型和 `<output>.imitation.dat` 模仿学习模型。应在相同未见种子上比较两个模型及示范基线，再选模型挑战。不要把模仿训练集准确率当成实战胜率。评测会标记步数上限导致的截断；截断分数不是完整对局的最终分数。

模型在自己的错误局面中继续模仿学习可用 `refine`。它采用 [DAgger 的数据聚合思路](https://proceedings.mlr.press/v15/ross11a.html)，在模型实际访问的状态补充示范标签，采集阶段混入 20% 示范动作，重点加权纠错、物品和商店决策；正式推理不混入示范动作。`refine` 会更新指定检查点，先复制一份以保留原模型：

```powershell
Copy-Item training_runs/pilot-v1.dat.imitation.dat training_runs/pilot-dagger.dat
python neural_pilot.py refine --episodes 12 --steps 3000 --seed 7000 --output training_runs/pilot-dagger.dat
```

`refine --skill-drills` 增加消耗品购买和使用的示范覆盖率：这些决策在采样阶段使用 80% 示范动作，普通移动仍为 20%。程序记录实际采样动作计数；正式 `play` 始终完全由网络选择动作，不混入示范策略。技能专项模型也需独立评测，覆盖了动作不代表掌握了最佳使用时机。

`refine --aim-drills` 增加单个/少量目标的瞄准示范，在 Boss 练习场景使用 80% 示范动作。首轮训练、独立对照和正式成绩见 [NEURAL_RESULTS.md](NEURAL_RESULTS.md)。

### 精确瞄准与主动拾取

`refine --tactics-drills` 自动把旧网络扩展到 110 维，保留旧权重并将新增输入的初始权重设为零。旧版 90 维检查点仍可加载，不会被自动改写。

```powershell
Copy-Item training_runs/champion.dat training_runs/pilot-tactics.dat
python neural_pilot.py refine --tactics-drills --skill-drills --episodes 12 --steps 3500 --seed 12000 --output training_runs/pilot-tactics.dat
python neural_pilot.py diagnose --steps 2500 --seed 81000 --output training_runs/pilot-tactics.dat
python neural_pilot.py evaluate --episodes 5 --steps 5000 --seed 3100 --output training_runs/pilot-tactics.dat
```

训练先使用 6,000 个纯观测几何练习，再收集完整游戏中的纠错样本。几何练习只构造文本接口形状的观测，不创建或修改游戏，不产生战绩。完整练习局通过原有普通操作游玩，采样时混入 70% 示范动作；正式 `play` 仍仅用神经网络输出选动作。

新示范顺序为：避开眼前碰撞危险、靠近安全且较低的掉落物、对准目标预计交会位置、无目标时巡航。子弹和飞船速度由连续可见位置估计；尚未测到时采用初始速度估计。敌人预测外推最多 120 帧，遇边界按反弹近似。它无法预知敌人的转向，路线危险估计也不是完整路径规划。

`diagnose` 用不同种子的单目标、移动目标、掉落物、敌人与掉落物并存、危险物五类观测检查网络动作。动作正确率是相对示范标签的几何测试结果，不是游戏胜率。`evaluate` 另报告真实离线局的金币收入、单目标未对准时停住（可能仍在开火）的步数，以及安全低位掉落物出现时朝其移动的比例；朝向比例不等于最终拾取率。

`training_runs/` 已被 Git 忽略。权重和评测数据通过项目的 `encrypt_json` / `decrypt_json` 保存为 `.dat`，不是游戏存档，不得复制到玩家存档中。

## 训练隔离

离线 `Practice` 使用独立临时存档，没有登录身份，禁用更新检查和战绩上传。复用原 `run_game()` 每一帧更新和绘制，通过训练专用时钟省略帧间等待，不增加移动速度、伤害、生命、金币或掉落率。练习局之间仅保留正常获得和购买的成长，独立评测每局均从新档开始。离线分数不会上传。

## 实时挑战

正常登录后启用接口：

```powershell
python alien_invasion.py --text-control
python neural_pilot.py play --start --seconds 900 --output training_runs/pilot-v1.dat
```

`--start` 只从主菜单按正常规则开始新局；若当前暂停，会继续该局。实战只通过 `GameClient` 的本地 HTTP 接口，保持原来 60 FPS，没有训练时钟。自然结算通过原流程上传成绩。达到时限后正常暂停，输出 `max_score_seen`；这可能是未结束对局的中间成绩，需与在线榜单确认的成绩区分。

每 5 秒报告生命、分数、关卡和动作计数。输入超时会释放移动/射击；停止脚本后才能稳定地手动接管。

## 相关修复与测试

商店原来的 `_apply_skills()` 会在购买任何物品时再次乘上速度技能倍率。现在购买后只应用旧/新速度等级的倍率之比，其他物品不再重复增加移速。新局仍按原规则应用技能，速度上限不变。

新账号缺少存档时，现在深复制默认物品/技能数据，避免同进程内不同新账号共享可变字典。独立评测使用这个修复后的新档隔离；旧版隔离不完整的评测均已废弃。

接口与商店测试：`python -m unittest discover -s tests -v`。

训练短跑：`python neural_pilot.py train --episodes 1 --steps 100 --ppo 1 --output training_runs/smoke.dat`。
