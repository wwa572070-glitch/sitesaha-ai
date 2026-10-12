"""§4 应急页收口（第 20 轮 P0）。

你实测整页「拨打 120」出现 6 次、「拨打 119」5 次，同屏重复显得杂乱。

四处改动：
  1. 拨号按钮组改为**吸底常驻**（滚动时始终可见，出事时不用找）
  2. 119 用橙红区分于 120 的正红（两码事，视觉上要分开）
  3. 加「打印这张卡」按钮
  4. 加打印样式：只印应急内容，去掉导航与页脚（A4）

卡片本身的电话 pill 已经做了（.em-card-dial），不再重复大按钮。

用法：python patch_sos_card.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
TIERS = BUILD / "v16_tiers.css"

OLD_BLOCK = '''          <div class="em-calls">

            <a id="call120" class="danger-button" href="tel:120"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 拨打 120 急救</a>

            <a id="call119" class="danger-button" href="tel:119"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 拨打 119 火警 / 救援</a>

          </div>'''

NEW_BLOCK = '''          <div class="em-call-bar" id="emCallBar">

            <a id="call120" class="call-button is-medical" href="tel:120"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 120 急救</a>

            <a id="call119" class="call-button is-fire" href="tel:119"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 119 火警</a>

            <button id="sosPrint" class="call-button is-print" type="button"><svg class="ico" aria-hidden="true"><use href="#i-print"/></svg> 打印这张卡</button>

          </div>'''

CSS = """

/* ==========================================================================
   §4 应急页收口（第 20 轮）
   --------------------------------------------------------------------------
   原来 120/119 在页面中段，且全站重复出现 5~6 次。
   现在：拨号条吸底常驻，120 正红 / 119 橙红，另加打印。
   ========================================================================== */
.em-call-bar {
  position: sticky; bottom: 0; z-index: 30;
  display: flex; flex-wrap: wrap; gap: 10px;
  padding: 12px 0 4px;
  background: linear-gradient(to top, var(--surface) 72%, transparent);
}
.call-button {
  flex: 1 1 auto; min-height: 52px; min-width: 120px;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  border-radius: var(--r-sm); border: 1px solid transparent;
  font-size: var(--fs-lg); font-weight: 800;
  text-decoration: none; cursor: pointer;
}
.call-button.is-medical { background: #b3261e; color: #fff; }
.call-button.is-medical:hover { background: #8f1d17; color: #fff; }
.call-button.is-fire { background: #d9622b; color: #fff; }
.call-button.is-fire:hover { background: #bf5320; color: #fff; }
.call-button.is-print {
  background: var(--surface); color: var(--i700); border-color: var(--i300);
  flex: 0 0 auto; font-size: var(--fs-md); min-width: 0;
}
.call-button.is-print:hover { border-color: var(--brand); color: var(--brand); }
.call-button:focus-visible { outline: 3px solid var(--brand); outline-offset: 2px; }

@media (max-width: 640px) {
  .em-call-bar { gap: 8px; }
  .call-button { font-size: var(--fs-base); min-height: 50px; }
  .call-button.is-print { flex: 1 1 100%; }
}

/* 打印：只印应急卡内容 */
@media print {
  .site-header, header, nav, .tabs, footer,
  .sos-fab, .em-call-bar, .no-print { display: none !important; }
  #sos { display: block !important; }
  .view { display: none !important; }
  #sos .panel { break-inside: avoid; border: 1px solid #000; }
  .sos-alert {
    background: #fff !important; color: #000 !important;
    border: 2px solid #000 !important; border-left-width: 6px !important;
  }
  .sos-alert-title, .sos-alert-chant span, .sos-alert-sub, .sos-alert-note {
    color: #000 !important; background: none !important;
  }
  .sos-alert-chant span { border: 2px solid #000 !important; }
  .emergency-card { border: 1.5px solid #000 !important; break-inside: avoid; }
  body { background: #fff !important; }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    body = BODY.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    if "em-call-bar" not in body:
        old = "\n\n".join(OLD_BLOCK.split("\n"))
        new = "\n\n".join(NEW_BLOCK.split("\n"))
        if old in body:
            body = body.replace(old, new, 1)
            applied += 1
            print("  [ok] 拨号条改为吸底 + 119 橙红 + 打印按钮")
        else:
            print("  [FAIL] 拨号块锚点未匹配")
            return 1
    else:
        print("  [跳过] 拨号条已改")

    if "§4 应急页收口" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("  [ok] 样式与打印样式已加入")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    TIERS.write_text(tiers, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
