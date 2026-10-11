"""补完 ask 页语音区收敛（第 16 轮 §6）。

上一版只改到一半：
  · composer-tools 的锚点因为 emoji 替换已过期，没匹配上
  · speakVoiceRow 被误删，但脚本仍引用它 → JS 检查报缺 id
  · composer-status 缺样式

本版按**当前实际内容**改：
  · 主行只留 1 个主录音按钮 + 1 个朗读开关
  · 音色下拉（speakVoiceRow）与浏览器识别收进 <details> 折叠区，
    保留 id 以免脚本报错
  · recordStopButton / speakStopButton 保留但移出主行（脚本控制显隐）

用法：python collapse_voice_controls2.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

OLD = '''          <div class="composer-tools">

            <button id="recordButton" class="voice-button" type="button"><svg class="ico" aria-hidden="true"><use href="#i-mic"/></svg> 录音提问</button>

            <button id="recordStopButton" class="danger-button" type="button" hidden>停止并识别</button>

            <button id="voiceButton" class="secondary-button" type="button" disabled><svg class="ico" aria-hidden="true"><use href="#i-keyboard"/></svg> 浏览器识别</button>

            <button id="speakButton" class="secondary-button" type="button" disabled><svg class="ico" aria-hidden="true"><use href="#i-speaker"/></svg> 朗读回答</button>

            <button id="speakStopButton" class="ghost-button" type="button" hidden>停止朗读</button>

            <span class="answer-meta" style="margin-left:auto">Ctrl + Enter 快速提交</span>

          </div>'''

NEW = '''          <div class="composer-tools">

            <button id="recordButton" class="voice-button ico-button" type="button"><svg class="ico" aria-hidden="true"><use href="#i-mic"/></svg> 录音提问</button>

            <button id="speakButton" class="secondary-button ico-button" type="button" disabled><svg class="ico" aria-hidden="true"><use href="#i-speaker"/></svg> 朗读回答</button>

            <span class="answer-meta composer-kbd">Ctrl + Enter 快速提交</span>

          </div>

          <details class="composer-more">

            <summary>更多输入与朗读方式</summary>

            <div class="composer-more-body">

              <p class="answer-meta">服务端语音识别不可用时可改用浏览器识别；朗读音色只在系统提供多个中文音色时才需要选。</p>

              <div class="composer-more-row">

                <button id="voiceButton" class="secondary-button ico-button" type="button" disabled><svg class="ico" aria-hidden="true"><use href="#i-keyboard"/></svg> 浏览器识别</button>

                <button id="recordStopButton" class="danger-button" type="button" hidden>停止并识别</button>

                <button id="speakStopButton" class="ghost-button" type="button" hidden>停止朗读</button>

              </div>

              <div id="speakVoiceRow" class="voice-row"></div>

            </div>

          </details>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    if OLD not in body:
        print("[跳过] 主行锚点未匹配（可能已改）")
        return 0
    body = body.replace(OLD, NEW, 1)
    print("[ok] 语音主行收敛为 1 主录音 + 1 朗读开关；其余收进折叠区")

    # 确认关键 id 都在
    for ident in ("speakVoiceRow", "voiceButton", "recordStopButton",
                  "speakStopButton", "recordButton", "speakButton"):
        mark = "ok" if f'id="{ident}"' in body else "缺失"
        print(f"  [{mark}] #{ident}")

    if body.count(chr(92)):
        print("[FAIL] 引入反斜杠")
        return 1

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0
    BODY.write_text(body, encoding="utf-8")
    print("[ok] index_body.html 已更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
