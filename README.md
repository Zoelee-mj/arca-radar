# ARCA 活动雷达 · 使用说明（小白版）

这套工具每天自动从 Luma、lablab、Devpost 抓 AI 活动，按 ARCA 标准打分筛选，
生成一个网页报告（report.html），新活动排在最前面。

你不需要写任何代码，按下面的步骤点鼠标就行。

---

## 一、它由哪些文件组成（了解即可，不用动）

- `main.py`            主程序（把下面几块串起来）
- `scorer.py`          打分大脑（ARCA 筛选规则都在这里，想调分数改这个）
- `report.py`          出图器（生成 report.html）
- `fetch_luma.py`      抓 Luma（要加/删日历，改里面的 LUMA_CALENDARS）
- `fetch_lablab.py`    抓 lablab
- `fetch_devpost.py`   抓 Devpost
- `sources_common.py`  公共抓取工具
- `sample_events.json` 示例数据（连不上网时的兜底）
- `.github/workflows/daily.yml`  每天自动运行的定时器

---

## 二、让它每天自动出报告（一次性设置，约 20 分钟）

### 第 1 步：注册 GitHub（免费）
打开 https://github.com → Sign up → 用邮箱注册。

### 第 2 步：新建一个仓库（Repository）
登录后点右上角「+」→「New repository」。
- Repository name 随便填，比如 `arca-radar`
- 选「Public」
- 点「Create repository」

### 第 3 步：上传文件
在新仓库页面点「uploading an existing file」→
把这个文件夹里的所有文件**拖进去**（含 `.github` 文件夹）→
最下面点「Commit changes」。

> 注意：`.github` 是隐藏文件夹，拖动整个项目文件夹通常会带上它。
> 如果没传上去，单独再传一次 `.github/workflows/daily.yml`。

### 第 4 步：打开 Pages（生成你的专属网页链接）
仓库页面点「Settings」→ 左侧「Pages」→
「Build and deployment」下的 Source 选「GitHub Actions」。

### 第 5 步：先手动跑一次试试
仓库页面点「Actions」→ 左侧点「ARCA daily report」→
右侧点「Run workflow」→ 绿色按钮「Run workflow」。
等 1-2 分钟，出现绿色对勾就成功了。

### 第 6 步：拿到你的链接
回到「Settings → Pages」，上方会显示一个网址
（形如 `https://你的用户名.github.io/arca-radar/`）。
打开它就是今天的报告。把它存成浏览器书签即可。

以后每天北京时间早上 9 点，这个链接会自动刷新成最新活动。

---

## 三、常见调整（以后想改时再看）

- **改打分规则**：打开 `scorer.py`，POSITIVE 是加分词、NEGATIVE 是减分词。
- **加/减 Luma 日历**：打开 `fetch_luma.py`，改 `LUMA_CALENDARS` 列表。
- **改运行时间**：打开 `.github/workflows/daily.yml`，改 cron（`0 1 * * *` 是 UTC，比北京时间晚 8 小时）。
- **某个来源抓不到**：报告还是会正常出，缺失的来源会在 Actions 日志里写明原因，把日志发我即可。
