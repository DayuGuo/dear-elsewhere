# Dear Elsewhere（致别处）

*An invitation to notice the world.* 一份重新观察世界的邀请。

在 X 发布原创探索邀请并加上 `#DearElsewhereQuest`，或在现实中完成一次探索，直接回复原帖并加上 `#DearElsewhereDone`。参与者只需使用 X。邀请长期开放。

网站有四个公开页面。首页可抽取任务，独立的 [How to play](https://dearelsewhere.anotherdayu.com/how-to-play) 通过一对示例明信片说明邀请和回信的规则。点击抽签可从公开索引随机得到三封不同的邀请，任选一封即可查看详情；不足三封时显示现有邀请。抽签使用本地数据库，不消耗 X API 额度。首页的「任务与回信」按任务发布时间倒序排列。手机每行两张，桌面每行三至四张，每张以任务为起点，最近一封直接回信嵌在同一张卡片内，可单独折起。日期旁的箭头通往对应的 X 原帖。详情页可阅读全部直接回应并前往 X 写回信。About 介绍项目理念。首页卡片、抽出的来信和任务详情共用一套纸色与排版。浏览器通过 X 官方 oEmbed 读取文字，列表展示摘要，抽信和详情页展示全文及正文链接。纯图片帖使用 X 官方嵌入组件，禁用 JavaScript 或组件加载失败时仍有原文链接。模拟模式完全离线。

## 界面与语言

项目标志是一枚野蔷薇邮票。票面借用十九世纪博物学图谱的铜版排线与淡彩，墨绿铭条上印有植物学名 *Rosa canina*。中英文页眉各有一份可独立使用的组合标，浏览器标签页使用专为小尺寸绘制的花形简版。[邮票原图](elsewhere/static/brand/mark.svg) · [中文组合标](elsewhere/static/brand/logo-zh.svg) · [英文组合标](elsewhere/static/brand/logo-en.svg) · [图标](elsewhere/static/brand/favicon.svg)

<details>
<summary>邮票插画制作记录</summary>

花枝插画采用内置 imagegen 生成，齿孔边框、铭条、字标组合和小尺寸图标另行绘制。插画提示词如下。

> Botanical specimen artwork for the center of a small postage stamp. A single flowering sprig of Rosa canina on plain uniform warm white. One large open five-petalled dog rose in three-quarter view, a golden cluster of stamens, one small closed bud, two serrated leaves and a short gently arched stem. Compact vertical arrangement with strong silhouette and a large blossom. Authentic 19th-century natural history plate, delicate dark olive copperplate outlines and directional burin hatching, pale dusty pink watercolor on petals, muted sage leaves. Quiet, lucid and finely observed. Fill the composition with the sprig. No text, numbers, border, shadows, postage marks or additional specimens.

</details>

页面采用从挂信树插画空白处取样的暖白色（`#FCF9F6`）。点击挂信树或“抽三封信”，会随机取到最多三封来信。每封都可以独立拆开、折起，读完再选一封带出门。枝上的回信也可以逐封展开与收起。拆信使用浏览器原生控件，可以用键盘操作；系统开启减少动态效果时，页面直接显示展开结果。[观看早期版的取信与拆信演示](docs/previews/picking-letters.mp4)

首页的挂信树以十九世纪手工着色的铜版博物学图谱为参照。页面提供简体中文与英文。首次访问跟随浏览器语言，页首可切换并记住选择，抽签结果和当前页码会保留。界面、日期与虚构演示来信随语言切换，真实 X 原帖保留作者原文。

站点本地加载 Cormorant Garamond 和 Noto Serif SC 的 WOFF2 字体子集，授权文件位于 `elsewhere/static/fonts/`。中文子集收录当前模板与演示来信所用的字，其余字回退到设备宋体。

| 模拟数据首页 | 桌面（1360 × 1000） | 手机（390 × 844） |
| --- | --- | --- |
| 中文 | [查看截图](docs/previews/desktop-zh.png) | [查看截图](docs/previews/mobile-zh.png) |
| English | [View screenshot](docs/previews/desktop-en.png) | [View screenshot](docs/previews/mobile-en.png) |

开启 JavaScript 时，刷新、分享网址或切换语言都能保留已拆开的信。三封展开的模拟来信可见[桌面版](docs/previews/three-letters-zh.png)及[手机版](docs/previews/three-letters-mobile-zh.png)。[八项设计复核](docs/design-review.md)记录了早期拆信界面的取舍及验证结果。

## VPS 一键安装

默认站点为 **https://dearelsewhere.anotherdayu.com/**。首次安装前，在 `anotherdayu.com` 的 DNS 管理面板添加 A 记录，主机名填 `dearelsewhere`，值填 VPS 公网 IPv4。若使用 AAAA 记录，指向同一台可通过 IPv6 访问的 VPS。使用 Cloudflare 时可先选「仅 DNS」。在云防火墙及 VPS 防火墙放行入站 TCP 80 和 443，Gunicorn 的 8791 端口只需在本机监听。

在使用 systemd 的 Debian 12+ 或 Ubuntu 24.04+ VPS 上登录交互式 SSH，准备好 X 应用的 **Bearer Token** 和 `curl`，然后执行：

```sh
curl -fsSLo "$HOME/dear-elsewhere-install.sh" https://raw.githubusercontent.com/DayuGuo/dear-elsewhere/main/install.sh && sudo bash "$HOME/dear-elsewhere-install.sh"
```

域名提示直接回车即可使用默认域名，也可填写自己的子域名。首次安装时再粘贴 X Bearer Token，输入隐藏。脚本启动网站和每小时定时器，立即执行一次标签同步，然后配置 HTTPS。首次同步查询最近七天，可能使用 X API 额度。同步和 HTTPS 分别报告结果，任一失败时脚本返回非零状态。

- **空闲 VPS** 使用 Caddy 自动签发和续期证书，并将 HTTP 跳转到 HTTPS。
- **已有反向代理** 时，脚本复用运行中的标准 systemd Caddy 或 Nginx。Caddy 使用标准 Caddyfile，Nginx 使用包含在主配置中的 `/etc/nginx/conf.d/*.conf`。Nginx 路径通过 Certbot 的 webroot 模式向 Let's Encrypt 申请证书，接受其订户协议，启用 `certbot.timer`，续期后重载 Nginx。已有其他服务占用公网端口时，脚本会提示在该服务中添加域名，并保留已运行的应用和定时器。
- **仅本机测试** 时，域名提示输入 `-` 会跳过代理配置。可从自己电脑运行 `ssh -N -L 18791:127.0.0.1:8791 用户名@VPS地址`，再打开 <http://127.0.0.1:18791>。已有的公网配置会继续生效。

安装成功后直接打开脚本显示的 HTTPS 地址。如果 DNS 尚未生效或证书未签发，检查解析及端口后重新执行同一条命令，已有 X Token 和数据会保留。

在 VPS 上可查看下次同步时间和最近的同步结果：

```sh
systemctl list-timers --all dear-elsewhere-sync.timer
sudo journalctl -u dear-elsewhere-sync.service -n 40 --no-pager
```

重复执行安装命令可更新代码并再次同步，已有 Token、自定义配置、索引和同步游标会保留。要替换 Token，执行 `sudo bash "$HOME/dear-elsewhere-install.sh" --replace-token`。配置存放在仅 root 可读写的 `/etc/dear-elsewhere.env`，数据库默认位于 `/var/lib/dear-elsewhere/index.sqlite3`。

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

## 服务配置

Gunicorn 使用一个 worker 和两个线程。systemd 在启动网站前初始化数据库，只有同步进程使用 Token。修改配置可执行 `sudoedit /etc/dear-elsewhere.env`，网页设置在 `sudo systemctl restart dear-elsewhere.service` 后生效，同步设置在下次运行时生效。

| 变量 | 默认值或示例 | 用途 |
| --- | --- | --- |
| `DEAR_DB` | `/var/lib/dear-elsewhere/index.sqlite3` | 生产库路径。开发时未设置则使用当前目录下的 `instance/index.sqlite3` |
| `X_BEARER_TOKEN` | 留空 | X 开发者应用的 app-only Bearer Token，真实查询时必填 |
| `X_MONTHLY_READ_LIMIT` | `1500` | UTC 自然月内搜索和按 ID 复查共享的本地读取额度，设为 0 可暂停所有 API 读取 |
| `X_MAX_PAGES` | `12` | 每轮最多处理的搜索页数，达到上限后下轮续跑 |
| `DEAR_CONTACT_EMAIL` | 留空 | 公开站点的联系邮箱，配置后 About 显示移除及失效链接反馈入口 |

Gunicorn 监听 `127.0.0.1:8791`，公网 80/443 由反向代理监听。自管代理可在现有站点管理工具中将域名转发到这个上游。容器内的代理需要能连接宿主机上的上游。

### 手动触发同步

在 X Developer Console 确认应用可以调用 Recent Search，有可用额度，并设置适合的消费上限。一键安装已启用定时器，需要立即检查新邀请时可执行下面的命令。

```sh
sudo systemctl start dear-elsewhere-sync.service
sudo journalctl -u dear-elsewhere-sync.service -n 40 --no-pager
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

更新前可用 SQLite 的在线 backup 功能备份索引，再重新执行 VPS 一键安装命令。

- 网站启动失败时查看 `sudo journalctl -u dear-elsewhere.service -n 50`，核对数据库目录所有权和监听端口。
- 同步失败时查看同步日志和 `dear status`。401/403 先检查应用权限与 Token，402 检查 X 余额，429 等待冷却。长时间停用同步可执行 `sudo systemctl disable --now dear-elsewhere-sync.timer`。
- 站内显示文字和已确认的纯图片附件。含视频、动图、混合图片与视频或媒体类型未知的帖子以隐藏媒体的模式嵌入，仍可在 X 打开原帖。同步只保存一个图片展示标记。旧索引升级时默认隐藏媒体，使用 `check-links` 复查可恢复旧图片帖的展示。
- 嵌入组件可能被浏览器隐私设置拦截，页面始终提供 X 原文链接。

## 开源许可

项目代码采用 [MIT 许可证](LICENSE)。随附字体沿用各自的 [SIL Open Font License](elsewhere/static/fonts/)。X 用户发布的内容由原作者在 X 上提供。
