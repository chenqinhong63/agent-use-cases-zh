# Agent 用例库 · 中文版

别人用 AI Agent 真干成了什么 — [agentusecases.ai](https://agentusecases.ai/) 的中文整理。

在线地址：https://chenqinhong63.github.io/agent-use-cases-zh/

## 这是什么

原站是 Alex Finn 运营的免费 AI Agent 实战案例库，每天从 X、Reddit、Hacker News 等公开平台扫描新增案例。本站把它的案例翻译成中文，做成可搜索、可筛选的静态网站：

- 2263 条案例（2026-11-21 全量搬运，后续每天自动同步新增）
- 11 个分类：软件与运维、运营与效率、生活与家庭、增长与营销、金钱账单与权益、研究与分析、购物与比价、创意与内容、出行与旅行、游戏、科学
- 支持中英文搜索、按分类筛选、按 Agent 筛选、每页 24 条、随机来一条
- 每条点开有中文简介、可一键复制的中文提示词
- 中文原创案例置顶显示，带“中文原创”徽标，支持投稿（见下节）

## 中文原创投稿

翻译之外，本站收中文原创案例，目标是变成中文首发源：别人用 Agent 真干成的事，中文读者先在这里看到。

- 投稿入口：[提交原创案例](https://github.com/chenqinhong63/agent-use-cases-zh/issues/new?template=submit-use-case.yml)（GitHub Issue 模板，会问标题、用的 Agent、做了什么、结果、提示词、可验证的链接、署名）
- 审核流程：只收真实做过的事，不收编造和搬运；维护者审核通过后，把案例加入 `data/cases-original.json`，上站时署投稿人的名，置顶显示“中文原创”徽标
- 每日自动更新只同步翻译案例，原创靠人工审核入库，不走自动流程
- 种子原创 10 条来自站长本人已核实的项目：美客多西语客服 Agent、美客多卖家助手网站、热点搬运 Agent、AI 全员群、Agent 用例库中文版本身、FDE 陪跑首单、个人商铺 1 天开店包、抖音 AI 工具搞钱、系统提示词拆解学习法、美客多免费制图流程

## 本地预览

```bash
python -m http.server
```

然后打开 http://localhost:8000/ 。不要直接双击 `index.html` 打开，浏览器会拦 `fetch('data/cases.json')`。

## 每日自动更新

`.github/workflows/daily.yml` 每天北京时间 09:00（UTC 01:00）自动运行，也可手动触发（Actions → 每日更新案例 → Run workflow）：

1. 跑 `python scripts/update.py`：读原站 sitemap，找出本地没有的新案例，逐个抓详情页解析；
2. 若 `data/cases.json` 有变化，自动 commit 并 push，GitHub Pages 随后自动重新发布。

翻译用的 Key 只从仓库 Secrets 读 `DASHSCOPE_API_KEY`，绝不写进仓库文件。没配 Key 时新增条目会先以英文原文入库并标“待翻译”；已入库的待翻译条目不会在后续运行中自动重翻，如需补翻需手动处理。

手动跑一次（只看会新增哪些，不写文件、不调翻译接口）：

```bash
python scripts/update.py --dry-run
```

## 翻译说明

- 标题与简介是原站案例的中文翻译，保留了原文的关键数字、结果与缺点，没有夸大。
- 提示词是按案例改写的中文提示词模板（带 `[ ]` 占位符），不是原站提示词原文；原站提示词原文存在每条数据的 `prompt_en` 字段里备查（仅每日更新的新增条目有，老的 2263 条当时只取了分类页，没有逐条抓详情页的提示词原文）。
- 部分案例是美国场景（如报税、Comcast、AT&T、Medicare），翻译时保留了原场景，没有改成中国场景。

## 数据来源与免责

- 数据来源：[agentusecases.ai](https://agentusecases.ai/)（Alex Finn），每条案例都链回原站详情页。
- 案例是网友分享的整理，未经本站逐条独立实测验证；照抄前请先点“看原站详情”确认原文。
- 本站为翻译整理，内容版权归原作者及原站所有。
