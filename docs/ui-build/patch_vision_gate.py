"""§4 视觉幻觉防护硬闸（第 16 轮 v2）。

实测证据（本轮 verify_contracts.py）：
  传 1x1 像素 PNG，模型输出 structured.work_type = "深基坑开挖"，risks = 3 条，
  还带 "画面中上部" / "画面中部" 的位置标签 —— 全是编的。
  而且 API 层已标记 image_quality=low，说明"只标记不拦截"不够。

两处改动：
  1. 服务端在调用模型**之前**解码图片尺寸；小于阈值直接返回
     image_quality=low + 看不清的提示，**不送模型**。
     这是唯一可靠的一道闸：模型对退化图必然编造。
  2. prompt 里把"看不清就直说"提到最前面，并明确禁止编造位置标签。

为什么要在服务端拦：前端预检可以被绕过（直接打接口），
安全产品的红线不能只依赖客户端。

用法：python patch_vision_gate.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
APP = BUILD.parent.parent
WEBAPP = APP / "webapp.py"
LLM = APP / "sitesaha" / "llm.py"

# ---------- 1) 服务端硬闸 ----------
GATE_HELPER = '''def image_geometry(data: bytes) -> tuple[int, int, str]:
    """从图片字节里读出宽高与格式 —— 不引入依赖，只解析文件头。

    支持的格式：PNG / JPEG / GIF / BMP / WebP。
    读不出时返回 (0, 0, "")，调用方按"无法判断"处理。

    为什么要做这个：模型对退化图像（1x1 像素、纯色）会凭空编造整个作业场景，
    实测输出过"深基坑开挖 + 3 条风险 + 画面中上部"这类完全不存在的细节。
    安全产品里这是红线，所以必须在送模型之前拦掉。
    """
    if len(data) < 24:
        return 0, 0, ""

    # PNG: 8 字节签名 + IHDR
    if data[:8] == b"\\x89PNG\\r\\n\\x1a\\n":
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        return width, height, "png"

    # GIF
    if data[:6] in (b"GIF87a", b"GIF89a"):
        width = int.from_bytes(data[6:8], "little")
        height = int.from_bytes(data[8:10], "little")
        return width, height, "gif"

    # BMP
    if data[:2] == b"BM":
        width = int.from_bytes(data[18:22], "little", signed=True)
        height = abs(int.from_bytes(data[22:26], "little", signed=True))
        return width, height, "bmp"

    # WebP (VP8X / VP8L / VP8 )
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
            return width, height, "webp"
        if chunk == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, "webp"
        if chunk == b"VP8 ":
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            return width, height, "webp"

    # JPEG: 扫 SOFn 段
    if data[:2] == b"\\xff\\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            length = int.from_bytes(data[index + 2:index + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height = int.from_bytes(data[index + 5:index + 7], "big")
                width = int.from_bytes(data[index + 7:index + 9], "big")
                return width, height, "jpeg"
            index += 2 + max(length, 2)
        return 0, 0, "jpeg"

    return 0, 0, ""


# 低于这个边长或字节数就认为不是实拍
MIN_EDGE_PX = 200
MIN_BYTES = 8 * 1024


def looks_degenerate(width: int, height: int, size: int) -> bool:
    """判断图片是否明显不是实拍。宽高未知时只看字节数。"""
    if size < MIN_BYTES:
        return True
    if width and height and (width < MIN_EDGE_PX or height < MIN_EDGE_PX):
        return True
    return False


'''

REJECT_BLOCK = '''            # ---- §4 硬闸：退化图不送模型 ----
            # 实测：1x1 像素 PNG 会让模型输出"深基坑开挖 + 3 条风险 + 画面中上部"，
            # 全是编的。前端预检可被绕过（直接打接口），所以服务端也必须拦。
            width, height, image_format = image_geometry(image_bytes)
            if looks_degenerate(width, height, len(image_bytes)):
                self._write_json(
                    {
                        "text": "这张照片看不清，请重拍。",
                        "text_plain": "这张照片看不清，请重拍。",
                        "structured": {
                            "work_type": "",
                            "risks": [],
                            "uncertain": [],
                            "citations": [],
                        },
                        "image_quality": "low",
                        "rejected": True,
                        "image": {
                            "width": width,
                            "height": height,
                            "format": image_format,
                            "bytes": len(image_bytes),
                        },
                        "sources": [],
                        "warnings": [
                            "照片过小或不像实拍，没有送去识别。"
                            "请对着作业面重新拍一张，把防护设施和周边环境一起拍进去。"
                        ],
                        "hint": "光线不足时先补光；不要拍人脸和证件。",
                    }
                )
                return

'''

# ---------- 2) prompt 加固 ----------
PROMPT_ANCHOR = "SITESHAHA_VISION_SYSTEM"

PROMPT_PREFIX = '''SITESHAHA_VISION_SYSTEM = (
    "第一步先判断这张照片能不能看。如果它模糊、过暗、过曝、近乎纯色，"
    "或者看不出任何作业场景（比如只是地面、墙面、天空的特写），"
    "你必须只回答「这张照片看不清，请重拍。」然后结束，"
    "不要推测场景，不要列举通用风险，不要给出任何部位描述。"
    "只有在能明确识别出作业场景时，才按下面的格式回答。\\n\\n"
    "严禁编造位置。你说出的每个位置（如\\u201c画面中部\\u201d\\u201c左侧\\u201d）"
    "都必须是照片里真实可见的，不能凭想象补。\\n\\n"
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = WEBAPP.read_text(encoding="utf-8")
    changed = 0

    if "def image_geometry" not in text:
        anchor = "def answer_payload(question: str, answer: Answer) -> dict[str, Any]:"
        if anchor not in text:
            print("[FAIL] 找不到 answer_payload 锚点")
            return 1
        text = text.replace(anchor, GATE_HELPER + anchor, 1)
        changed += 1
        print("[ok] 加入 image_geometry / looks_degenerate")
    else:
        print("[跳过] image_geometry 已存在")

    if '"rejected": True' not in text:
        # 插在视觉调用之前
        anchor = "                sources = self.services.engine.retrieve("
        if anchor in text:
            text = text.replace(anchor, REJECT_BLOCK + anchor, 1)
            changed += 1
            print("[ok] 退化图在送模型前直接拒收")
        else:
            # 退而求其次：找视觉 API 调用点
            import re
            match = re.search(r"\n(                [^\n]*inspect_image[^\n]*)", text)
            if match:
                text = text[: match.start() + 1] + REJECT_BLOCK + text[match.start() + 1:]
                changed += 1
                print("[ok] 退化图在 inspect_image 调用前拒收")
            else:
                print("[FAIL] 找不到视觉调用锚点")
                return 1
    else:
        print("[跳过] 硬闸已存在")

    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"[FAIL] webapp.py 语法错误：{exc}")
        return 1
    print("[ok] webapp.py 语法通过")

    # ---------- prompt ----------
    llm_text = LLM.read_text(encoding="utf-8")
    if "第一步先判断这张照片能不能看" not in llm_text:
        if PROMPT_ANCHOR not in llm_text:
            print("[WARN] llm.py 里找不到视觉 system prompt")
        else:
            index = llm_text.find(PROMPT_ANCHOR)
            line_start = llm_text.rfind("\n", 0, index) + 1
            llm_text = llm_text[:line_start] + PROMPT_PREFIX + llm_text[line_start:]
            try:
                ast.parse(llm_text)
            except SyntaxError as exc:
                print(f"[FAIL] llm.py 语法错误：{exc}")
                return 1
            if not args.dry_run:
                LLM.write_text(llm_text, encoding="utf-8")
            changed += 1
            print("[ok] 视觉 prompt 前置「先判断能否看清」与「禁止编造位置」")
    else:
        print("[跳过] prompt 已加固")

    if args.dry_run:
        print(f"（dry-run，未写入；{changed} 处）")
        return 0
    WEBAPP.write_text(text, encoding="utf-8")
    print(f"[ok] 已写入（{changed} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
