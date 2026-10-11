"""脚本内 emoji → 内联 SVG（第 16 轮 §5：界面无 emoji）。

上一版失败的两个原因，本版都规避：
  1. 用短锚点（如 "🌙 夜间"）会误伤长表达式内部，且后续替换会命中已改坏的内容
     → 本版全部用**完整长锚点**，且**按位置从后往前**替换，一个锚点只处理一次
  2. 直接把 HTML 标签塞进 JS 字符串会破坏语法（属性里的双引号撞车）
     → 本版先生成单引号字符串 '<svg ...>'，再按原始上下文用 + 拼接
       分片禁止反斜杠，所以不能用转义，只能靠单引号包裹

用法：python patch_script_emoji2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
A = BUILD / "index_script_a.js"
B = BUILD / "index_script_b.js"

SQ = chr(39)
DQ = chr(34)


def ico(symbol: str, cls: str = "ico") -> str:
    """生成单引号包裹的 SVG 字符串（可直接参与 JS 拼接）。"""
    return (
        SQ + '<svg class=' + DQ + cls + DQ + ' aria-hidden=' + DQ + 'true' + DQ
        + '><use href=' + DQ + '#' + symbol + DQ + '/></svg> ' + SQ
    )


# (文件, 完整锚点, 替换, 说明)
EDITS: list[tuple[str, str, str, str]] = [
    # ---------- a：主题按钮 ----------
    ("a",
     'button.textContent = theme === ' + DQ + 'dark' + DQ
     + ' ? ' + DQ + '☀️ 白天' + DQ + ' : ' + DQ + '🌙 夜间' + DQ + ';',
     'button.textContent = theme === ' + DQ + 'dark' + DQ
     + ' ? ' + ico("i-clock") + ' + ' + DQ + ' 白天' + DQ
     + ' : ' + ico("i-clock") + ' + ' + DQ + ' 夜间' + DQ + ';',
     "主题切换按钮"),

    # ---------- a：应急类型图标（icon 字段）----------
    ("a", DQ + '🩹' + DQ, ico("i-firstaid"), "受伤图标"),
    ("a", DQ + '🔥' + DQ, ico("i-fire"), "火灾图标"),
    ("a", DQ + '⚡' + DQ, ico("i-shock"), "触电图标"),
    ("a", DQ + '🏗️' + DQ, ico("i-collapse"), "坍塌图标"),
    ("a", DQ + '🧗' + DQ, ico("i-fall"), "坠落图标"),
    ("a", DQ + '⚠️' + DQ, ico("i-alert"), "其他危险图标"),

    # ---------- a：工种卡片的四个小标题 ----------
    ("a", DQ + '⚠ 常见风险' + DQ, ico("i-alert") + ' + ' + DQ + '常见风险' + DQ, "常见风险标题"),
    ("a", DQ + '✓ 必守规矩' + DQ, ico("i-check") + ' + ' + DQ + '必守规矩' + DQ, "必守规矩标题"),
    ("a", DQ + '✗ 典型违规' + DQ, ico("i-close") + ' + ' + DQ + '典型违规' + DQ, "典型违规标题"),
    ("a", DQ + '🦺 防护用品' + DQ, ico("i-helmet") + ' + ' + DQ + '防护用品' + DQ, "防护用品标题"),
    ("a", '"✓";', ico("i-check", "ico ico-sm") + ';', "步骤完成对勾"),

    # ---------- b ----------
    ("b", DQ + '📚 ' + DQ + ' + (item.title', ico("i-doc") + ' + (item.title', "快捷提问书本图标"),
    ("b", DQ + '⚠ ' + DQ + ' + warning', ico("i-alert", "ico ico-sm") + ' + warning', "警告条前缀（气泡）"),
    ("b", DQ + '⚠ ' + DQ + ' + warning', ico("i-alert", "ico ico-sm") + ' + warning', "警告条前缀（复制文本）"),
    ("b",
     DQ + '🎙️ 录音提问（最长 60 秒）' + DQ + ' : ' + DQ + '🎙️ 录音提问' + DQ,
     ico("i-mic") + ' + ' + DQ + '录音提问（最长 60 秒）' + DQ
     + ' : ' + ico("i-mic") + ' + ' + DQ + '录音提问' + DQ,
     "录音按钮文案"),
    ("b", DQ + '🛑 正在听…' + DQ, ico("i-mic") + ' + ' + DQ + '正在听…' + DQ, "识别中状态"),
    ("b",
     'phone === ' + DQ + '120' + DQ + ' ? ' + DQ + '📞 拨打 120 急救' + DQ
     + ' : ' + DQ + '📞 拨打 119 火警 / 救援' + DQ,
     'phone === ' + DQ + '120' + DQ + ' ? ' + ico("i-phone") + ' + ' + DQ + '拨打 120 急救' + DQ
     + ' : ' + ico("i-phone") + ' + ' + DQ + '拨打 119 火警 / 救援' + DQ,
     "拨打按钮文案"),
    ("b", DQ + '🔊 朗读处置步骤' + DQ, ico("i-speaker") + ' + ' + DQ + '朗读处置步骤' + DQ, "朗读按钮"),
    ("b", 'ok ? ' + DQ + '✔' + DQ + ' : ' + DQ + '○' + DQ,
     'ok ? ' + ico("i-check", "ico ico-sm") + ' : ' + DQ + '○' + DQ, "培训步骤对勾"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = {"a": A, "b": B}
    texts = {key: path.read_text(encoding="utf-8") for key, path in files.items()}
    applied = 0
    skipped = 0

    # 按文件分组，组内按锚点在文中的位置从后往前替换
    for key in ("a", "b"):
        text = texts[key]
        located: list[tuple[int, str, str, str]] = []
        for file_key, old, new, note in EDITS:
            if file_key != key:
                continue
            position = text.find(old)
            if position < 0:
                continue
            located.append((position, old, new, note))
        for position, old, new, note in sorted(located, key=lambda item: -item[0]):
            texts[key] = texts[key].replace(old, new, 1)
            applied += 1
            print(f"  [ok] {key}: {note}")
        matched_notes = {item[3] for item in located}
        for file_key, _old, _new, note in EDITS:
            if file_key == key and note not in matched_notes:
                skipped += 1
                print(f"  [跳过] {key}: {note}（锚点未匹配）")

    for key, path in files.items():
        backslashes = texts[key].count(chr(92))
        if backslashes:
            print(f"[FAIL] {path.name} 含反斜杠 {backslashes} 处")
            return 1
    print("[ok] 无反斜杠")

    for key, path in files.items():
        left = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", texts[key])
        print(f"  [复核] {path.name} 剩余 emoji {len(left)} 个 {left[:8]}")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处，跳过 {skipped} 处）")
        return 0
    for key, path in files.items():
        path.write_text(texts[key], encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
