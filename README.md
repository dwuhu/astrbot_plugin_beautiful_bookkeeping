# 精美记账 · AstrBot 插件 v1.0.2

[![Release](https://img.shields.io/github/v/release/dwuhu/astrbot_plugin_beautiful_bookkeeping?label=release)](https://github.com/dwuhu/astrbot_plugin_beautiful_bookkeeping/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.24-ff69b4)](https://github.com/AstrBotDevs/AstrBot)

多平台精美记账插件：**QQ / 个人微信 / 公众号 / 企业微信** 一套代码，液态玻璃图片卡片 + **AstrBot 面板内嵌记账页面**。

仓库：<https://github.com/dwuhu/astrbot_plugin_beautiful_bookkeeping> · 作者：**九月月**


> 核心原则：**所有账目只能由用户手动录入**，机器人不会、也不能自动抓取任何支付账单；**数字全部由程序算，AI 只负责解读和建议**，永远不改数据。

这是面向开源发布的**首个正式版本**（当前 **v1.0.2**）：记账 / 查账 / 改删 / 预算与梯度提醒 / 存钱目标与购买力测算 / 每日简报 / 收支对比图 / 账单截图导入 / 每日扣款 / AI 技能中心 / **省钱建议** / 面板 8 页签，全部收在这一版里。v1.0.1 按插件审核要求把数据改到 `data/plugin_data/<插件名>`；v1.0.2 新增「记账 省钱建议」，读上月支出、点名可压缩的分类并给出下月目标预算。逐条变更见 [`CHANGELOG.md`](./CHANGELOG.md)，GitHub Release 文案见 [`RELEASE_NOTES.md`](./RELEASE_NOTES.md)。

---

## 一、先看这 6 条规则

1. **账本隔离键** = `platform + session_id + user_id`
   同一个 QQ，在 A 群、B 群、私聊，是三本完全独立的账；同群内每个人只看得到自己的。
2. **录入方式**：聊天指令手动记账；AI 自然语言记账解析后必须你回「确认」才写入。
3. **退款**算抵扣：冲减支出和预算消耗，不算收入。
4. **月度预算**：只统计当月支出（退款已抵扣），用到 70% / 90% / 超支各提醒一次（每月每档一次，不刷屏）。
5. **天气**不需要任何 API Key，走公开天气源；查不到时可以交给 AI 兜底。
6. **输出**：文字 / 图片两种，可个人设默认，也可单次临时指定。
7. **存钱目标**：进度 = 目标起点已存 + 从目标开始那天到今天的净结余（收入 − 支出 + 退款），所以你正常记账它自己往前走，不用每天手填。
8. **购买力测算**：结论由程序按「可动用存款 − 拟购金额 vs 一个月生活费安全垫」算三档（可以买 / 建议再等等 / 不建议现在买），AI 只补一段解读。

---

## 一·五、效果预览（截图见 `docs/screenshots/`，全部由插件真实渲染）

以下都是插件真实渲染的图（带「示例数据」水印，不是真实账本）：

| 聊天卡片 | 面板页面 |
|---|---|
| ![本月报表](./docs/screenshots/report.jpg) | ![面板设置页](./docs/screenshots/view_settings.jpg) |
| ![每日简报](./docs/screenshots/digest.jpg) | ![存钱目标页](./docs/screenshots/view_goal.jpg) |

聊天卡片：

| 文件 | 说明 |
|---|---|
| `docs/screenshots/report.jpg` | 本月报表：三 KPI + 支出结构环 + 预算灯带 + 上月对比复盘 + 明细分页 |
| `docs/screenshots/alert.jpg` | 超预算提醒：70% / 90% 阈值刻度、已超出金额、暖色安抚文案 |
| `docs/screenshots/digest.jpg` | 每日简报：天气（免 Key）+ 今日收支 + 预算 + **存钱目标进度** + 今日明细 + AI 小结 |
| `docs/screenshots/ai.jpg` | AI 消费分析：分段解读 + 三指标 + 分类条形 |
| `docs/screenshots/goal.jpg` | 存钱目标卡：进度环（按节奏变色）+ 目标/已存/还差 三块 + 灯带 + 日均建议 + AI 建议 |
| `docs/screenshots/advice.jpg` | 购买力测算卡：结论大字 + 可动用/买完剩/安全垫三块 + 依据 + 怎么做 + AI 解读 |
| `docs/screenshots/saving.jpg` | **下月省钱建议卡**：上月支出 / 可省空间 / 下月目标三指标 + 逐类怎么省 + 分类占比条 |
| `docs/screenshots/trend_today.jpg` | **今收支图卡**：今日收/支/结余三 KPI + 近 7 天双色柱（柱下标注收 / 支金额）+ 今日支出结构 + 与昨天对比一句话 |
| `docs/screenshots/trend_month.jpg` | **月收支图卡**：本月三 KPI + 近 6 个月双色柱 + 本月支出结构 + 与上月对比 |
| `docs/screenshots/trend_year.jpg` | **年收支图卡**：今年三 KPI + 近 5 年双色柱 + 今年支出结构 + 与去年对比 |
| `docs/screenshots/help.jpg` `help2.jpg` `help3.jpg` | 图文指令手册 3 页：12 类 59 条分 3 张，每张一屏可读，二次元夜景底图 + 纯白字 + 红色点缀 |

面板页面（AstrBot → 插件 → 精美记账 → 记账本）：

| 文件 | 说明 |
|---|---|
| `docs/screenshots/view_overview.jpg` | 总览：4 KPI + 7 天趋势折线 + 支出结构甜甜圈 + 活跃账本 |
| `docs/screenshots/view_records.jpg` | 流水：按时间倒序、类型色块、改 / 删、翻页 |
| `docs/screenshots/view_budget.jpg` | 预算：每本账的月预算、灯带进度、健康 / 已超支状态，右上角「⚙ 提醒设置」跳到设置页 |
| `docs/screenshots/view_settings.jpg` | **⚙ 设置页**：提醒开关 / 档位 / 频率表 + 指令速查 + 运行信息 |
| `docs/screenshots/view_settings_alert.jpg` | 设置页把某本账改成「档位 50,90 + 每次都提醒」并保存后的状态 |
| `docs/screenshots/view_goal.jpg` | 存钱目标：目标表（金额/已存/进度/预计达成）、新建、改、删 |
| `docs/screenshots/view_goal_advice.jpg` | 同一页的**购买力测算**区：填金额点「算一算」就地出结论、依据、怎么做 |
| `docs/screenshots/view_push.jpg` | 推送与城市：推送开关、城市、时间、推送日志 |
| `docs/screenshots/view_category.jpg` | 分类：改名、改色、启停、合并 |
| `docs/screenshots/view_ai.jpg` | AI：开关状态 + 调用日志 + 清复盘缓存 |

平台适配（`platform` 字段 → 显示标签）：

| platform | 来源 | 标签 |
|---|---|---|
| `aiocqhttp` | QQ（OneBot） | QQ |
| `wechatpadopen` / `wechat` | 个人微信 | 微信 |
| `wechat_official_account` | 公众号 | 公众号 |
| `wecom` | 企业微信 | 企业微信 |
| 其他 | 未知适配器 | 原样显示 |

> 私聊的 `session_id` 固定写成字符串 `private`，群聊写群号，所以「同一个人在群 A / 群 B / 私聊」是三本互不相干的账。

---

## 二、目录结构

```
astrbot_plugin_beautiful_bookkeeping/
├── metadata.yaml            # 插件元信息
├── _conf_schema.json        # 配置项（AstrBot 面板会读这个）
├── requirements.txt
├── main.py                  # 指令入口、消息分发、简报推送、注册面板接口
├── core/
│   ├── database.py          # SQLite 全部表 + CRUD（含 saving_goal 存钱目标表）
│   ├── stats.py             # 时间区间、预算进度、上月对比、目标进度、资金稳定性、购买力测算
│   ├── render_text.py       # 文字报表
│   ├── helpdoc.py           # 指令手册（文字版 / 图片版共用一份数据）
│   ├── render_image.py      # Jinja2 + Playwright 渲染图片
│   ├── ai_skill.py          # AI 分析 / 复盘 / 口语记账解析 / 全量账本上下文 / 购买建议
│   ├── weather.py           # 天气（免 Key）
│   ├── viewapi.py           # 面板页面用到的 27 个接口
│   └── scheduler.py         # 每日简报定时器
├── templates/               # 聊天图片卡片模板（液态玻璃）
│   ├── base.css
│   ├── report.html          # 本月/今日报表卡
│   ├── alert.html           # 预算提醒卡
│   ├── digest.html          # 每日简报卡（带天气 + 目标进度）
│   ├── ai.html              # AI 分析卡
│   ├── goal.html            # 存钱目标卡
│   ├── advice.html          # 购买力测算卡
│   └── help.html            # 图文指令手册卡（二次元夜景底图 + 白字红点缀）
├── assets/                  # 卡片用图（打包内置，离线可用）
│   └── anime_bg.jpg         # 帮助卡底图（内联成 data URI 渲染）
├── views/bookkeeping/       # 面板页面（AstrBot Plugin View）
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .astrbot-plugin/i18n/    # 页面标题 / 描述的多语言文案
│   └── zh-CN.json
├── dev/                     # 开发自测（不参与运行，可删）
└── docs/screenshots/        # README 用的示例截图（带「示例数据」水印）
```

> 运行时数据**不写在插件目录里**：数据库与渲染出的卡片统一放在 AstrBot 的 `data/plugin_data/astrbot_plugin_beautiful_bookkeeping/`（`bookkeeping.db` + `cards/`），符合插件审核对持久化位置的要求。升级自 `v1.8` 以前的版本时，旧 `data/bookkeeping.db` 会自动复制到新位置。

---

## 三、安装（Windows + AstrBot，一次说清）

### 1. 把插件放进 AstrBot 插件目录

把整个 `astrbot_plugin_beautiful_bookkeeping` 文件夹复制到：

```
<你的 AstrBot 目录>/data/plugins/astrbot_plugin_beautiful_bookkeeping
```

### 2. 装依赖（用 AstrBot 自己的那个 Python）

在 AstrBot 目录打开 PowerShell，执行：

```powershell
.\venv\Scripts\activate
pip install -r data\plugins\astrbot_plugin_beautiful_bookkeeping\requirements.txt
```

> 如果 AstrBot 用的是别的虚拟环境路径，就先进那个环境再 pip。

### 3. 装浏览器内核（图片卡片必需）

```powershell
python -m playwright install chromium
```

> 装不上也没关系：插件会自动依次尝试 **自带 chromium → 系统 Edge → 系统 Chrome**；三者都没有时才降级成文字模式（不会报错、不会卡消息）。

### 4. 重载插件

AstrBot WebUI → 插件管理 → 找到「精美记账」→ 重载（或重启 AstrBot）。
日志里出现 `[记账] 插件已加载，数据目录: ...` 与 `[记账] 面板接口已注册 27/27 条` 就成功了。

### 5. 试一条

```
记账 支出 餐饮 18.5 晚饭
记账 本月
```

### 6. 打开记账页面

AstrBot WebUI → **插件** → 找到「精美记账」→ 点进插件详情里的 **记账本** 页面。
（页面由框架直接托管，不需要额外开端口、不需要账号密码，登录过 WebUI 就能看。）

---

## 四、指令速查

```
# 帮助
记账 帮助              （文字版，12 类 59 条）
记账 帮助 图片          （图文版，分 3 张卡片，按顺序看）

# 记账
记账 支出 餐饮 18.5 晚饭 #聚餐
记账 收入 工资 4500
记账 退款 购物 39 退货
记账 餐饮 18.5           （省略类型 = 支出）

# 查询（后面可加「图片」或「文字」单次切换）
记账 今日 / 本周 / 本月 / 上月 / 全部
记账 本月 收入 / 支出
记账 本月 第2页
记账 查 关键词   记账 查 #标签   记账 查分类 餐饮
记账 查时间段 2026-11-01 2026-11-20

# 收支对比图（今日 / 月 / 年三个口径，都可加「图片 / 文字」）
记账 今日收支            （今日三 KPI + 近 7 天双色柱 + 今日支出结构 + 对比昨天）
记账 月度收支            （本月三 KPI + 近 6 个月双色柱 + 本月支出结构 + 对比上月）
记账 年度收支            （今年三 KPI + 近 5 年双色柱 + 今年支出结构 + 对比去年）
记账 收支 本月 文字       （统称：记账 收支 今日/本月/本年 [图片|文字]）

# 账单截图导入（AI 读图，核对后入账）
（发账单截图）记账 导入    （读明细 → 回「记账 确认」入账）
（发账单截图）记账 导入 直接（跳过核对，直接写进账本）

# 改 / 删（序号来自最近一次查询）
记账 修改 3 支出 餐饮 35 换个备注
记账 删除 3

# 预算
记账 设置月预算 3000
记账 查看月预算
记账 取消月预算

# 预算主动提醒（聊天里可改，改完存在数据库里，优先级高于配置文件）
记账 预算提醒                     （看这本账的：开关 / 档位 / 频率，每本账各一套）
记账 预算提醒 开 / 关              （关掉只是不主动推，简报里的进度照旧显示）
记账 预算提醒 档位 50 80 100       （1~999 的百分比，想设几个设几个，默认 70/90/100）
记账 预算提醒 频率 每次            （每次＝每笔都检查；每月＝每档每月一次（默认）；一次＝每档只响一次）

# 每日扣款（每天 0 点静默自动记一笔固定支出，不打扰、不推送）
记账 每日扣款 12 餐饮 早餐          （金额 + 分类 + 备注，分类写不对会按关键词猜，猜不到归「其他」）
记账 每日扣款                       （看金额 / 分类 / 开关 / 上次扣款日期）
记账 每日扣款 关 / 开               （暂停或恢复自动扣款，设置都留着）
记账 每日扣款 删除                  （彻底删掉这条规则）
      想改就直接重新设置一遍；跨天离线只补当天那一笔，不回填历史

# 输出模式
记账 模式 文字 / 图片

# 天气 & 每日简报
记账 设置城市 宜宾
记账 查看城市
记账 天气
记账 开启每日推送 / 关闭每日推送
记账 设置推送时间 21:30
      简报内容 = 天气 + 今日收入 / 支出 / 结余 + 本月预算进度 + 存钱目标进度 + 今日明细

# 存钱目标
记账 存钱目标 买相机 6000                     （开一个目标，进度从今天开始算）
记账 存钱目标 买相机 6000 截止 2027-03-01 已存 1200
记账 目标 / 存钱进度 / 我的目标 / 存钱         （多目标时一起列出来，带还差和节奏）
记账 目标 相机                                （只看某一个目标的详细卡）
记账 已存 2000                                （把目标之前已经攒的钱填成起点，可加目标名）
记账 存钱计划 相机                            （倒推每天 / 每周 / 每月存多少，AI 补一段从哪省）
记账 删除目标 买相机
      存到 25% / 50% / 75% / 100% 各播报一次；达标那天额外挂一句 AI 鼓励

# 购买力测算（要不要买）
记账 能买吗 4800 相机
记账 买得起吗 / 买不买 / 购买力 / 值得买吗      （同一能力的不同叫法）

# 省钱建议（读上月支出，给下月方案）
记账 省钱建议 / 下月建议 / 支出建议
记账 省钱建议 图片                          （出 AI 分析卡样式，指标换成可省空间 / 下月目标）

# AI
记账 AI 帮我分析本月消费
记账 AI 我现在能买 4800 的相机吗               （会走购买力分支，给结论 + 依据 + 怎么做）
记账 AI 帮我定个存钱计划
记账 AI 晚饭花了26                            → 回「记账 确认」才写入
记账 确认 / 取消

# 分类
记账 分类列表
记账 添加支出分类 健身
记账 添加收入分类 副业
记账 删除分类 健身
记账 合并分类 旧分类 新分类
```

> 任何查询后面加「图片」或「文字」可单次切换输出，例如 `记账 目标 图片`、`记账 能买吗 4800 相机 图片`。

---

## 四·五、技能中心（给 AI 调用，只含普通用户权限）

插件内置 22 个技能，把「用户自己能做的事」全部包出来：记账 / 查账 / 改删 / 报表 / 稳定性 / 预算 / 预算提醒设置 / 存钱目标增删查 / 购买力测算 / 分类增删合并 / 今日简报 / 帮助 / 输出模式。

**明确不含**后台管理权限：没有管理员登录、没有跨账本读写、没有面板路由管理、没有导出/备份/清日志这类运维动作。技能只能动**调用者自己这本账**（`platform + session_id + user_id`），改删前校验归属，越权直接拒。

用法一 · 聊天指令（不用开函数调用也能用）：

```
记账 技能                                   # 列 22 个技能
记账 技能 调用 book_add {"amount": 18.5, "category": "餐饮"}
记账 技能 调用 book_buy_advice {"amount": 4800, "title": "相机"}
记账 技能 调用 book_alert_config {"levels": "50,80,100", "repeat": "always"}
```

也支持 `k=v` 简写：`记账 技能 调用 book_add amount=18.5 category=餐饮`。

用法二 · 框架函数调用（AI 自己调）：插件注册了两个 LLM 工具，开启「函数调用」后 AI 会先调 `bookkeeping_skills` 拿清单，再调 `bookkeeping_call` 传 `skill` + `args`（JSON 字符串），返回值也是 JSON。

22 个技能 id：

| 分组 | 技能 id |
|---|---|
| 流水 | `book_add` `book_list` `book_update` `book_delete` `book_import` |
| 统计 | `book_summary` `book_stability` `book_trend` |
| 预算 | `book_budget_view` `book_budget_set` `book_alert_config` |
| 存钱目标 | `book_goal_list` `book_goal_set` `book_goal_delete` |
| 决策 | `book_buy_advice` |
| 分类 | `book_category_list` `book_category_add` `book_category_delete` `book_category_merge` |
| 其他 | `book_digest` `book_help` `book_mode` |

配置里 `skill_enable` 可整体关闭技能中心；`allow_delete=false` 时技能也删不了账。

---

## 五、面板页面（AstrBot 插件视图）

打开方式：**AstrBot WebUI → 插件 → 精美记账 → 记账本**。页面在框架内以受控 iframe 加载，静态资源和接口都走框架自动注入的 token，不用自己配鉴权。

### 页面里能做什么

| 页签 | 内容 |
|---|---|
| 总览 | 本月收入 / 支出 / 结余 / 活跃账本；7 天收支趋势折线；本月支出结构甜甜圈 + 图例；活跃账本列表（一键跳到该账本流水） |
| 流水 | 按账本筛选、按类型 / 关键词筛、当月翻页浏览、就地修改金额与分类、逐条删除、导出 CSV |
| 预算 | 每个账本一行：设月预算、看已花 / 剩余 / 进度条；右上角「⚙ 提醒设置」一键跳到设置页 |
| ⚙ 设置 | 顶部「每日扣款」表：每本账一行，金额 / 分类 / 备注 / 保存 / 暂停 / 删除，显示上次扣款日期；下方是预算提醒开关 / 档位 / 频率 + 保存；再下面是指令速查与运行信息（与聊天指令同一份数据） |
| 存钱目标 | 每个账本的目标表：目标名、金额、起点已存、进度灯带、预计达成日；可直接改金额 / 截止日 / 起点已存、一键删除。下方是**购买力测算**：填「买什么 + 金额」点「算一算」，就地给出结论、三块关键数字、依据、怎么做 |
| 推送与城市 | 每个账本设城市和推送时间；一键开关每日简报；下方是最近 60 条推送日志（sent / skipped / failed + 原因） |
| 分类 | 改名、改色（颜色块直接在页面上挑）、启用 / 停用、新增分类、合并分类（把旧分类的账并到新分类） |
| AI | AI 技能 / 上月复盘的开关状态；最近调用记录（时间、账本、提问、结果）；清空复盘缓存 |

### 实现方式（给二次开发看的）

- 页面文件在 `views/bookkeeping/`，由 AstrBot 自动识别为插件视图，标题取自 `.astrbot-plugin/i18n/zh-CN.json` 的 `views.bookkeeping.title`。
- 前端用 `window.AstrBotPluginView` 桥接：`ready()` → `apiGet(endpoint, params)` / `apiPost(endpoint, body)`，endpoint 不带前缀（如 `overview`）。
- 后端在 `main.py` 的 `_register_view_api()` 里用 `context.register_web_api("/<插件名>/<路径>", handler, methods=[...])` 注册，共 27 条；处理函数在 `core/viewapi.py`，参数从 `astrbot.api.web.request` 取。
- 页面**自包含**：没有 CDN、没有外链字体，图表是手写 SVG + `conic-gradient`，断网也不白屏。
- 页面和聊天读写同一个 `data/bookkeeping.db`（WAL 模式），聊天里记一笔，刷新页面就能看到。
- 配置项 `view_page_enable`（默认开）控制是否注册这些接口；关掉只影响页面，聊天功能照旧。
- 需要 **AstrBot 4.24+**（提供 Plugin Views / `register_web_api`）。旧版本插件会自动跳过注册并打一行日志，聊天记账不受影响。

---

## 六、配置项说明（`_conf_schema.json`）

| 键 | 默认 | 说明 |
|---|---|---|
| `enable_group` / `enable_private` | true | 群聊 / 私聊开关 |
| `default_output_mode` | text | 新用户默认输出模式 |
| `page_size` | 8 | 每次查询条数（决定「第N页」跨度） |
| `allow_delete` | true | 是否允许删除 |
| `require_confirm_delete` | false | 删除是否要二次确认 |
| `allow_custom_date` | false | 是否允许指定日期记账 |
| `default_categories` / `income_categories` | 内置 | 初始化分类，只在首次建库生效 |
| `view_page_enable` | true | 是否在框架面板里注册记账页面 |
| `weather_enable` | true | 天气总开关 |
| `weather_source` | auto | auto = 优先公开源，失败交 AI |
| `default_push_time` | 21:00 | 新用户默认推送时间 |
| `push_when_no_record` | false | 当天没记账也推送 |
| `budget_alert_enable` | true | 预算主动提醒总开关（聊天指令会覆盖此项） |
| `budget_alert_levels` | 70,90,100 | 提醒档位，逗号分隔的百分比，可随意加减（如 `50,80,100`） |
| `budget_alert_repeat` | month | month＝每档每月一次；once＝每档只提醒一次；always＝每次都提醒 |
| `deduct_enable` | true | 每日扣款总开关（关掉后聊天指令和面板都不再接受设置） |
| `ai_skill_enable` | true | AI 技能总开关 |
| `import_confirm` | true | 截图导入账单前是否要回「记账 确认」核对 |
| `ai_nl_book_confirm` | true | 口语记账是否要确认 |
| `ai_monthly_review_enable` | true | 本月卡是否带上月复盘 |
| `render.card_width` / `scale` | 1080 / 2 | 卡片宽度、渲染倍率（2 = 2 倍高清） |
| `render.background` | nebula | 背景：nebula / aurora / deep / anime（帮助卡固定用 anime 底图） |
| `render.enable_glow` | true | 霓虹光晕开关 |

---

## 七、这版做了什么，没做什么

**已实现**
- 多平台隔离账本、增删改查、分页、标签/分类/时间段检索、退款抵扣
- 文字 + 液态玻璃图片卡片（报表 / 预算提醒 / 每日简报 / AI 分析 四套）
- 月度预算主动提醒：默认 70 / 90 / 100 三档，聊天指令可改档位与频率（每次 / 每月一次 / 只一次），可整体关闭
- 本月卡片内置「上月对比复盘」面板（数字程序算，AI 只写建议，当天缓存）
- 每日简报：开关、自定义时间、天气、预算进度、可选 AI 一句话小结
- AI：消费分析、口语记账（需确认）、预算建议、上月复盘、**省钱建议**（上月分类 → 可压缩项 → 下月目标预算，刚性支出自动跳过）
- 框架内嵌记账页面：总览 / 流水 / 预算 / 存钱目标 / 推送与城市 / 分类 / AI / ⚙设置 八个页签，改删、调预算、改提醒设置、改分类、CSV 导出都在页面里做完
- 存钱目标：多目标共存、起点已存、截止日、进度环 / 灯带、按近 30 天速度推算达成日、25/50/75/100% 里程碑播报
- 购买力测算：三档结论 + 三块关键数字 + 依据 / 怎么做，聊天里一条指令、面板里点一下都能算
- 图文指令手册：`记账 帮助` 文字版（12 类 59 条）、`记账 帮助 图片` 三张玻璃卡片分页列清，和文字版共用同一份数据不会对不上
- 每日扣款：每本账可设一条「每天 0 点自动记一笔固定支出」，金额 / 分类 / 备注都能改，开关 / 删除随手可做；静默执行不推送，跨天离线只补当天一笔，面板「⚙ 设置」页可直接改
- 存钱计划：按目标倒推每天 / 每周 / 每月要存多少，差多少速度也会点出来
- 每日简报升级成「每日报账」：天气 + 今日收入 / 支出 / 结余 + 预算进度 + 目标进度 + 明细 + AI 小结
- AI 技能全量读账本：一次注入今日 / 本周 / 本月 / 上月、分类、预算、近 3 月稳定性、所有目标、最近 12 条流水，能答「能买吗」「帮我定存钱计划」「为什么这个月攒不下钱」

**暂缓 / 留了接口**
- 账单文件导入（CSV 上传解析）：表结构已够用，下一步加
- 预算按分类细分额度
- 多币种
- 页面里的 AI 复盘卡片（现在页面展示算好的数字与调用日志，AI 文本在聊天里生成）
- 目标到期前的主动倒计时提醒（现在只在 25/50/75/100% 与每日简报里出现）

---

## 七·五、口径说明（重要，避免误解）

**目标进度**
```
已存 = 起点已存（你手填的 saved_base） + 从 start_date 到今天 的净结余
净结余 = 收入 − 支出 + 退款
```
所以开目标后你只要照常记账，进度自己涨；想把「目标之前就攒下的钱」也算进来，用 `记账 已存 1200` 填起点。
一本账开多个目标时，各自从自己的 `start_date` 起算，想给每个目标分不同起点就分别用「已存 名字 金额」。

**资金稳定性**（用来判断"能不能买"）
- 近 3 个月逐月净结余 → 均值 / 波动 / 正结余月数
- 最近 8 周是否连续正结余
- 月均支出 → 折成「安全垫 = 1 个月生活费」
- 合成 0~100「稳健分」，分「稳 / 一般 / 偏紧」三档

**购买力三档**
```
可动用 = 有目标 ? 目标已存 : 近 3 个月累计净结余
买完剩 = 可动用 − 拟购金额
可以买     : 买完剩 ≥ 安全垫
建议再等等 : 买完剩 > 0 但 < 安全垫
不建议现在买: 买完剩 ≤ 0
```
AI 只在这三个数字之上补一句人话，不会改动结论。

---

## 八、常见问题

**图片发不出来 / 只有文字**
说明渲染引擎没起来。日志里搜 `[记账] 图片渲染不可用`。执行 `python -m playwright install chromium`，或确认系统装了 Edge / Chrome。

**面板里找不到「记账本」页面**
三种原因：① AstrBot 版本低于 4.24；② 配置里 `view_page_enable` 被关了；③ 插件没重载。日志里应有 `[记账] 面板接口已注册 27/27 条`，没有就按这三点排查。

**页面能打开但数据空白**
页面和插件共用 `data/bookkeeping.db`。确认插件正常加载过（`data/` 下生成了 `bookkeeping.db`），再点页面右上角「刷新」。

**公众号 / 企业微信不收图片**
部分账号类型不支持主动发图，`_send_proactive` 已经做了纯文字降级，简报仍会照常到达。

**每日简报没收到**
先看「推送与城市」页的推送日志：`skipped` = 当天没记账且关了 `push_when_no_record`；没日志 = 定时器没跑（确认插件已加载、该账本推送开关是「已开启」）。

**天气查不到**
公开源偶发限流，稍等再试；或在配置里把 `weather_source` 保持 `auto`，让 AI 兜底。

**预算提醒太吵 / 一次都不提醒？**
发 `记账 预算提醒` 看这本账的设置：`关` 就不主动推（简报里的进度仍在）；`频率 每次` 会每笔都查一遍，`每月` / `一次` 更安静。档位改完只影响之后的判定，已经提醒过的档位不会倒回去重发。

**提醒设置是全局还是每本账各一套？**
每本账各一套，而且按「平台 + 群 / 私聊 + 用户」分开存（`plugin_setting` 表里带账本前缀）。同一个群里每个人、同一个人的不同群、私聊，全都互不影响；换本账发 `记账 预算提醒` 看到的是那一本的值。

**提醒改完重启会丢吗？**
不会。聊天里改的开关 / 档位 / 频率写在数据库的 `plugin_setting` 表里，重启后仍生效；配置文件里那三个键只是首次的默认值。

**两个存钱目标的「已存」一样多？**
因为它们的进度都来自同一本账的净结余，起点相同就会同步走。想分开，就用 `记账 已存 名字 金额` 给每个目标设不同起点。

**开了目标之后，进度突然变大 / 变负？**
进度是把目标开始那天之后的净结余累加进来的；如果你在目标开始后才补记了大额收入，它会一次性跳上去，反之补记大额支出会把它压下来。想从某个时点重新算，用 `记账 已存 金额` 重置起点即可。

**购买力测算和 AI 说的不一样？**
结论永远以程序算的为准（会打印依据里的几行数字），AI 只是把这几行数字讲成人话；如果 AI 那段看着不对，关掉 `ai_skill_enable` 也照样能用测算。

---

## 九、发布与版本号

仓库：<https://github.com/dwuhu/astrbot_plugin_beautiful_bookkeeping>，发布材料三件套：`CHANGELOG.md`（逐条变更）、`RELEASE_NOTES.md`（可直接粘贴成 GitHub Release 文案）、`LICENSE`（MIT）。`.gitignore` 已排除真实账本（`*.db`）、预览目录与打包产物。

```bash
# 在项目根目录（有 README.md / main.py 的那一层）
git push -u origin main
git push origin v1.0.2
```

改版本号时同步这 5 处，别漏：

| 位置 | 字段 |
|---|---|
| `metadata.yaml` | `version: v1.0.2` |
| `main.py` | `@register(...)` 第 4 个参数 `"1.0.2"` |
| `views/bookkeeping/app.js` | `SET_STATS` 里的 `["版本", "v1.0.2"]` |
| `README.md` | 标题 `v1.0.2` |
| `CHANGELOG.md` | 新增一节，并把 `RELEASE_NOTES.md` 标题一起改 |

打包用 `python dev/pack_release.py`，会在项目根目录生成同名 zip 并复制到桌面；GitHub Release 的 tag 填 `v1.0.2`，正文复制 `RELEASE_NOTES.md`，附件上传这个 zip。










