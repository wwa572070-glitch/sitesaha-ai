"""补上超时重试按钮（第 20 轮 §2，用正则匹配避开空行数量差异）。

前两次失败原因：
  appendAnswer 与 askQuestion 之间是**两个空行**，而 blank() 只生成一个，
  所以跨函数的锚点匹配不上。

本次改成：
  1. appendAnswer 的 return 用「speak.disabled 那一行」做唯一锚点，不跨函数
  2. 重试按钮用正则跨空行匹配

用法：python patch_retry_button2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"


def blank(text: str) -> str:
    return "\n\n".join(text.split("\n"))


RETURN_OLD = blank('''      if (speak) speak.disabled = !lastAnswerText || !("speechSynthesis" in window);

      row.appendChild(bubble);

      stream.appendChild(row);

      row.scrollIntoView({ behavior: "smooth", block: "start" });

    }''')

RETURN_NEW = blank('''      if (speak) speak.disabled = !lastAnswerText || !("speechSynthesis" in window);

      row.appendChild(bubble);

      stream.appendChild(row);

      row.scrollIntoView({ behavior: "smooth", block: "start" });

      /* 返回气泡，便于调用方追加内容（如超时后的重试按钮） */
      return bubble;

    }''')

RETRY_BLOCK = '''        /* 重试按钮：复用原问题，不丢输入 */
        if (failBox) {
          var retryButton = make("button", "secondary-button ico-button", "重试这个问题");
          retryButton.type = "button";
          retryButton.addEventListener("click", function () {
            var box = $("question");
            if (box) box.value = question;
            askQuestion();
          });
          failBox.appendChild(retryButton);
        }

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    text = SCRIPT_B.read_text(encoding="utf-8")

    # ---- 1) appendAnswer 返回 bubble ----
    if "return bubble;" in text and "便于调用方追加内容" in text:
        print("  [跳过] appendAnswer 已返回 bubble")
    elif RETURN_OLD in text:
        text = text.replace(RETURN_OLD, RETURN_NEW, 1)
        applied += 1
        print("  [ok] appendAnswer 返回 bubble")
    else:
        print("  [FAIL] appendAnswer 锚点未匹配")

    # ---- 2) 重试按钮（正则跨空行）----
    if "重试这个问题" in text:
        print("  [跳过] 重试按钮已存在")
    else:
        pattern = re.compile(
            r"(\}, role\);)(\s*)(\} finally \{\s*button\.disabled = false;)"
        )
        match = pattern.search(text)
        if match:
            text = (
                text[: match.start(2)]
                + "\n\n"
                + RETRY_BLOCK.rstrip("\n")
                + text[match.start(2):]
            )
            applied += 1
            print("  [ok] 重试按钮已插入")
        else:
            print("  [FAIL] 重试按钮锚点未匹配（正则也没找到）")

    if text.count(chr(92)):
        print("[FAIL] 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
