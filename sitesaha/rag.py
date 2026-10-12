from __future__ import annotations

import re

from .config import AppConfig
from .db import KnowledgeBase
from .hybrid import HybridRetriever
from .llm import LocalModelClient
from .models import Answer, SearchResult
from .text import overlap_units, split_sentences, strip_markdown, truncate

EMERGENCY_TERMS = {"坍塌", "坠落", "触电", "火灾", "起火", "失血", "昏迷", "窒息", "重伤", "急救", "事故", "报警", "被困", "爆炸"}
HIGH_RISK_TERMS = {"高处", "临边", "洞口", "脚手架", "基坑", "塔吊", "吊装", "吊物", "吊车", "起重机", "吊钩", "吊索", "配电箱", "触电", "电焊", "动火", "气瓶", "机械", "有限空间", "受限空间", "临时用电", "起重", "临电", "高空", "坠物", "物体打击"}
NEW_WORKER_TERMS = {"第一次", "新工人", "新人", "入职", "入场", "新进场", "培训", "不懂", "第一次上工地"}
UNCERTAIN_TERMS = {"能不能", "可以吗", "能上吗", "还能", "可不可以", "安全吗", "怎么办", "怎么处理"}


def classify_question(question: str) -> str:
    if any(term in question for term in EMERGENCY_TERMS):
        return "紧急情况"
    if any(term in question for term in HIGH_RISK_TERMS):
        return "高风险作业"
    if any(term in question for term in NEW_WORKER_TERMS):
        return "新人入场"
    if any(term in question for term in {"怎么用", "怎么做", "步骤", "操作", "检查", "流程", "如何"}):
        return "操作流程"
    return "普通咨询"


def risk_level(question: str, intent: str) -> str:
    if intent == "紧急情况":
        return "红色"
    if intent == "高风险作业" or any(x in question for x in UNCERTAIN_TERMS):
        return "橙色"
    if intent == "操作流程":
        return "黄色"
    return "绿色"


def _sentence_score(sentence: str, units: set[str]) -> float:
    candidate = overlap_units(sentence)
    if not units:
        return 0.0
    overlap = len(units.intersection(candidate)) / len(units)
    length_bonus = 1.0 if 18 <= len(sentence) <= 180 else 0.3
    return overlap * 3.0 + length_bonus



def _strip_page_number(text: str) -> str:
    """剥掉粘在句子开头的页码或条目编号。

    标准 PDF 转文本后常见 "91\n起重吊装作业前应…" 这种，
    页码会被并到句子里，显示成 "91 起重吊装作业前应…"。
    """
    if not text:
        return text
    # 开头是 1~4 位数字，后面紧跟非数字（说明是页码而不是内容里的数字）
    cleaned = re.sub(r"^\s*\d{1,4}\s*[、.．)）]?\s+(?=\D)", "", text)
    # 纯页码行
    if re.fullmatch(r"\s*\d{1,4}\s*", cleaned or ""):
        return ""
    return cleaned


def _looks_like_table_fragment(text: str) -> bool:
    """判断一段文字是不是评分表/表格碎片，不适合直接给用户看。

    为什么需要：JGJ59 这类标准里有大量评分表，检索会把
    「吊运易散落物件不使用吊笼，扣6 分」「10」「8」「高处」这种片段捞出来。
    它们单独看没有意义，堆在答案里就像乱码。

    判定依据（任一命中即视为碎片）：
      · 含「扣X分」「得X分」这类评分用语
      · 去掉标点后大部分是数字
      · 太短（少于 10 个字）
      · 只由若干短词堆叠、没有完整谓语结构
    """
    if not text:
        return True
    stripped = re.sub(r"\s+", "", text)

    # 评分表用语
    if re.search(r"[扣得加]\s*\d+\s*分", text):
        return True
    if re.search(r"应得\s*分|实得\s*分|评分\s*分", text):
        return True

    # 太短
    if len(stripped) < 10:
        return True

    # 数字占比过高
    digits = sum(1 for ch in stripped if ch.isdigit())
    if digits / max(len(stripped), 1) > 0.35:
        return True

    # 缺少句读：中文正常句子会有标点，表格碎片往往没有
    if not re.search(r"[，。；：、！？,.;:]", stripped):
        return True

    # 连续短词堆叠（如评分表里逐行排列的短词），标点密度过低
    punctuation = len(re.findall(r"[，。；：、！？,.;:]", stripped))
    if punctuation == 0 and len(stripped) < 40:
        return True

    return False




class RAGEngine:
    def __init__(self, kb: KnowledgeBase, config: AppConfig):
        self.kb = kb
        self.config = config
        self.model = LocalModelClient(config)
        self.retriever = HybridRetriever(kb)

    def retrieve(self, question: str) -> list[SearchResult]:
        return self.retriever.search(question, top_k=self.config.top_k)

    def answer(self, question: str, *, worker_role: str = "", training_context: str = "") -> Answer:
        clean_question = (question or "").strip()
        if not clean_question:
            return Answer(
                text="""你可以直接用大白话问我。比如：

- “我第一次上工地，要先注意什么？”
- “这个东西怎么安全使用？”
- “这里有危险吗？”
- “有人触电了怎么办？”

不知道专业名称也没关系，把你看到的、准备做的事情告诉我就行。""",
                mode="validation",
            )

        intent = classify_question(clean_question)
        risk = risk_level(clean_question, intent)
        role_hint = f"{worker_role}岗位" if worker_role else ""
        enriched_question = f"{clean_question} {role_hint} {training_context}".strip()
        sources = self.retriever.search(enriched_question, top_k=self.config.top_k, worker_role=worker_role)
        warnings: list[str] = []

        if not sources:
            if intent == "紧急情况":
                text = "🚨 先保安全\n\n立即停止危险行为，撤到安全区域并呼叫现场应急人员；不要在不了解现场风险的情况下贸然施救。\n\n当前知识库没有检索到足够依据，请立即按项目应急预案和现场安全员指令处理。"
            elif risk == "橙色":
                text = "⚠️ 先不要继续操作。\n\n当前知识库没有足够依据确认这个操作是否安全。停止操作、避开危险区域，并向班组长或安全员确认。"
            else:
                text = "当前知识库没有检索到足够依据。请联系项目安全员确认，正式使用前应导入适用的规范全文和项目制度。"
            return Answer(text=text, mode="no_match", warnings=["未检索到来源，系统没有生成推测性安全结论。"])

        status = self.model.status()
        if self.config.llm_mode != "off" and status.available:
            try:
                text = self.model.generate(clean_question, sources, mode=f"{intent}/{risk}风险", worker_role=worker_role, training_context=training_context)
                if intent == "紧急情况" and not any(x in text for x in ("撤", "停止", "呼救", "报警")):
                    text = "🚨 先停止危险行为并撤到安全区域，立即呼叫现场应急人员。\n\n" + text
                if risk == "橙色" and "不要擅自" not in text and "不要继续" not in text:
                    text = "⚠️ 在完成安全交底、条件确认和必要授权前，不要擅自继续操作。\n\n" + text
                return Answer(text=text, sources=sources, mode="local-llm", warnings=[f"风险等级：{risk}"])
            except Exception as exc:
                # 保留真实原因 —— 只记异常类名（ProviderError）没法定位问题
                detail = type(exc).__name__
                code = getattr(exc, "code", "")
                message = str(getattr(exc, "message", "") or exc)
                if code:
                    detail = f"{detail}/{code}"
                if message:
                    detail = f"{detail}：{message[:120]}"
                warnings.append(f"在线模型生成失败，已回退到检索摘要（{detail}）")
        elif self.config.llm_mode != "off":
            warnings.append(status.detail)

        return Answer(text=self._extractive_answer(clean_question, sources, intent, risk), sources=sources, mode="extractive", warnings=[f"风险等级：{risk}", *warnings])
    def _extractive_answer(self, question: str, sources: list[SearchResult], intent: str, risk: str) -> str:
        units = overlap_units(question)
        selected: list[tuple[float, str, int]] = []
        seen: set[str] = set()
        for source_index, source in enumerate(sources[:4], start=1):
            for sentence in split_sentences(source.content):
                normalized = re.sub(r"\s+", "", strip_markdown(sentence))
                if not normalized or normalized in seen or len(normalized) < 8:
                    continue
                # 剔除评分表碎片 —— 否则回退答案会把「扣10分」这类片段堆出来
                if _looks_like_table_fragment(sentence):
                    continue
                # 剥掉粘在句首的页码，如 "91 起重吊装作业前应…"
                cleaned = _strip_page_number(sentence).strip()
                if _looks_like_table_fragment(cleaned):
                    continue
                seen.add(normalized)
                selected.append((_sentence_score(cleaned, units), cleaned, source_index))
        selected.sort(key=lambda item: item[0], reverse=True)
        actions: list[tuple[str, int]] = []
        for _, sentence, source_index in selected:
            actions.append((truncate(sentence, 180), source_index))
            if len(actions) >= 4:
                break

        headings = {"紧急情况": "🚨 先保安全", "高风险作业": "⚠️ 先确认再操作", "新人入场": "👷 新人先记住", "操作流程": "🔧 按步骤做", "普通咨询": "安全要点"}
        lines = [f"{headings[intent]}："]
        if risk == "红色":
            lines.append("1. 立即停止危险行为，撤离/隔离危险区域并呼救；不要贸然施救。")
        elif risk == "橙色":
            if any(term in question for term in {"吊物", "吊装", "塔吊", "起重", "吊车", "起重机"}):
                lines.append("1. 不要站在吊物下方，也不要进入未设置警戒的吊装危险区域；正在吊装时先离开危险区域并听从现场指挥。")
            elif any(term in question for term in {"临边", "洞口", "高处", "高空", "脚手架", "基坑"}):
                lines.append("1. 先停止可能导致坠落或坍塌的操作，离开危险区域，并由班组长或安全员确认防护条件。")
            elif any(term in question for term in {"临电", "临时用电", "配电箱", "触电", "电焊", "动火"}):
                lines.append("1. 先停止相关作业并保持安全距离，不要自行带电处理；由具备相应资格的人员确认。")
            else:
                lines.append("1. 未完成安全交底、条件确认或必要授权前，不要继续操作。")
        elif intent == "新人入场":
            lines.append("1. 先完成安全教育和班前交底，确认作业区域、风险点、个人防护和撤离路线。")
        else:
            lines.append("1. 按现场安全交底和下方依据执行，不确定时先停下来确认。")
        for index, (action, source_index) in enumerate(actions, start=2):
            lines.append(f"{index}. {action} [{source_index}]")
        if not actions:
            lines.append("2. 请打开下方依据，并结合现场交底确认。")
        if len(actions) < 2:
            lines.append("")
            lines.append("提示：知识库里这个问题的可读内容较少（检索到的主要是标准评分表）。"
                         "如需成段解释，请让管理员确认文字模型是否可用。")
        lines.append("")
        lines.append("依据编号对应下方“规范依据”。")
        return "\n".join(lines)
