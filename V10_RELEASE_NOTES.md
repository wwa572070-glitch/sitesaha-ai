# 筑安智培 V10.0.0 发布说明

## 版本要点

V10 在 V9.1 在线版基础上完成三件大事：**界面与排版重构**、**拍照与语音链路真正可用**、
**知识库标准扩充**。后端接口保持向后兼容，只做纯新增。

- 页面来源可辨识：首页新增 `<meta name="sitesaha-version" content="10.0.0">`

## 一、界面与排版重构

- 首页改为「大屏指标条 + 主行动卡 + 今日三件事 + 培训模块 + 警示案例」，明确回答"我现在该干什么"。
- 7 个模块统一「页头 → 一句摘要 → 内容卡片 → 操作区」骨架：首页 / 现场问答 / 安全培训 /
  真实案例 / 开工前检查 / 知识库 / 应急求助。
- 设计令牌对齐申报书框架图：深蓝 `#0c2b4a` + 琥珀黄 `#f2a33c`，警戒斜纹条，风险三色。
- **正文阅读度量**：`--measure:40em`（≈600px ≈ 40 个汉字），正文行高 `--line-prose:1.78`，
  中英混排 `letter-spacing:0.05em`。此前正文在桌面端单行可达 70–84 个汉字。
- 标题层级由 17 种字号归并为 Hero 26 / h2 20-21 / h3 17 / h4 14.5。
- 对比度：修正 `.panel-kicker`（2.60:1）与 `.amber-button:hover`（2.91:1），
  并把 `--risk-high` / `--risk-low` 微调至白字 ≥ 4.5:1，全部通过 WCAG AA。
- 新增组件：数据表格（≤720px 转卡片式）、加载骨架屏、检索高亮。
- 可点击元素统一 `min-height:44px` 触控区下限；断点 1180 / 1000 / 720 / 420 全覆盖。
- 零外部依赖：不引入 CDN、网络字体或图标库，可离线内网运行。

## 二、拍照链路（修复 + 增强）

**修复了一个从上线起就存在的隐藏缺陷**：`POST /api/inspect-image` 原本用
`part.get_name()` 读取 multipart 字段，但在 CPython 3.12 下 `BytesParser` 产出的是
`EmailMessage`，它没有 `get_name()` / `get_filename()`（那两个方法 3.13+ 才有），
`Message.iter_parts()` 也返回空序列。**因此即使配置了视觉模型，拍照功能也只会返回 500。**
现在改为 `get_payload()` + 从 `Content-Disposition` 头解析字段名。

新增能力：

- 移动端调起摄像头（`capture="environment"`）；桌面端 `getUserMedia` 实时预览 + 拍照。
- 上传前本机压缩：长边 ≤1600px、JPEG q=0.82，并守住 8 MB 上限。
- 预览 + 尺寸/大小徽标 + 「重拍 / 换一张」+ 上传进度 + 可取消。
- 失败原因分类提示：格式不支持 / 超过 8MB / **未配置视觉服务** / 服务端错误。
- 未配置视觉模型时后端返回 **503 + `vision_configured` 提示**，而不是 `RuntimeError` 与 HTTP 500。

## 三、语音链路（服务端 ASR + 降级）

- 新增 **`POST /api/transcribe`**：前端 `MediaRecorder` 录音（30 秒上限）→ 上传 →
  OpenAI 兼容转写接口 → 回填输入框。
- 新增配置：`SITESHAHA_ASR_BASE_URL` / `_API_KEY` / `_MODEL` / `_API_STYLE` /
  `_ENDPOINT_PATH` / `_TIMEOUT_SECONDS`，以及 `SITESHAHA_MAX_AUDIO_BYTES`。
- **未配置 ASR 时自动降级**到浏览器识别，并在界面如实说明当前通道。
- 错误码如实展示并给下一步：`not-allowed` / `service-not-allowed` / `network` /
  `no-speech` / `audio-capture` / `aborted` / `language-not-supported`。
- 明确安全上下文限制：非 HTTPS 且非 `127.0.0.1` 时浏览器直接禁用摄像头与麦克风，
  界面会提示改用文件选择，而不是静默失败。
- 朗读：中文音色下拉 + 暂停 / 继续 / 停止，无中文语音包时明确提示。
- 离开页面自动停止录音并释放摄像头。

## 四、知识库与标准扩充

- 国家标准元数据由 **8 部扩充到 28 部**，全部核实现行有效，登记编号、名称、状态、
  发布与实施日期、官方入口与在线预览。
- 采集只走 `scripts/fetch_public_standards.py` 的合规通道：**不绕过验证码、登录或付费墙**；
  取不到全文的标准只登记元数据，**不用推测内容补全条款**。
- 新增 `GET /api/standards` 只读接口，知识库页新增「标准现行状态」表格，支持编号/名称检索与高亮。
- 已知缺口写入 `data/sources/PENDING_STANDARDS.md`：JGJ 系列与 GB 50xxx/55xxx
  工程建设标准不在国家标准全文公开系统的收录范围，需人工按合法渠道补齐。

## 五、培训与学习记录

- 培训内容由 `sitesaha/training.py` 提供（纯数据，经 `GET /api/training` 下发）：
  5 步培训路线、6 个工种专项（常见风险 / 必守规矩 / 典型违规 / 防护用品）、
  **20 道知识测验**（11 个风险域，含逐题解析与错题本）。
- 新增**学习积分**：培训步骤、测验答对、班前自检分别计分，累计 120 分可生成
  **可打印的 A4 培训记录单**（`@media print` 只输出记录单）。
- 记录单明确标注「不能替代项目三级安全教育、安全技术交底与持证要求，不作为上岗资格证明」。
- 测验成绩、路线进度、班前勾选与积分**全部保存在浏览器 localStorage**，不上传服务端。

## 六、接口变更（纯新增，向后兼容）

| 接口 | 变更 |
| --- | --- |
| `GET /api/training` | **新增**，返回培训路线、工种专项与测验题库 |
| `GET /api/standards` | **新增**，返回标准元数据 |
| `POST /api/transcribe` | **新增**，服务端语音识别 |
| `GET /api/status` | 新增字段 `vision_configured`、`asr_configured` |
| `GET /healthz` | 新增字段 `asr_configured` |
| `POST /api/ask` | 新增**可选**字段 `worker_role`；不传时行为与 V9.1 完全一致 |
| `POST /api/inspect-image` | 未配置视觉时由 500 改为 **503 + 错误码** |

原有接口路径、请求体与响应字段均未删除或改名。

## 七、测试

```powershell
python -m unittest discover -s tests -v
```

用例总数 57。沙箱环境下固定有 12 个 `PermissionError [WinError 5]`（测试使用
`tempfile.TemporaryDirectory()` 建临时目录被沙箱拒绝），与代码无关；
`AssertionError` 计数为 0。

界面侧自检工具在 `docs/ui-build/`：`assemble.py`（结构与 id 一致性）、`check_js.py`
（node 真实语法编译 + 关键实现标记）、`inject.py`（往返比对 + 接口契约校验）、
`check_page.py`（HTML 解析、样式覆盖、断点、无障碍、安全文案）、
`audit_ui.py`（A–J 十项排版与对比度审计，当前为 0 问题）、
`run_dom_sim.js`（最小 DOM 桩真跑 init()，验证零运行时错误）。

## 八、升级与配置

新增的环境变量（未配置时功能自动降级，不会报错）：

```dotenv
# 拍照（多模态视觉模型）
SITESHAHA_VISION_BASE_URL=
SITESHAHA_VISION_API_KEY=
SITESHAHA_VISION_MODEL=
SITESHAHA_VISION_API_STYLE=chat

# 语音（OpenAI 兼容转写接口）
SITESHAHA_ASR_BASE_URL=
SITESHAHA_ASR_API_KEY=
SITESHAHA_ASR_MODEL=
SITESHAHA_ASR_API_STYLE=chat
```

## 九、已知限制

1. 标准扩充项均为 `metadata_only`，**不含条款正文**，问答系统无法引用这些标准的具体条文。
2. 摄像头与麦克风需要**安全上下文**（HTTPS 或 `127.0.0.1` / `localhost`）。
   用手机通过 `http://局域网IP` 访问时浏览器会直接拒绝，这不是程序缺陷。
3. 未配置视觉或 ASR 服务时，对应功能只提供可操作的降级提示。
4. 学习积分与记录单只反映本机学习行为，不构成资格证明。

## 十、安全底线

模型输出仅作辅助，**不替代正式规范、项目制度、作业许可、安全技术交底和现场安全员判断**。
高后果安全决策必须由现场安全员、项目交底、作业许可和应急指挥确认。
紧急情况先撤离、报警和报告，不接受未经训练人员冒险施救。
