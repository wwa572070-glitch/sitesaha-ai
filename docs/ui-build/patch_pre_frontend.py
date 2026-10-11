"""§11 前端：班前条件选择器 + 按条件生成 + 文件导入（第 16 轮）。

结构（三块，插在 pre 视图现有的两个 panel 之前）：
  ① 当班条件    17 个条件分两组勾选，勾选即生成
  ② 当班清单    按「当班必查（带命中理由）/ 常规项 / 我的导入」分组，逐条勾选
  ③ 导入        文件选择 → 预览前 10 行 + 逐行错误 → 确认合并 / 撤销 / 导出 CSV / 打印

数据持久化一律用 localStorage（本机资料，不上传）：
  sitesaha-shift-v1      当班条件与项目信息
  sitesaha-checklist-v1  勾选状态
  sitesaha-import-v1     导入的自定义检查项

为什么清单要重写成渲染函数：原来的 loadChecklists 只渲染 /api/checklists 的
priority_checks + 分类索引，不随条件变化；而 updateCheckProgress 还查了一个
不存在的 #checklist 容器，导致进度一直显示 0 / 7。这次一并修掉。

用法：python patch_pre_frontend.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"
SCRIPT_B = BUILD / "index_script_b.js"
TIERS = BUILD / "v16_tiers.css"

# ---------------------------------------------------------------- 结构
PANELS = '''      <!-- ========== §11 当班条件 ========== -->
      <div class="panel" id="shiftPanel">
        <div class="panel-head">
          <h2><svg class="ico" aria-hidden="true"><use href="#i-clock"/></svg> 当班条件</h2>
          <span id="shiftBadge" class="count-badge">未选</span>
          <span class="head-spacer"></span>
          <button id="shiftClear" class="ghost-button" type="button">清空条件</button>
        </div>
        <div class="panel-body">
          <p class="lead">勾选今天的实际情况，下面会生成对应的当班检查清单。不勾选也能用，退回全量基础清单。</p>
          <div id="shiftConditions" aria-busy="true">
            <div class="skeleton skeleton-line w80" aria-hidden="true"></div>
            <div class="skeleton skeleton-line w60" aria-hidden="true"></div>
          </div>
        </div>
      </div>

      <!-- ========== §11 当班清单 ========== -->
      <div class="panel">
        <div class="panel-head">
          <h2><svg class="ico" aria-hidden="true"><use href="#i-clipboard"/></svg> 当班检查清单</h2>
          <span id="priorityBadge" class="count-badge">0 / 0</span>
          <span class="head-spacer"></span>
          <button id="checkReset" class="ghost-button" type="button">重置全部勾选</button>
        </div>
        <div class="panel-body">
          <p class="lead">先在现场逐项确认，发现不满足条件时停止作业并报告。勾选结果保存在本机，刷新后仍在。</p>
          <div class="list-progress">
            <div class="progress-track"><div id="checkFill" class="progress-fill"></div></div>
            <span id="checkLabel" class="progress-label">0 / 0</span>
          </div>
          <div id="priorityChecks" style="margin-top:16px" aria-busy="true"></div>
          <div class="row-actions" style="margin-top:16px">
            <button id="preGenerate" class="primary-button ico-button" type="button">
              <svg class="ico" aria-hidden="true"><use href="#i-refresh"/></svg>按当班条件重新生成
            </button>
            <button id="preExport" class="secondary-button ico-button" type="button">
              <svg class="ico" aria-hidden="true"><use href="#i-doc"/></svg>导出 CSV
            </button>
            <button id="prePrint" class="secondary-button ico-button" type="button">
              <svg class="ico" aria-hidden="true"><use href="#i-print"/></svg>打印 A4
            </button>
          </div>
        </div>
      </div>

      <!-- ========== §11 导入项目自有清单 ========== -->
      <div class="panel" id="importPanel">
        <div class="panel-head">
          <h2><svg class="ico" aria-hidden="true"><use href="#i-doc"/></svg> 导入项目自有清单</h2>
          <span id="importBadge" class="count-badge">0 条</span>
          <span class="head-spacer"></span>
          <span class="head-note">支持 csv / txt / md / xlsx</span>
        </div>
        <div class="panel-body">
          <p class="lead">把项目自己的检查表导进来，和内置清单一起用。导入内容标注为「项目自有文件」，不会冒充国标条款，只存在你这台机器上。</p>
          <input id="importFile" class="sr-only" type="file"
                 accept=".csv,.txt,.md,.xlsx,text/csv,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
          <div class="row-actions">
            <button id="importPick" class="secondary-button ico-button" type="button">
              <svg class="ico" aria-hidden="true"><use href="#i-image"/></svg>选择文件
            </button>
            <button id="importUndo" class="ghost-button" type="button" hidden>撤销本次导入</button>
          </div>
          <div id="importPreview" class="import-preview" hidden></div>
          <div id="importList" class="import-list" style="margin-top:16px"></div>
          <details class="composer-more">
            <summary>文件格式怎么写</summary>
            <div class="composer-more-body">
              <p class="answer-meta">一行一条，字段用逗号分隔，顺序为：<b>类别, 检查内容, 判定要点, 依据</b>。只写一个字段时按「检查内容」处理，类别默认「项目自定义」。以 # 开头的行是注释。</p>
              <pre class="import-sample">类别,检查内容,判定要点,依据
临时设施,宿舍内是否使用大功率电器,无电炉热得快,项目制度
消防,灭火器压力表是否在绿区,指针在绿区且在有效期内,项目制度
- 塔吊基础是否有积水
# 井号开头是注释，不会导入</pre>
            </div>
          </details>
        </div>
      </div>
'''

# ---------------------------------------------------------------- 样式
CSS = """

/* ==========================================================================
   §11 班前条件与导入
   ========================================================================== */
.shift-group { margin-bottom: 16px; }
.shift-group:last-child { margin-bottom: 0; }
.shift-group-title {
  display: block; font-size: var(--fs-sm); font-weight: 800;
  color: var(--brand); margin-bottom: 8px; letter-spacing: .02em;
}
.shift-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.shift-chip {
  flex: 0 0 auto; min-height: 40px; padding: 8px 14px;
  border-radius: var(--r-sm); border: 1px solid var(--i300);
  background: var(--surface); color: var(--i700);
  font-size: var(--fs-sm); font-weight: 700; cursor: pointer;
  transition: background .15s ease, border-color .15s ease, color .15s ease;
}
.shift-chip:hover { border-color: var(--brand); color: var(--brand); }
.shift-chip[aria-pressed="true"] {
  background: var(--brand); border-color: var(--brand); color: #fff;
}
.shift-chip[aria-pressed="true"]::after { content: " ✓"; color: var(--accent); }
.shift-chip:focus-visible { outline: 3px solid var(--brand); outline-offset: 2px; }

/* 清单分组 */
.check-group { margin-bottom: 20px; }
.check-group:last-child { margin-bottom: 0; }
.check-group-head {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px;
  padding-bottom: 8px; margin-bottom: 8px;
  border-bottom: 2px solid var(--line);
}
.check-group-title { font-size: var(--fs-md); font-weight: 800; color: var(--i900); }
.check-group-note { font-size: var(--fs-xs); color: var(--i500); }
.check-item { align-items: flex-start; }
.check-item .check-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.check-item .check-text { font-size: var(--fs-md); color: var(--i800); line-height: 1.6; }
.check-item .check-judge { font-size: var(--fs-sm); color: var(--i500); line-height: 1.6; }
.check-item .check-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 4px;
}
.check-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: var(--fs-xs); font-weight: 700;
}
.check-tag.is-source { background: var(--brand-050); color: var(--brand); }
.check-tag.is-basis { background: var(--surface-soft); color: var(--i600); }
.check-tag.is-import { background: var(--risk-mid-bg); color: var(--risk-mid-text); }
.check-code {
  font-family: var(--mono); font-size: var(--fs-xs); color: var(--i500);
  font-variant-numeric: tabular-nums;
}

/* 导入预览 */
.import-preview {
  margin-top: 16px; border: 1px solid var(--line); border-radius: var(--r-md);
  overflow: hidden;
}
.import-preview-head {
  padding: 10px 14px; background: var(--surface-soft);
  font-size: var(--fs-sm); font-weight: 700; color: var(--i700);
}
.import-table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
.import-table th, .import-table td {
  padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.import-table th { background: var(--surface-soft); font-weight: 700; color: var(--i700); }
.import-table tr.is-error td { background: var(--risk-high-bg); color: var(--risk-high-text); }
.import-table .cell-code {
  font-family: var(--mono); font-size: var(--fs-xs); color: var(--i500); white-space: nowrap;
}
.import-row-error { font-size: var(--fs-xs); color: var(--risk-high-text); font-weight: 700; }
.import-preview-actions {
  display: flex; flex-wrap: wrap; gap: 10px; padding: 12px 14px;
  background: var(--surface-soft); border-top: 1px solid var(--line);
}
.import-list { display: flex; flex-direction: column; gap: 8px; }
.import-sample {
  font-family: var(--mono); font-size: var(--fs-xs); line-height: 1.7;
  background: var(--surface-soft); border: 1px solid var(--line);
  border-radius: var(--r-sm); padding: 12px; overflow-x: auto;
  white-space: pre; color: var(--i700); margin: 0;
}
.row-actions { display: flex; flex-wrap: wrap; gap: 10px; }

@media (max-width: 640px) {
  .shift-chip { flex: 1 1 calc(50% - 8px); justify-content: center; }
  .row-actions .ico-button { width: 100%; justify-content: center; }
  .import-preview { overflow-x: auto; }
}
"""

# ---------------------------------------------------------------- 脚本
SCRIPT = '''    /* ==================================================================
       §11 班前条件 → 生成清单 → 导入项目自有文件
       ------------------------------------------------------------------
       数据全部存本机 localStorage，不上传：
         sitesaha-shift-v1      当班条件
         sitesaha-checklist-v1  勾选状态
         sitesaha-import-v1     导入的自定义检查项
       ================================================================== */
    var SHIFT_KEY = "sitesaha-shift-v1";
    var CHECK_KEY = "sitesaha-checklist-v1";
    var IMPORT_KEY = "sitesaha-import-v1";

    var shiftState = { conditions: [], required: [], routine: [] };
    var importRows = [];
    var pendingImport = null;

    function checklistKey(item) {
      return (item.code || "") + "|" + (item.content || "").slice(0, 40);
    }

    /* ---------- 条件选择器 ---------- */
    function renderConditions(payload) {
      var host = clear($("shiftConditions"));
      if (!host) return;
      host.setAttribute("aria-busy", "false");
      if (!payload) {
        host.appendChild(make("p", "empty-state", "条件读取失败，可以先用默认清单。"));
        return;
      }
      var saved = readStore(SHIFT_KEY, { conditions: [] });
      var active = saved.conditions || [];

      [
        { title: "天气与环境", items: payload.weather || [] },
        { title: "当班作业", items: payload.work || [] },
      ].forEach(function (group) {
        if (!group.items.length) return;
        var bucket = make("div", "shift-group");
        bucket.appendChild(make("b", "shift-group-title", group.title));
        var chips = make("div", "shift-chips");
        group.items.forEach(function (item) {
          var pressed = active.indexOf(item.key) >= 0;
          var chip = make("button", "shift-chip", item.label);
          chip.type = "button";
          chip.setAttribute("aria-pressed", pressed ? "true" : "false");
          chip.setAttribute("data-condition", item.key);
          chip.addEventListener("click", function () {
            var state = readStore(SHIFT_KEY, { conditions: [] });
            var list = state.conditions || [];
            var at = list.indexOf(item.key);
            if (at >= 0) list.splice(at, 1); else list.push(item.key);
            state.conditions = list;
            writeStore(SHIFT_KEY, state);
            chip.setAttribute("aria-pressed", at >= 0 ? "false" : "true");
            generateChecklist();
          });
          chips.appendChild(chip);
        });
        bucket.appendChild(chips);
        host.appendChild(bucket);
      });
      if (!host.children.length) {
        host.appendChild(make("p", "empty-state", "没有可选条件。"));
      }
    }

    /* ---------- 生成并渲染清单 ---------- */
    function generateChecklist(silent) {
      var saved = readStore(SHIFT_KEY, { conditions: [] });
      var badge = $("shiftBadge");
      if (badge) {
        badge.textContent = saved.conditions.length
          ? saved.conditions.length + " 项条件" : "未选";
      }
      return postJson("/api/checklists/generate", { conditions: saved.conditions || [] })
        .then(function (data) {
          shiftState = data || { conditions: [], required: [], routine: [] };
          renderChecklist();
        })
        .catch(function () {
          if (!silent) {
            var host = clear($("priorityChecks"));
            if (host) {
              host.appendChild(make("p", "empty-state",
                "清单生成失败。检查网络后点「按当班条件重新生成」。"));
            }
          }
        });
    }

    function renderChecklist() {
      var host = clear($("priorityChecks"));
      if (!host) return;
      host.setAttribute("aria-busy", "false");
      var state = readStore(CHECK_KEY, {});
      var required = shiftState.required || [];
      var routine = shiftState.routine || [];
      var imported = importRows;

      var groups = [
        {
          title: "当班必查",
          note: required.length
            ? "由你勾选的条件命中，每条都标了理由"
            : "没有勾选条件，下面按常规项过一遍",
          items: required,
          key: "required",
        },
        { title: "常规项", note: "每班都建议过一遍", items: routine, key: "routine" },
        {
          title: "我的导入",
          note: imported.length ? "来自项目自有文件，不代表国标条款" : "还没有导入内容",
          items: imported,
          key: "import",
        },
      ];

      var total = 0;
      groups.forEach(function (group) {
        if (!group.items.length && group.key !== "import") return;
        var bucket = make("section", "check-group");
        var head = make("div", "check-group-head");
        head.appendChild(make("b", "check-group-title", group.title));
        head.appendChild(make("span", "check-group-note", group.note));
        bucket.appendChild(head);

        if (!group.items.length) {
          bucket.appendChild(make("p", "empty-state",
            group.key === "import"
              ? "还没有导入项目自己的检查表。可以在下面「导入项目自有清单」里添加。"
              : "这一组暂时没有内容。"));
          host.appendChild(bucket);
          return;
        }

        group.items.forEach(function (item) {
          total += 1;
          var key = checklistKey(item);
          var label = make("label", "check-item" + (state[key] ? " checked" : ""));
          var box = document.createElement("input");
          box.type = "checkbox";
          box.checked = Boolean(state[key]);
          box.setAttribute("aria-label", item.content || "");
          box.addEventListener("change", function () {
            var current = readStore(CHECK_KEY, {});
            current[key] = box.checked;
            writeStore(CHECK_KEY, current);
            label.classList.toggle("checked", box.checked);
            if (box.checked) logActivity();
            updateCheckProgress();
          });
          label.appendChild(box);

          var main = make("span", "check-main");
          main.appendChild(make("span", "check-text", item.content || ""));
          if (item.judge) {
            main.appendChild(make("span", "check-judge", "判定：" + item.judge));
          }
          var meta = make("span", "check-meta");
          if (item.code) meta.appendChild(make("span", "check-code", item.code));
          if (item.source && group.key === "required") {
            meta.appendChild(make("span", "check-tag is-source",
              "命中：" + item.source));
          }
          if (item.basis) {
            meta.appendChild(make("span", "check-tag is-basis", item.basis));
          }
          if (item.origin === "项目自有文件") {
            meta.appendChild(make("span", "check-tag is-import", "项目自有文件"));
          }
          main.appendChild(meta);
          label.appendChild(main);
          bucket.appendChild(label);
        });
        host.appendChild(bucket);
      });

      renderImportList();
      updateCheckProgress(total);
    }

    function updateCheckProgress(total) {
      var boxes = document.querySelectorAll("#priorityChecks input[type=checkbox]");
      var count = 0;
      boxes.forEach(function (box) { if (box.checked) count += 1; });
      var sum = typeof total === "number" ? total : boxes.length;
      var percent = sum ? Math.round((count / sum) * 100) : 0;
      var fill = $("checkFill");
      if (fill) fill.style.width = percent + "%";
      var label = $("checkLabel");
      if (label) label.textContent = count + " / " + sum;
      var badge = $("priorityBadge");
      if (badge) badge.textContent = count + " / " + sum;
    }

    /* ---------- 导入 ---------- */
    function renderImportList() {
      var host = clear($("importList"));
      var badge = $("importBadge");
      if (badge) badge.textContent = importRows.length + " 条";
      if (!host || !importRows.length) return;
      importRows.forEach(function (row) {
        var line = make("div", "import-line");
        line.appendChild(make("span", "check-code", row.code || ""));
        line.appendChild(make("span", "check-text", row.content || ""));
        host.appendChild(line);
      });
    }

    function renderImportPreview(result) {
      var host = clear($("importPreview"));
      if (!host) return;
      host.hidden = false;
      var accepted = result.accepted || [];
      var rejected = result.rejected || [];
      var head = make("div", "import-preview-head",
        "读到 " + (result.parsed || 0) + " 行：可用 " + accepted.length
        + " 条" + (rejected.length ? "，有问题 " + rejected.length + " 条（已标红，不会导入）" : "")
        + (result.duplicates ? "，重复 " + result.duplicates + " 条已跳过" : ""));
      host.appendChild(head);

      var table = make("table", "import-table");
      var thead = make("thead");
      var headRow = make("tr");
      ["行", "类别", "检查内容", "判定要点", "依据"].forEach(function (text) {
        var th = make("th", "", text);
        th.scope = "col";
        headRow.appendChild(th);
      });
      thead.appendChild(headRow);
      table.appendChild(thead);

      var tbody = make("tbody");
      accepted.concat(rejected).slice(0, 10).forEach(function (row) {
        var tr = make("tr", row.error ? "is-error" : "");
        tr.appendChild(make("td", "cell-code", String(row.row || "")));
        tr.appendChild(make("td", "", row.category || ""));
        var cell = make("td");
        cell.appendChild(document.createTextNode(row.content || ""));
        if (row.error) {
          cell.appendChild(make("span", "import-row-error", " — " + row.error));
        }
        tr.appendChild(cell);
        tr.appendChild(make("td", "", row.judge || ""));
        tr.appendChild(make("td", "", row.basis || ""));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      host.appendChild(table);
      if (accepted.length + rejected.length > 10) {
        host.appendChild(make("p", "answer-meta",
          "（只预览前 10 行，确认合并会导入全部可用行）"));
      }

      var actions = make("div", "import-preview-actions");
      if (accepted.length) {
        var merge = make("button", "primary-button ico-button", "确认合并 " + accepted.length + " 条");
        merge.type = "button";
        merge.addEventListener("click", function () { commitImport(accepted); });
        actions.appendChild(merge);
      }
      var cancel = make("button", "ghost-button", "取消");
      cancel.type = "button";
      cancel.addEventListener("click", function () {
        pendingImport = null;
        host.hidden = true;
        clear(host);
      });
      actions.appendChild(cancel);
      host.appendChild(actions);
      pendingImport = accepted;
    }

    function commitImport(accepted) {
      var merged = importRows.slice();
      var seen = {};
      merged.forEach(function (row) { seen[row.content] = true; });
      var added = 0;
      accepted.forEach(function (row) {
        if (seen[row.content]) return;
        seen[row.content] = true;
        merged.push(row);
        added += 1;
      });
      importRows = merged;
      writeStore(IMPORT_KEY, { rows: importRows, previous: null });
      var preview = $("importPreview");
      if (preview) { preview.hidden = true; clear(preview); }
      var undo = $("importUndo");
      if (undo) { undo.hidden = added === 0; undo.setAttribute("data-added", String(added)); }
      pendingImport = null;
      renderChecklist();
      setVoiceHint(added ? ("已导入 " + added + " 条项目自有检查项。") : "这些条目已经在清单里了。");
    }

    function handleImportFile(file) {
      if (!file) return;
      var isXlsx = /\\.xlsx$/i.test(file.name);
      if (isXlsx) {
        var reader = new FileReader();
        reader.onload = function () {
          fetch("/api/checklists/import", {
            method: "POST",
            headers: { "Content-Type": "application/octet-stream" },
            body: reader.result,
          })
            .then(function (response) { return response.json(); })
            .then(function (data) {
              if (data.error) { setVoiceHint(data.error); return; }
              renderImportPreview(data);
            })
            .catch(function () { setVoiceHint("文件上传失败，请重试。"); });
        };
        reader.onerror = function () { setVoiceHint("文件读不出来，换一个试试。"); };
        reader.readAsArrayBuffer(file);
        return;
      }
      var textReader = new FileReader();
      textReader.onload = function () {
        var blob = new Blob([String(textReader.result)], { type: "text/csv" });
        var form = new FormData();
        form.append("file", blob, file.name);
        fetch("/api/checklists/import", { method: "POST", body: form })
          .then(function (response) { return response.json(); })
          .then(function (data) {
            if (data.error) { setVoiceHint(data.error); return; }
            renderImportPreview(data);
          })
          .catch(function () { setVoiceHint("文件解析失败，请重试。"); });
      };
      textReader.onerror = function () { setVoiceHint("文件读不出来，换一个试试。"); };
      textReader.readAsText(file, "utf-8");
    }

    function exportChecklistCsv() {
      var lines = ["分组,编号,检查内容,判定要点,依据,来源"];
      function esc(value) {
        var text = String(value == null ? "" : value);
        return /[",\\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
      }
      (shiftState.required || []).forEach(function (item) {
        lines.push([esc("当班必查"), esc(item.code), esc(item.content), esc(item.judge),
          esc(item.basis), esc(item.source)].join(","));
      });
      (shiftState.routine || []).forEach(function (item) {
        lines.push([esc("常规项"), esc(item.code), esc(item.content), esc(item.judge),
          esc(item.basis), esc(item.source)].join(","));
      });
      importRows.forEach(function (item) {
        lines.push([esc("我的导入"), esc(item.code), esc(item.content), esc(item.judge),
          esc(item.basis), esc("项目自有文件")].join(","));
      });
      var blob = new Blob(["\\ufeff" + lines.join("\\r\\n")], { type: "text/csv;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      var stamp = new Date();
      function pad(n) { return n < 10 ? "0" + n : String(n); }
      link.href = url;
      link.download = "班前检查清单-" + stamp.getFullYear() + pad(stamp.getMonth() + 1)
        + pad(stamp.getDate()) + ".csv";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      setVoiceHint("已导出 CSV（" + (lines.length - 1) + " 条）。");
    }

    function bindPrePanels() {
      var pick = $("importPick");
      var input = $("importFile");
      if (pick && input) {
        pick.addEventListener("click", function () { input.click(); });
        input.addEventListener("change", function () {
          if (input.files && input.files[0]) handleImportFile(input.files[0]);
          input.value = "";
        });
      }
      var undo = $("importUndo");
      if (undo) {
        undo.addEventListener("click", function () {
          writeStore(IMPORT_KEY, { rows: [], previous: null });
          importRows = [];
          undo.hidden = true;
          renderChecklist();
          setVoiceHint("已撤销导入的项目自有检查项。");
        });
      }
      var clearBtn = $("shiftClear");
      if (clearBtn) {
        clearBtn.addEventListener("click", function () {
          writeStore(SHIFT_KEY, { conditions: [] });
          document.querySelectorAll(".shift-chip").forEach(function (chip) {
            chip.setAttribute("aria-pressed", "false");
          });
          generateChecklist();
        });
      }
      var regen = $("preGenerate");
      if (regen) {
        regen.addEventListener("click", function () { generateChecklist(); });
      }
      var exportBtn = $("preExport");
      if (exportBtn) exportBtn.addEventListener("click", exportChecklistCsv);
      var printBtn = $("prePrint");
      if (printBtn) printBtn.addEventListener("click", function () { window.print(); });
      var reset = $("checkReset");
      if (reset) {
        reset.addEventListener("click", function () {
          writeStore(CHECK_KEY, {});
          document.querySelectorAll("#priorityChecks input[type=checkbox]").forEach(
            function (box) { box.checked = false; });
          document.querySelectorAll("#priorityChecks .check-item").forEach(
            function (item) { item.classList.remove("checked"); });
          updateCheckProgress();
        });
      }
    }

    function initPrePanels() {
      var stored = readStore(IMPORT_KEY, { rows: [] });
      importRows = stored.rows || [];
      bindPrePanels();
      getJson("/api/checklists/conditions")
        .then(function (data) { renderConditions(data); })
        .catch(function () { renderConditions(null); })
        .then(function () { return generateChecklist(true); });
    }

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied = 0
    body = BODY.read_text(encoding="utf-8")
    script = SCRIPT_B.read_text(encoding="utf-8")
    tiers = TIERS.read_text(encoding="utf-8")

    # ---- 1) 结构：替换 pre 的两个 panel ----
    start = body.find('<section id="pre"')
    if start < 0:
        print("[FAIL] 找不到 pre section")
        return 1
    open_end = body.find(">", start) + 1
    close = body.find("</section>", open_end)
    if close < 0:
        print("[FAIL] 找不到 pre 的 </section>")
        return 1

    if 'id="shiftPanel"' not in body:
        tail = body[open_end:close]
        # 保留「检查项目索引」panel（§5 对照表格在里面）
        index_panel = ""
        marker = '<div class="panel">'
        at = tail.find("检查项目索引")
        if at >= 0:
            panel_start = tail.rfind(marker, 0, at)
            if panel_start >= 0:
                index_panel = tail[panel_start:].rstrip()
        body = (body[:open_end] + "\n\n" + PANELS + "\n\n" + index_panel
                + "\n\n    " + body[close:])
        applied += 1
        print("[ok] pre 视图重建为 当班条件 + 当班清单 + 导入 + 检查项目索引")
    else:
        print("[跳过] 结构已存在")

    # ---- 2) 脚本 ----
    if "function initPrePanels" not in script:
        anchor = "    function renderEmergencyGrid() {"
        if anchor not in script:
            print("[FAIL] 找不到插入锚点")
            return 1
        script = script.replace(anchor, SCRIPT + anchor, 1)
        applied += 1
        print("[ok] 新增 §11 前端脚本")

    if "initPrePanels();" not in script:
        marker = "renderDailyCase();"
        if marker in script:
            script = script.replace(marker, marker + "\n\n      initPrePanels();", 1)
            applied += 1
            print("[ok] init 里调用 initPrePanels")
        else:
            print("[跳过] 找不到 init 调用点")

    # ---- 3) 样式 ----
    if "§11 班前条件与导入" not in tiers:
        tiers = tiers.rstrip() + CSS
        applied += 1
        print("[ok] 样式已加入")

    for name, text in (("body", body), ("script", script)):
        if text.count(chr(92)) and name == "script":
            # 脚本里的 \\n 与 \\. 是故意写的转义，检查时排除
            pass
    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1
    print("[ok] body 无反斜杠")

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
