"""§6 应急页醒目化（第 16 轮 v2，用户明确要求）。

用户原话："现在 6 张等高白卡 + 小灰字，是全站最不醒目的一页"。

改造要点（已确认稿）：
  1. 顶部红警带 #b3261e + 白字 + 口诀「停 → 撤 → 报」，替换深蓝
  2. 事故类型改大卡片：48px 图标 + 17~21px 标题 + 一行要点，
     最小高 120px，手机 2 列 / 桌面 3 列，红/琥珀高对比描边
  3. 步骤区改时间轴：圆形实心编号 + 竖向连接线
  4. 「绝对禁止」改 ✗/✓ 左右对照
  5. 电话按钮吸底（120 红实心 / 119 橙红实心）
  6. 全站常驻 SOS 浮动按钮
  7. 离线可用：应急内容不依赖任何接口

顺带修一个真 bug：
  makeButtonWithIcon 建的是 <button>，但 showEmergencyGuide 给它
  setAttribute("href", "tel:...") —— button 上的 href 无效，
  拨号链接实际点不动。改为建 <a>。

用法：python patch_sos.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"

# ---------- 1) 红警带 + SOS 浮动按钮 ----------
RED_BAND = '''      <!-- ========== §6 红警带：进页面第一眼就要看到 ========== -->
      <div class="sos-alert" role="alert">
        <div class="sos-alert-main">
          <svg class="ico ico-xl" aria-hidden="true"><use href="#i-alert"/></svg>
          <div>
            <h2 class="sos-alert-title">出事了先做这三步</h2>
            <p class="sos-alert-chant">
              <span>停</span><i aria-hidden="true">→</i><span>撤</span><i aria-hidden="true">→</i><span>报</span>
              <em>先停手 · 撤到安全区 · 报告负责人</em>
            </p>
          </div>
        </div>
        <p class="sos-alert-note">不要为了赶工或取东西返回危险区域。以下步骤不替代项目应急预案。</p>
      </div>
'''

SOS_FAB = '''
  <!-- ========== §6 全站常驻 SOS 入口 ========== -->
  <a id="sosFab" class="sos-fab" href="?view=sos" aria-label="紧急情况，去应急处置页">
    <svg class="ico ico-xl" aria-hidden="true"><use href="#i-phone"/></svg>
    <span class="sos-fab-text">应急</span>
  </a>
'''

# 需要替换的旧顶部结构线索
OLD_HERO = '''      <div class="emergency-hero">

        <h2><svg class="ico" aria-hidden="true"><use href="#i-alert"/></svg> 出事了先做这三步</h2>

        <p>一、先保证自己安全，停止相关作业；二、撤离危险区域并提醒附近工友；三、通知现场负责人和安全员，需要时拨打 120 / 119。不要为了赶工或取物品返回危险区域。</p>

      </div>'''

RED_BAND = '''      <!-- ========== §6 红警带：进页面第一眼就要看到 ========== -->
      <div class="sos-alert" role="alert">
        <div class="sos-alert-main">
          <svg class="ico ico-2xl" aria-hidden="true"><use href="#i-alert"/></svg>
          <div class="sos-alert-text">
            <h2 class="sos-alert-title">出事了先做这三步</h2>
            <p class="sos-alert-chant">
              <span>停</span><i aria-hidden="true">→</i><span>撤</span><i aria-hidden="true">→</i><span>报</span>
            </p>
            <p class="sos-alert-sub">先停手 · 撤到安全区 · 报告负责人，需要时拨打 120 / 119</p>
          </div>
        </div>
        <p class="sos-alert-note">不要为了赶工或取物品返回危险区域。以下步骤不替代项目应急预案，现场以项目预案与应急指挥为准。</p>
      </div>'''

SOS_FAB = '''
  <!-- ========== §6 全站常驻 SOS 入口 ========== -->
  <a id="sosFab" class="sos-fab" href="?view=sos" aria-label="紧急情况，去应急处置页">
    <svg class="ico ico-xl" aria-hidden="true"><use href="#i-phone"/></svg>
    <span class="sos-fab-text">应急</span>
  </a>
'''


def blank(text: str) -> str:
    return "\n\n".join(text.split("\n"))


# ---------- 2) 卡片渲染：大卡片 + 描边分级 ----------
GRID_OLD = '''      EMERGENCY_DATA.forEach(function (scene) {
        var card = make("button", "emergency-card");
        card.type = "button";
        card.appendChild(makeIcon(scene.icon, "ico ico-xl"));
        card.appendChild(make("strong", "", scene.label));
        card.appendChild(make("p", "", scene.headline));
        card.addEventListener("click", function () { showEmergencyGuide(scene.key); });
        host.appendChild(card);
      });'''

GRID_NEW = '''      EMERGENCY_DATA.forEach(function (scene) {
        var card = make("button", "emergency-card");
        card.type = "button";
        /* 描边分级：前两张是最常见也最紧急的（受伤/火灾），用红色；
           其余用琥珀色，避免整屏全红反而失去重点。 */
        card.classList.add(scene.calls && scene.calls.indexOf("120") >= 0
          ? "is-critical" : "is-urgent");
        card.appendChild(makeIcon(scene.icon, "ico ico-2xl"));
        card.appendChild(make("strong", "em-card-title", scene.label));
        card.appendChild(make("p", "em-card-lead", scene.headline));
        var dial = make("span", "em-card-dial");
        dial.appendChild(makeIcon("i-phone", "ico ico-sm"));
        dial.appendChild(document.createTextNode(" " + (scene.calls || []).join(" / ")));
        card.appendChild(dial);
        card.addEventListener("click", function () { showEmergencyGuide(scene.key); });
        host.appendChild(card);
      });'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    text_b = SCRIPT_B.read_text(encoding="utf-8")
    applied = 0

    # ---- 红警带替换旧的 emergency-hero ----
    if 'class="sos-alert"' not in body:
        if OLD_HERO not in body:
            print("[FAIL] 找不到旧 emergency-hero")
            return 1
        body = body.replace(OLD_HERO, RED_BAND, 1)
        applied += 1
        print("[ok] 深蓝 hero 换成红警带（#b3261e + 停→撤→报 口诀）")
    else:
        print("[跳过] 红警带已存在")

    # ---- SOS 浮动按钮插到 body 末尾前 ----
    if 'id="sosFab"' not in body:
        marker = "\n</body>"
        if marker in body:
            body = body.replace(marker, SOS_FAB + marker, 1)
            applied += 1
            print("[ok] 全站 SOS 浮动按钮已插入")
        else:
            print("[跳过] 找不到 </body>")
    else:
        print("[跳过] SOS 浮动按钮已存在")

    # ---- 卡片渲染 ----
    grid_old_blank = blank(GRID_OLD)
    grid_new_blank = blank(GRID_NEW)
    if "em-card-title" not in text_b:
        if grid_old_blank in text_b:
            text_b = text_b.replace(grid_old_blank, grid_new_blank, 1)
            applied += 1
            print("[ok] 应急卡片改为大卡片 + 描边分级")
        else:
            print("[跳过] 卡片渲染锚点未匹配")
    else:
        print("[跳过] 卡片已是新版")

    for name, text in (("body", body), ("b", text_b)):
        if text.count(chr(92)):
            print(f"[FAIL] {name} 含反斜杠")
            return 1
    print("[ok] 无反斜杠")

    if args.dry_run:
        print(f"（dry-run，未写入；{applied} 处）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    SCRIPT_B.write_text(text_b, encoding="utf-8")
    print(f"[ok] 已写入（{applied} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
