"""统一按钮 emoji 的使用纪律（CRAFT-07@1 的处理）。

决策背景：
  规则 CRAFT-07 的例外是"陌生/高风险动作需要文字"，我们不完全适用 —— 本项目的
  用户是识字水平参差的新工人，emoji 是可识别线索，删掉反而提高理解成本。
  所以处置方式是「保留 + 加纪律」，而不是全部删除。

扫描发现的三类真问题：
  1. `⚪ 拍下这一张` —— 白色圆圈不传达任何信息，是纯噪声
  2. `⏹ 停止并识别`、`⏸ 停止朗读` —— 图标是通用媒体符号，与文字重复
  3. 成对动作不一致：`📷 打开摄像头` 有图标而 `关闭摄像头` 没有；
     `🖼 从相册 / 文件选择` 有而 `取消` 没有

处置：
  · 删除无意义/重复的 3 个符号（⚪、⏹、⏸）
  · 补齐成对动作：关闭摄像头、重拍、取消
  · 保留 10 个高识别度符号，并写进 DESIGN.md 作为明确例外

用法：python unify_action_emoji.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

# (原文, 新文, 说明)
EDITS = [
    ("⚪ 拍下这一张", "📷 拍下这一张", "删掉无意义的白圈，改回相机符号"),
    ("⏹ 停止并识别", "停止并识别", "媒体符号与文字重复，删除"),
    ("⏸ 停止朗读", "停止朗读", "同上"),
    (">关闭摄像头<", ">📷 关闭摄像头<", "补齐成对动作：打开/关闭摄像头应同族"),
    (">重拍 / 换一张<", ">🔄 重拍 / 换一张<", "补齐（重拍是循环语义）"),
    (">取消<", ">✖ 取消<", "补齐（取消是关闭语义）"),
]

KEEP = [
    "🌙 夜间", "🎙️ 录音提问", "⌨️ 浏览器识别", "🔊 朗读回答",
    "📷 打开摄像头拍照", "🖼 从相册 / 文件选择", "📷 拍下这一张",
    "🖨 打印 / 存为 PDF", "📷 关闭摄像头", "🔄 重拍 / 换一张", "✖ 取消",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    before = len(body)

    print("=== 逐项处置 ===")
    for old, new, why in EDITS:
        n = body.count(old)
        if n:
            body = body.replace(old, new)
        print(f"  {'改' if n else '未命中'}  {old[:24]:<26} → {new[:24]:<26} {why}")

    if not args.dry_run:
        BODY.write_text(body, encoding="utf-8")
        print(f"\n[ok] index_body.html {before} → {len(body)} 字符")

    # 复扫
    def has_emoji(text: str) -> bool:
        return any(ord(c) > 0x2000 and not (0x4E00 <= ord(c) <= 0x9FFF) for c in text)

    groups: dict[str, list[str]] = {"有符号": [], "无符号": []}
    for m in re.finditer(r"<button[^>]*>([^<]*)</button>", body):
        txt = m.group(1).strip()
        if txt:
            groups["有符号" if has_emoji(txt) else "无符号"].append(txt)

    print()
    print(f"=== 复扫：有符号 {len(groups['有符号'])} 个 / 无符号 {len(groups['无符号'])} 个 ===")
    for t in groups["有符号"]:
        print("   ", t)

    print()
    print("=== 保留清单（写进 DESIGN.md 作为例外依据）===")
    for t in KEEP:
        ok = t in body
        print(f"  {'✓' if ok else '✗'} {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
