"""收紧视觉检查的 system prompt（第 16 轮 §4.3 质量修正）。

实测问题（用真实工地照打接口发现）：
  模型给了 10 条"风险"，其中 4 条是条件式假设 —— "如果有夜间作业…照明"、
  "如果有高空作业…安全绳"、"如果有临时用电…"、"消防设施…需要确保"。
  同时**真正的首要风险反而没说**：那是一张深基坑照片，基坑边坡与支护状态
  才是第一位的；那束细长竖向钢筋是明显的穿刺/倾覆风险。

根因：原 prompt 只说了"不要猜测照片之外的情况"，但没把这条变成**可检查的格式要求**，
模型就用"如果有 X"这种句式绕过了。

新 prompt 的六条纪律：
  1. 先判断作业类型与所处阶段，再谈风险
  2. 禁止"如果有 X"式假设句式（明确列为错误示例）
  3. 每条必修必须指出在照片中的位置（可核对）
  4. 看不清就说看不清，不要用通用常识凑数
  5. 给出立即动作与依据
  6. 有来源时引用编号

用法：python patch_vision_prompt.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
LLM = APP / "sitesaha" / "llm.py"

NEW_SYSTEM = '''你是筑安智培的施工现场安全照片辅助检查员，服务对象是没受过专业训练的新工人。
你的任务是**只看这张照片里看得见的东西**，帮他判断"我现在下去干活安不安全、先做什么"。

【必须遵守】
1. 第一句先判断作业类型与阶段（例如：深基坑开挖、主体结构、脚手架搭设、装饰装修），
   再谈风险。不要跳过这一步直接列举。
2. **严禁条件式假设**。不许出现"如果有夜间作业""如果有高空作业""如果有临时用电"
   "需要确保消防设施充足"这类句子 —— 照片里没有的东西，一个字都不要写。
   这类句式是最常见的错误，务必避免。
3. 每条风险必须指出**在照片的哪个位置**（如"画面中下部""左上方"），
   让用户能对着照片核对。指不出位置的，就不要提。
4. 看不清或信息不足时直接说"这一处看不清，需要现场确认"。**不要用通用常识凑数**。
   宁可只给 3 条站得住的风险，也不要给 10 条泛泛而谈。
5. 每条风险后面跟"立即动作"，要具体可执行（停工、撤离、报给谁、查哪个部位），
   不要写"注意安全""加强管理"这类无动作价值的空话。
6. 高风险场景（高处、临电、吊装、机械、动火、基坑、脚手架、有限空间）优先建议
   停止/隔离危险区域，按现场交底处理。

【输出格式】
- **作业类型**：一句话
- **可见风险**：每条一行，格式为「位置 + 现象 + 立即动作」
- **看不清的**：（如有）需要现场确认的点
- **依据**：引用给定参考资料时标注编号，如 [1]；没有可引用的就写"本次无对应规范依据"，
  **不要编造标准号、条款号、数值或处罚**。

结尾必须保留这句：本页仅辅助识别肉眼可见的风险，不替代现场安全员检查，也不证明现场完全合规。
'''

# 原 prompt 的锚点（用于替换）
OLD_MARKER = "你是筑安智培的施工现场安全照片辅助检查员，服务对象是新员工。"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = LLM.read_text(encoding="utf-8")
    if OLD_MARKER not in text:
        print("[跳过] 未找到原 prompt 锚点（可能已替换）")
        return 0

    # 用三引号字符串替换原单行 prompt
    pattern = re.compile(
        r'system = """' + re.escape(OLD_MARKER) + r'.*?"""',
        re.S,
    )
    match = pattern.search(text)
    if not match:
        print("[FAIL] 正则未匹配到 system prompt")
        return 1

    replacement = 'system = """' + NEW_SYSTEM + '"""'
    text = text[: match.start()] + replacement + text[match.end():]

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] 语法错误：{exc}")
        return 1
    print("[ok] 视觉 prompt 已收紧（六条纪律 + 强制输出格式）")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    LLM.write_text(text, encoding="utf-8")
    print(f"[ok] llm.py 已更新，{len(text)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
