"""修线上「回答堆砌规范条文 + 线路中断」问题（第 16 轮线上反馈）。

线上现象：问「我没有挂安全带」时回答变成一大坨规范条款，底部报错。
排查结论（已实证）：
  · 模型调用**间歇性失败**（免费模型限流），系统回退到 _extractive_answer
  · 而 _extractive_answer 从 JGJ59 标准里挑出的"句子"是**评分表碎片**：
        物从人的正上方通过，扣10 分
        起重机吊具载运人员，扣10 分
        10
        8
        高处
        作业
    这些不是能读的句子，堆起来就像乱码
  · rag.py 把真实错误丢掉了，只留异常类名（ProviderError），无法定位

三处修复：
  1. 回退答案加**质量过滤**：剔除评分碎片、纯数字、过短片段
  2. 保留**真实错误信息**：把 code 与 message 写进 warnings
  3. 限流退避**加长**：免费模型 429 后需要更久才恢复

用法：python fix_answer_fallback.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
RAG = APP / "sitesaha" / "rag.py"
LLM = APP / "sitesaha" / "llm.py"

# ---------- 1) 回退答案加质量过滤 ----------
FILTER_FUNC = '''

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
    stripped = re.sub(r"\\s+", "", text)

    # 评分表用语
    if re.search(r"[扣得加]\\s*\\d+\\s*分", text):
        return True
    if re.search(r"应得\\s*分|实得\\s*分|评分\\s*分", text):
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

'''

SENTENCE_OLD = '''            for sentence in split_sentences(source.content):
                normalized = re.sub(r"\\s+", "", strip_markdown(sentence))
                if not normalized or normalized in seen or len(normalized) < 8:
                    continue
                seen.add(normalized)
                selected.append((_sentence_score(sentence, units), sentence.strip(), source_index))'''

SENTENCE_NEW = '''            for sentence in split_sentences(source.content):
                normalized = re.sub(r"\\s+", "", strip_markdown(sentence))
                if not normalized or normalized in seen or len(normalized) < 8:
                    continue
                # 剔除评分表碎片 —— 否则回退答案会把「扣10分」这类片段堆出来
                if _looks_like_table_fragment(sentence):
                    continue
                seen.add(normalized)
                selected.append((_sentence_score(sentence, units), sentence.strip(), source_index))'''

# 回退答案为空时的兜底
EMPTY_OLD = '''        if not actions:
            lines.append("2. 请打开下方依据，并结合现场交底确认。")'''
EMPTY_NEW = '''        if not actions:
            lines.append("2. 请打开下方依据，并结合现场交底确认。")
        if len(actions) < 2:
            lines.append("")
            lines.append("提示：知识库里这个问题的可读内容较少（检索到的主要是标准评分表）。"
                         "如需成段解释，请让管理员确认文字模型是否可用。")'''

# ---------- 2) 保留真实错误 ----------
RAG_EXC_OLD = '''            except Exception as exc:
                warnings.append(f"在线模型生成失败，已回退到检索摘要：{type(exc).__name__}")'''

RAG_EXC_NEW = '''            except Exception as exc:
                # 保留真实原因 —— 只记异常类名（ProviderError）没法定位问题
                detail = type(exc).__name__
                code = getattr(exc, "code", "")
                message = str(getattr(exc, "message", "") or exc)
                if code:
                    detail = f"{detail}/{code}"
                if message:
                    detail = f"{detail}：{message[:120]}"
                warnings.append(f"在线模型生成失败，已回退到检索摘要（{detail}）")'''

# ---------- 3) 退避加长 ----------
RETRY_OLD = '''def with_retry(operation, *, attempts: int = 3, base_delay: float = 0.8,
               max_delay: float = 2.0):
    """对可重试的 ProviderError 做指数退避。

    依据第 16 轮 §4.2：429/5xx 退避 0.8s → 2s，最多 2 次重试（共 3 次尝试）。
    """'''

RETRY_NEW = '''def with_retry(operation, *, attempts: int = 4, base_delay: float = 2.0,
               max_delay: float = 12.0):
    """对可重试的 ProviderError 做指数退避。

    依据第 16 轮 §4.2，并在线上实测后调整：
    免费模型（glm-4-flash）的限流恢复比较慢，原来 0.8s→2s 的重试窗口太短，
    实测会出现「重试完仍然 429 → 回退成检索摘要」。
    现在改成 2s → 4s → 8s（封顶 12s），共 4 次尝试。
    """'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    rag = RAG.read_text(encoding="utf-8")
    llm = LLM.read_text(encoding="utf-8")

    if "_looks_like_table_fragment" not in rag:
        anchor = "    def _extractive_answer(self, question: str"
        if anchor not in rag:
            print("[FAIL] 找不到 _extractive_answer")
            return 1
        rag = rag.replace(anchor, FILTER_FUNC.lstrip("\n") + "\n" + anchor, 1)
        applied += 1
        print("[ok] 新增 _looks_like_table_fragment 过滤器")
    else:
        print("[跳过] 过滤器已存在")

    if "剔除评分表碎片" not in rag:
        if SENTENCE_OLD in rag:
            rag = rag.replace(SENTENCE_OLD, SENTENCE_NEW, 1)
            applied += 1
            print("[ok] 回退答案接入过滤")
        else:
            print("[跳过] 句子筛选锚点未匹配")
    else:
        print("[跳过] 过滤已接入")

    if "可读内容较少" not in rag:
        if EMPTY_OLD in rag:
            rag = rag.replace(EMPTY_OLD, EMPTY_NEW, 1)
            applied += 1
            print("[ok] 回退内容过少时给出明确提示")
        else:
            print("[跳过] 兜底文案锚点未匹配")
    else:
        print("[跳过] 兜底文案已加")

    if "只记异常类名" not in rag:
        if RAG_EXC_OLD in rag:
            rag = rag.replace(RAG_EXC_OLD, RAG_EXC_NEW, 1)
            applied += 1
            print("[ok] 保留真实错误信息（code + message）")
        else:
            print("[跳过] 异常处理锚点未匹配")
    else:
        print("[跳过] 异常信息已保留")

    if "线上实测后调整" not in llm:
        if RETRY_OLD in llm:
            llm = llm.replace(RETRY_OLD, RETRY_NEW, 1)
            applied += 1
            print("[ok] 限流退避加长（2s→4s→8s，4 次尝试）")
        else:
            print("[跳过] with_retry 锚点未匹配")
    else:
        print("[跳过] 退避已调整")

    try:
        ast.parse(rag)
        ast.parse(llm)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 语法通过")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    RAG.write_text(rag, encoding="utf-8")
    LLM.write_text(llm, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
