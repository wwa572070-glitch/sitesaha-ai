# GitHub 项目集成说明

本项目选择并集成了：

`priscilla254/RAG-Construction-Assistant`

- 仓库地址：https://github.com/priscilla254/RAG-Construction-Assistant
- 许可证：MIT
- 原项目场景：英国建筑法规和 HSE 施工安全文件
- 原项目技术：BM25 + Chroma + Streamlit + 有引用生成

## 采纳的架构

1. 检索结果必须来自受控资料，不允许模型自行补充条款。
2. 关键词检索和语义检索分别召回，再通过 RRF 融合。
3. 限制同一来源占用过多结果，避免一个标准挤掉其他相关规范。
4. 生成回答必须使用 `[n]` 引用，界面单独显示来源。
5. 没有检索依据时明确拒答。

## 本项目的本地化改造

- 英国法规替换为济南住建公开的 JGJ、GB/T 和 GB 标准。
- Chroma 和外部 Embedding 服务替换为 SQLite FTS5 + 本地稀疏特征向量。
- 云端 Groq 替换为可选的本机 OpenAI 兼容模型，未启动模型时回退到检索摘要。
- 英文问答替换为面向中国建筑新工人的中文口语问答。
- 增加班前检查、应急处置和培训场景快捷问题。

## 许可证处理

本项目保留了原项目许可证副本，并在 `THIRD_PARTY_NOTICES.md` 中说明来源。
参考项目文件存放在 `third_party/github/RAG-Construction-Assistant/`，不会把其
英国法规数据和向量数据库混入本项目知识库。
