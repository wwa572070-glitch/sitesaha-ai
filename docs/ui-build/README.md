# 筑安智培 前端界面构建说明（V9.1 → V10 首页重构）

`webapp.py` 里的 `INDEX_HTML` 是一个 12 万字符的内嵌单文件页面（HTML + CSS + JS）。
直接编辑那一个字面量很容易改坏，所以这里用「分片 → 拼装 → 注入 → 自检」的流程维护。

## 分片文件

| 文件 | 内容 | 行数 |
| --- | --- | --- |
| `index_head.html` | `<!doctype>` … `<style>` 设计系统 `</style>` `</head>` | 约 670 |
| `index_body.html` | `<body>` … 顶栏 / 状态条 / 导航 / 7 个模块 / 侧栏 / 页脚 | 约 535 |
| `index_script_a.js` | `<script>` 开头，逻辑第 1–9 节（工具、视图、首页、工种、测验引擎） | 约 890 |
| `index_script_b.js` | 逻辑第 10–16 节（问答会话、拍照、清单、案例、应急、知识库、初始化）`</script></body></html>` | 约 665 |
| `index_full.html` | 拼装产物，**不要直接改**，改分片后重新生成 | 约 2770 |

> 分片刻意不含反斜杠。这样注入时可以用普通三引号字符串，Python 会逐字保留内容，
> 不会把 `\n` 这类序列当成转义符处理。`inject.py` 会强制校验这一点。

## 标准流程

```powershell
# 1) 改完分片后，拼装 + 结构与语法自检 + 注入 webapp.py
python assemble.py
python check_js.py
python inject.py

# 2) 页面静态完整性、样式覆盖、断点、无障碍、安全文案检查
$env:SITESHAHA_LLM_MODE="off"
python check_page.py

# 3) 起服务，抓接口夹具，跑 DOM 仿真（无需浏览器）
python webapp.py --port 8503        # 另开一个终端
python fetch_fixtures.py
node run_dom_sim.js index_full.html
```

## 每个脚本做什么

- **`assemble.py`**：按顺序拼接四个分片，并自检 script/style/body/html 标签配对、
  `id` 是否有重复、JS 里 `$("...")` 引用的 id 是否真实存在、`data-view` 与
  `<section class="view">` 是否一一对应。
- **`check_js.py`**：抽出 `<script>` 块交给 `node --check` 做真实语法编译，并检查
  12 个关键实现标记（会话流、工种上下文、`/api/training`、判分、掌握度环、
  localStorage 键名、应急步骤、文档分组、风险域统计等）是否都还在。
- **`inject.py`**：把 `index_full.html` 写回 `webapp.py` 的 `INDEX_HTML`，要求：
  注入后能被 `ast` 解析、往返比对逐字节一致、后端契约字符串全部健在、
  旧首页痕迹（`home-safety-tools` / `big-action` / `emergencyGuides`）已清除。
  `python inject.py --revert` 可从 `webapp.py.bak-v91` 还原。
- **`check_page.py`**：用 `html.parser` 真实解析注入后的 HTML，检查标签闭合、
  重复 id、HTML 用到但没有样式定义的 class、1180/1000/720/420 四个断点、
  `label[for]` 指向的控件是否存在、以及 6 条安全底线文案是否静态落在页面里。
- **`run_dom_sim.js`**：用最小 DOM 桩在 Node 里执行真实页面脚本（含 `init()` 的
  异步链），配合 `fixture_*.json` 验证所有渲染路径真的产出内容、且零运行时错误。
  无头浏览器在本机被沙箱拦截，这是最接近真实运行的替代验证。
- **`fetch_fixtures.py`**：从本地运行中的服务抓 `/api/training`、`/api/status`、
  `/api/cases`、`/api/checklists` 的真实响应，作为 DOM 仿真的数据夹具。

## 自检通过的标准输出

```
structure check: OK
JS syntax (node --check): OK
JS check: OK
inject check: OK
page check: OK
DOM simulation: OK
```

## 设计依据

视觉对齐 `Desktop\筑安智培\3.筑安智培申报书\筑安智培项目框架图.jpg`：
深蓝 `#0c2b4a` + 琥珀黄 `#f2a33c`，警戒斜纹条，风险三色
（高 `#dc3f2e` / 注意 `#e0a92b` / 安全 `#1f8a53`），等宽数字大屏指标条。

页面零外部依赖（不加载字体、图标库、CDN），因为服务端 CSP 是
`default-src 'self'`，并且需要能离线内网运行。

## 注意

- 新增训练内容请改 `sitesaha/training.py`（纯数据），不要写死进 HTML；
  页面通过 `GET /api/training` 读取。
- 安全底线文案（"安全底线优先于进度和评分"等）已纳入 `check_page.py` 的强制检查，
  改动时不要删。
- 修改 `webapp.py` 后端时，`inject.py` 的 `MUST_KEEP` 列表会校验 7 个接口路径和
  4 个核心类/函数是否还在，避免误删。
