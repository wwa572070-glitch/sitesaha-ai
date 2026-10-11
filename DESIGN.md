---
name: "筑安智培 · 新工人安全助手"
version_scope: "15.0.0"
colors:
  canvas: "--canvas"          # 亮 #f4f6f7 / 暗 #10151a
  surface: "--surface"        # 亮 #ffffff / 暗 #161c23
  surface-soft: "--i50"       # 亮 #f7f9fa / 暗 #1b222a
  ink: "--i950"               # 亮 #0f1215 / 暗 #0b0e11 —— 顶栏与主行动卡底色
  text: "--i600"              # 亮 #4b535c / 暗 #c3cad2 —— 正文
  text-strong: "--i800"       # 亮 #22272e / 暗 #f3f4f6 —— 强调文字
  text-muted: "--i500"        # 亮 #6b7480 / 暗 #8b93a1 —— 次要文字
  primary: "--safety"         # 亮 #b23a0a / 暗 #f97316 —— 安全警示橙
  primary-hover: "--safety-700"
  signal: "--signal"          # 亮 #d9a300 / 暗 #fbbf24 —— 警示黄，只做标记不做文字底
  danger: "--red"             # 亮 #c0341d / 暗 #f87171
  warn: "--amber"             # 亮 #a86400 / 暗 #fbbf24
  success: "--green"          # 亮 #1c6b45 / 暗 #4ade80
  border: "--i200"            # 亮 #e3e7eb / 暗 #2a323b
  border-strong: "--i300"     # 亮 #c3cad2 / 暗 #3a434e
typography:
  family: 'Arial, "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif'
  mono: 'Consolas, "Cascadia Mono", monospace'
  scale: [11, 12, 13, 14, 16, 18, 21, 26]
  roles:
    xs: 11px       # 状态标签、表注
    sm: 13px       # 次要说明
    md: 14px       # 正文与面板标题基准
    base: 16px     # 品牌标题、强调正文
    lg: 18px       # 次级标题
    xl: 21px       # 应急区主标题、证书标题
    display: 26px  # Hero 主标题（唯一展示级）
  line-height: [1.4, 1.6, 1.8]
  letter-spacing: "0.05em"
radius:
  sm: 2px     # 按钮、输入、标签
  md: 3px
  lg: 4px     # 面板、卡片
  xl: 6px     # 最大容器
  note: "唯一例外：.status-pill 用 999px，承载实时状态语义"
spacing:
  scale: [0, 2, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64]
  base: 4
  on_grid_ratio: "93.9%"
  note: "所有 padding / margin / gap 必须落在 4 的网格上"
layout:
  container: 1024px
  breakpoints: [992, 640]
  reading_flow: "单列纵向，禁止并排分栏"
  header_stripe: "6px 施工警示斜纹（135deg，主色 10px + 墨色 10px）"
motion:
  duration: { fast: 150ms, base: 200ms, slow: 400ms }
  easing: ease
  reduced-motion: "已处理（3 处 !important，位于 prefers-reduced-motion 媒体查询内）"
---

# Design System: 筑安智培 · 新工人安全助手

本文档是项目的**视觉权威**。任何界面改动都应先对照本文件；偏离须显式说明理由。

## 1. 设计定位

- **页面类型**：trust-first 公共服务型安全工具（不是营销落地页，也不是数据仪表盘）
- **受众**：中国建筑施工现场新工人。识字水平参差，多用手机，常在嘈杂、多尘、光线差的现场
- **气质**：工业警示、权威、高可读性
- **视觉语言**：施工警示标识系统（安全橙 + 深墨 + 警示斜纹）
- **刻度**（Taste Skill 第 1.A 节）：
  - `DESIGN_VARIANCE: 7` —— 有明确视觉记忆点（斜纹、橙黑对比），但要可预期
  - `MOTION_INTENSITY: 2` —— 现场网络差、设备旧，动效是负担
  - `VISUAL_DENSITY: 5` —— 信息要密但要清楚

## 2. 颜色

两套主题共用同一套令牌名，只在 `:root` 与 `[data-theme="dark"]` 里换值。

- **主色（安全警示橙）`--safety #b23a0a`**：白字对比度 7.3:1。用于主按钮、选中态、面板标题左侧短线、Hero 左边框、警示斜纹。
- **副色（警示黄）`--signal #d9a300`**：**只做标记，不做文字底**（黄底白字不可读）。
- **墨色阶 `--i950 … --i50` 共 11 级**：`--i950`/`--i900` 是**背景色**，不得用作文本色（踩过这个坑：暗色模式下深字压深底，8 个标题消失）。
- **文字三档**：`--i800`（强调）/ `--i600`（正文）/ `--i500`（次要）。
- **功能色**：`--red` 高 / `--amber` 中 / `--green` 低，只出现在风险标识与状态上。
- **一致性锁**：一个页面只用一个主色。

## 3. 排版

- **字体族**：`Arial, "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif`
- **字号刻度**：**只允许 8 档** —— 11 / 12 / 13 / 14 / 16 / 18 / 21 / 26
- **行高**：只允许 1.4 / 1.6 / 1.8
- **字距**：正文 `0.05em`
- **展示级 26px 只用于 Hero 主标题**，不进面板

## 4. 间距

- **基准 4px，全部间距落在 4 的网格上**（实测对齐率 93.9%）
- 禁止 5/6/7/9/10/11/13/14/15/17/18/22/26px 这类零散值

## 5. 圆角与层级

- **圆角 4 档**：2px（按钮/输入/标签）/ 3px / 4px（面板卡片）/ 6px（最大容器）
- 唯一例外：`.status-pill` 用 `999px`
- **禁止大圆角**（12px 以上）
- **层级靠底色差与边框，不靠阴影**

## 6. 布局

- **容器**：1024px 居中
- **断点**：992px / 640px
- **单一阅读流**：主内容纵向单列，**禁止并排分栏**
- 连续条目用分隔线，不用一个个卡片框；卡片只给真正独立的信息块
- **顶栏斜纹**是身份元素，不可移除

## 7. 动效

- 时长 ≤ 400ms；缓动 `ease`
- 只动 `transform` / `opacity`
- `prefers-reduced-motion` 已处理

## 8. 可访问性

- 文字对比度 ≥ 4.5:1（`audit_ui.py` 逐条校验，当前 0 问题）
- **跳态环用 `--safety`（6.00:1）**，不用 `--amber`（4.68:1）
- 触控目标 ≥ 44px
- 不靠颜色单独传达状态
- 已验证：对比度、行宽、行高、字号层级、触控区、断点、492px 无横向溢出

## 9. craft-guard 审计结论（22 条规则）

`.scratch/run-001/craft-guard.md`，机器校验 `G8 OK`。

- `clear` 20 条 · `blocked` 1 条（PERF-01，缺运行时测量）· `not-applicable` 2 条（RESP-01 无视口契约、I18N-01 单语）
- 审计后已修：`A11Y-02` 跳态对比度
- 未决：`CRAFT-07` 7 个按钮的 emoji 前缀（取舍需用户决定：emoji 同时是弱识字用户的可识别线索）

## 10. 行动符号（emoji）使用纪律

**决策依据**：本项目用户为识字水平参差的新工人，emoji 承担**识别**功能，全删会提高理解成本。
因此采「保留 + 加纪律」，而不是照搬通用规则去掉。

**保留清单（11 个，均为高识别度动作标记）**：

| 符号 | 用途 |
|---|---|
| 🌙 | 夜间主题切换（切换后变 ☀️） |
| 🎙️ | 语音提问 |
| ⌨️ | 浏览器语音识别降级 |
| 🔊 | 朗读回答 |
| 📷 | 摄像头三态：打开 / 拍下 / 关闭 |
| 🖼 | 从相册或文件选择 |
| 🔄 | 重拍 / 换一张 |
| ✖ | 取消 |
| 🖨 | 打印 / 存为 PDF |

**纪律**：

1. **导航保持纯文字** —— 顶级导航不出现符号，避免与动作符号混淆
2. **成对动作必须同族** —— 打开/关闭摄像头、拍摄/重拍、确认/取消，两侧要么都有符号要么都没有
3. **禁止不传达信息的符号** —— 例如曾用的 ⚪（白色圆圈）已删除
4. **禁止与文字重复的通用媒体符号** —— ⏹ ⏸ 已删除，文字已表达停止语义
5. → 是方向指示而非 emoji，可用于跳转类按钮

**改动此清单须同步更新 docs/ui-build/unify_action_emoji.py**，该脚本是清单的可执行版本。

## 11. 截图与测量的正确做法（重要，踩过两次）

**Windows 无头 Edge 的 --window-size 有最小尺寸（实测约 492×705）。** 低于它时
浏览器**缩放**渲染结果而不是真正缩小视口 —— 于是「390×844 截图」实际是 492px 布局
被横向压扁成 390px，文字看起来像被裁切，其实是压缩。这个假象误导了两轮排查。

**要真实视口必须用 CDP 的 Emulation.setDeviceMetricsOverride：**

`
python docs/ui-build/cdp_probe.py --width 390 --height 844 --view home
python docs/ui-build/shot_evidence.py --view home      # 按 §5 规范出图
`

**另一个陷阱：ody { overflow-x: hidden } 会把超宽内容静默裁掉**，不产生滚动条，
所以任何基于 scrollWidth > clientWidth 的溢出检测都天然看不见它。
判断越界要用「元素 getBoundingClientRect().right > documentElement.clientWidth」。

**手机端已知约束**：真机 390px 下导航原本溢出（
av-inner scrollWidth 419 > 390），
最后一个「学习与资料」被推到视口外。已在 640px 断点改为自动换行。

## 12. 配色（第 16 轮变更：安全橙 → 深蓝 + 琥珀）

**依据**：第 16 轮指令 §5 —— 保留深蓝 + 琥珀 + 风险三色。

| 角色 | 值 | 对比度 | 用途 |
| --- | --- | --- | --- |
| 主色 深蓝 | #0c2b4a | 白字 14.38:1 | 顶栏、L1/L3 标题、主按钮、进度填充、顶边斜纹 |
| 强调 琥珀 | #f2a33c | 深蓝上 6.90:1 | 警示斜纹、品牌块、L3 徽标、热力格 |
| 页面底 | #f5f7fa | — | 页面背景 |
| 卡片 | #ffffff | — | 内容容器 |
| 分隔线 | #e3e9f0 | — | 边框与分隔 |
| 正文 | #3d4c5c | 白卡 8.0:1 | 段落文字 |
| 风险高 | 展示 #dc3f2e / 文字 #c0321c | 文字版 5.65:1 | 高危标识 |
| 风险中 | 展示 #e0a92b / 文字 #8a6410 | 文字版 5.37:1 | 中危标识 |
| 风险低 | 展示 #1f8a53 / 文字 #1a7a49 | 文字版 5.35:1 | 低危/完成 |

### 三条硬规则（都经对比度核算）

1. **琥珀永远不做按钮底色。** 白字配琥珀只有 2.08:1。琥珀只做强调、斜纹、徽标；要做按钮就用**深蓝底白字**。
2. **风险色分「展示色」与「文字安全色」两套。** #e0a92b 在白底上只有 2.13:1，不能承载文字。展示色用于圆点/色条/环，文字用加深版。
3. **小尺寸实心徽标不用展示色配白字。** #dc3f2e/#1f8a53 落在对比度死区——白字 4.38/4.36、近黑字 4.34/3.95，**两边都过不了 4.5:1**。所以用同色系**浅底 + 深字**。

### 深色主题

底色用**深蓝灰 #0f1b2a 系**（不是近黑），与主色同族。深色下实心按钮改用**琥珀底 + 近黑字**（深蓝在深底上对比不足）。默认浅色——工地强光下更可读。

### 形状与字阶（§5）

- 圆角：卡片 10 / 按钮 8 / 大容器 14
- 阴影：只两级（--shadow-1 / --shadow-2），-3 与别名都指向这两级
- 字阶：7 级 —— 12 / 13 / 15 / 17 / 21 / 27 / 34
- 正文 15px、行高 1.7、行宽 34em（约 32~42 汉字）

## Source Evidence & Confidence

- [observed] path: `docs/ui-build/v15_theme.css`
  sha256: `d1d5dad23af958b0b9302d537d4ee4d50e4bf6dcc86d9bf2e46a3b4d89596cbc`
  confidence: high
- [observed] path: `docs/ui-build/v15_dark.css`
  sha256: `82f28cb0296a26ba9da815d53a78a32b599ae0df07d8379e5463cdf9ff9f5388`
  confidence: high
- [observed] path: `docs/ui-build/v13_layout.css`
  sha256: `75c81264e08d68e739942dff46f75be7844c67e227eb37875800fcaa6b41ae0a`
  confidence: high
- [observed] path: `docs/ui-build/v13_phases.css`
  sha256: `22ae77e38615a4ae88e0cf87c692b18cfacd90a6d1728dacd15ed63ba0874815`
  confidence: high
- [observed] path: `docs/ui-build/index_head.html`
  sha256: `0a4d9e120626e804b9f5d6029a22f1673342aa48885b80d3d8c8a2c3fe08a3d7`
  confidence: high
- [observed] path: `docs/ui-build/index_body.html`
  sha256: `3aa3ee1da8bed66f6e5b088f20c9dea3be436c59f11ee8658f06f78ab9a29b9f`
  confidence: high

## 已归档（不再是权威）

`_deprecated-css/`（项目外）：`v12_theme.css`、`v12_dark.css`、`v13_theme.css`、`v14_theme.css`、`v13_dark.css`。
V13/V14 两层已由 V15 完整覆盖（令牌零缺失，`plan_layer_removal.py` 验证），保留只会抬高复杂度。
