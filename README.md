# Dear Elsewhere（致别处）

*An invitation to notice the world.* 一份重新观察世界的邀请。

在 X 发布原创探索邀请并加上 `#DearElsewhereQuest`，或在现实中完成一次探索，直接回复原帖并加上 `#DearElsewhereDone`。参与者只需使用 X。邀请长期开放。

网站有三个页面。首页先介绍玩法。点击抽签可从公开索引随机得到三封不同的邀请，任选一封即可查看详情；不足三封时显示现有邀请。抽签使用本地数据库，不消耗 X API 额度。下方按时间倒序列出邀请，每封附上最近一条完成回应，以枝线标出关联。详情页可阅读全部直接回应并前往 X 写回信。About 介绍项目理念。正式页面通过 X 官方组件展示内容，禁用 JavaScript 或组件加载失败时仍有原文链接。模拟模式完全离线。

## 先看演示

需要 Python 3.11 或以上版本。以下命令适用于 macOS 和 Linux。在 Debian 12 上可先执行 `sudo apt install git python3-venv`。首次安装依赖需要联网。

```sh
git clone https://github.com/DayuGuo/dear-elsewhere.git
cd dear-elsewhere
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export DEAR_DB="$PWD/instance/demo.sqlite3"
.venv/bin/python -m elsewhere demo
.venv/bin/gunicorn --no-control-socket --bind 127.0.0.1:8791 elsewhere.web:app
```

打开 <http://127.0.0.1:8791>。在 VPS 上运行时，从自己电脑另开终端执行下列命令，再打开同一地址。把 `vps` 换成自己的 SSH 主机别名。

```sh
ssh -N -L 8791:127.0.0.1:8791 vps
```

演示库有六封虚构邀请，足以体验抽签和重抽。打开声音探索邀请可以查看两条完成回应。已安装旧演示库时再运行一次 demo 命令即可补齐样本。演示库标记为 demo，重复初始化不会产生副本，对它运行同步会被拒绝。按 Ctrl+C 停止演示，再执行 `unset DEAR_DB`。离线回归测试用临时数据库运行：

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## 部署到 Debian 12

架构为 Flask + Jinja + SQLite，Gunicorn 使用一个 worker、两个线程。systemd 管理网站和每小时一次的同步。以下步骤均在上面已经克隆的仓库根目录执行。私有仓库需要先给部署用户配置 GitHub 读取权限，也可用已获授权的 SSH 地址克隆。

### 1. 安装应用

```sh
sudo apt update
sudo apt install python3-venv
getent passwd dear-elsewhere >/dev/null || sudo useradd --system --user-group --home-dir /var/lib/dear-elsewhere --no-create-home --shell /usr/sbin/nologin dear-elsewhere
sudo install -d -m 0755 /opt/dear-elsewhere
git archive HEAD | sudo tar -x -C /opt/dear-elsewhere
sudo python3 -m venv /opt/dear-elsewhere/.venv
sudo /opt/dear-elsewhere/.venv/bin/pip install -r /opt/dear-elsewhere/requirements.txt
sudo install -d -o dear-elsewhere -g dear-elsewhere -m 0700 /var/lib/dear-elsewhere
sudo install -m 0644 deploy/dear-elsewhere* /etc/systemd/system/
sudo systemctl daemon-reload
```

### 2. 配置并启动网站

首次安装时复制环境示例，再用编辑器填入服务端配置。

```sh
sudo test -e /etc/dear-elsewhere.env || sudo install -m 0600 .env.example /etc/dear-elsewhere.env
sudoedit /etc/dear-elsewhere.env
sudo systemctl enable --now dear-elsewhere.service
curl -fsS http://127.0.0.1:8791/ >/dev/null
```

启动前服务会执行幂等的 `python -m elsewhere init`。即使没有 X Token，首页也可以访问，显示等待第一封邀请的状态。生产索引与演示库使用不同文件。环境文件由 systemd 读取，Web 进程启动时会移除 Token。

| 变量 | 默认值或示例 | 用途 |
| --- | --- | --- |
| `DEAR_DB` | `/var/lib/dear-elsewhere/index.sqlite3` | 生产库路径。开发时未设置则使用当前目录下的 `instance/index.sqlite3` |
| `X_BEARER_TOKEN` | 留空 | X 开发者应用的 app-only Bearer Token，真实查询时必填 |
| `X_MONTHLY_READ_LIMIT` | `1500` | UTC 自然月内搜索和按 ID 复查共享的本地读取额度，设为 0 可暂停所有 API 读取 |
| `X_MAX_PAGES` | `12` | 每轮最多处理的搜索页数，达到上限后下轮续跑 |
| `DEAR_CONTACT_EMAIL` | 留空 | 公开站点的联系邮箱，配置后 About 显示移除及失效链接反馈入口 |

默认只监听回环地址 `127.0.0.1:8791`，可继续使用前述 SSH 隧道。对公网开放时，在现有反向代理中给项目域名添加独立站点，将上游指向该地址并配置 HTTPS。例如已有 Caddy 时，站点内容可用 `reverse_proxy 127.0.0.1:8791`。容器内的代理需使用其可达的宿主机上游。安装步骤不需要占用 80 或 443 端口。

### 3. 首次真实同步

在 X Developer Console 确认应用可以调用 Recent Search，有可用额度，并设置适合的消费上限。将 Token 填入环境文件。先单次运行并检查日志，再启用定时器。

```sh
sudo systemctl start dear-elsewhere-sync.service
sudo journalctl -u dear-elsewhere-sync.service -n 40 --no-pager
sudo systemctl enable --now dear-elsewhere-sync.timer
systemctl list-timers dear-elsewhere-sync.timer
```

成功但收到 0 条结果是正常情况。可在 X 发布一条带标签的公开原创邀请，等 X 编入搜索后跑一次同步，再直接回复原帖并用相同方式验证。首页应出现邀请，详情应出现回应。排查凭据时查看 HTTP 状态码即可，不要将 Token 写入工单或命令行历史。

## 同步与费用

每小时请求 `GET /2/tweets/search/recent`，查询为：

```text
(#DearElsewhereQuest OR #DearElsewhereDone) -is:retweet
```

- 首次使用 Recent Search 默认的最近七天窗口。有可用游标时使用 `since_id`。分页保留原查询边界，每页的索引记录与下页令牌在同一事务中提交。整批成功后才更新正式游标。进程崩溃或达到页数上限时从已提交的分页位置恢复。
- 帖子 ID 为去重键。原创邀请必须带邀请标签。回应必须带完成标签，并通过 `referenced_tweets.replied_to` 指向直接父帖。存在 `conversation_id` 时额外验证它与邀请 ID 一致。父帖暂未发现时保留回应，父帖入库后自动显示。如果邀请已超出七天窗口且从未入库，回应会继续待关联。
- 网络故障和 5xx 进行有界退避重试。429 持久化冷却截止时间，由后续定时任务重试。401、403 和额度错误保留正式游标。长时间停机后只能恢复最近七天内仍可搜索的帖子。同步和复查使用同一文件锁。
- 数据库保存 ID、发布时间、父帖及会话 ID、索引类型、隐藏或移除状态、游标和额度。原文链接由 ID 生成。正文、作者资料、图片和视频不会写入数据库或日志。
- 每次发请求前先持久化预留读取数。完整成功的响应按返回数量核销；结果不明确时保留预留，防止超时、重试或进程退出绕过上限。搜索每页至少请求 10 条，因此本月余额不足 10 时停止搜索，次月自动恢复。日志中的数字是本地保护计数。
- 按 30 条/日、30 天、每条读取 0.005 美元计算，基础读取约 **4.50 美元/月**。首次回填、复查和重读可能增加用量。实际费用以账号的端点价格及账单为准。[X 公开价格](https://developer.x.com/) · [X 计费说明](https://docs.x.com/x-api/getting-started/pricing)

[Recent Search 参考](https://docs.x.com/x-api/posts/search-recent-posts) · [分页与增量查询](https://docs.x.com/x-api/posts/search/integrate/paginate)

## 管理索引

在 VPS 的 shell 中定义以下函数即可对生产实例执行命令。它复用生产服务的账户、工作目录和环境文件，不会把令牌写入命令行。

```sh
dear() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --uid=dear-elsewhere --gid=dear-elsewhere \
    --working-directory=/opt/dear-elsewhere \
    --property=EnvironmentFile=/etc/dear-elsewhere.env \
    /opt/dear-elsewhere/.venv/bin/python -m elsewhere "$@"
}
dear status
```

| 命令 | 效果 |
| --- | --- |
| `dear hide POST_ID` | 立即隐藏记录，隐藏整封邀请也会使其回应无法从网站访问 |
| `dear show POST_ID` | 核实仍公开后恢复已隐藏记录 |
| `dear remove POST_ID` | 删除索引记录，只保留屏蔽 ID，避免同步再次收录 |
| `dear check-links ID [ID ...]` | 通过 X Lookup 复查 1–100 个 ID，会消耗读取额度。对确认已失效、无权查看或被 withheld 的记录执行隐藏。模糊结果和 API 故障不会触发批量隐藏 |

将占位符替换为 X 原文链接末尾的数字。正式公开前填写联系邮箱，对删除、保护及更正请求及时处理。Recent Search 用来发现新帖，无法通知所有旧帖的状态变化；收到失效报告时先隐藏，再按 ID 核实。永久移除后请保留数据库中的屏蔽记录，恢复备份时注意重新应用备份之后的移除。运营要求见 [X Developer Policy](https://docs.x.com/developer-terms/policy)。

## 更新与排查

在克隆目录执行 `git pull --ff-only`，重新执行“安装应用”中的代码导出、依赖安装、unit 安装和 daemon-reload，再执行 `sudo systemctl restart dear-elsewhere.service`。同步任务下次运行时读取新代码及配置。升级前可用 SQLite 的在线 backup 功能备份索引。配置和数据库均位于代码目录以外。

- 网站启动失败时查看 `sudo journalctl -u dear-elsewhere.service -n 50`，核对数据库目录所有权和监听端口。
- 同步失败时查看同步日志和 `dear status`。401/403 先检查应用权限与 Token，402 检查 X 余额，429 等待冷却。长时间停用同步可执行 `sudo systemctl disable --now dear-elsewhere-sync.timer`。
- 嵌入组件可能被浏览器隐私设置拦截，页面始终提供 X 原文链接。
