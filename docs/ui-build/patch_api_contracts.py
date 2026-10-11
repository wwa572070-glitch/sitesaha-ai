"""接线 §3.2 与 §3.3（第 16 轮 v2）。

§3.3 结构化返回：
  /api/inspect-image 的响应增加 structured 字段（work_type / risks /
  uncertain / citations）与 image_quality；前端优先用 structured 渲染，
  取不到时回退 text。text 保留供复制与朗读。

§3.2 错误收敛：
  /api/ask 不再把 Python 异常原文写进响应体。
  实测泄漏样例：400 {"error": "Expecting value: line 1 column 1 (char 0)"}
  改为 model_unavailable + 中文提示 + 保留检索摘要兜底。

用法：python patch_api_contracts.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"

# ---------- 1) 导入 ----------
IMPORT_OLD = "from sitesaha.llm import ProviderError, with_retry"
IMPORT_NEW = ("from sitesaha.llm import ProviderError, with_retry\n"
              "from sitesaha.structure import parse_inspection, strip_markdown")

# ---------- 2) 视觉响应加结构化字段 ----------
VISION_OLD = '''                self._write_json({"text": text, "sources": [asdict(x) for x in sources], "warnings": ["照片识别仅基于可见信息，不能证明现场完全合规。高风险情况请现场确认。"]})'''
VISION_NEW = '''                structured = parse_inspection(text)

                # 图片质量：字节数与是否解析出作业类型都算信号。
                # 模型对退化图像会凭空编造场景（实测 1x1 像素图也能输出"深基坑"），
                # 所以这里给前端一个显式标记，让它能把"看不清的"置顶并提示重拍。
                quality = "ok"

                if len(image_bytes) < 8 * 1024 or not structured["work_type"]:

                    quality = "low"

                self._write_json(

                    {

                        "text": text,

                        "text_plain": strip_markdown(text),

                        "structured": structured,

                        "image_quality": quality,

                        "sources": [asdict(x) for x in sources],

                        "warnings": ["照片识别仅基于可见信息，不能证明现场完全合规。高风险情况请现场确认。"],

                    }

                )'''

# ---------- 3) /api/ask 错误收敛 ----------
ASK_OLD = '''        except (ValueError, json.JSONDecodeError) as exc:

            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)'''
ASK_NEW = '''        except (ValueError, json.JSONDecodeError):

            # 不把 Python 异常原文写进响应体（实测泄漏过
            # "Expecting value: line 1 column 1 (char 0)"）。
            self._write_json(

                {

                    "error": "请求格式不正确，没能解析你提交的内容。",

                    "error_code": "bad_request",

                    "hint": "刷新页面后重试；如果反复出现，请联系管理员。",

                },

                HTTPStatus.BAD_REQUEST,

            )

        except ProviderError as exc:

            self._write_provider_error(exc)'''

# ProviderError 在 ask 路径上的兜底：把"未配模型"变成可操作提示
ASK_PROVIDER_OLD = '''                sources = self.services.engine.retrieve(clean_question)'''

PROVIDER_HINT_BLOCK = '''    def _answer_or_summary(self, question: str, mode: str, worker_role: str) -> dict[str, Any]:
        """调模型生成回答；模型不可用时退回检索摘要，而不是抛异常给用户。

        依据 §3.2：/api/status 已有"未配置模型服务地址，当前使用检索摘要"的能力，
        这里复用它，保证任何情况下用户都能拿到有用的东西。
        """
        engine = self.services.engine
        try:
            answer = engine.answer(question, worker_role=worker_role)
            return answer_payload(question, answer)
        except ProviderError as exc:
            summary = engine.retrieve(question)
            payload = answer_payload(question, Answer(
                text=summary_text(question, summary),
                mode="retrieve-only",
                warnings=[exc.message + (" " + exc.hint if exc.hint else "")],
                sources=summary,
            ))
            payload["error_code"] = exc.code
            payload["degraded"] = True
            return payload
        except (RuntimeError, ValueError) as exc:
            summary = engine.retrieve(question)
            payload = answer_payload(question, Answer(
                text=summary_text(question, summary),
                mode="retrieve-only",
                warnings=["模型暂时不可用，下面是知识库里的相关条目。"],
                sources=summary,
            ))
            payload["error_code"] = "model_unavailable"
            payload["degraded"] = True
            payload["hint"] = "联系管理员配置 SITESHAHA_LLM_*；在此之前检索摘要仍可用。"
            payload["detail"] = type(exc).__name__
            return payload

'''


def summary_text(question: str, sources: list) -> str:
    """把检索结果拼成一段可读的摘要（模型不可用时的兜底）。"""
    if not sources:
        return ("当前未连接文字模型，知识库里也没有检索到相关条目。\n"
                "可以直接把问题换个说法再问，或联系现场安全员确认。")
    lines = ["当前未连接文字模型，下面是知识库里与你的问题最相关的条目：", ""]
    for index, source in enumerate(sources[:4], 1):
        title = getattr(source, "title", "") or "未命名"
        heading = getattr(source, "heading", "")
        content = (getattr(source, "content", "") or "").strip().replace("\n", " ")
        lines.append(f"[{index}] {title}" + (f" / {heading}" if heading else ""))
        if content:
            lines.append("　　" + content[:180])
        lines.append("")
    lines.append("需要成段的解释时，请让管理员配置文字模型。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")
    changed = 0

    if "from sitesaha.structure import" not in text:
        if IMPORT_OLD not in text:
            print("[FAIL] 找不到 llm 导入锚点")
            return 1
        text = text.replace(IMPORT_OLD, IMPORT_NEW, 1)
        changed += 1
        print("[ok] 导入 parse_inspection / strip_markdown")
    else:
        print("[跳过] 导入已存在")

    if '"structured"' not in text:
        if VISION_OLD not in text:
            print("[FAIL] 找不到视觉响应锚点")
            return 1
        text = text.replace(VISION_OLD, VISION_NEW, 1)
        changed += 1
        print("[ok] 视觉响应加 structured / text_plain / image_quality")
    else:
        print("[跳过] 视觉结构化已存在")

    if '"bad_request"' not in text:
        if ASK_OLD not in text:
            print("[WARN] 找不到 ask 异常锚点，跳过")
        else:
            text = text.replace(ASK_OLD, ASK_NEW, 1)
            changed += 1
            print("[ok] /api/ask 不再泄漏 Python 异常原文")
    else:
        print("[跳过] ask 错误收敛已存在")

    if "_answer_or_summary" not in text:
        anchor = "class RequestThrottle:"
        if anchor not in text:
            print("[FAIL] 找不到 RequestThrottle 锚点")
            return 1
        text = text.replace(anchor, PROVIDER_HINT_BLOCK + anchor, 1)
        changed += 1
        print("[ok] 新增 _answer_or_summary（模型不可用时退回检索摘要）")
    else:
        print("[跳过] _answer_or_summary 已存在")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] webapp.py 语法通过")

    if args.dry_run:
        print(f"（dry-run，未写入；{changed} 处）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
