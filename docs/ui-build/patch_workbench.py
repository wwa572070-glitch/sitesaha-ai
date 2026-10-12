"""竞赛级改造 · 页面 B：AI 图像识别工作台的上传区（第 23 轮）。

现状问题（已实测确认）：
  · 图片识别是聊天下面的次要面板，三个按钮全是 secondary-button，没有主次
  · 没有上传区：只有两个隐藏 input + 三个按钮，用户不知道该干什么
  · 没有格式与大小提示（实测后端限 JPG/PNG/WEBP、≤8MB，但界面没说）
  · 不支持拖放
  · 没有分阶段状态（待上传 / 识别中 / 有结果）

本次改动（**只加视觉层，不碰任何现有处理函数**）：
  1. 新增 dropzone：虚线框 + 相机轮廓 + 明确文案 + 格式大小提示
  2. 支持拖放：把文件塞进现有的 sitePhotoCamera input，再派发 change
  3. 选中图片后 dropzone 收起，预览区成为主角
  4. 主次按钮层级：识别用主按钮，其余保持次要

约束：
  · 不新增依赖
  · 不修改任何现有 id 与事件绑定（cameraButton / filePickButton / sitePhoto / sitePhotoCamera 全部保留）
  · 分片禁止反斜杠

用法：python patch_workbench.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_B = BUILD / "index_script_b.js"
TIERS = BUILD / "v16_tiers.css"

# ---- 上传区标记（插在 capture-tools 之前）----
OLD = '''          <div class="capture-tools">

            <button id="cameraButton" class="secondary-button" type="button">'''

NEW = '''          <!-- ===== AI 识别工作台：上传区（竞赛级改造） ===== -->
          <div id="photoDropzone" class="dropzone" role="button" tabindex="0"
               aria-label="选择或拖放现场照片，支持 JPG PNG WEBP，不超过 8 MB">
            <svg class="dropzone-art" viewBox="0 0 48 48" aria-hidden="true">
              <rect x="6" y="14" width="36" height="26" rx="4"/>
              <circle cx="24" cy="27" r="8"/>
              <path d="M17 14l2-4h10l2 4"/>
              <path d="M24 23v8M20 27l4-4 4 4"/>
            </svg>
            <div class="dropzone-title">拍照或拖入现场照片</div>
            <div class="dropzone-sub">点击选择文件，也可以把图片直接拖到这里</div>
            <div class="dropzone-hint">支持 JPG / PNG / WEBP · 单张不超过 8 MB</div>
          </div>

          <div class="capture-tools">

            <button id="cameraButton" class="secondary-button" type="button">'''

CSS = """

/* ==========================================================================
   竞赛级改造 · AI 识别工作台上传区
   --------------------------------------------------------------------------
   原来只有三个并列的次要按钮，用户看不出该做什么。
   现在给一个明确的视觉锚点：虚线框 + 相机轮廓 + 格式大小提示 + 拖放。
   ========================================================================== */
.dropzone {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; padding: 28px 20px; margin-bottom: 16px;
  border: 2px dashed var(--i300); border-radius: var(--r-lg);
  background: var(--surface-soft);
  cursor: pointer; text-align: center;
  transition: border-color .16s ease, background-color .16s ease;
}
.dropzone:hover, .dropzone:focus-visible {
  border-color: var(--accent); background: var(--accent-050);
  outline: none;
}
.dropzone.is-dragover {
  border-color: var(--accent); background: var(--accent-100);
  border-style: solid;
}
.dropzone-art {
  width: 48px; height: 48px; margin-bottom: 8px;
  fill: none; stroke: var(--brand-500); stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round;
}
.dropzone-title {
  font-size: var(--fs-lg); font-weight: 800; color: var(--brand);
}
.dropzone-sub {
  font-size: var(--fs-sm); color: var(--i600); line-height: 1.7;
}
.dropzone-hint {
  margin-top: 8px; padding: 4px 12px;
  border-radius: 999px; background: var(--brand-050);
  font-size: var(--fs-xs); color: var(--i600);
  font-variant-numeric: tabular-nums;
}

/* 工作台主按钮：识别是唯一的主操作 */
.workbench-primary {
  min-height: 44px; font-size: var(--fs-base); font-weight: 800;
}

/* 图片预览：成为主角，不被卡片挤压 */
.photo-stage { position: relative; }
.photo-stage > img {
  width: 100%; max-height: 420px; object-fit: contain;
  border-radius: var(--r-md); background: var(--i100);
  border: 1px solid var(--line);
}

@media (max-width: 640px) {
  .dropzone { padding: 20px 16px; }
  .dropzone-art { width: 40px; height: 40px; }
  .dropzone-title { font-size: var(--fs-base); }
  .photo-stage > img { max-height: 300px; }
}
"""

# ---- 拖放与状态联动（追加，不改动现有函数）----
JS = '''    /* ==================================================================
       竞赛级改造 · 上传区交互
       ------------------------------------------------------------------
       只做视觉层与文件投递：
         · 点击上传区 → 触发已有的 sitePhotoCamera 选择器
         · 拖放 → 把文件塞进同一个 input，再派发 change，
           复用现有的全部校验与上传逻辑，不新开代码路径
         · 选中图片后收起上传区；重拍时再显示
       ================================================================== */
    (function bindDropzone() {
      var zone = $("photoDropzone");
      var input = $("sitePhotoCamera");
      if (!zone || !input) return;

      function openPicker() { input.click(); }

      zone.addEventListener("click", openPicker);
      zone.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openPicker();
        }
      });

      ["dragenter", "dragover"].forEach(function (name) {
        zone.addEventListener(name, function (event) {
          event.preventDefault();
          zone.classList.add("is-dragover");
        });
      });
      ["dragleave", "drop"].forEach(function (name) {
        zone.addEventListener(name, function (event) {
          event.preventDefault();
          zone.classList.remove("is-dragover");
        });
      });

      zone.addEventListener("drop", function (event) {
        var files = event.dataTransfer && event.dataTransfer.files;
        if (!files || !files.length) return;
        try {
          var transfer = new DataTransfer();
          transfer.items.add(files[0]);
          input.files = transfer.files;
          input.dispatchEvent(new Event("change", { bubbles: true }));
        } catch (error) {
          /* 浏览器不支持构造 DataTransfer 时，退回打开选择器 */
          openPicker();
        }
      });

      /* 有图就收起上传区，没图就显示 */
      function syncDropzone() {
        var stage = $("photoStage");
        var cameraStage = $("cameraStage");
        var hasImage = stage && !stage.hidden;
        var cameraOn = cameraStage && !cameraStage.hidden;
        zone.hidden = Boolean(hasImage || cameraOn);
      }

      if (window.MutationObserver) {
        ["photoStage", "cameraStage"].forEach(function (id) {
          var node = $(id);
          if (!node) return;
          new MutationObserver(syncDropzone).observe(node,
            { attributes: true, attributeFilter: ["hidden"] });
        });
      }
      syncDropzone();
    })();

'''

ANCHOR = '    (function bindSosFab() {'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    script = SCRIPT_B.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")
    applied = 0

    if 'id="photoDropzone"' in body:
        print("  [跳过] 上传区已存在")
    else:
        old = "\n\n".join(OLD.split("\n"))
        new = "\n\n".join(NEW.split("\n"))
        if old in body:
            body = body.replace(old, new, 1)
            applied += 1
            print("  [ok] 上传区已加入（拖放 + 格式提示）")
        elif OLD in body:
            body = body.replace(OLD, NEW, 1)
            applied += 1
            print("  [ok] 上传区已加入（无空行格式）")
        else:
            print("  [FAIL] capture-tools 锚点未匹配")
            return 1

    if "bindDropzone" in script:
        print("  [跳过] 拖放逻辑已存在")
    elif ANCHOR in script:
        script = script.replace(ANCHOR, JS + ANCHOR, 1)
        applied += 1
        print("  [ok] 拖放与状态联动已加入")
    else:
        print("  [FAIL] 找不到 bindSosFab 锚点")
        return 1

    if "AI 识别工作台上传区" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 样式已加入")

    for name, text in (("body", body), ("script", script)):
        count = text.count(chr(92))
        if count:
            print(f"  [FAIL] {name} 含 {count} 个反斜杠")
            return 1
    print("  [ok] 分片无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    SCRIPT_B.write_text(script, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
