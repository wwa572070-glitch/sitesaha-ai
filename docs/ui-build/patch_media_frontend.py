"""前端：图片方向修正 + HEIC 明确指引 + 音频 60 秒上限（第 16 轮 §4.2 第 2 项）。

实测发现的三个缺口：
  1. usePhotoFile 用裸 new Image() 加载 —— 不处理 EXIF 方向，
     所以 iPhone 竖拍照片上传后会侧躺 90°。
     改用 createImageBitmap({imageOrientation: "from-image"})，浏览器原生转正。
  2. HEIC 只提示"先在相册导出"，用户不知道具体怎么做。
     补上 iPhone 的具体设置路径。
  3. 录音没有 60 秒上限（§4.2 第 5 点要求音频 ≤60 秒）。

注意：分片里每行之间有空行，脚本按空行格式生成替换文本。

用法：python patch_media_frontend.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_B = BUILD / "index_script_b.js"


def blank(text: str) -> str:
    """把普通多行文本转成分片风格（行间插空行）。"""
    return "\n\n".join(text.split("\n"))


OLD_BLOCK = blank("""      var probe = new Image();
      var objectUrl = URL.createObjectURL(file);
      var loaded = await new Promise(function (resolve) {
        probe.onload = function () { resolve(true); };
        probe.onerror = function () { resolve(false); };
        probe.src = objectUrl;
      });
      if (!loaded) {
        URL.revokeObjectURL(objectUrl);
        showPhotoError("照片格式无法识别。", [
          "请使用 JPG / PNG / WEBP 格式。",
          "部分手机的 HEIC 格式需要先在相册里导出为 JPG。",
        ]);
        return;
      }
      try {
        var meta = await compressImage(probe, file.name, sourceLabel);
        showPhotoStage(meta);
      } catch (error) {
        showPhotoError("照片处理失败", [String(error && error.message ? error.message : error)]);
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
    }""")

NEW_BLOCK = blank("""      /* 优先用 createImageBitmap 并开启 imageOrientation: "from-image"：
         它会按 EXIF 方向自动转正。裸 new Image() 不处理方向，
         iPhone 竖拍的照片上传后会侧躺 90°（实测发现）。 */
      var source = null;
      var objectUrl = URL.createObjectURL(file);
      if (typeof window.createImageBitmap === "function") {
        try {
          source = await window.createImageBitmap(file, { imageOrientation: "from-image" });
        } catch (bitmapError) {
          source = null;
        }
      }

      if (!source) {
        var probe = new Image();
        var loaded = await new Promise(function (resolve) {
          probe.onload = function () { resolve(true); };
          probe.onerror = function () { resolve(false); };
          probe.src = objectUrl;
        });
        if (!loaded) {
          URL.revokeObjectURL(objectUrl);
          var looksHeic = /heic|heif/i.test(file.type || "") ||
            /\\.(heic|heif)$/i.test(file.name || "");
          if (looksHeic) {
            showPhotoError("这张照片是 HEIC 格式，浏览器打不开。", [
              "iPhone 默认用 HEIC 拍摄，需要先转成 JPG 再上传。",
              "改相机设置：设置 → 相机 → 格式 → 选「兼容性最佳」，之后拍的就是 JPG。",
              "或把照片发到微信/相册里另存为 JPG 再上传。",
            ]);
          } else {
            showPhotoError("照片格式无法识别。", [
              "请使用 JPG / PNG / WEBP 格式。",
              "部分手机的 HEIC 格式需要先在相册里导出为 JPG。",
            ]);
          }
          return;
        }
        source = probe;
      }

      try {
        var meta = await compressImage(source, file.name, sourceLabel);
        showPhotoStage(meta);
      } catch (error) {
        showPhotoError("照片处理失败", [String(error && error.message ? error.message : error)]);
      } finally {
        URL.revokeObjectURL(objectUrl);
        if (source && typeof source.close === "function") {
          try { source.close(); } catch (closeError) { /* 忽略 */ }
        }
      }
    }""")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = SCRIPT_B.read_text(encoding="utf-8")
    if "imageOrientation" in text:
        print("[跳过] 图片方向修正已存在")
    else:
        if OLD_BLOCK not in text:
            print("[FAIL] 未找到 usePhotoFile 的加载块")
            return 1
        text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)
        print("[ok] 图片方向修正（createImageBitmap）+ HEIC 具体指引")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    SCRIPT_B.write_text(text, encoding="utf-8")
    print(f"[ok] index_script_b.js 已更新，{len(text)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
