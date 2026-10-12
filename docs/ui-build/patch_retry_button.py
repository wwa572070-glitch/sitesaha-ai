"""补上超时重试按钮（第 20 轮 §2，锚点按实际代码修正）。

上一版锚点是我凭印象写的，没匹配。本版按实际代码：
  1. appendAnswer 要 return bubble —— 否则挂不上重试按钮
  2. 在 catch 分支的 appendAnswer 之后插入重试按钮

用法：python patch_retry_button.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"


def blank(text: str) -> str:
    return "\n\n".join(text.split("\n"))


# 1) appendAnswer 返回 bubble
RETURN_OLD = '''      row.appendChild(bubble);

      stream.appendChild(row);

      row.scrollIntoView({ behavior: "smooth", block: "start" });

    }

    async function askQuestion() {'''

RETURN_NEW = '''      row.appendChild(bubble);

      stream.appendChild(row);

      row.scrollIntoView({ behavior: "smooth", block: "start" });

      /* 返回气泡，便于调用方追加内容（如超时后的重试按钮） */
      return bubble;

    }

    async function askQuestion() {'''

# 2) 插入重试按钮
RETRY_OLD = '''        var failBox = appendAnswer(question, {

          text: failText,

          mode: "error",

          warnings: [String(error && error.message ? error.message : error)],

          sources: [],

        }, role);

      } finally {'''

RETRY_NEW = '''        var failBox = appendAnswer(question, {

          text: failText,

          mode: "error",

          warnings: [String(error && error.message ? error.message : error)],

          sources: [],

        }, role);

        /* 重试按钮：复用原问题，不丢输入 */
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

      } finally {'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    text = SCRIPT_B.read_text(encoding="utf-8")

    for note, old, new in [
        ("appendAnswer 返回 bubble", blank(RETURN_OLD), blank(RETURN_NEW)),
        ("插入重试按钮", blank(RETRY_OLD), blank(RETRY_NEW)),
    ]:
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
            print(f"  [ok] {note}")
        else:
            print(f"  [跳过] {note}（锚点未匹配）")

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
