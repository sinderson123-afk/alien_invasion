# la-vps 部署与运维

## 服务位置

- 域名：`https://logan-ai.org`；Cloudflare 代理 + Full (strict)。
- 主机：SSH `la-vps`；公网 `192.3.232.28`；Tailscale `100.70.0.54`。
- 应用：`/opt/alien-invasion/web`；Python：`/opt/alien-invasion/venv`。
- Nginx TCP 443 → Gunicorn `127.0.0.1:8080`（2 workers）。
- SQLite：`/var/lib/alien-invasion/game.sqlite3`；Redis：`127.0.0.1:6379/1`（共享限流）。
- 配置：`/etc/alien-invasion.env`，root 所有、0600，含原 Resend 密钥。
- 服务：`alien-invasion.service`；备份：`alien-invasion-backup.timer`（每日，保留最近 14 份）。

## TLS 与网络

Nginx 使用 Cloudflare Origin CA 证书，文件位于 `/etc/nginx/alien-tls/`，私钥仅 root 可读。证书有效期至 **2041-09-15**，需在到期前更换；这种源站证书依赖 Cloudflare 代理，不能关闭橙云后直接供普通浏览器访问。HTTP 308 跳转到 HTTPS。

Nginx 仅信任 Cloudflare 官方 IP 段的 `CF-Connecting-IP`，列表在 `/etc/nginx/snippets/alien-cloudflare-realip.conf`，2026-09-19 从 Cloudflare `/ips` API 核实。后续应随官方列表更新。

防火墙放行 TCP 80/443；Hysteria 继续使用 UDP 443。Redis 和 Gunicorn 只监听本机。维护开关：创建 `/etc/nginx/alien-maintenance` 时公网源站返回 503，删除该文件恢复，无需 reload。后端本机端口不受此开关影响。

## 旧版客户端兼容

旧 EXE 固定使用 `https://alien-invasion-1018096304579.asia-east1.run.app`。该 Cloud Run 服务改为 Nginx 透明代理，通过 HTTPS 直连 VPS，验证 Origin CA 和域名，保留 HTTP 方法、请求体及 Authorization。

- 项目：`my-server-502313`，区域：`asia-east1`。
- 新 revision：`alien-invasion-la-proxy-20260919`。
- 原 revision：`alien-invasion-00005-k48`，保留但不接收服务流量。
- 代理镜像：`asia-east1-docker.pkg.dev/my-server-502313/cloud-run-source-deploy/alien-invasion-proxy:20260919`。
- 配置来源：`deploy/cloudrun-proxy/`，其中 CA 是公开根证书，不是私钥。
- 新版客户端源码改用 `https://logan-ai.org`；发布新客户端、确认旧版本退出使用后，才能关闭兼容服务并完全移除 GCP 运行依赖。
- 兼容地址的请求按 Cloud Run 出口 IP 限流；新域名按实际客户端 IP 限流。大量旧版用户共用出口时，需迁移客户端或增加可信客户端 IP 传递机制。

原 Cloud Build GitHub 触发器 `888eb7ae-eea8-48e8-b487-8e04de647eec` 已禁用，防止覆盖代理。原 Pages 项目 `my-web-page` 保留用于回退，关闭自动生产和预览部署；另一个 `proxy` Pages 项目未变更。

## 更新应用

在本机仓库中执行：

```powershell
./web/deploy/update.ps1
```

脚本只上传指定代码/静态资源，先执行数据库备份，再安装依赖、重启应用并检查健康状态；不会上传本地环境密钥或数据库，不覆盖已有 TLS 配置。脚本依赖本机 `tar`、`scp`、`ssh la-vps`。目前没有为 VPS 配置 GitHub 自动部署：推送仓库后仍需执行此脚本，尤其是发布时更新的 `web/version.json`。

首次在空机器部署时，安装 `python3-venv nginx redis-server certbot python3-certbot-nginx`，复制 web 到上述目录，再运行 `sh /opt/alien-invasion/web/deploy/install.sh`。首次默认仅 HTTP，需另行安装证书、真实 IP 配置和 `deploy/nginx-tls.conf`。

## 检查与备份

```sh
systemctl status alien-invasion nginx redis-server
journalctl -u alien-invasion --since '30 minutes ago'
curl -fsS http://127.0.0.1:8080/health
curl -fsS https://logan-ai.org/api/leaderboard
systemctl start alien-invasion-backup.service
systemctl list-timers alien-invasion-backup.timer
```

备份位于 `/var/lib/alien-invasion/backups`，使用 SQLite backup API 生成一致快照并做 integrity_check；不能直接复制正在写入的主库而遗漏 WAL。恢复需停止应用，保存现有数据库及 WAL/SHM，恢复校验过的备份、设置服务用户所有权，再启动。当前是同机备份，尚未配置异机备份。

SQLite 文档适配层适合当前小规模单机运行；查询在内存筛选/排序。写 API 使用 IMMEDIATE 事务防止并发注册和最高分覆盖。邮件网络请求当前占用写事务；若访问量增长，应改为专用 SQL 索引查询及异步邮件发送。

## 迁移数据与回退资料

迁移集合：`users`、`leaderboard`、`codes`。保留用户 ID、密码哈希、登录令牌及战绩；导入工具拒绝非空库，失败整体回滚。导出工具拒绝未处理的集合、子集合或字段类型。

本机备份目录：`%LOCALAPPDATA%\AlienInvasionMigration\20260919`（限制为当前用户访问），包含原 Cloud Run 配置、原构建触发器、预检导出和最终导出。其中有密钥、密码哈希和令牌，不要提交或分享。VPS 迁移副本也只保存在 root 或服务用户私有目录。

gcloud 登录后可使用 PowerShell 7 脚本导出（正式导出前必须冻结旧写入）：

```powershell
./web/deploy/export-firestore.ps1 -OutputPath /path/outside/repo/firestore-export.json
```

Python 环境若有 ADC 和 `google-cloud-firestore`，也可使用 `migrate_firestore.py export`；VPS 导入不需要任何 Google SDK/凭据。

原 DNS：CNAME `logan-ai.org` → `calendar-bwl.pages.dev`，proxied=true，ttl=1；记录 ID `a9f1cec3a7a9aeae90ac4b3b31e9e111`。Cloudflare zone `123042705e751b04f2080fc99b3529d5`。

**切换后不能直接把流量切回旧 Firestore**：新产生的数据只在 SQLite。回退前必须暂停写入、备份和对账，优先保留新数据库恢复应用；需要回迁时单独规划转换。原 Firestore 和 GCP VM 未删除，VM 上的 ASF/Hysteria 属于其他服务。

## 验证范围及邮件配置

独立临时库已验证：注册、登录、重置密码/令牌失效、最高分保留、排行榜、回滚、重开数据库、并发写入和备份恢复。迁移预检逐字段对比了实际导出的所有文档。

`mail.logan-ai.org` 已在 Resend 验证，2026-09-19 通过 API 再次确认状态为 verified。生产环境及代码默认发件人已改为 `Alien Invasion <noreply@mail.logan-ai.org>`，服务已重启。通过公网 `/api/auth/send-code` 向站主 Gmail 发送验证码，接口返回 200，Resend 最终状态为 **delivered**（收件服务器已接受，不代表用户已阅读或一定进入收件箱）。邮件 ID：`01a0b972-447b-72da-a181-40903eb0de8c`。此测试未注册账号、重置密码或变更排行榜。

参考：[Cloudflare Origin CA](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/)、[Cloud Run 流量切换](https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)、[SQLite WAL](https://www.sqlite.org/wal.html)。

## 2026-09-19 切换完成记录

### 桌面客户端 Cloudflare 兼容配置

Python urllib 默认请求曾被 Cloudflare Browser Integrity Check 返回 HTTP 403 / 1010，客户端将其显示为 `Could not connect to server`。2026-09-19 已添加 `http_config_settings` 规则，仅对 `logan-ai.org` 的 `/api/` 路径和 `/version.json` 设置 `bic: false`，其他防护不变。规则集 ID：`b806cd8618ab41d1b2c8a25d8c45b0f5`；规则 ID：`b264ea564a784bf4b0039e1dc843a451`。已用游戏实际 Python 环境及未修改的 `WebClient` 验证排行榜、账号登录成功；未改动游戏分数或存档。后续验收应包含默认 urllib 请求，不能仅用浏览器或 PowerShell。

参考：[Cloudflare Error 1010](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/)。

桌面端实测：`CodexPilot` 正常注册、登录、游玩后，由客户端自动上传 1,950 分 / 第 2 关；游戏内排行榜成功读回。没有手工写入分数或修改存档。

### 初次切换验收

- UTC 10:05 左右完成最终数据导入，逐字段核对 1 个账号、1 条排行榜、2 条验证码；原令牌认证有效。
- UTC 10:05:48 将域名 A 记录切至 VPS，移除原 Pages 域名绑定；Cloudflare Full (strict) 保持不变。
- 公网 `/health`、排行榜、JS 返回 la-vps 内容；最高分 67600；源码路径返回 404。
- 新旧 API 地址返回相同数据，旧地址的请求已由 VPS 处理。
- 最终导入后已执行一致性备份。Firestore 原数据和旧 revision 保留。
- 浏览器确认排行榜展示 demoloong，下载链接自动更新至 v1.5.0，未出现控制台错误；新旧 API 的 POST 请求体和原 Authorization 已验证透传，使用非法分数验证而未修改战绩。
