from __future__ import annotations



import argparse

import base64

import json

import os

import time

from collections import defaultdict, deque

from email import policy

from email.parser import BytesParser

import mimetypes

import re
import threading

import urllib.error

import urllib.request

import webbrowser

from dataclasses import asdict, dataclass

from http import HTTPStatus

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from typing import Any

from urllib.parse import urlparse



from sitesaha.checklists import INSPECTION_CATEGORIES, PRIORITY_START_CHECKS

from sitesaha.config import AppConfig

from sitesaha.db import KnowledgeBase

from sitesaha.ingest import seed_default_knowledge

from sitesaha.models import Answer

from sitesaha.rag import RAGEngine
from sitesaha.llm import ProviderError, with_retry
from sitesaha.structure import parse_inspection, strip_markdown
from sitesaha import checklists as checklists_mod
from sitesaha.xlsx import XlsxError, to_text as xlsx_to_text

from sitesaha.standards import load_standards

from sitesaha.cases import CASES, find_cases

from sitesaha.training import (

    QUESTIONS as TRAINING_QUESTIONS,

    QUIZ_META,

    TRAINING_PATH,

    TRAINING_STEPS,

    WORKER_ROLES,

)





APP_VERSION = "16.0.0"



# 单次问答注入的培训上下文上限，避免占用过多模型上下文。

TRAINING_CONTEXT_LIMIT = 400





def build_training_context(worker_role: str) -> str:

    """把工人所选工种与培训阶段整理成一段简短上下文，用于增强问答。



    只取最关键的几条，控制长度；未选工种或工种未知时返回空串，

    此时问答行为与接入前完全一致。

    """

    role = (worker_role or "").strip()

    if not role:

        return ""

    profile = WORKER_ROLES.get(role)

    if not isinstance(profile, dict):

        return ""



    parts = [f"工种为{role}。"]

    summary = str(profile.get("summary", "")).strip()

    if summary:

        parts.append(summary)

    hazards = [str(item) for item in profile.get("hazards", []) if str(item).strip()]

    if hazards:

        parts.append("本工种主要风险：" + "、".join(hazards) + "。")

    rules = [str(item) for item in profile.get("rules", []) if str(item).strip()]

    if rules:

        parts.append("本工种必守规矩：" + "；".join(rules[:3]) + "。")

    context = "".join(parts)

    if len(context) > TRAINING_CONTEXT_LIMIT:

        context = context[:TRAINING_CONTEXT_LIMIT].rstrip() + "…"

    return context





def training_payload() -> dict[str, Any]:

    """培训模块数据：培训路线、工种专项、测验题库。"""

    return {

        "training_path": TRAINING_PATH,

        "training_steps": TRAINING_STEPS,

        "worker_roles": WORKER_ROLES,

        "roles": list(WORKER_ROLES.keys()),

        "questions": TRAINING_QUESTIONS,

        "quiz": QUIZ_META,

    }







INDEX_HTML = """<!doctype html>

<html lang="zh-CN">

<head>

  <meta charset="utf-8">

  <meta name="viewport" content="width=device-width, initial-scale=1">

  <meta name="robots" content="noindex, nofollow">

  <meta name="theme-color" content="#0c2b4a">

  <meta name="sitesaha-version" content="16.0.0">

  <title>筑安智培 | 新工人安全助手</title>

  <style>

/* ==========================================================================

   筑安智培 V10 设计系统

   视觉来源：申报书《筑安智培项目框架图》——深蓝 + 琥珀黄 + 安全警戒指纹

   风险三色：红橙(高) / 琥珀(注意) / 绿(安全)

   约束：纯 CSS，零外部依赖（CSP default-src 'self'，且需离线可用）

   ========================================================================== */

:root {

  color-scheme: light;

  /* 阅读度量：40em ≈ 600px ≈ 40 个汉字，落在 32-42 字的目标区间内 */

  --measure:40em;

  --measure-narrow:34em;

  --line-prose:1.78;

  --line-ui:1.62;

  --font:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC","Source Han Sans SC",sans-serif;

  --mono:"Cascadia Mono",Consolas,"SFMono-Regular","Courier New",monospace;

}

* { box-sizing:border-box; }

html, body { margin:0; min-height:100%; }

body {

  background:var(--paper); color:var(--body); font-family:var(--font);

  line-height:var(--line-ui); font-size:13px; overflow-x:hidden;

  letter-spacing:0.05em; font-kerning:normal; text-rendering:optimizeLegibility;

  -webkit-text-size-adjust:100%;

}

body::before {

  content:""; position:fixed; inset:0 -10% auto; height:360px; z-index:0; pointer-events:none;

  background:linear-gradient(180deg,rgba(12,43,74,.05),rgba(12,43,74,0));

}

button, input, textarea, select { font:inherit; color:inherit; }

button { cursor:pointer; }

a { color:var(--navy-600); }

/* 中文标题不需要额外字距；正文统一 0.05em 以改善中英混排 */

h1,h2,h3,h4 { color:var(--ink); margin:0; letter-spacing:0; }

.num, pre, .ring-num, code, .record-timer { letter-spacing:0; }

p { margin:0; }

ul,ol { margin:0; padding:0; list-style:none; }

:focus-visible { outline:3px solid var(--safety); outline-offset:2px; border-radius:4px; }

.sr-only {

  position:absolute; width:1px; height:1px; padding:0; margin:-0px;

  overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; border:0;

}

.num { font-variant-numeric:tabular-nums; font-feature-settings:"tnum"; }



/* ---------- 顶栏 ---------- */

.top-band {

  height:7px;

  background:repeating-linear-gradient(135deg,var(--amber) 0 11px,var(--navy-800) 11px 22px);

}

header { position:relative; z-index:2; background:var(--navy-800); color:#fff; }

.header-inner {

  max-width:1400px; margin:0 auto; padding:12px 20px;

  display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;

}

.brand { display:flex; align-items:center; gap:12px; min-width:0; }

.brand-mark {

  width:46px; height:46px; flex:0 0 46px; border-radius:11px;

  background:linear-gradient(150deg,var(--amber) 0%,var(--amber-dark) 100%);

  color:var(--navy-900); display:grid; place-items:center;

  font-size:21px; font-weight:800; box-shadow:0 3px 10px rgba(0,0,0,.25);

}

.brand-text h1 { color:#fff; font-size:21px; line-height:1.4; }

.brand-text p { color:#a9c1d8; font-size:12px; margin-top:2px; }

.header-right { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

.status-pill {

  display:inline-flex; align-items:center; gap:8px;

  padding:4px 12px; border-radius:999px; font-size:12px; font-weight:700;

  background:#123f2a; color:#7ee0a8; border:1px solid #1f5c3c; white-space:nowrap;

}

.status-pill::before {

  content:""; width:7px; height:7px; border-radius:50%; background:currentColor;

  box-shadow:0 0 0 3px rgba(126,224,168,.18);

}

.status-pill.offline { background:#4a2a12; color:#f5b872; border-color:#6d4420; }

.status-pill.offline::before { box-shadow:0 0 0 3px rgba(245,184,114,.18); }

.version-tag {

  font-family:var(--mono); font-size:12px; color:#95b0c9;

  border:1px solid rgba(255,255,255,.22); border-radius:6px; padding:4px 8px;

}



/* ---------- 大屏指标条 ---------- */

.stat-bar { position:relative; z-index:2; background:var(--navy-900); border-top:1px solid rgba(255,255,255,.07); }

.stat-inner {

  max-width:1400px; margin:0 auto; padding:0 20px;

  display:grid; grid-template-columns:repeat(4,minmax(0,1fr));

}

.stat-cell { padding:12px 16px; border-left:1px solid rgba(255,255,255,.09); }

.stat-cell:first-child { border-left:0; padding-left:0; }

.stat-cell b {

  display:block; font-family:var(--mono); font-size:27px; line-height:1.4;

  color:var(--amber); font-weight:700; letter-spacing:-.01em;

}

.stat-cell span { display:block; font-size:12px; color:#8fa8c0; margin-top:2px; }

.stat-cell small { display:block; font-size:12px; color:#6d8399; margin-top:0px; }

.stat-cell.is-risk b { color:#ff7a6a; }



/* ---------- 主导航 ---------- */

nav { position:sticky; top:0; z-index:20; background:var(--panel); border-bottom:1px solid var(--line-strong); box-shadow:var(--shadow-sm); }

.nav-inner { max-width:1400px; margin:0 auto; padding:0 20px; display:flex; gap:2px; overflow-x:auto; scrollbar-width:thin; }

.nav-button {

  border:0; border-bottom:3px solid transparent; background:transparent; color:var(--muted);

  padding:12px 16px 8px; font-weight:700; font-size:13px; white-space:nowrap;

  transition:color .15s ease,border-color .15s ease,background .15s ease;

}

.nav-button:hover { color:var(--navy-700); background:var(--navy-050); }

.nav-button.active { color:var(--navy-800); border-bottom-color:var(--amber); }

.nav-button .nav-ico { margin-right:4px; }

.nav-button.emergency-tab { color:var(--risk-high); margin-left:auto; }

.nav-button.emergency-tab.active { border-bottom-color:var(--risk-high); }



/* ---------- 主体布局 ---------- */

main {

  position:relative; z-index:1; max-width:1400px; margin:0 auto; padding:20px;

  display:grid; grid-template-columns:minmax(0,1fr) 330px; gap:20px; align-items:start;

}

.view { display:none; min-width:0; }

.view.active { display:block; animation:viewIn .28s ease both; }

@keyframes viewIn { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:none; } }



/* ---------- 卡片 ---------- */

.panel {

  position:relative; background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);

  box-shadow:var(--shadow); overflow:hidden;

}

.panel + .panel { margin-top:16px; }

.panel-body { padding:20px; }

.panel-head {

  padding:16px 20px; border-bottom:1px solid var(--line);

  display:flex; align-items:center; gap:12px; flex-wrap:wrap;

  background:linear-gradient(180deg,#ffffff,#f3f7fb);

}

.panel-head h2 { font-size:15px; }

.panel-head .head-spacer { margin-left:auto; }

.panel-head .head-note { font-size:12px; color:var(--muted); }

.panel-kicker {

  display:inline-block; font-family:var(--mono); font-size:12px; font-weight:700;

  letter-spacing:.1em; text-transform:uppercase; color:#8a6410;

  background:var(--amber-soft); border-radius:4px; padding:2px 8px;

}

.panel-body > .panel-kicker { margin-bottom:8px; }

.panel-body > h2 { font-size:21px; }

.lead { color:var(--muted); font-size:13px; margin-top:4px; line-height:var(--line-prose); }

.lead + .lead { margin-top:4px; }

.notice {

  border-left:4px solid var(--amber); background:var(--amber-soft); color:#6d5217;

  border-radius:0 var(--radius-sm) var(--radius-sm) 0; padding:12px 12px;

  font-size:12px; line-height:var(--line-prose); margin-bottom:16px;

}

/* 正文段落统一阅读度量：桌面端避免出现 70-84 字长行 */

.explain, .quiz-result p, .em-never, .source-card p, .em-step, .hero-desc {

  max-width:var(--measure);

  line-height:var(--line-prose);

}

.sec-title { font-size:15px; }

.sec-sub { font-size:12px; color:var(--muted); margin-top:2px; }



/* ---------- 首页 hero ---------- */

.hero {

  position:relative; overflow:hidden; border:1px solid var(--line); border-radius:14px;

  background:

    radial-gradient(900px 260px at 88% -35%, rgba(242,163,60,.20), transparent 70%),

    linear-gradient(140deg,var(--navy-800) 0%,var(--navy-700) 55%,#16456f 100%);

  box-shadow:var(--shadow-lg); padding:24px; margin-bottom:16px; color:#dbe3ec;

}

.hero::after {

  content:""; position:absolute; right:-70px; bottom:-80px; width:270px; height:270px;

  border:44px solid rgba(255,255,255,.05); border-radius:50%; pointer-events:none;

}

.hero-kicker {

  display:inline-flex; align-items:center; gap:8px; font-size:12px; font-weight:700;

  color:var(--amber); background:rgba(242,163,60,.14); border:1px solid rgba(242,163,60,.35);

  border-radius:999px; padding:4px 12px; margin-bottom:12px;

}

.hero h2 { color:#fff; font-size:27px; line-height:1.4; max-width:19em; }

.hero h2 em { font-style:normal; color:var(--amber); }

.hero-desc { margin-top:8px; font-size:13px; color:#a8c0d6; max-width:44em; }

.hero-sub { margin-top:12px; display:flex; gap:8px; flex-wrap:wrap; }

.hero-chip {

  font-size:12px; color:#c6d8e8; border:1px solid rgba(255,255,255,.2);

  border-radius:999px; padding:4px 8px; background:rgba(255,255,255,.05);

}



/* ---------- 首页主行动卡 ---------- */

.home-actions { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:16px 0; }

.action-card {

  display:flex; flex-direction:column; gap:8px; text-align:left; font-family:inherit;

  border:1px solid var(--line); border-radius:12px; background:var(--panel); padding:16px 16px;

  box-shadow:var(--shadow); transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease;

}

.action-card:hover { transform:translateY(-3px); box-shadow:var(--shadow-lg); border-color:var(--line-strong); }

.action-ico {

  width:44px; height:44px; border-radius:11px; display:grid; place-items:center; font-size:21px;

  background:var(--navy-050); border:1px solid var(--line);

}

.action-card strong { font-size:15px; color:var(--ink); display:block; }

.action-card p { font-size:12px; color:var(--muted); line-height:1.4; }

.action-go { font-size:12px; font-weight:700; color:var(--navy-600); margin-top:auto; }

.action-card.is-primary { background:linear-gradient(160deg,#123a61,#0c2b4a); border-color:#1a4b78; }

.action-card.is-primary strong, .action-card.is-primary .action-go { color:#fff; }

.action-card.is-primary p { color:#a8c0d6; }

.action-card.is-primary .action-ico { background:rgba(242,163,60,.16); border-color:rgba(242,163,60,.35); }

.action-card.is-danger { border-color:#f0bdb7; background:linear-gradient(160deg,#fef2f2,#fff); }

.action-card.is-danger strong { color:#a8291c; }

.action-card.is-danger .action-ico { background:var(--risk-high-soft); border-color:#f0bdb7; }

.action-card.is-danger .action-go { color:var(--risk-high); }



/* ---------- 首页两列 ---------- */

.home-grid { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:16px; align-items:start; }

.home-col { display:grid; gap:16px; min-width:0; }



/* ---------- 今日三件事 ---------- */

.todo-list { display:grid; gap:8px; }

.todo-item {

  display:flex; gap:12px; align-items:flex-start; border:1px solid var(--line);

  border-radius:var(--radius-sm); padding:12px 12px; background:var(--panel-soft); cursor:pointer;

  transition:border-color .15s ease,background .15s ease;

}

.todo-item:hover { border-color:var(--line-strong); background:var(--panel-soft); }

.todo-item input { margin-top:4px; width:17px; height:17px; accent-color:var(--navy-600); flex:0 0 17px; }

.todo-item b { display:block; font-size:13px; color:var(--ink); }

.todo-item span { display:block; font-size:12px; color:var(--muted); }

.todo-item.done { background:var(--risk-low-soft); border-color:#bfe3ce; }

.todo-item.done b { color:var(--risk-low); }

.progress-row { display:flex; align-items:center; gap:12px; margin-top:12px; }

.progress-track { flex:1; height:9px; border-radius:999px; background:var(--navy-100); overflow:hidden; }

.progress-fill {

  height:100%; width:0%; border-radius:999px;

  background:linear-gradient(90deg,var(--amber),var(--amber-dark));

  transition:width .55s cubic-bezier(.4,0,.2,1);

}

.progress-label { font-family:var(--mono); font-size:13px; font-weight:700; color:var(--navy-700); white-space:nowrap; }



/* ---------- 培训路线 / 步骤 ---------- */

.step-list { display:grid; gap:8px; }

.step-item {

  display:grid; grid-template-columns:38px minmax(0,1fr) auto; gap:12px; align-items:start;

  border:1px solid var(--line); border-radius:var(--radius-sm); padding:12px 16px; background:var(--panel-soft);

  transition:border-color .15s ease,box-shadow .15s ease;

}

.step-item:hover { border-color:var(--line-strong); box-shadow:var(--shadow-sm); }

.step-item.is-done { background:var(--risk-low-soft); border-color:#bfe3ce; }

.step-order {

  width:38px; height:38px; border-radius:50%; display:grid; place-items:center;

  background:var(--navy-800); color:var(--amber); font-family:var(--mono); font-weight:700; font-size:13px;

}

.step-item.is-done .step-order { background:var(--risk-low); color:#fff; }

.step-item h3 { font-size:15px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

.step-item .step-meta { font-size:12px; color:var(--muted); font-family:var(--mono); }

.step-points { margin-top:8px; display:grid; gap:4px; }

.step-points li { position:relative; padding-left:16px; font-size:13px; color:var(--body); }

.step-points li::before {

  content:""; position:absolute; left:2px; top:9px; width:5px; height:5px;

  border-radius:50%; background:var(--amber-dark);

}

.step-check { font-size:12px; color:var(--navy-700); background:var(--navy-050); border-radius:6px; padding:8px 8px; margin-top:8px; }

.step-side { display:grid; gap:8px; justify-items:end; }



/* ---------- 工种选择 ---------- */

.role-chips { display:flex; flex-wrap:wrap; gap:8px; }

.role-chip {

  border:1px solid var(--line-strong); background:var(--panel); color:var(--body);

  border-radius:999px; padding:8px 12px; font-size:13px; font-weight:700;

  transition:all .15s ease;

}

.role-chip:hover { border-color:var(--navy-600); color:var(--navy-700); }

.role-chip.active { background:var(--navy-800); border-color:var(--navy-800); color:#fff; }

.role-chip.active::after { content:" ✓"; color:var(--amber); }

.role-detail { margin-top:12px; border-top:1px dashed var(--line-strong); padding-top:12px; }

.role-detail h3 { font-size:15px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

.role-summary { margin-top:8px; font-size:13px; color:var(--body); }

.role-cols { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:12px; }

.role-block { border:1px solid var(--line); border-radius:var(--radius-sm); padding:12px 12px; background:var(--panel-soft); }

.role-block h4 { font-size:15px; display:flex; align-items:center; gap:4px; margin-bottom:8px; }

.role-block ul { display:grid; gap:4px; }

.role-block li { position:relative; padding-left:16px; font-size:12px; color:var(--body); }

.role-block li::before { content:""; position:absolute; left:2px; top:8px; width:5px; height:5px; border-radius:50%; background:var(--navy-600); }

.role-block.is-danger li::before { background:var(--risk-high); }

.role-block.is-safe li::before { background:var(--risk-low); }



/* ---------- 训练模块卡 ---------- */

.training-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }

.training-card {

  display:flex; flex-direction:column; gap:8px; text-align:left; font-family:inherit;

  border:1px solid var(--line); border-left:4px solid var(--amber); border-radius:var(--radius-sm);

  background:var(--panel); padding:16px 16px; box-shadow:var(--shadow-sm);

  transition:transform .15s ease,box-shadow .15s ease;

}

.training-card:hover { transform:translateY(-2px); box-shadow:var(--shadow); }

.training-card strong { font-size:13px; color:var(--ink); }

.training-card p { font-size:12px; color:var(--muted); }

.training-card small { font-size:12px; color:var(--amber-dark); font-weight:700; font-family:var(--mono); }



/* ---------- 测验 ---------- */

.quiz-status {

  display:grid; grid-template-columns:auto minmax(0,1fr); gap:16px; align-items:center;

  border:1px solid var(--line); border-radius:var(--radius); padding:16px; background:var(--navy-050);

}

.ring-wrap { display:grid; place-items:center; gap:8px; }

.ring { transform:rotate(-90deg); }

.ring circle { fill:none; stroke-linecap:round; }

.ring .ring-bg { stroke:var(--navy-100); }

.ring .ring-fg {

  stroke:var(--amber-dark); stroke-dasharray:345.58;

  stroke-dashoffset:var(--ring-offset,345.58);

  transition:stroke-dashoffset .7s cubic-bezier(.4,0,.2,1),stroke .3s ease;

}

.ring-num { font-family:var(--mono); font-size:27px; font-weight:700; color:var(--navy-800); line-height:1.4; }

.ring-cap { font-size:12px; color:var(--muted); }

.quiz-actions { display:flex; gap:8px; flex-wrap:wrap; }

.quiz-meta-row { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:12px; }

.quiz-stat { border:1px solid var(--line); border-radius:var(--radius-sm); padding:12px 12px; background:var(--panel); }

.quiz-stat b { display:block; font-family:var(--mono); font-size:21px; color:var(--navy-800); }

.quiz-stat span { font-size:12px; color:var(--muted); }

.domain-bars { margin-top:12px; display:grid; gap:8px; }

.domain-bar { display:grid; grid-template-columns:132px minmax(0,1fr) 62px; gap:12px; align-items:center; font-size:12px; }

.domain-bar .dname { color:var(--body); font-weight:700; }

.domain-bar .dtrack { height:8px; border-radius:999px; background:var(--navy-100); overflow:hidden; }

.domain-bar .dfill { height:100%; width:0%; border-radius:999px; background:var(--risk-low); transition:width .55s ease; }

.domain-bar.warn .dfill { background:var(--risk-mid); }

.domain-bar.bad .dfill { background:var(--risk-high); }

.domain-bar .dval { font-family:var(--mono); color:var(--muted); text-align:right; }

.quiz-progress { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; flex-wrap:wrap; }

.quiz-progress .qcount { font-family:var(--mono); font-size:13px; color:var(--navy-700); font-weight:700; }

.q-role-tag {

  display:inline-block; font-size:12px; font-weight:700; color:var(--navy-700);

  background:var(--navy-100); border-radius:4px; padding:2px 8px;

}

.q-head { font-size:15px; line-height:1.4; margin:8px 0 12px; max-width:var(--measure); }

.options { display:grid; gap:8px; }

.option {

  display:flex; gap:12px; align-items:flex-start; text-align:left; font-family:inherit;

  border:1px solid var(--line-strong); border-radius:var(--radius-sm); background:var(--panel);

  padding:12px 12px; font-size:13px; transition:all .14s ease;

}

.option:hover:not(:disabled) { border-color:var(--navy-600); background:var(--navy-050); }

.option .opt-key {

  flex:0 0 25px; width:25px; height:25px; border-radius:6px; display:grid; place-items:center;

  background:var(--navy-100); color:var(--navy-700); font-weight:800; font-size:12px; font-family:var(--mono);

}

.option:disabled { cursor:default; }

.option.is-correct { border-color:var(--risk-low); background:var(--risk-low-soft); }

.option.is-correct .opt-key { background:var(--risk-low); color:#fff; }

.option.is-wrong { border-color:var(--risk-high); background:var(--risk-high-soft); }

.option.is-wrong .opt-key { background:var(--risk-high); color:#fff; }

.option.is-dim { opacity:.62; }

.explain {

  margin-top:12px; border-left:4px solid var(--amber); background:var(--amber-soft);

  border-radius:0 var(--radius-sm) var(--radius-sm) 0; padding:12px 12px; font-size:13px;

}

.explain b { color:var(--ink); }

.quiz-result { border:1px solid var(--line); border-radius:var(--radius); padding:16px; background:var(--panel); }

.quiz-result h3 { font-size:15px; }

.score-big { font-family:var(--mono); font-size:27px; font-weight:700; color:var(--navy-800); line-height:1.4; }

.score-big.pass { color:var(--risk-low); }

.score-big.fail { color:var(--risk-mid); }

.wrong-list { margin-top:12px; display:grid; gap:8px; }

.wrong-item { border:1px solid #f0cdc8; border-left:4px solid var(--risk-high); border-radius:var(--radius-sm); padding:12px 12px; background:#f7f8fa; }

.wrong-item b { display:block; font-size:13px; color:var(--ink); }

.wrong-item p { font-size:12px; color:var(--body); margin-top:4px; }



/* ---------- 问答（会话式） ---------- */

.chat-toolbar {

  display:flex; align-items:center; gap:12px; flex-wrap:wrap;

  padding:12px 16px; border-bottom:1px solid var(--line); background:linear-gradient(180deg,#ffffff,#f3f7fb);

}

.chat-toolbar .tb-label { font-size:12px; color:var(--muted); font-weight:700; }

.chat-stream { padding:16px; display:grid; gap:16px; min-height:150px; background:var(--panel-soft); }

.msg-row { display:flex; gap:12px; align-items:flex-start; }

.msg-row.from-user { flex-direction:row-reverse; }

.avatar {

  flex:0 0 35px; width:35px; height:35px; border-radius:9px; display:grid; place-items:center;

  font-size:13px; font-weight:800; background:var(--navy-800); color:var(--amber);

}

.msg-row.from-user .avatar { background:var(--amber); color:var(--navy-900); }

.bubble {

  max-width:min(100%,720px); border-radius:12px; padding:12px 16px; font-size:13px;

  background:var(--panel); border:1px solid var(--line); box-shadow:var(--shadow-sm); min-width:0;

}

.msg-row.from-user .bubble { background:var(--navy-800); border-color:var(--navy-800); color:#fff; }

.bubble-title { font-size:13px; font-weight:700; color:var(--ink); }

.msg-row.from-user .bubble-title { color:#fff; }

.bubble-meta { font-size:12px; color:var(--muted); margin-top:2px; }

.msg-row.from-user .bubble-meta { color:#a8c0d6; }

.answer-body { margin-top:8px; white-space:pre-wrap; line-height:var(--line-prose); color:var(--body); max-width:var(--measure); }

.answer-note {

  margin-top:12px; border-left:4px solid var(--amber); background:var(--amber-soft);

  border-radius:0 6px 6px 0; padding:8px 12px; font-size:12px; color:#6d5217;

}

.warn-box { border-radius:var(--radius-sm); background:var(--risk-high-soft); color:#8a2f20; padding:8px 12px; font-size:12px; margin-top:8px; }

.thinking { display:inline-flex; gap:4px; align-items:center; }

.thinking i {

  width:7px; height:7px; border-radius:50%; background:var(--amber-dark);

  animation:bounce 1.15s infinite ease-in-out;

}

.thinking i:nth-child(2) { animation-delay:.15s; }

.thinking i:nth-child(3) { animation-delay:.3s; }

@keyframes bounce { 0%,80%,100% { transform:translateY(0); opacity:.42; } 40% { transform:translateY(-6px); opacity:1; } }

.src-block { margin-top:12px; border-top:1px dashed var(--line-strong); padding-top:12px; }

.src-title { font-size:12px; font-weight:700; color:var(--ink); margin-bottom:8px; }

.source-list { display:grid; gap:8px; }

.source-card { border:1px solid var(--line); border-left:3px solid var(--navy-600); border-radius:6px; padding:12px 12px; background:var(--panel-soft); }

.source-card h4 { font-size:13px; }

.source-card p { font-size:12px; color:var(--body); margin-top:4px; white-space:pre-wrap; }

.source-meta { font-size:12px; color:var(--muted); margin-top:4px; }

.related-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }

.chat-composer { border-top:1px solid var(--line); padding:16px 16px; background:var(--panel); }

.composer-grid { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; align-items:stretch; }

textarea {

  width:100%; min-height:92px; resize:vertical; border:1px solid var(--line-strong);

  border-radius:var(--radius-sm); padding:12px 12px; background:var(--panel-soft); outline:none;

  transition:border-color .15s ease,box-shadow .15s ease;

}

textarea:focus { border-color:var(--navy-600); box-shadow:0 0 0 3px rgba(26,75,120,.12); background:var(--panel); }

input[type="text"], input[type="search"] {

  width:100%; padding:12px 12px; border:1px solid var(--line-strong); border-radius:var(--radius-sm);

  background:var(--panel-soft); outline:none;

}

input[type="text"]:focus, input[type="search"]:focus { border-color:var(--navy-600); box-shadow:0 0 0 3px rgba(26,75,120,.12); background:var(--panel); }

.composer-tools { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:12px; }

.quick-list { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }

.quick-button {

  border:1px solid var(--line-strong); border-radius:999px; background:var(--panel); color:var(--body);

  padding:8px 12px; font-size:12px; text-align:left; transition:all .15s ease;

}

.quick-button:hover { border-color:var(--navy-600); color:var(--navy-700); background:var(--navy-050); }



/* ---------- 按钮 ---------- */

.primary-button {

  align-self:stretch; min-width:118px; border:0; border-radius:var(--radius-sm);

  background:var(--navy-800); color:#fff; padding:0 20px; font-weight:800; font-size:13px;

  transition:background .15s ease,transform .15s ease;

}

.primary-button:hover:not(:disabled) { background:var(--navy-700); }

.primary-button:disabled { opacity:.6; cursor:wait; }

.amber-button {

  border:0; border-radius:var(--radius-sm); background:var(--amber); color:var(--navy-900);

  padding:8px 16px; font-weight:800; font-size:13px; transition:background .15s ease;

}

.amber-button:hover:not(:disabled) { background:var(--amber-dark); color:#3d2a06; }

.amber-button:disabled { opacity:.6; cursor:wait; }

.secondary-button {

  border:1px solid var(--line-strong); border-radius:var(--radius-sm); background:var(--panel); color:var(--body);

  padding:8px 16px; font-weight:700; font-size:13px; transition:all .15s ease;

}

.secondary-button:hover:not(:disabled) { border-color:var(--navy-600); color:var(--navy-700); }

.secondary-button:disabled { opacity:.55; cursor:not-allowed; }

.ghost-button {

  border:1px solid transparent; background:transparent; color:var(--navy-600);

  padding:8px 12px; font-weight:700; font-size:12px; border-radius:6px;

}

.ghost-button:hover { background:var(--navy-050); }

.danger-button {

  border:0; border-radius:var(--radius-sm); background:var(--risk-high); color:#fff;

  padding:12px 12px; font-weight:800; font-size:13px; text-align:center; text-decoration:none;

  display:inline-block; transition:background .15s ease;

}

.danger-button:hover { background:#b9301f; }

.voice-button {

  border:1px solid #bfd4e8; border-radius:var(--radius-sm); background:var(--navy-050);

  color:var(--navy-700); padding:8px 16px; font-weight:800; font-size:13px;

}

.voice-button:hover:not(:disabled) { background:var(--navy-100); }

.voice-button:disabled { opacity:.55; cursor:not-allowed; }

.voice-row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }

.answer-meta { font-size:12px; color:var(--muted); }



/* ---------- 拍照 ---------- */

.upload-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; align-items:center; margin-top:12px; }

.file-input {

  border:1px dashed var(--line-strong); border-radius:var(--radius-sm); padding:12px 12px;

  background:var(--panel-soft); font-size:13px; width:100%;

}

.file-input::file-selector-button {

  border:0; border-radius:6px; background:var(--navy-100); color:var(--navy-700);

  padding:8px 12px; font-weight:700; margin-right:12px; cursor:pointer; font-family:inherit;

}

.capture-tools { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }

.camera-stage {

  display:grid; gap:12px; margin-top:12px; border:1px solid var(--line);

  border-radius:var(--radius); background:#0b1220; padding:12px;

}

.camera-stage video { width:100%; max-height:380px; border-radius:var(--radius-sm); background:#000; display:block; object-fit:contain; }

.camera-hint { font-size:12px; color:#a9c1d8; }

.photo-stage {

  display:grid; gap:12px; margin-top:12px; border:1px solid var(--line);

  border-radius:var(--radius); background:var(--panel-soft); padding:12px;

}

.photo-stage img { width:100%; max-height:380px; border-radius:var(--radius-sm); background:#000; display:block; object-fit:contain; }

.photo-facts { display:flex; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--muted); }

.photo-facts span { background:var(--panel); border:1px solid var(--line); border-radius:999px; padding:2px 8px; }

.progress-inline { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); }

.progress-inline .bar { flex:1; height:7px; border-radius:999px; background:var(--navy-100); overflow:hidden; }

.progress-inline .bar i { display:block; height:100%; width:0%; background:var(--amber); transition:width .2s linear; }

.error-card {

  border:1px solid #f0bdb7; border-left:4px solid var(--risk-high); background:#f7f8fa;

  border-radius:0 var(--radius-sm) var(--radius-sm) 0; padding:12px 12px; font-size:13px; color:#8a2f20;

}

.error-card b { display:block; margin-bottom:4px; color:#a8291c; }

.error-card ul { margin-top:4px; display:grid; gap:4px; }

.error-card li { padding-left:12px; position:relative; }

.error-card li::before { content:""; position:absolute; left:2px; top:8px; width:5px; height:5px; border-radius:50%; background:var(--risk-high); }

.recording-row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:8px; }

.rec-dot {

  width:10px; height:10px; border-radius:50%; background:var(--risk-high); flex:0 0 10px;

  animation:pulse 1.15s infinite ease-in-out;

}

@keyframes pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:.35; transform:scale(.82); } }

.record-timer { font-family:var(--mono); font-size:13px; color:var(--risk-high); font-weight:700; }

.voice-select {

  border:1px solid var(--line-strong); border-radius:6px; background:var(--panel); color:var(--body);

  padding:8px 12px; font-size:12px; font-family:inherit; max-width:100%;

}

.result-box {

  margin-top:12px; border:1px solid var(--line); border-left:4px solid var(--navy-600);

  border-radius:0 var(--radius-sm) var(--radius-sm) 0; background:var(--panel-soft); padding:12px 16px;

  white-space:pre-wrap; font-size:13px; line-height:1.6;

}

.photo-tips { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:12px; }

.photo-tip { border:1px solid var(--line); border-radius:var(--radius-sm); padding:12px 12px; background:var(--panel); font-size:12px; }

.photo-tip b { display:block; color:var(--ink); font-size:13px; margin-bottom:2px; }



/* ---------- 案例 ---------- */

.filter-row { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }

.filter-chip {

  border:1px solid var(--line-strong); border-radius:999px; background:var(--panel); color:var(--body);

  padding:4px 12px; font-size:12px; font-weight:700;

}

.filter-chip:hover { border-color:var(--navy-600); color:var(--navy-700); }

.filter-chip.active { background:var(--navy-800); border-color:var(--navy-800); color:#fff; }

.case-search { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; margin-bottom:12px; }

.case-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }

.case-card {

  border:1px solid var(--line); border-top:4px solid var(--risk-high); border-radius:var(--radius-sm);

  background:var(--panel); padding:16px; box-shadow:var(--shadow-sm); display:flex; flex-direction:column; gap:8px;

}

.case-card.is-hidden { display:none; }

.case-tag {

  display:inline-block; font-size:12px; font-weight:800; padding:2px 8px; border-radius:999px;

  background:var(--risk-high-soft); color:#a8291c; align-self:flex-start;

}

.case-card h3 { font-size:15px; line-height:1.4; }

.case-card p { font-size:13px; color:var(--body); }

.case-card .case-label { font-weight:700; color:var(--ink); font-size:12px; }

.case-detail { border-top:1px dashed var(--line-strong); margin-top:4px; padding-top:8px; display:grid; gap:8px; }

.case-lesson {

  background:var(--risk-low-soft); border-left:3px solid var(--risk-low); border-radius:0 6px 6px 0;

  padding:8px 12px; font-size:12px; color:#155f3a;

}

.case-source { font-size:12px; color:var(--muted); }



/* ---------- 检查清单 ---------- */

.list-progress { display:flex; align-items:center; gap:12px; margin-top:12px; }

.check-group { border-top:1px solid var(--line); padding:16px 0; }

.check-group:first-child { border-top:0; padding-top:0; }

.check-group h3 { font-size:15px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

.check-group .scope { font-size:12px; color:var(--muted); margin:4px 0 8px; }

.check-item {

  display:flex; gap:8px; align-items:flex-start; padding:8px 12px; border-radius:6px;

  font-size:13px; cursor:pointer; transition:background .14s ease;

}

.check-item:hover { background:var(--navy-050); }

.check-item input { margin-top:4px; width:17px; height:17px; accent-color:var(--navy-600); flex:0 0 17px; }

.check-item.checked { background:var(--risk-low-soft); color:#155f3a; }

.check-item.checked span { text-decoration:line-through; text-decoration-color:rgba(21,95,58,.45); }

.count-badge {

  font-family:var(--mono); font-size:12px; font-weight:700; color:var(--navy-700);

  background:var(--navy-100); border-radius:999px; padding:2px 8px;

}



/* ---------- 知识库 ---------- */

.doc-group { border-top:1px solid var(--line); padding:12px 0; }

.doc-group:first-child { border-top:0; padding-top:0; }

.doc-group h3 { font-size:15px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

.document-list { display:grid; gap:0; margin-top:8px; }

.document-list li { border-top:1px solid var(--line); padding:12px 0; font-size:13px; }

.document-list li:first-child { border-top:0; }

.document-list strong { color:var(--ink); font-weight:700; }

.doc-cat-bar { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }

pre {

  margin:12px 0 0; background:var(--navy-900); color:#c9dcee; border-radius:var(--radius-sm);

  padding:12px; font-family:var(--mono); font-size:12px; line-height:1.6; overflow-x:auto;

}

.kv-list { margin-top:12px; display:grid; gap:0; }

.kv-list div { display:flex; justify-content:space-between; gap:12px; padding:8px 0; border-top:1px solid var(--line); font-size:13px; }

.kv-list div:first-child { border-top:0; }

.kv-list dt { color:var(--muted); }

.kv-list dd { margin:0; font-weight:700; color:var(--ink); font-family:var(--mono); font-size:12px; }



/* ---------- 检索与高亮 ---------- */

.search-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; margin-bottom:12px; }

.search-hint { font-size:12px; color:var(--muted); margin:-4px 0 12px; }

mark.hit {

  background:#fef3c7; color:#6b4a04; border-radius:3px; padding:0 2px;

  box-shadow:inset 0 -2px 0 rgba(242,163,60,.45);

}

.doc-count-line { font-size:12px; color:var(--muted); margin-bottom:12px; }

.doc-count-line b { color:var(--navy-800); font-family:var(--mono); }



/* ---------- 学习积分 ---------- */

.points-head { display:grid; grid-template-columns:auto minmax(0,1fr); gap:16px; align-items:center; margin-top:12px; }

.points-total {

  border:1px solid var(--line); border-radius:var(--radius); background:var(--navy-050);

  padding:12px 16px; text-align:center; min-width:132px;

}

.points-total b { display:block; font-family:var(--mono); font-size:27px; line-height:1.4; color:var(--navy-800); }

.points-total span { font-size:12px; color:var(--muted); }

.points-breakdown { display:grid; gap:8px; }

.points-breakdown div { display:flex; justify-content:space-between; gap:12px; font-size:12px; }

.points-breakdown .pb-label { color:var(--body); }

.points-breakdown .pb-value { font-family:var(--mono); color:var(--navy-700); font-weight:700; }



/* ---------- 培训记录单（A4 可打印） ---------- */

.certificate {

  margin-top:16px; border:2px solid var(--navy-800); border-radius:var(--radius);

  background:var(--panel); padding:24px 28px; max-width:760px;

}

.cert-kicker { font-family:var(--mono); font-size:12px; letter-spacing:.14em; color:var(--amber-dark); text-transform:uppercase; }

.cert-title { font-size:27px; margin-top:8px; color:var(--navy-800); }

.cert-sub { font-size:13px; color:var(--muted); margin-top:4px; }

.cert-rule { height:4px; margin:16px 0; background:repeating-linear-gradient(135deg,var(--amber) 0 9px,var(--navy-800) 9px 18px); border-radius:2px; }

.cert-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px 20px; margin-top:4px; }

.cert-grid div { border-bottom:1px dashed var(--line-strong); padding:8px 0; font-size:13px; display:flex; justify-content:space-between; gap:12px; }

.cert-grid dt { color:var(--muted); }

.cert-grid dd { margin:0; font-weight:700; color:var(--ink); }

.cert-steps { margin-top:12px; display:grid; gap:4px; }

.cert-steps div { display:flex; align-items:center; gap:8px; font-size:13px; }

.cert-steps .tick { color:var(--risk-low); font-weight:800; }

.cert-steps .untick { color:var(--line-strong); font-weight:800; }

.cert-foot { margin-top:16px; padding-top:12px; border-top:1px solid var(--line); font-size:12px; color:var(--muted); line-height:1.6; }

.cert-sign { display:flex; gap:32px; margin-top:16px; flex-wrap:wrap; }

.cert-sign div { flex:1; min-width:170px; border-top:1px solid var(--ink); padding-top:4px; font-size:12px; color:var(--muted); }



/* ---------- 应急 ---------- */

.emergency-hero {

  border:1px solid #f0bdb7; border-radius:12px; padding:16px 20px; margin-bottom:16px;

  background:linear-gradient(140deg,#fef2f2,#fff); position:relative; overflow:hidden;

}

.emergency-hero::before { content:""; position:absolute; left:0; top:0; bottom:0; width:6px; background:var(--risk-high); }

.emergency-hero h2 { color:#a8291c; font-size:21px; }

.emergency-hero p { color:#8a3a30; font-size:13px; margin-top:8px; max-width:56em; }

.emergency-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }

.emergency-card {

  border:1px solid #f0cdc8; border-radius:var(--radius); background:var(--panel); padding:16px 12px;

  text-align:left; font-family:inherit; display:flex; flex-direction:column; gap:4px;

  box-shadow:var(--shadow-sm); transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease;

}

.emergency-card:hover { transform:translateY(-2px); box-shadow:var(--shadow); border-color:var(--risk-high); }

.emergency-card .em-ico { font-size:27px; }

.emergency-card strong { font-size:15px; color:#a8291c; }

.emergency-card p { font-size:12px; color:var(--muted); }

.emergency-guide {

  margin-top:16px; border:1px solid #f0cdc8; border-radius:var(--radius); background:#f7f8fa; padding:16px;

}

.emergency-guide h3 { font-size:15px; color:#a8291c; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

.em-steps { margin-top:12px; display:grid; gap:8px; }

.em-step { display:flex; gap:12px; align-items:flex-start; font-size:13px; color:var(--body); }

.em-step .em-num {

  flex:0 0 24px; width:24px; height:24px; border-radius:50%; display:grid; place-items:center;

  background:var(--risk-high); color:#fff; font-family:var(--mono); font-size:12px; font-weight:700;

}

.em-never {

  margin-top:12px; border-left:4px solid var(--risk-high); background:var(--panel);

  border-radius:0 6px 6px 0; padding:12px 12px; font-size:13px; color:#8a2f20;

}

.em-never b { display:block; margin-bottom:4px; color:#a8291c; }

.em-calls { display:flex; gap:12px; flex-wrap:wrap; margin-top:16px; }

.em-note { font-size:12px; color:var(--muted); margin-top:12px; }



/* ---------- 侧栏 ---------- */

aside { display:grid; gap:16px; align-content:start; }

.side-title { font-size:15px; }

.metric-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:12px; }

.metric { border:1px solid var(--line); border-radius:var(--radius-sm); padding:12px 12px; background:var(--navy-050); }

.metric strong { display:block; font-family:var(--mono); font-size:21px; color:var(--navy-800); line-height:1.4; }

.metric span { font-size:12px; color:var(--muted); }

.side-list li { border-top:1px solid var(--line); padding:8px 0; font-size:12px; }

.side-list li:first-child { border-top:0; }

.side-list strong { display:block; color:var(--ink); font-size:13px; }

.side-hot { display:grid; gap:8px; margin-top:12px; }

.side-hot li {

  display:flex; justify-content:space-between; gap:12px; align-items:center;

  border:1px solid var(--line); border-radius:6px; padding:8px 12px; background:var(--panel-soft); font-size:13px;

}

.side-hot .hot-count { font-family:var(--mono); font-size:12px; color:var(--navy-700); font-weight:700; }

.callout {

  border-radius:var(--radius-sm); padding:12px 12px; font-size:12px; line-height:1.6;;

  background:var(--navy-050); border-left:4px solid var(--navy-600); color:var(--body);

}

.callout.is-danger { background:var(--risk-high-soft); border-left-color:var(--risk-high); color:#7c2c1f; }

.callout.is-amber { background:var(--amber-soft); border-left-color:var(--amber); color:#6d5217; }

.callout b { display:block; margin-bottom:4px; }

.empty-state { color:var(--muted); font-size:13px; padding:12px 0; }



/* ---------- 页脚 ---------- */

footer {

  position:relative; z-index:1; max-width:1400px; margin:0 auto; padding:4px 20px 32px;

  color:var(--muted); font-size:12px;

}

.footer-inner { border-top:1px solid var(--line-strong); padding-top:16px; display:grid; gap:8px; }

.footer-line { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }

.footer-line b { color:var(--navy-700); }



/* ---------- 标准 / 数据表格（≤720px 转卡片式） ---------- */

.table-wrap { overflow-x:auto; margin-top:12px; border:1px solid var(--line); border-radius:var(--radius-sm); }

table { width:100%; border-collapse:collapse; font-size:13px; background:var(--panel); }

caption { caption-side:top; text-align:left; padding:8px 12px; font-size:12px; color:var(--muted); }

th, td { padding:8px 12px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }

th { background:var(--navy-050); color:var(--navy-800); font-weight:700; white-space:nowrap; }

tbody tr:last-child td { border-bottom:0; }

tbody tr:hover { background:var(--panel-soft); }

.std-status { display:inline-block; font-size:12px; font-weight:800; border-radius:999px; padding:2px 8px; }

.std-status.active { background:var(--risk-low-soft); color:#155f3a; }

.std-status.pending { background:var(--risk-mid-soft); color:#7a5a06; }

.std-status.unknown { background:var(--navy-100); color:var(--navy-700); }



/* ---------- 加载骨架 ---------- */

.skeleton {

  border-radius:var(--radius-sm);

  background:linear-gradient(90deg,#eef2f7 25%,#e5e7eb 37%,#eef2f7 63%);

  background-size:400% 100%; animation:shimmer 1.4s ease-in-out infinite;

}

@keyframes shimmer { 0% { background-position:100% 0; } 100% { background-position:0 0; } }

.skeleton-line { height:12px; margin:8px 0; }

.skeleton-line.w60 { width:60%; }

.skeleton-line.w80 { width:80%; }

.skeleton-card { height:96px; margin-top:12px; }

.skeleton-badge { height:22px; width:88px; border-radius:999px; }

.loading-hint { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); margin-top:12px; }

.loading-hint .pulse-dot { width:8px; height:8px; border-radius:50%; background:var(--amber-dark); animation:pulse 1.2s infinite ease-in-out; }



/* ---------- 触控区下限（≥44px） ---------- */

.role-chip, .filter-chip, .quick-button, .option, .voice-button, .secondary-button,

.amber-button, .ghost-button, .danger-button, .training-card, .action-card,

.emergency-card {

  min-height:44px;

}



/* ---------- J 正文排版收敛层（必须放在最后，覆盖上面各模块的零散声明） ---------- */

.lead,

.notice,

.hero-desc,

.answer-body,

.explain,

.quiz-result p,

.em-never,

.source-card p,

.em-step,

.callout,

.q-head {

  max-width:var(--measure);

  line-height:var(--line-prose);

}

/* 列表与卡片内文字已被列宽自然约束，只统一行高 */

.step-points li,

.role-block li,

.case-card p,

.photo-tip,

.source-card p:not(:first-of-type) {

  line-height:var(--line-prose);

}

/* 培训步骤要点在宽屏下会撑满整列，单独收口 */

.step-points li { max-width:var(--measure); }

.answer-body { line-height:var(--line-prose); }

.source-card p { font-size:12px; }



/* ---------- 响应式 ---------- */

@media (max-width:1180px) {

  .home-grid { grid-template-columns:1fr; }

  .stat-inner { grid-template-columns:repeat(2,minmax(0,1fr)); }

  .stat-cell:nth-child(3) { border-left:0; padding-left:0; }

}

@media (max-width:1000px) {

  main { grid-template-columns:1fr; padding:16px; }

  aside { grid-template-columns:repeat(2,minmax(0,1fr)); }

  .home-actions { grid-template-columns:1fr; }

  .training-grid, .case-grid, .photo-tips, .role-cols { grid-template-columns:1fr; }

  .emergency-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }

  .nav-button.emergency-tab { margin-left:0; }

}

@media (max-width:720px) {

  .header-inner { padding:12px 16px; }

  .brand-text h1 { font-size:17px; }

  .brand-text p { font-size:12px; }

  .hero { padding:20px 16px; border-radius:12px; }

  .hero h2 { font-size:21px; }

  .panel-body { padding:16px; }

  .panel-head { padding:12px 16px; }

  .composer-grid, .upload-row, .case-search { grid-template-columns:1fr; }

  .primary-button { min-height:50px; }

  /* 手机端导航标签也要满足 44px 触控区 */

  .nav-button { min-height:44px; padding:12px 16px 12px; }

  .quiz-status { grid-template-columns:1fr; }

  aside { grid-template-columns:1fr; }

  .emergency-grid { grid-template-columns:1fr; }

  .domain-bar { grid-template-columns:96px minmax(0,1fr) 54px; }

  /* 表格在窄屏转为"每行一张卡"，避免横向滚动 */

  table, thead, tbody, tr, th, td { display:block; width:100%; }

  thead { display:none; }

  tbody tr { border-bottom:1px solid var(--line); padding:4px 0; }

  tbody tr:last-child { border-bottom:0; }

  th, td { border-bottom:0; padding:4px 12px; }

  td::before {

    content:attr(data-label);

    display:block; font-size:12px; font-weight:700; color:var(--muted);

    text-transform:none; margin-bottom:2px;

  }

  td:empty { display:none; }

  .step-item { grid-template-columns:32px minmax(0,1fr); }

  .step-side { grid-column:2; justify-items:start; }

  .chat-stream { padding:12px; }

  .bubble { max-width:100%; }

}

@media (max-width:420px) {

  .brand-mark { width:40px; height:40px; flex-basis:40px; font-size:21px; }

  .hero h2 { font-size:21px; }

  .stat-cell b { font-size:21px; }

  .quiz-meta-row { grid-template-columns:1fr; }

}

@media (prefers-reduced-motion:reduce) {

  *, *::before, *::after { animation-duration:.001ms !important; transition-duration:.001ms !important; }

}

@media (max-width:720px) {

  .points-head { grid-template-columns:1fr; }

  .cert-grid { grid-template-columns:1fr; }

  .certificate { padding:16px 16px; }

  .cert-title { font-size:21px; }

}



/* ---------- 打印：只输出培训记录单（A4） ---------- */

@media print {

  @page { size:A4; margin:14mm; }

  body { background:var(--panel); color:#000; letter-spacing:0; }

  body::before, .top-band, header, .stat-bar, nav, aside, footer,

  .panel:not(#pointsPanel), .hero, .camera-stage, .photo-stage {

    display:none !important;

  }

  main { display:block; padding:0; max-width:none; }

  .panel, .certificate { border:0; box-shadow:none; margin:0; padding:0; max-width:none; }

  #pointsPanel .panel-head, .points-head, .progress-row, .quiz-actions, #pointsHint {

    display:none !important;

  }

  .certificate { border:2px solid #000; padding:16mm 14mm; page-break-inside:avoid; }

  .cert-title { color:#000; font-size:22pt; }

  .cert-rule { background:repeating-linear-gradient(135deg,#666 0 6px,#000 6px 12px); }

  .cert-foot, .cert-sign div, .cert-grid dt, .cert-sub { color:#333; }

  mark.hit { background:transparent; box-shadow:none; }

}

  









































































































































































































































































































































































































/* ===== V13 PHASES BEGIN ===== */
.phase { margin:32px 0 0; }
.phase:first-of-type { margin-top:24px; }
.phase-head { display:flex; align-items:baseline; gap:12px; margin-bottom:12px; flex-wrap:wrap; }
.phase-no {
  flex:0 0 auto; width:26px; height:26px; border-radius:50%;
  background:var(--green-700); color:#fff; font-size:13px; font-weight:700;
  display:inline-grid; place-items:center; font-family:var(--mono); line-height:1.4;;
}
.phase-title { font-size:17px; font-weight:700; color:var(--ink-800); letter-spacing:-.01em; }
.phase-desc { font-size:13px; color:var(--ink-400); flex:1 1 240px; min-width:0; }
.phase-rule { height:1px; background:var(--ink-100); margin:0 0 16px; }
.phase-cols { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:24px; align-items:start; }
.phase-cols > .phase-main { display:grid; gap:20px; min-width:0; }
.phase-cols > .phase-side { display:grid; gap:20px; min-width:0; }
.phase-single { display:grid; gap:20px; }
@media (max-width:1200px) {
  .phase-cols { grid-template-columns:1fr; }
  .phase-cols > .phase-side { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width:900px) {
  .phase-cols > .phase-side { grid-template-columns:1fr; }
  .phase { margin-top:24px; }
  .phase-title { font-size:15px; }
}
@media (max-width:640px) {
  .phase-head { gap:8px; }
  .phase-no { width:23px; height:23px; font-size:12px; }
}
/* ===== V13 PHASES END ===== */

/* ===== V13 LAYOUT BEGIN ===== */
/* ==========================================================================
   V13-L 布局层：把主内容收成单一纵向阅读流
   --------------------------------------------------------------------------
   为什么改：V13 的首页是"两栏并排 + 5 段分组"，但每一段内部又是 2 栏并排，
   再加上每块都是带边框的白卡片，结果同屏并排 3~4 个视线落点，
   眼睛不知道该先看哪个 —— 这就是"没有条理、看着乱"的直接来源。

   规则（强制，不再有例外）：
     1) 主内容最大宽度收到 960px 并居中；阅读时视线只走一条竖线
     2) 不再出现并排的分栏容器，全部改为纵向堆叠
     3) 卡片只用于"独立信息块"；连续条目改用分隔线，不再一块一个边框
     4) 段与段之间用留白 + 一条浅分隔线分开，不再用编号圆点和大标题
   ========================================================================== */

/* ---------- 单一阅读流 ---------- */
main {
  max-width:960px;
  margin:0 auto;
  padding:28px 24px 56px;
  display:block;          /* 取消栅格，改为普通纵向流 */
}
.view { display:none; }
.view.active { display:block; }

/* 首页：所有阶段容器都是纵向堆叠，不再有 phase-cols / phase-main / phase-side */
.phase { margin:0; }
.phase-cols,
.phase-single,
.phase-main,
.phase-side {
  display:block;
  margin:0;
  padding:0;
}
.phase-cols > *,
.phase-single > *,
.phase-main > *,
.phase-side > * { margin:0; }
.phase-cols > * + *,
.phase-single > * + *,
.phase-main > * + *,
.phase-side > * + * { margin-top:20px; }

/* ---------- 阶段：改为"小标签 + 细分隔线"，去掉大编号圆点 ---------- */
.phase { margin-top:40px; }
.phase:first-of-type { margin-top:12px; }
.phase-head {
  display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; margin-bottom:4px;
}
.phase-no {
  display:none;   /* 编号圆点在单列流里反而增加噪声，收进标题里表达 */
}
.phase-title {
  font-size:13px; font-weight:700; color:var(--green-700);
  letter-spacing:.08em; font-family:var(--mono); text-transform:uppercase;
}
.phase-desc {
  font-size:13px; color:var(--ink-400); flex:1 1 auto; min-width:0;
}
.phase-rule { height:1px; background:var(--ink-100); margin:8px 0 20px; }

/* ---------- 卡片：只给真正独立的信息块 ---------- */
.panel {
  box-shadow:none;
  border:1px solid var(--ink-100);
  border-radius:var(--r-md);
}
.panel:hover { box-shadow:none; }
.panel + .panel { margin-top:20px; }
.panel-head { padding:12px 16px; }
.panel-head h2 { font-size:15px; }
.panel-head::before { height:14px; width:3px; margin-right:8px; }
.panel-body { padding:16px; }

/* 连续条目：用分隔线而不是一个个边框 */
.todo-item, .check-item, .side-doc-list li, .source-card, .option, .training-card,
.quiz-stat, .role-block, .case-card, .step-item, .photo-tip, .result-box {
  border:0;
  border-bottom:1px solid var(--ink-100);
  border-radius:0;
  background:transparent;
  box-shadow:none;
}
.todo-item:last-child, .check-item:last-child, .side-doc-list li:last-child,
.source-card:last-child, .option:last-child, .training-card:last-child,
.case-card:last-child, .step-item:last-child { border-bottom:0; }
.todo-item { padding:12px 2px; }
.todo-item:hover { background:var(--ink-50); }
.check-item { padding:12px 2px; }
.training-card { padding:12px 2px; border-left:0; }
.case-card { padding:12px 2px; border-top:0; border-bottom:1px solid var(--ink-100); }
.step-item { padding:12px 2px; }
.option { padding:12px 2px; margin-bottom:0; }
.option:hover:not(:disabled) { background:var(--green-50); }
.source-card { padding:12px 2px; border-left:0; }
.role-block, .quiz-stat, .result-box, .photo-tip { padding:12px 2px; }

/* 网格容器全部改为单列纵向 */
.metric-grid, .training-grid, .case-grid, .role-cols, .photo-tips,
.home-actions, .entries, .document-list, .source-list, .em-calls {
  display:block;
}
.metric-grid > * + *,
.training-grid > * + *,
.case-grid > * + *,
.role-cols > * + *,
.home-actions > * + *,
.entries > * + *,
.source-list > * + *,
.em-calls > * + * { margin-top:12px; }

/* 指标块：改为横向一行四格，不再各自成卡 */
.metric-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.metric {
  border:0; background:var(--ink-50); border-radius:var(--r-sm);
  padding:12px 12px; text-align:left;
}
.metric strong { font-size:21px; }
.metric span { display:block; font-size:12px; color:var(--ink-400); margin-top:2px; }

/* 三个主入口：横向一行三格 */
.entries, .home-actions {
  display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px;
}

/* ---------- Hero：收窄，去掉大标题压迫感 ---------- */
/* 注意：不要在这里直接写 color —— .hero 的选择器权重会盖过
   [data-theme="dark"] .hero，导致暗色模式失效。正文颜色统一交给令牌。 */
.hero { padding:24px; margin-bottom:28px; }
.hero h2 { font-size:21px; line-height:1.4;; }
.hero-desc { font-size:13px; }

/* ---------- Hero 内嵌的指标行 ----------
   原来是一条独立的深色横带，占 78px，把三个主入口挤到首屏之外。
   现在并进 Hero，压成一行紧凑数据：数字 + 单位并排，去掉第二行说明。 */
.hero-stats {
  display:flex; flex-wrap:wrap; gap:8px 24px;
  margin:16px 0 4px; padding:12px 0;
  border-top:1px solid var(--ink-100); border-bottom:1px solid var(--ink-100);
}
.hero-stats .stat-cell {
  padding:0; border:0; display:flex; align-items:baseline; gap:4px; min-width:0;
}
.hero-stats .stat-cell b {
  font-size:17px; font-weight:700; color:var(--ink-800);
  font-variant-numeric:tabular-nums; letter-spacing:-.01em;
}
.hero-stats .stat-cell span { font-size:12px; color:var(--ink-400); }
.hero-stats .stat-cell small { display:none; }
.hero-stats .stat-cell.is-risk b { color:var(--danger-600); }

/* ---------- 行动卡：去掉大图标块，改小图标行 ---------- */
.action-card {
  display:flex; align-items:flex-start; gap:12px;
  padding:16px; border-radius:var(--r-md); border:1px solid var(--ink-100);
}
.action-ico {
  width:32px; height:32px; flex:0 0 32px; border-radius:var(--r-sm); font-size:15px;
}
.action-card strong { font-size:13px; }
.action-card p { font-size:12px; line-height:1.6;;; }
.action-go { display:none; }   /* 整块可点，不需要额外箭头 */

/* 深色主卡里的绿字要提亮，否则深底压深绿看不清 */
.action-card.is-primary .action-go,
.action-card.is-primary p { color:#a7f3d0; }

/* ---------- 顶栏与导航同步收窄 ---------- */
.header-inner, .stat-inner, .nav-inner { max-width:960px; }
main, footer { max-width:960px; }
footer { padding:20px 24px 48px; }

/* ---------- 响应式 ---------- */
@media (max-width:900px) {
  main { padding:20px 16px 48px; }
  .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .entries, .home-actions { grid-template-columns:1fr; }
  .action-card { align-items:center; }
  .hero h2 { font-size:21px; }
  .phase { margin-top:32px; }
}
@media (max-width:640px) {
  main { padding:16px 12px 40px; }
  .header-inner, .stat-inner, .nav-inner { padding-left:12px; padding-right:12px; }
  .hero { padding:16px; }
  .hero h2 { font-size:17px; }
  .hero-desc { font-size:13px; }
  .panel-head, .panel-body { padding:12px; }
  .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
  .metric { padding:8px 12px; }
  .metric strong { font-size:15px; }
  .phase-title { font-size:12px; }
  .phase-desc { flex-basis:100%; }
  .primary-button { width:100%; }
}
/* ===== V13 LAYOUT END ===== */

/* ===== V15 THEME BEGIN ===== */
/* ==========================================================================
   V15 视觉层：工业警示风
   --------------------------------------------------------------------------
   方向依据（用户提供的参考：Nike 暗色霓虹、美食暖色、NFT 高饱和、企业模板）：
     共同点是「深色打底 + 饱和点缀、强烈字号对比、大留白、有视觉记忆点」。

   与 V14 政务风的区别：
     主色      政务蓝 #0b5fa8        → 安全警示橙 #b23a0a（施工现场警示色）
     顶栏      平涂深蓝              → 深墨底 + 斜纹 + 品牌橙块
     字号      最大 26px             → 最大 28px，且拉开档距
     卡片      白色细边方块          → 减少卡片，用留白与细分隔线
     符号      无                    → 工程斜纹（贯穿全站的视觉语言）

   参考里不能照搬的部分（已在 DESIGN.md 记录原因）：
     深色霓虹发光 —— 工地强光下手机屏看不清
     大图视觉主体 —— 项目无产品摄影素材
     装饰性动效   —— 现场网络差、设备旧
   ========================================================================== */
:root {
  /* ---------- 中性：墨色阶 ---------- */
  --i950:#0f1215;   /* 顶栏、主行动卡 */
  --i900:#161a1f;
  --i800:#22272e;   /* 强调文字 */
  --i700:#343a42;
  --i600:#4b535c;   /* 正文 */
  --i500:#6b7480;   /* 次要文字 */
  --i400:#98a1ac;
  --i300:#c3cad2;
  --i200:#e3e7eb;   /* 分隔线 */
  --i100:#eff2f5;
  --i50:#f7f9fa;
  --surface:#ffffff;
  --canvas:#f4f6f7;

  /* ---------- 主色：安全警示橙 ---------- */
  --safety:#b23a0a;      /* 白字对比度 7.3:1 */
  --safety-700:#8f2d06;
  --safety-500:#d9541a;  /* 悬停 / 图形 */
  --safety-100:#fdeee6;
  --safety-50:#fef7f2;

  /* ---------- 副色：警示黄（只做标记，不做文字底） ---------- */
  --signal:#d9a300;
  --signal-100:#fff6d9;
  --signal-50:#fffbef;

  /* ---------- 功能色 ---------- */
  --red:#c0341d;
  --red-bg:#fdeeea;
  --amber:#a86400;
  --amber-bg:#fff5df;
  --green:#1c6b45;
  --green-bg:#eaf5ef;

  /* ---------- 旧令牌全部指向新体系 ---------- */
  --n900:var(--i950);
  --n800:var(--i800);
  --n700:var(--i600);
  --n600:var(--i600);
  --n500:var(--i500);
  --n400:var(--i400);
  --n300:var(--i300);
  --n200:var(--i200);
  --n100:var(--i100);
  --n050:var(--i50);
  --b900:var(--i950);
  --b800:var(--i800);
  --b700:var(--safety);
  --b600:var(--safety-500);
  --b500:var(--safety-500);
  --b300:var(--safety-100);
  --b100:var(--safety-100);
  --b050:var(--safety-50);
  --ink-900:var(--i950);
  --ink-800:var(--i800);
  --ink-700:var(--i600);
  --ink-600:var(--i600);
  --ink-500:var(--i500);
  --ink-400:var(--i500);
  --ink-300:var(--i400);
  --ink-200:var(--i200);
  --ink-100:var(--i200);
  --ink-50:var(--i50);
  --green-700:var(--green);
  --green-600:var(--green);
  --green-500:var(--green);
  --green-100:var(--green-bg);
  --green-50:var(--green-bg);
  --gold-700:var(--amber);
  --gold-500:var(--signal);
  --gold-100:var(--signal-100);
  --gold-50:var(--signal-50);
  --orange:var(--safety);
  --orange-bg:var(--safety-100);
  --danger-700:var(--red);
  --danger-600:var(--red);
  --danger-100:#f0c4bc;
  --danger-50:var(--red-bg);
  --warn-700:var(--amber);
  --warn-100:var(--amber-bg);
  --ok-700:var(--green);
  --ok-100:var(--green-bg);
  --risk-high:var(--red);
  --risk-mid:var(--amber);
  --risk-low:var(--green);
  --risk-high-soft:var(--red-bg);
  --risk-mid-soft:var(--amber-bg);
  --risk-low-soft:var(--green-bg);
  --brand:var(--safety);
  --brand-700:var(--safety-700);
  --brand-600:var(--safety-500);
  --brand-500:var(--safety-500);
  --brand-100:var(--safety-100);
  --brand-050:var(--safety-50);
  --accent:var(--safety);
  --accent-600:var(--safety-500);
  --accent-100:var(--safety-100);
  --navy-900:var(--i950);
  --navy-800:var(--i950);
  --navy-700:var(--i800);
  --navy-600:var(--i700);
  --navy-100:var(--i200);
  --navy-050:var(--i100);
  --amber-dark:var(--amber);
  --amber-soft:var(--amber-bg);
  --ink:var(--i800);
  --body:var(--i600);
  --muted:var(--i500);
  --paper:var(--canvas);
  --panel:var(--surface);
  --panel-soft:var(--i50);
  --line:var(--i200);
  --line-strong:var(--i300);

  /* 形状：小圆角，工业感不甜腻 */
  --r-sm:2px;
  --r-md:3px;
  --r-lg:4px;
  --r-xl:6px;
  --radius:var(--r-lg);
  --radius-sm:var(--r-md);
  --shadow-1:0 1px 2px rgba(15,18,21,.06);
  --shadow-2:0 1px 3px rgba(15,18,21,.10);
  --shadow-3:0 4px 14px rgba(15,18,21,.12);
  /* 旧别名：基础层与布局层仍在引用（共 12 处），从 V13 层搬过来，
     否则删掉 V13 后这些引用会失效、阴影全部消失 */
  --shadow-sm:var(--shadow-1);
  --shadow:var(--shadow-2);
  --shadow-lg:var(--shadow-3);

  /* 字号：拉开对比。正文 14，标题可到 28 */
  --fs-xs:11px;
  --fs-sm:13px;
  --fs-md:14px;
  --fs-base:16px;
  --fs-lg:18px;
  --fs-xl:22px;
  --fs-2xl:28px;
}

/* ==========================================================================
   1. 顶栏：深墨 + 工程斜纹 + 橙色品牌块
   ========================================================================== */
header { background:var(--i950); position:relative; }
/* 安全警示斜纹：贯穿全站的视觉符号，取自施工现场警戒带 */
.top-band {
  height:6px;
  background:repeating-linear-gradient(
    135deg, var(--safety) 0 10px, var(--i950) 10px 20px
  );
}
.header-inner { max-width:1024px; padding:12px 16px; }
.brand-mark {
  width:40px; height:40px; flex-basis:40px; border-radius:var(--r-sm);
  background:var(--safety); color:#fff; font-size:21px; font-weight:800;
  box-shadow:0 0 0 1px rgba(255,255,255,.12) inset;
}
.brand-text h1 { font-size:15px; font-weight:800; color:#fff; letter-spacing:.02em; }
.brand-text p { font-size:12px; color:var(--i400); letter-spacing:.06em; }
.version-tag {
  border-color:rgba(255,255,255,.16); color:var(--i400);
  font-size:12px; border-radius:var(--r-sm); font-family:var(--mono);
}
.status-pill {
  font-size:12px; border-radius:var(--r-sm); padding:4px 8px;
  background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.22); color:#e8edf2;
}
.status-pill.offline { background:rgba(217,163,0,.20); border-color:rgba(217,163,0,.45); color:#ffe9a8; }
.theme-toggle {
  background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.18);
  color:#fff; border-radius:var(--r-sm); padding:4px 12px; font-size:12px; font-weight:600;
}
.theme-toggle:hover { background:rgba(255,255,255,.2); }

/* ==========================================================================
   2. 导航：白底 + 主色下划线，字重加重
   ========================================================================== */
.nav { background:var(--surface); border-bottom:1px solid var(--i200); }
.nav-inner { max-width:1024px; padding:0 16px; gap:0; }
.nav-button {
  padding:16px 16px 12px; font-size:13px; font-weight:700;
  color:var(--i500); border-bottom:3px solid transparent; border-radius:0;
  letter-spacing:.02em;
}
.nav-button:hover { color:var(--i800); background:var(--i50); }
.nav-button.active { color:var(--safety); border-bottom-color:var(--safety); background:transparent; }
.nav-button.emergency-tab { color:var(--red); }
.nav-button.emergency-tab.active { border-bottom-color:var(--red); }

/* ==========================================================================
   3. 主容器：加宽到 1024，留白加大
   ========================================================================== */
main { max-width:1024px; padding:28px 16px 56px; }
.stat-bar { display:none; }

/* ==========================================================================
   4. Hero：白底 + 左侧粗橙线 + 大标题
   ========================================================================== */
.hero {
  background:var(--surface); border:1px solid var(--i200); border-left:5px solid var(--safety);
  border-radius:var(--r-lg); padding:24px; margin-bottom:20px; color:var(--i600);
  box-shadow:var(--shadow-1); background-image:none;
}
.hero::after { display:none; }
.hero-kicker {
  display:inline-block; background:var(--i950); color:#fff;
  font-size:12px; font-weight:700; padding:4px 8px; border-radius:var(--r-sm);
  letter-spacing:.08em; margin-bottom:12px; border:0;
}
.hero h2 {
  color:var(--i950); font-size:var(--fs-2xl); line-height:1.4; font-weight:800;
  letter-spacing:-.01em; max-width:22em;
}
.hero h2 em { color:var(--safety); font-style:normal; font-weight:800; }
.hero-desc { color:var(--i600); font-size:13px; margin-top:8px; max-width:38em; }
.hero-chip {
  background:var(--i50); border:1px solid var(--i200); color:var(--i600);
  font-size:12px; padding:4px 8px; border-radius:var(--r-sm); font-weight:600;
}
.hero-stats {
  display:flex; flex-wrap:wrap; gap:8px 28px;
  margin:16px 0 4px; padding:12px 0;
  border-top:1px solid var(--i200); border-bottom:1px solid var(--i200);
}
.hero-stats .stat-cell { padding:0; border:0; display:flex; align-items:baseline; gap:4px; }
.hero-stats .stat-cell b {
  font-size:21px; font-weight:800; color:var(--i950); letter-spacing:-.02em;
  font-variant-numeric:tabular-nums;
}
.hero-stats .stat-cell span { font-size:12px; color:var(--i500); font-weight:600; }
.hero-stats .stat-cell small { display:none; }
.hero-stats .stat-cell.is-risk b { color:var(--red); }

/* ==========================================================================
   5. 主行动卡：三格，主卡深墨 + 橙图标
   ========================================================================== */
.entries, .home-actions { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:20px 0; }
.action-card {
  display:flex; align-items:flex-start; gap:12px; padding:16px;
  border:1px solid var(--i200); border-radius:var(--r-lg); background:var(--surface);
  box-shadow:var(--shadow-1); position:relative; overflow:hidden;
}
.action-card::before {
  /* 顶部细橙条：把三张卡在视觉上串起来 */
  content:""; position:absolute; left:0; right:0; top:0; height:3px; background:var(--safety);
}
.action-card:hover { border-color:var(--safety); box-shadow:var(--shadow-3); transform:translateY(-1px); }
.action-ico {
  width:34px; height:34px; flex:0 0 34px; border-radius:var(--r-sm); font-size:15px;
  background:var(--safety-100); border:0; display:grid; place-items:center;
}
.action-card strong { font-size:13px; color:var(--i900); font-weight:800; }
.action-card p { font-size:12px; color:var(--i500); line-height:1.6;; }
.action-go { display:none; }
.action-card.is-primary { background:var(--i950); border-color:var(--i950); }
.action-card.is-primary strong { color:#fff; }
.action-card.is-primary p { color:var(--i400); }
.action-card.is-primary .action-ico { background:var(--safety); }
.action-card.is-primary::before { background:var(--signal); }
.action-card.is-danger { background:var(--surface); border-color:var(--danger-100); }
.action-card.is-danger::before { background:var(--red); }
.action-card.is-danger strong { color:var(--red); }
.action-card.is-danger .action-ico { background:var(--red-bg); }

/* ==========================================================================
   6. 面板：减少卡片感，靠留白与细分隔线
   ========================================================================== */
.panel {
  background:var(--surface); border:1px solid var(--i200);
  border-radius:var(--r-lg); box-shadow:none;
}
.panel + .panel { margin-top:20px; }
.panel-head {
  padding:12px 16px; border-bottom:1px solid var(--i200); background:var(--surface);
  border-radius:var(--r-lg) var(--r-lg) 0 0; display:flex; align-items:center; gap:8px;
}
.panel-head h2 { font-size:15px; font-weight:800; color:var(--i900); letter-spacing:.01em; }
.panel-head .head-note { font-size:12px; color:var(--i400); }
.panel-head::before {
  content:""; display:block; width:4px; height:16px; border-radius:1px;
  background:var(--safety); margin-right:0; flex:0 0 4px;
}
.panel-body { padding:20px; }

/* ==========================================================================
   7. 按钮
   ========================================================================== */
.primary-button, .amber-button, .secondary-button, .ghost-button, .danger-button,
.voice-button, .quick-button, .filter-chip, .role-chip, .option {
  border-radius:var(--r-sm); font-weight:700; font-size:13px; letter-spacing:.01em;
}
.primary-button { background:var(--safety); color:#fff; }
.primary-button:hover:not(:disabled) { background:var(--safety-700); }
.amber-button { background:var(--safety); color:#fff; }
.amber-button:hover:not(:disabled) { background:var(--safety-700); color:#fff; }
.secondary-button, .voice-button, .quick-button, .filter-chip, .role-chip {
  background:var(--surface); border:1px solid var(--i300); color:var(--i700);
}
.secondary-button:hover, .voice-button:hover, .quick-button:hover,
.filter-chip:hover, .role-chip:hover {
  border-color:var(--safety); color:var(--safety); background:var(--safety-50);
}
.filter-chip.active, .role-chip.active {
  background:var(--safety); border-color:var(--safety); color:#fff;
}
.danger-button { background:var(--red); color:#fff; }
.danger-button:hover:not(:disabled) { background:#9a2a17; }

/* ==========================================================================
   8. 输入
   ========================================================================== */
textarea, input[type="text"], input[type="search"] {
  background:var(--surface); border:1.5px solid var(--i300); border-radius:var(--r-sm);
  color:var(--i800); font-size:13px;
}
textarea:focus, input:focus {
  border-color:var(--safety); box-shadow:0 0 0 3px var(--safety-100); background:var(--surface);
}
textarea::placeholder, input::placeholder { color:var(--i400); }

/* ==========================================================================
   9. 清单条目：分隔线，勾选态用绿
   ========================================================================== */
.todo-item, .check-item, .quiz-stat, .role-block, .option, .training-card,
.source-card, .doc-group, .step-item, .case-card, .photo-tip, .result-box {
  background:transparent; border:0; border-bottom:1px solid var(--i200);
  border-radius:0; box-shadow:none;
}
.todo-item { padding:12px 2px; }
.todo-item:hover { background:var(--i50); }
.todo-item b, .check-item b { color:var(--i900); font-size:13px; font-weight:700; }
.todo-item span, .check-item small { color:var(--i500); font-size:12px; }
.todo-item.done, .check-item.checked, .step-item.is-done {
  background:var(--green-bg); border-color:#c6e6d3;
}
.todo-item.done b, .check-item.checked b, .step-item.is-done h3 { color:var(--green); }

/* ==========================================================================
   10. 进度与指标
   ========================================================================== */
.progress-track, .domain-bar .dtrack { background:var(--i200); border-radius:2px; }
.progress-fill, .domain-bar .dfill { background:var(--safety); border-radius:2px; }
.domain-bar .dname { color:var(--i700); font-size:13px; font-weight:600; }
.domain-bar .dval { color:var(--i500); font-size:12px; font-variant-numeric:tabular-nums; }
.metric { background:var(--i50); border:1px solid var(--i200); border-radius:var(--r-sm); padding:12px 12px; }
.metric strong { font-size:21px; color:var(--i950); font-weight:800; letter-spacing:-.02em; }
.metric span { font-size:12px; color:var(--i500); }

/* ==========================================================================
   11. 培训与案例
   ========================================================================== */
.training-card { padding:16px 2px; border-left:0; border-bottom:1px solid var(--i200); }
.training-card strong { font-size:13px; color:var(--i900); font-weight:700; }
.training-card p { font-size:12px; color:var(--i500); }
.training-card .tc-no { color:var(--safety); font-family:var(--mono); font-size:12px; font-weight:700; }
.case-card { padding:16px 2px; border-top:0; border-bottom:1px solid var(--i200); }
.case-card h3 { font-size:13px; color:var(--i900); font-weight:700; }
.case-card p { font-size:12px; color:var(--i600); }
.case-tag {
  background:var(--signal-100); color:#7a5a00; border-radius:var(--r-sm);
  font-size:12px; font-weight:700; padding:2px 8px;
}
.case-lesson {
  background:var(--green-bg); border-left:3px solid var(--green);
  border-radius:0 var(--r-sm) var(--r-sm) 0; color:#14532d; font-size:12px;
}

/* ==========================================================================
   12. 提示条
   ========================================================================== */
.warn-box {
  background:var(--amber-bg); border:1px solid #f0d9a8; border-left:4px solid var(--amber);
  color:#7a4a06; border-radius:0 var(--r-sm) var(--r-sm) 0; padding:12px 16px; font-size:13px;
}
.warn-box b { color:#7a4a06; }
.error-card {
  background:var(--red-bg); border:1px solid var(--danger-100); border-left:4px solid var(--red);
  border-radius:0 var(--r-sm) var(--r-sm) 0; color:#8f2110; padding:12px 16px; font-size:13px;
}
.error-card b { color:#8f2110; }

/* ==========================================================================
   13. 会话
   ========================================================================== */
.chat-stream { background:var(--i50); }
/* 头像与步骤序号：必须显式指定前景色。
   基础层里写着 var(--amber) on var(--i800)（对比度仅 3.21:1），
   原先被 V13 层压着，V13 归档后就露出来了。 */
.avatar {
  border-radius:var(--r-sm); background:var(--i800); color:#fff; font-weight:800;
}
.msg-row.from-user .avatar { background:var(--safety); color:#fff; }
.step-order {
  background:var(--safety); color:#fff; font-weight:800; border-radius:50%;
}
.bubble {
  background:var(--surface); border:1px solid var(--i200); border-radius:var(--r-lg);
  font-size:13px;
}
.msg-row.from-user .bubble { background:var(--i950); border-color:var(--i950); }
.bubble-title { color:var(--i900); font-size:13px; font-weight:800; }
.msg-row.from-user .bubble-title { color:#fff; }
.bubble-meta, .answer-meta { color:var(--i400); font-size:12px; }
.answer-body { color:var(--i600); line-height:1.8; }
.source-card { border-left:0; border-bottom:1px solid var(--i200); padding:12px 2px; }
.src-title, .source-card h5 { color:var(--i900); font-size:13px; font-weight:700; }
.source-card p { color:var(--i600); font-size:13px; }
.source-meta { color:var(--i400); font-size:12px; }

/* ==========================================================================
   14. 表格
   ========================================================================== */
.table-wrap { border:1px solid var(--i200); border-radius:var(--r-lg); }
th { background:var(--i950); color:#fff; font-size:12px; font-weight:700; letter-spacing:.03em; }
td { border-color:var(--i200); color:var(--i600); font-size:13px; }
tbody tr:hover { background:var(--safety-50); }

/* ==========================================================================
   15. 检索高亮
   ========================================================================== */
mark.hit { background:#ffe9a8; color:#5c4200; border-radius:2px; padding:0 2px; }

/* ==========================================================================
   16. 应急区
   ========================================================================== */
.emergency-hero {
  background:var(--i950); border:0; border-radius:var(--r-lg);
  padding:20px 24px; color:var(--i300);
}
.emergency-hero h2 { font-size:21px; color:#fff; font-weight:800; }
.emergency-hero p { color:var(--i400); font-size:13px; }
.emergency-card {
  border:1px solid var(--i200); border-radius:var(--r-lg); background:var(--surface); padding:16px;
}
.emergency-card:hover { border-color:var(--red); box-shadow:var(--shadow-2); }
.emergency-card strong { font-size:13px; color:var(--i900); font-weight:700; }
.emergency-card small { color:var(--i500); font-size:12px; }
.emergency-guide, .guide {
  background:var(--surface); border:1px solid var(--i200); border-left:4px solid var(--red);
  border-radius:var(--r-lg); padding:20px;
}
.em-step .em-num { background:var(--red); color:#fff; border-radius:var(--r-sm); font-weight:800; }
.em-never {
  background:var(--red-bg); border-left:4px solid var(--red);
  border-radius:0 var(--r-sm) var(--r-sm) 0; color:#8f2110; font-size:13px; font-weight:600;
}
.call-btn { background:var(--red); color:#fff; border-radius:var(--r-sm); font-weight:800; font-size:13px; }
.call-btn:hover { background:#9a2a17; }

/* ==========================================================================
   17. 证书
   ========================================================================== */
.certificate { background:#fff; border:2px solid var(--i950); border-radius:var(--r-lg); padding:24px 28px; }
.cert-kicker { color:var(--safety); font-family:var(--mono); font-size:12px; letter-spacing:.14em; font-weight:700; }
.certificate h3 { color:var(--i950); font-size:21px; font-weight:800; }
.cert-rule { background:var(--safety); height:3px; }
.certificate dt { color:var(--i500); font-size:13px; }
.certificate dd { color:var(--i900); font-weight:700; font-size:13px; }

/* ==========================================================================
   18. 阶段标签：编号 + 斜纹短条
   ========================================================================== */
.phase { margin-top:32px; }
.phase-title {
  color:var(--i900); font-size:13px; font-weight:800; letter-spacing:.1em;
  text-transform:uppercase;
}
.phase-desc { color:var(--i500); font-size:12px; }
.phase-rule {
  height:3px; background:repeating-linear-gradient(
    135deg, var(--i300) 0 5px, transparent 5px 10px
  ); margin:12px 0 20px;
}

/* ==========================================================================
   19. 页脚
   ========================================================================== */
footer { max-width:1024px; padding:20px 16px 48px; color:var(--i500); font-size:12px; }
.footer-line { border-top:3px solid var(--i950); padding-top:12px; }
.footer-line b { color:var(--i800); }

/* ==========================================================================
   20. 响应式
   ========================================================================== */
@media (max-width:992px) {
  main { padding:20px 16px 48px; }
  .header-inner, .nav-inner { padding-left:16px; padding-right:16px; }
  .hero h2 { font-size:27px; }
}
@media (max-width:640px) {
  body { font-size:13px; }
  main { padding:16px 12px 40px; }
  .entries, .home-actions { grid-template-columns:1fr; }
  .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .hero { padding:16px; border-left-width:4px; }
  .hero h2 { font-size:21px; }
  .hero-desc { font-size:13px; }
  .hero-stats { gap:8px 20px; }
  .hero-stats .stat-cell b { font-size:17px; }
  .panel-head, .panel-body { padding:16px; }
  .primary-button { width:100%; min-height:48px; }
  .nav-button { padding:12px 12px 12px; font-size:13px; }
  .action-card { padding:16px; }
}
/* ===== V15 THEME END ===== */

/* ===== V15 DARK BEGIN ===== */
/* ==========================================================================
   V15 暗色：深墨底 + 警示橙
   与亮色共用同一套规则，只覆盖令牌。
   作用域：[data-theme="dark"]
   ========================================================================== */
[data-theme="dark"] {
  color-scheme: dark;

  --i950:#0b0e11;
  --i900:#12161a;
  --i800:#f3f4f6;
  --i700:#d1d5db;
  --i600:#c3cad2;
  --i500:#8b93a1;
  --i400:#6b7480;
  --i300:#3a434e;
  --i200:#2a323b;
  --i100:#222932;
  --i50:#1b222a;
  --surface:#161c23;
  --canvas:#10151a;

  /* 警示橙在深底上要提亮 */
  --safety:#f97316;
  --safety-700:#ea580c;
  --safety-500:#fb923c;
  --safety-100:#3a2317;
  --safety-50:#2a1a12;

  --signal:#fbbf24;
  --signal-100:#3d3212;
  --signal-50:#2a2312;

  --red:#f87171;
  --red-bg:#2a1717;
  --amber:#fbbf24;
  --amber-bg:#2a2312;
  --green:#4ade80;
  --green-bg:#12291d;

  --shadow-1:0 1px 2px rgba(0,0,0,.4);
  --shadow-2:0 1px 3px rgba(0,0,0,.45);
  --shadow-3:0 4px 14px rgba(0,0,0,.5);
}

/* 顶栏与主行动卡在暗色下比页面更深，保持层次 */
[data-theme="dark"] header,
[data-theme="dark"] .action-card.is-primary,
[data-theme="dark"] .emergency-hero { background:#0b0e11; }

/* 警示斜纹在暗色下用亮橙，保持信号感 */
[data-theme="dark"] .top-band {
  background:repeating-linear-gradient(135deg, var(--safety) 0 10px, #0b0e11 10px 20px);
}
[data-theme="dark"] .phase-rule {
  background:repeating-linear-gradient(135deg, #3a434e 0 5px, transparent 5px 10px);
}

/* 主按钮：亮橙底配近黑字，深底上对比度最高 */
[data-theme="dark"] .primary-button,
[data-theme="dark"] .amber-button { background:var(--safety); color:#1a0d05; }
[data-theme="dark"] .primary-button:hover:not(:disabled),
[data-theme="dark"] .amber-button:hover:not(:disabled) { background:var(--safety-500); color:#1a0d05; }
[data-theme="dark"] .danger-button { background:var(--red); color:#2a0f0f; }
[data-theme="dark"] .danger-button:hover:not(:disabled) { background:#fca5a5; }
[data-theme="dark"] .filter-chip.active,
[data-theme="dark"] .role-chip.active { background:var(--safety); border-color:var(--safety); color:#1a0d05; }

/* 顶栏内元素 */
[data-theme="dark"] .hero-kicker { background:#0b0e11; color:#f3f4f6; }
[data-theme="dark"] .status-pill { background:rgba(255,255,255,.08); border-color:rgba(255,255,255,.14); color:#c3cad2; }
[data-theme="dark"] .status-pill.offline { background:rgba(251,191,36,.16); border-color:rgba(251,191,36,.36); color:#fcd34d; }

/* Hero */
[data-theme="dark"] .hero { background:var(--surface); border-color:var(--i200); border-left-color:var(--safety); }
[data-theme="dark"] .hero h2 { color:var(--i900); }
[data-theme="dark"] .hero h2 em { color:var(--safety); }
[data-theme="dark"] .hero-desc { color:var(--i600); }
[data-theme="dark"] .hero-chip { background:var(--i50); border-color:var(--i200); color:var(--i600); }
[data-theme="dark"] .hero-stats { border-color:var(--i200); }
[data-theme="dark"] .hero-stats .stat-cell b { color:var(--i900); }
[data-theme="dark"] .hero-stats .stat-cell.is-risk b { color:var(--red); }

/* 行动卡 */
[data-theme="dark"] .action-card { background:var(--surface); border-color:var(--i200); }
[data-theme="dark"] .action-card strong { color:var(--i900); }
[data-theme="dark"] .action-card p { color:var(--i500); }
[data-theme="dark"] .action-ico { background:var(--safety-100); }
[data-theme="dark"] .action-card.is-primary strong { color:#fff; }
[data-theme="dark"] .action-card.is-primary p { color:var(--i400); }
[data-theme="dark"] .action-card.is-primary .action-ico { background:var(--safety); }
[data-theme="dark"] .action-card.is-danger { background:var(--surface); border-color:#4a2a22; }
[data-theme="dark"] .action-card.is-danger .action-ico { background:var(--red-bg); }

/* 面板与表头 */
[data-theme="dark"] .panel,
[data-theme="dark"] .panel-head { background:var(--surface); border-color:var(--i200); }
[data-theme="dark"] .panel-head h2 { color:var(--i900); }
[data-theme="dark"] th { background:#0b0e11; color:#f3f4f6; }
[data-theme="dark"] td { border-color:var(--i200); color:var(--i600); }
[data-theme="dark"] tbody tr:hover { background:var(--safety-50); }

/* 清单与条目 */
[data-theme="dark"] .todo-item b,
[data-theme="dark"] .check-item b { color:var(--i900); }
[data-theme="dark"] .todo-item span,
[data-theme="dark"] .check-item small { color:var(--i500); }
[data-theme="dark"] .todo-item.done,
[data-theme="dark"] .check-item.checked,
[data-theme="dark"] .step-item.is-done { background:var(--green-bg); border-color:#2c5a3d; }
[data-theme="dark"] .todo-item.done b,
[data-theme="dark"] .check-item.checked b { color:var(--green); }
[data-theme="dark"] .todo-item:hover { background:var(--i50); }

/* 复选框：必须显式上色，否则浅字压白底看不见 */
[data-theme="dark"] input[type="checkbox"],
[data-theme="dark"] input[type="radio"] {
  background:var(--i50); border:1px solid var(--i300); accent-color:var(--safety);
}
[data-theme="dark"] input[type="checkbox"]:checked,
[data-theme="dark"] input[type="radio"]:checked { background:var(--safety); border-color:var(--safety); }

/* 提示条与标签 */
[data-theme="dark"] .warn-box { background:var(--amber-bg); border-color:#4a3a1e; color:#fcd34d; }
[data-theme="dark"] .warn-box b { color:#fcd34d; }
[data-theme="dark"] .error-card { background:var(--red-bg); border-color:#5a2b2b; color:#fca5a5; }
[data-theme="dark"] .error-card b { color:#fca5a5; }
[data-theme="dark"] .em-never { background:var(--red-bg); border-color:#5a2b2b; color:#fca5a5; }
[data-theme="dark"] .case-tag { background:var(--signal-100); color:var(--signal); }
[data-theme="dark"] .case-lesson { background:var(--green-bg); border-color:var(--green); color:#86efac; }
[data-theme="dark"] mark.hit { background:#4a3a10; color:#ffe9b0; }

/* 会话 */
[data-theme="dark"] .avatar { background:#3a434e; color:var(--surface); }
[data-theme="dark"] .msg-row.from-user .avatar { background:var(--safety); color:#1a0d05; }
[data-theme="dark"] .bubble { background:var(--i50); border-color:var(--i200); }
[data-theme="dark"] .msg-row.from-user .bubble { background:#3a2317; border-color:#4d2f1e; }
[data-theme="dark"] .bubble-title { color:var(--i900); }
[data-theme="dark"] .msg-row.from-user .bubble-title { color:#fdba74; }
[data-theme="dark"] .answer-body { color:var(--i600); }
[data-theme="dark"] .chat-stream { background:var(--canvas); }

/* 指标、进度 */
[data-theme="dark"] .metric { background:var(--i50); border-color:var(--i200); }
[data-theme="dark"] .metric strong { color:var(--i900); }
[data-theme="dark"] .progress-track,
[data-theme="dark"] .domain-bar .dtrack { background:#3a434e; }

/* 证书：打印目标，保持白底黑字 */
[data-theme="dark"] .certificate { background:#fff; border-color:#0b0e11; }
[data-theme="dark"] .certificate h3,
[data-theme="dark"] .certificate dd { color:#0b0e11; }
[data-theme="dark"] .certificate dt { color:#6b7480; }
[data-theme="dark"] .certificate .cert-kicker { color:#b23a0a; }
[data-theme="dark"] .certificate .cert-rule { background:#b23a0a; }
[data-theme="dark"] .certificate .cert-sign div { border-top-color:#98a1ac; color:#6b7480; }

/* 页脚 */
[data-theme="dark"] .footer-line { border-top-color:#f3f4f6; }
[data-theme="dark"] .footer-line b { color:var(--i700); }

/* 骨架屏 */
[data-theme="dark"] .sk {
  background:linear-gradient(90deg,#1b222a 25%,#242d37 37%,#1b222a 63%);
  background-size:400% 100%;
}

/* 打印始终走亮色 */
@media print {
  [data-theme="dark"] body { background:#fff; color:#000; }
  [data-theme="dark"] .certificate { background:#fff; color:#000; }
}

/* ==========================================================================
   修复：V15 主题层里有 14 处把「背景色令牌」当文字色用
   （--i950 / --i900 在暗色下是近黑，于是深字压深底，标题整片消失）。
   这里统一把这些选择器的文字色改为对两个主题都成立的中性色：
   --i800 在亮色下是 #22272e（深），在暗色下是 #f3f4f6（浅）。
   ========================================================================== */
[data-theme="dark"] .hero h2,
[data-theme="dark"] .hero-stats .stat-cell b,
[data-theme="dark"] .action-card strong,
[data-theme="dark"] .panel-head h2,
[data-theme="dark"] .todo-item b,
[data-theme="dark"] .check-item b,
[data-theme="dark"] .metric strong,
[data-theme="dark"] .training-card strong,
[data-theme="dark"] .case-card h3,
[data-theme="dark"] .bubble-title,
[data-theme="dark"] .src-title,
[data-theme="dark"] .source-card h5,
[data-theme="dark"] .emergency-card strong,
[data-theme="dark"] .phase-title {
  color: var(--i800);
}
[data-theme="dark"] .certificate h3,
[data-theme="dark"] .certificate dd { color: #0b0e11; }
/* ===== V15 DARK END ===== */

/* ===== V16 TIERS BEGIN ===== */
/* ==========================================================================
   V16 五档重量排版系统
   --------------------------------------------------------------------------
   为什么需要：第 15 轮全站 28 个 h2 对 1 个 h3、0 个 h4 —— 所有内容重量相同。
   "单调"的第一原因是层级扁平，不是配色。本层建立五档并用用量限制锁死。

     L1 Hero 带   视图开场的身份/场景 —— 深底 + 警示斜纹 + 一行结论，每视图 ≤1
     L2 指标条    可量化的状态 —— 等宽数字 + 单位 + 说明，每屏 ≤4 个数字
     L3 主行动卡  这一屏要我干什么 —— 琥珀描边 + 一个「动词+名词」按钮，每屏恰好 1
     L4 内容卡    列表/明细/表单 —— 白底细边，标题 15-16px，正文 15px
     L5 引用块    国标条款/来源/免责 —— 左 3px 色条 + 等宽编号 + 小字来源

   验收：任取一屏，冷读者 3 秒内能说出「这一屏要我干什么」。
   ========================================================================== */

/* ==========================================================================
   L1 — Hero 带
   深底 + 斜纹顶边 + 一行结论。每视图最多 1 处。
   ========================================================================== */
.tier-l1 {
  position: relative;
  background: var(--i950);
  color: #fff;
  border: 0;
  border-radius: var(--r-lg);
  padding:20px 24px 20px;
  margin-bottom:20px;
  overflow: hidden;
}
/* 斜纹顶边：身份元素，与页头同源 */
.tier-l1::before {
  content: "";
  position: absolute; left: 0; right: 0; top: 0; height: 5px;
  background: repeating-linear-gradient(
    135deg, var(--safety) 0 10px, var(--i950) 10px 20px
  );
}
.tier-l1 h2 {
  color: #fff; font-size: var(--fs-xl); font-weight: 800;
  line-height: 1.4; letter-spacing: -.01em; max-width: 24em;
}
.tier-l1 h2 em { color: var(--safety-500); font-style: normal; }
.tier-l1 .l1-kicker {
  display: inline-flex; align-items: center; gap:8px;
  font-size: var(--fs-xs); font-weight: 700; letter-spacing: .08em;
  color: var(--safety-500); margin-bottom:8px;
}
.tier-l1 .l1-kicker .ico { width: 15px; height: 15px; }
.tier-l1 .l1-lead {
  color: var(--i300); font-size: var(--fs-md); line-height: 1.7;
  margin-top:8px; max-width: 40em;
}
.tier-l1 .l1-foot {
  margin-top:16px; padding-top:12px;
  border-top: 1px solid rgba(255, 255, 255, .14);
  display: flex; flex-wrap: wrap; align-items: center; gap:8px 16px;
}
.tier-l1 .l1-foot .hint { color: var(--i400); font-size: var(--fs-xs); }

/* ==========================================================================
   L2 — 指标条
   等宽数字 + 单位 + 说明，最多 4 个数字。用分隔线而非卡片。
   ========================================================================== */
.tier-l2 {
  display: flex; flex-wrap: wrap; align-items: stretch;
  background: var(--surface);
  border: 1px solid var(--i200);
  border-radius: var(--r-lg);
  margin-bottom:20px;
  overflow: hidden;
}
.tier-l2 .l2-cell {
  flex: 1 1 150px; min-width: 130px;
  padding:16px 16px;
  border-right: 1px solid var(--i200);
  display: flex; flex-direction: column; gap:2px;
}
.tier-l2 .l2-cell:last-child { border-right: 0; }
.tier-l2 .l2-num {
  display: flex; align-items: baseline; gap:4px;
  font-family: var(--mono);
  font-size:27px; font-weight: 700; line-height: 1.15;
  color: var(--i900);
  font-variant-numeric: tabular-nums;
  letter-spacing: -.02em;
}
.tier-l2 .l2-num .unit { font-size: var(--fs-sm); font-weight: 700; color: var(--i500); }
.tier-l2 .l2-label { font-size: var(--fs-sm); font-weight: 700; color: var(--i700); }
.tier-l2 .l2-note { font-size: var(--fs-xs); color: var(--i500); }
.tier-l2 .l2-cell.is-risk .l2-num { color: var(--red); }
.tier-l2 .l2-cell.is-ok .l2-num { color: var(--green); }

/* ==========================================================================
   L3 — 主行动卡
   琥珀描边 + 恰好一个「动词+名词」按钮。每屏恰好 1 个。
   ========================================================================== */
.tier-l3 {
  position: relative;
  background: var(--surface);
  border: 2px solid var(--safety);
  border-radius: var(--r-lg);
  padding:20px 20px;
  margin-bottom:20px;
  box-shadow: 0 1px 3px rgba(178, 58, 10, .10);
}
.tier-l3::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
  background: var(--safety); border-radius: var(--r-lg) 0 0 var(--r-lg);
}
.tier-l3 .l3-head {
  display: flex; align-items: center; gap:8px; flex-wrap: wrap;
  margin-bottom:4px;
}
.tier-l3 h2 { font-size: var(--fs-lg); font-weight: 800; color: var(--i900); }
.tier-l3 .l3-badge {
  font-size: var(--fs-xs); font-weight: 700; letter-spacing: .04em;
  color: #fff; background: var(--safety);
  padding:2px 8px; border-radius: var(--r-sm);
}
.tier-l3 .l3-lead { font-size: var(--fs-md); color: var(--i600); line-height: 1.7; }
.tier-l3 .l3-action {
  display: flex; flex-wrap: wrap; align-items: center; gap:12px;
  margin-top:16px; padding-top:16px; border-top: 1px solid var(--i200);
}
.tier-l3 .l3-action .l3-hint { font-size: var(--fs-xs); color: var(--i500); }

/* ==========================================================================
   L3 内的进度行与计数
   ========================================================================== */
.tier-l3 .l3-progress {
  flex: 1; display: flex; align-items: center; gap:12px; min-width: 200px;
}
.tier-l3 .l3-progress .tier-progress { flex: 1; }
.tier-l3 .l3-count {
  font-family: var(--mono); font-size: var(--fs-md); font-weight: 700;
  color: var(--i700); font-variant-numeric: tabular-nums; white-space: nowrap;
}

/* L1 里的紧急求助入口：红字提示但仍是次级按钮 */
.ghost-button.is-emergency-link { color: var(--red); border-color: var(--danger-100); }
.ghost-button.is-emergency-link:hover { background: var(--red-bg); border-color: var(--red); }

/* L1 里的工种 chips（横排内联） */
.role-chips.is-inline { display: inline-flex; flex-wrap: wrap; gap:4px; }
.role-chips.is-inline .role-chip {
  padding:4px 12px; font-size: var(--fs-xs); min-height: 0;
}
/* 未选工种时的提示：深底上要浅色 */
.l1-rolehint {
  margin-top:12px; font-size: var(--fs-xs); line-height: 1.7;
  color: var(--i400);
}
.l1-rolehint.is-set { color: var(--safety-500); }

/* ==========================================================================
   L4 内容卡
   ========================================================================== */
.tier-l4 {
  background: var(--surface);
  border: 1px solid var(--i200);
  border-radius: var(--r-lg);
  margin-bottom:16px;
  overflow: hidden;
}
.tier-l4 > .l4-head {
  display: flex; align-items: center; gap:8px; flex-wrap: wrap;
  padding:12px 16px; border-bottom: 1px solid var(--i200);
}
.tier-l4 > .l4-head h2,
.tier-l4 > .l4-head h3 {
  font-size: var(--fs-base); font-weight: 800; color: var(--i900);
  letter-spacing: .01em;
}
.tier-l4 > .l4-head h3 { font-size: var(--fs-md); color: var(--i700); }
.tier-l4 > .l4-head .ico { width: 17px; height: 17px; color: var(--safety); flex: 0 0 17px; }
.tier-l4 > .l4-head .l4-note {
  margin-left: auto; font-size: var(--fs-xs); color: var(--i500);
}
.tier-l4 > .l4-body { padding:16px; }
.tier-l4 > .l4-body.is-flush { padding:0; }

/* L4 内的小标题层级：用 h3 建立真实的三级层次，不再全是 h2 */
.tier-l4 .l4-sub {
  font-size: var(--fs-sm); font-weight: 800; color: var(--i700);
  letter-spacing: .04em; text-transform: none;
  margin:16px 0 8px;
}
.tier-l4 .l4-sub:first-child { margin-top:0; }

/* ==========================================================================
   L5 — 引用块（国标条款 / 来源 / 免责）
   左 3px 色条 + 等宽编号 + 小字来源。
   ========================================================================== */
.tier-l5 {
  position: relative;
  background: var(--i50);
  border: 1px solid var(--i200);
  border-left: 3px solid var(--safety);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding:12px 16px;
  margin:12px 0;
}
.tier-l5 .l5-ref {
  display: flex; flex-wrap: wrap; align-items: center; gap:8px;
  margin-bottom:8px;
}
.tier-l5 .l5-code {
  font-family: var(--mono); font-size: var(--fs-xs); font-weight: 700;
  color: var(--i800); background: var(--surface);
  border: 1px solid var(--i300); border-radius: var(--r-sm);
  padding:2px 8px; letter-spacing: .02em;
}
.tier-l5 .l5-quote {
  font-size: var(--fs-md); color: var(--i700); line-height: 1.75;
}
.tier-l5 .l5-source {
  margin-top:8px; font-size: var(--fs-xs); color: var(--i500);
  display: flex; flex-wrap: wrap; align-items: center; gap:4px;
}
.tier-l5.is-caution { border-left-color: var(--amber); background: var(--amber-bg); }
.tier-l5.is-caution .l5-quote { color: #7a4a06; }
.tier-l5.is-danger { border-left-color: var(--red); background: var(--red-bg); }
.tier-l5.is-danger .l5-quote { color: #8f2110; }

/* 现行状态徽标（标准库用） */
.status-badge {
  display: inline-flex; align-items: center; gap:4px;
  font-size: var(--fs-xs); font-weight: 700;
  padding:2px 8px; border-radius: var(--r-sm);
  border: 1px solid transparent; white-space: nowrap;
}
.status-badge.is-active { color: #14532d; background: var(--green-bg); border-color: #b7dfc6; }
.status-badge.is-soon { color: #7a4a06; background: var(--amber-bg); border-color: #ecd9a8; }
.status-badge.is-dead { color: #8f2110; background: var(--red-bg); border-color: var(--danger-100); }
.status-badge::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: currentColor; flex: 0 0 6px;
}

/* ==========================================================================
   图标：内联 SVG，与 emoji 并存
   --------------------------------------------------------------------------
   决策依据（第 16 轮）：动作按钮用 SVG（风格统一、工地强光下清晰），
   emoji 保留在导航与状态标记（弱识字用户靠它快速扫读）。两者并存。
   ========================================================================== */
.ico {
  width: 18px; height: 18px; flex: 0 0 auto;
  display: inline-block; vertical-align: -3px;
  fill: none; stroke: currentColor; stroke-width: 1.8;
  stroke-linecap: round; stroke-linejoin: round;
}
.ico-lg { width: 24px; height: 24px; }
.ico-sm { width: 14px; height: 14px; }
.ico-xl { width: 30px; height: 30px; stroke-width: 1.6; }

/* 图标按钮：图标 + 文字，命中区 ≥44px */
.ico-button {
  display: inline-flex; align-items: center; gap:8px;
  min-height: 44px;
}

/* ==========================================================================
   风险三色环 + 进度环（纯 SVG stroke-dasharray）
   ========================================================================== */
.ring-wrap { display: flex; align-items: center; gap:16px; flex-wrap: wrap; }
.ring-figure { position: relative; width: 96px; height: 96px; flex: 0 0 96px; }
.ring-figure svg { transform: rotate(-90deg); display: block; }
.ring-figure .ring-bg { fill: none; stroke: var(--i200); stroke-width: 9; }
.ring-figure .ring-fg {
  fill: none; stroke: var(--safety); stroke-width: 9; stroke-linecap: round;
  transition: stroke-dashoffset .3s ease;
}
.ring-figure .ring-center {
  position: absolute; inset: 0; display: grid; place-items: center;
  text-align: center; line-height: 1.1;
}
.ring-figure .ring-num {
  font-family: var(--mono); font-size: 21px; font-weight: 700;
  color: var(--i900); font-variant-numeric: tabular-nums;
}
.ring-figure .ring-unit { font-size: var(--fs-xs); color: var(--i500); display: block; }
.ring-legend { display: flex; flex-direction: column; gap:8px; }
.ring-legend .row {
  display: flex; align-items: center; gap:8px;
  font-size: var(--fs-sm); color: var(--i700);
}
.ring-legend .dot { width: 10px; height: 10px; border-radius: 2px; flex: 0 0 10px; }
.ring-legend .dot.is-high { background: var(--red); }
.ring-legend .dot.is-mid { background: var(--amber); }
.ring-legend .dot.is-low { background: var(--green); }
.ring-legend b { font-family: var(--mono); font-variant-numeric: tabular-nums; }

/* 多段风险环：三段 arc 拼成一个环 */
.ring-figure .ring-seg {
  fill: none; stroke-width: 9;
  transition: stroke-dashoffset .3s ease;
}
.ring-figure .ring-seg.is-high { stroke: var(--red); }
.ring-figure .ring-seg.is-mid { stroke: var(--amber); }
.ring-figure .ring-seg.is-low { stroke: var(--green); }

/* ==========================================================================
   学习热力格（近 7 天）
   ========================================================================== */
.heat-grid { display: flex; gap:4px; }
.heat-cell {
  width: 26px; height: 26px; border-radius: var(--r-sm);
  background: var(--i100); border: 1px solid var(--i200);
  display: grid; place-items: center;
  font-size:12px; color: var(--i600);
}
/* 四档用同一套色相递进。3/4 档必须用深主色：
   --safety-500 配白字只有 4.01:1，达不到 4.5:1。*/
.heat-cell[data-level="1"] { background: #fbe3d5; border-color: #f2c9b0; color: #8f3a12; }
.heat-cell[data-level="2"] { background: #f5c4a3; border-color: #e8a97f; color: #7a3110; }
.heat-cell[data-level="3"] { background: var(--safety); border-color: var(--safety-700); color: #fff; }
.heat-cell[data-level="4"] { background: var(--safety-700); border-color: #6d2205; color: #fff; }
.heat-legend {
  display: flex; align-items: center; gap:4px;
  font-size: var(--fs-xs); color: var(--i500); margin-top:8px;
}

/* ==========================================================================
   测验正确率趋势（内联 SVG polyline）
   ========================================================================== */
.trend-figure { width: 100%; max-width: 420px; height: 108px; display: block; }
.trend-figure .axis { stroke: var(--i200); stroke-width: 1; }
.trend-figure .line {
  fill: none; stroke: var(--safety); stroke-width: 2.5;
  stroke-linejoin: round; stroke-linecap: round;
}
.trend-figure .area { fill: var(--safety-100); opacity: .55; }
.trend-figure .pt { fill: var(--safety); stroke: #fff; stroke-width: 2; }
.trend-figure .pt-label { font-size:12px; fill: var(--i500); font-family: var(--mono); }
.trend-empty {
  font-size: var(--fs-sm); color: var(--i700);
  padding:20px; text-align: center;
  background: var(--i50); border: 1px dashed var(--i300); border-radius: var(--r-sm);
}

/* ==========================================================================
   可点击领域分布图（点一下筛选标准库）
   ========================================================================== */
.domain-chart { display: flex; flex-direction: column; gap:8px; }
.domain-row {
  display: grid; grid-template-columns: minmax(90px, 150px) 1fr auto;
  align-items: center; gap:12px;
  padding:8px 8px; margin:0 -8px;
  border: 1px solid transparent; border-radius: var(--r-sm);
  background: none; text-align: left; width: 100%;
  cursor: pointer; font: inherit; color: inherit;
  transition: background .15s ease, border-color .15s ease;
}
.domain-row:hover { background: var(--safety-50); border-color: var(--safety-100); }
.domain-row.is-selected { background: var(--safety-100); border-color: var(--safety); }
.domain-row .dname { font-size: var(--fs-sm); font-weight: 700; color: var(--i700); }
.domain-row .dtrack {
  height: 9px; background: var(--i100); border-radius: 2px; overflow: hidden;
}
.domain-row .dfill {
  height: 100%; background: var(--safety); border-radius: 2px;
  transition: width .3s ease;
}
.domain-row .dval {
  font-family: var(--mono); font-size: var(--fs-xs); font-weight: 700;
  color: var(--i600); font-variant-numeric: tabular-nums; min-width: 34px; text-align: right;
}
.domain-row.is-selected .dname,
.domain-row.is-selected .dval { color: var(--safety-700); }

/* ==========================================================================
   应急处置时间轴（类型 → 步骤 → 电话）
   ========================================================================== */
.timeline { display: flex; flex-direction: column; gap:0; }
.tl-step {
  position: relative; display: flex; gap:12px;
  padding:0 0 16px 0;
}
.tl-step::before {
  content: ""; position: absolute;
  left: 15px; top: 32px; bottom: 0; width: 2px; background: var(--i200);
}
.tl-step:last-child::before { display: none; }
.tl-step .tl-no {
  flex: 0 0 32px; width: 32px; height: 32px; border-radius: 50%;
  display: grid; place-items: center; z-index: 1;
  font-family: var(--mono); font-size: var(--fs-md); font-weight: 700;
  background: var(--surface); color: var(--i500);
  border: 2px solid var(--i300);
}
.tl-step.is-current .tl-no {
  background: var(--red); color: #fff; border-color: var(--red);
}
.tl-step.is-done .tl-no {
  background: var(--green); color: #fff; border-color: var(--green);
}
.tl-step .tl-body { flex: 1; padding-top:4px; }
.tl-step .tl-body h4 {
  font-size: var(--fs-md); font-weight: 800; color: var(--i900); margin-bottom:2px;
}
.tl-step .tl-body p { font-size: var(--fs-sm); color: var(--i600); line-height: 1.7; }
.tl-step .tl-call { margin-top:8px; }

/* ==========================================================================
   进度条（统一）
   ========================================================================== */
.tier-progress {
  height: 7px; background: var(--i100); border-radius: 3px; overflow: hidden;
}
.tier-progress > i {
  display: block; height: 100%; background: var(--safety);
  border-radius: 3px; transition: width .3s ease;
}
.tier-progress.is-ok > i { background: var(--green); }

/* ==========================================================================
   动效：每个都说明它解释哪个状态变化
   ========================================================================== */
/* 视图切换 —— 解释「我在哪一屏」 */
@keyframes v16ViewIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.view.active { animation: v16ViewIn .24s ease both; }

/* 判分对错 —— 解释「这题答对/答错」 */
@keyframes v16MarkIn {
  from { opacity: 0; transform: scale(.86); }
  to   { opacity: 1; transform: scale(1); }
}
.is-correct .ico, .is-wrong .ico { animation: v16MarkIn .26s ease both; }

/* 提交成功 —— 解释「回答已生成」 */
@keyframes v16AnswerIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.bubble.is-new { animation: v16AnswerIn .2s ease both; }

/* 骨架屏 —— 解释「正在加载」，布局不跳动 */
@keyframes v16Shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -200% 0; }
}
.tier-skeleton {
  background: linear-gradient(90deg, var(--i100) 25%, var(--i50) 37%, var(--i100) 63%);
  background-size: 400% 100%;
  animation: v16Shimmer 1.2s ease-in-out infinite;
  border-radius: var(--r-sm);
}

/* ==========================================================================
   响应式：手机 390×844 是主要目标
   --------------------------------------------------------------------------
   注意：真机 390px 下导航原本会溢出（nav-inner scrollWidth 419 > clientWidth 390），
   最后一个「学习与资料」被推到视口外，靠横向滑动才能看到 —— 实测发现。
   手机端改为自动换行，5 个标签两行放完，全部可见。
   ========================================================================== */
@media (max-width: 640px) {
  .nav-inner { flex-wrap: wrap; overflow-x: visible; padding:0 12px; gap:0; }
  .nav-button { padding:12px 12px 8px; font-size: var(--fs-sm); flex: 0 0 auto; }
  .nav-button.emergency-tab { margin-left:0; }

  .tier-l1 { padding:16px 16px 16px; }
  .tier-l1 h2 { font-size: var(--fs-lg); }
  .tier-l1 .l1-lead { font-size: var(--fs-sm); }

  .tier-l2 .l2-cell { flex: 1 1 45%; min-width: 0; padding:12px 12px; }
  .tier-l2 .l2-cell:nth-child(2n) { border-right: 0; }
  .tier-l2 .l2-cell:nth-child(-n+2) { border-bottom: 1px solid var(--i200); }
  .tier-l2 .l2-num { font-size: 21px; }

  .tier-l3 { padding:16px 16px; }
  .tier-l3 .l3-action { flex-direction: column; align-items: stretch; }
  .tier-l3 .l3-action .primary-button,
  .tier-l3 .l3-action .amber-button { width: 100%; min-height: 48px; }

  .tier-l4 > .l4-head { padding:12px 16px; }
  .tier-l4 > .l4-head .l4-note { margin-left:0; width: 100%; }
  .tier-l4 > .l4-body { padding:16px; }

  .ring-figure { width: 82px; height: 82px; flex-basis: 82px; }
  .ring-figure .ring-num { font-size:17px; }

  .trend-figure { height: 92px; }
  .domain-row { grid-template-columns: minmax(76px, 104px) 1fr auto; gap:8px; }
  .heat-cell { width: 22px; height: 22px; }
}

/* 打印：引用块与免责要清楚 */
@media print {
  .tier-l1 { background: #fff; color: #000; border: 1px solid #999; }
  .tier-l1::before { display: none; }
  .tier-l1 h2 { color: #000; }
  .tier-l1 .l1-lead { color: #333; }
}

/* ==========================================================================
   每日警示案例（首页 L4 内容卡）
   ========================================================================== */
.case-daily { display: flex; flex-direction: column; gap: 10px; }
.case-daily-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.case-daily-date {
  font-family: var(--mono); font-size: var(--fs-xs); color: var(--i500);
  font-variant-numeric: tabular-nums;
}
.case-daily-title {
  font-size: var(--fs-lg); font-weight: 800; color: var(--i900);
  line-height: 1.5; max-width: 34em;
}
.case-daily-what,
.case-daily-why {
  font-size: var(--fs-md); color: var(--i600); line-height: 1.75;
  max-width: 40em;
}
.case-daily-what b,
.case-daily-why b { color: var(--i800); font-weight: 700; }
.case-daily-lesson {
  background: var(--risk-low-bg); border-left: 3px solid var(--risk-low);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding: 11px 13px; font-size: var(--fs-md); color: #14532d;
  line-height: 1.7; max-width: 40em;
}
.case-daily-lesson b { color: #14532d; font-weight: 800; }
.case-daily-foot {
  display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
  margin-top: 4px; padding-top: 12px; border-top: 1px solid var(--line);
}
.case-daily-source { font-size: var(--fs-xs); color: var(--i500); }
.case-empty { padding: 6px 0; }
.case-empty p { font-size: var(--fs-md); color: var(--i600); }
.case-empty-hint { font-size: var(--fs-sm); color: var(--i500); margin-top: 4px; }
[data-theme="dark"] .case-daily-lesson { background: var(--risk-low-bg); color: #86efac; }
[data-theme="dark"] .case-daily-lesson b { color: #86efac; }

/* ==========================================================================
   图表区块（热力格 / 趋势图）—— §7 图形语言
   ========================================================================== */
.chart-block {
  margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--i200);
}
.chart-block:first-of-type { border-top: 0; padding-top: 0; }
.chart-block #quizTrend { margin-top: 4px; }

/* ==========================================================================
   §6 应急处置页：全站最醒目的一页
   --------------------------------------------------------------------------
   用户明确要求："现在 6 张等高白卡 + 小灰字，是全站最不醒目的一页"。
   做法：红警带替换深蓝 hero、大卡片带描边分级、时间轴、✗/✓ 对照、吸底电话。
   ========================================================================== */

/* ---- 红警带 ---- */
.sos-alert {
  background: linear-gradient(135deg, #b3261e 0%, #8f1d17 100%);
  color: #fff; border-radius: var(--r-lg);
  padding: 20px 24px; margin-bottom: 20px;
  border-left: 5px solid var(--accent);
}
.sos-alert-main { display: flex; align-items: flex-start; gap: 16px; }
.sos-alert-main > .ico { flex: 0 0 auto; margin-top: 2px; color: #ffd9a0; }
.sos-alert-text { min-width: 0; }
.sos-alert-title {
  font-size: var(--fs-2xl); font-weight: 800; color: #fff;
  letter-spacing: .02em; line-height: 1.25;
}
.sos-alert-chant {
  display: flex; align-items: center; gap: 12px;
  margin-top: 8px; font-size: var(--fs-xl); font-weight: 800;
}
.sos-alert-chant span {
  display: inline-grid; place-items: center;
  width: 40px; height: 40px; border-radius: 50%;
  background: #fff; color: #b3261e; font-size: var(--fs-lg);
}
.sos-alert-chant i { font-style: normal; color: #ffd9a0; font-size: var(--fs-lg); }
.sos-alert-sub {
  margin-top: 12px; font-size: var(--fs-md); color: #ffe8d0; font-weight: 600;
}
.sos-alert-note {
  margin-top: 12px; padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, .28);
  font-size: var(--fs-sm); color: #ffd9c4; line-height: 1.6;
}

/* ---- 事故类型：大卡片 ---- */
.emergency-grid {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.emergency-card {
  min-height: 120px; padding: 16px;
  display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
  background: #fff; border: 2px solid var(--line);
  border-radius: var(--r-md); cursor: pointer; text-align: left;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.emergency-card > .ico { color: var(--brand); }
.emergency-card.is-critical { border-color: #b3261e; }
.emergency-card.is-critical > .ico { color: #b3261e; }
.emergency-card.is-urgent { border-color: #d9871f; }
.emergency-card.is-urgent > .ico { color: #a86400; }
.emergency-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-2); }
.emergency-card:focus-visible { outline: 3px solid var(--brand); outline-offset: 2px; }
.em-card-title { font-size: var(--fs-lg); font-weight: 800; color: var(--i900); }
.em-card-lead {
  font-size: var(--fs-sm); color: var(--i600); line-height: 1.6;
}
.em-card-dial {
  margin-top: auto; display: inline-flex; align-items: center; gap: 4px;
  font-family: var(--mono); font-size: var(--fs-xs); font-weight: 700;
  color: var(--brand);
}

/* ---- 处置步骤：时间轴 ---- */
.em-timeline { list-style: none; margin: 16px 0 0; padding: 0; }
.em-tl-item {
  position: relative; display: flex; align-items: flex-start; gap: 12px;
  padding: 0 0 16px 0;
}
.em-tl-item:last-child { padding-bottom: 0; }
.em-tl-item::before {
  content: ""; position: absolute; left: 12px; top: 28px; bottom: 0;
  width: 2px; background: var(--line);
}
.em-tl-item:last-child::before { display: none; }
.em-tl-num {
  position: relative; z-index: 1; flex: 0 0 28px;
  width: 28px; height: 28px; border-radius: 50%;
  display: inline-grid; place-items: center;
  background: #b3261e; color: #fff;
  font-family: var(--mono); font-size: var(--fs-sm); font-weight: 800;
}
.em-tl-text { font-size: var(--fs-md); color: var(--i700); line-height: 1.7; padding-top: 3px; }

/* ---- ✗ / ✓ 左右对照 ---- */
.em-compare {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px; margin-top: 20px;
}
.em-compare-col { border-radius: var(--r-md); padding: 12px 16px; }
.em-compare-col.is-bad {
  background: var(--risk-high-bg); border-left: 4px solid var(--risk-high);
}
.em-compare-col.is-good {
  background: var(--risk-low-bg); border-left: 4px solid var(--risk-low);
}
.em-compare-head { display: block; font-size: var(--fs-sm); font-weight: 800; margin-bottom: 5px; }
.em-compare-col.is-bad .em-compare-head { color: var(--risk-high-text); }
.em-compare-col.is-good .em-compare-head { color: var(--risk-low-text); }
.em-compare-col p { font-size: var(--fs-sm); line-height: 1.7; color: var(--i700); }

/* ---- 电话按钮吸底 ---- */
.em-calls {
  position: sticky; bottom: 0; z-index: 20;
  display: flex; flex-wrap: wrap; gap: 12px;
  margin-top: 20px; padding: 12px 0;
  background: linear-gradient(to top, var(--surface) 70%, transparent);
}
.em-calls .is-call { min-height: 52px; font-size: var(--fs-lg); flex: 1 1 auto; justify-content: center; }

/* ---- 全站 SOS 浮动按钮 ---- */
.sos-fab {
  position: fixed; right: 20px; bottom: 20px; z-index: 900;
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 16px; border-radius: 999px;
  background: #b3261e; color: #fff; font-weight: 800;
  font-size: var(--fs-md); text-decoration: none;
  box-shadow: 0 6px 18px rgba(179, 38, 30, .38);
  transition: transform .15s ease;
}
.sos-fab:hover { transform: scale(1.04); color: #fff; }
.sos-fab:focus-visible { outline: 3px solid var(--brand); outline-offset: 3px; }
.sos-fab-text { letter-spacing: .04em; }

@media (max-width: 900px) {
  .emergency-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .emergency-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .emergency-card { min-height: 132px; padding: 12px; }
  .em-card-title { font-size: var(--fs-md); }
  .em-compare { grid-template-columns: minmax(0, 1fr); }
  .sos-alert { padding: 16px; }
  .sos-alert-chant span { width: 36px; height: 36px; }
  .em-calls { flex-direction: column; }
  .em-calls .is-call { width: 100%; }
  .sos-fab { right: 12px; bottom: 12px; padding: 12px 16px; }
  .sos-fab-text { display: none; }
}

/* 图标尺寸阶梯：ico 默认 18，sm 14，xl 24，2xl 36（应急卡与红警带用） */
.ico-2xl { width: 36px; height: 36px; }
.ico-xl { width: 24px; height: 24px; }

/* ==========================================================================
   §7 方向 2：首页「班前 5 分钟」四步动线
   --------------------------------------------------------------------------
   用户要求"不合并"勾选项，所以 5 条全保留，只按步骤归位。
   好处：阅读变成一条动线，而不是 5 条平行清单。
   ========================================================================== */
.flow-step { margin-bottom: 16px; }
.flow-step:last-child { margin-bottom: 0; }
.flow-step-head {
  display: flex; align-items: flex-start; gap: 12px;
  margin-bottom: 8px;
}
.flow-step-num {
  flex: 0 0 28px; width: 28px; height: 28px; border-radius: 50%;
  display: inline-grid; place-items: center;
  background: var(--brand); color: #fff;
  font-family: var(--mono); font-size: var(--fs-sm); font-weight: 800;
}
.flow-step-titles { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; }
.flow-step-title { font-size: var(--fs-md); font-weight: 800; color: var(--i900); }
.flow-step-note { font-size: var(--fs-xs); color: var(--i500); }
.flow-step .todo-list { margin: 0 0 0 40px; }
[data-theme="dark"] .flow-step-num { background: var(--brand); color: #10151a; }

@media (max-width: 640px) {
  .flow-step .todo-list { margin-left: 0; }
}

/* ==========================================================================
   §7 方向 5：工种专项对比式教学排版
   --------------------------------------------------------------------------
   原来「常见风险 / 必守规矩 / 典型违规 / 防护用品」四块等宽并排，
   读起来是四个平行清单，看不出"违规 ↔ 正确做法"的对应关系。
   改为：风险与防护用品独立成行，违规与规矩左右对撞。
   ========================================================================== */
.role-block-wide { grid-column: 1 / -1; }
/* 基础层有 `.role-block ul { display:grid }`（特异性 0,1,1），
   所以这里必须写成 `.role-block .role-chip-list`（同为 0,1,1 且位置更后）
   才能把 display 改回 flex —— 只写 .role-chip-list 会被它压过，
   结果 li 变成 grid 项、宽度撑满整行。 */
.role-block .role-chip-list {
  display: flex; flex-wrap: wrap; gap: 8px;
  list-style: none; margin: 0; padding: 0;
}
/* 注意：.role-chip 已被 #roleChips 的工种选择按钮占用，
   这里必须限定在 .role-chip-list 内，否则会改坏工种选择器。 */
.role-chip-list .role-chip {
  flex: 0 0 auto; width: auto;
  padding: 4px 12px; border-radius: 999px;
  background: var(--surface-soft); border: 1px solid var(--line);
  font-size: var(--fs-sm); color: var(--i700);
  white-space: nowrap;
}
.role-block.is-danger .role-chip-list .role-chip {
  background: var(--risk-high-bg); border-color: var(--risk-high);
  color: var(--risk-high-text);
}

.role-compare {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px; margin-top: 12px;
}
.role-compare-col { border-radius: var(--r-md); padding: 12px 16px; }
.role-compare-col.is-wrong {
  background: var(--risk-high-bg); border-left: 4px solid var(--risk-high);
}
.role-compare-col.is-right {
  background: var(--risk-low-bg); border-left: 4px solid var(--risk-low);
}
.role-compare-head {
  display: block; font-size: var(--fs-md); font-weight: 800; margin-bottom: 6px;
}
.role-compare-col.is-wrong .role-compare-head { color: var(--risk-high-text); }
.role-compare-col.is-right .role-compare-head { color: var(--risk-low-text); }
.role-compare-col ul { margin: 0; padding-left: 18px; }
.role-compare-col li {
  font-size: var(--fs-sm); line-height: 1.7; color: var(--i700); margin-bottom: 4px;
}
.role-compare-col li:last-child { margin-bottom: 0; }
.role-block + .role-block { margin-top: 12px; }

@media (max-width: 640px) {
  .role-compare { grid-template-columns: minmax(0, 1fr); }
}

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
  flex: 0 0 auto; min-height: 40px; padding: 8px 16px;
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
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px;
  padding-bottom: 8px; margin-bottom: 8px;
  border-bottom: 2px solid var(--line);
}
.check-group-title { font-size: var(--fs-md); font-weight: 800; color: var(--i900); }
.check-group-note { font-size: var(--fs-xs); color: var(--i500); }
.check-item { align-items: flex-start; }
.check-item .check-main { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.check-item .check-text { font-size: var(--fs-md); color: var(--i800); line-height: 1.6; }
.check-item .check-judge { font-size: var(--fs-sm); color: var(--i500); line-height: 1.6; }
.check-item .check-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 4px;
}
.check-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 8px; border-radius: 999px;
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
  padding: 12px 16px; background: var(--surface-soft);
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
  display: flex; flex-wrap: wrap; gap: 12px; padding: 12px 16px;
  background: var(--surface-soft); border-top: 1px solid var(--line);
}
.import-list { display: flex; flex-direction: column; gap: 8px; }
.import-sample {
  font-family: var(--mono); font-size: var(--fs-xs); line-height: 1.7;
  background: var(--surface-soft); border: 1px solid var(--line);
  border-radius: var(--r-sm); padding: 12px; overflow-x: auto;
  white-space: pre; color: var(--i700); margin: 0;
}
.row-actions { display: flex; flex-wrap: wrap; gap: 12px; }

@media (max-width: 640px) {
  .shift-chip { flex: 1 1 calc(50% - 8px); justify-content: center; }
  .row-actions .ico-button { width: 100%; justify-content: center; }
  .import-preview { overflow-x: auto; }
}

/* 检查项目索引（§11 前端拆分后的独立区块） */
.index-cat { margin-bottom: 14px; }
.index-cat:last-child { margin-bottom: 0; }
.index-cat-head {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px;
  margin-bottom: 6px;
}
.index-cat-name { font-size: var(--fs-md); font-weight: 800; color: var(--i900); }
.index-cat-scope { font-size: var(--fs-xs); color: var(--i500); }
.index-cat-list { margin: 0; padding-left: 20px; }
.index-cat-list li {
  font-size: var(--fs-sm); line-height: 1.7; color: var(--i700); margin-bottom: 4px;
}

/* ==========================================================================
   回答正文排版（§3.3：模型返回 Markdown，需要正确渲染）
   ========================================================================== */
.answer-body .answer-line { margin: 0 0 8px; }
.answer-body .answer-line:last-child { margin-bottom: 0; }
.answer-body .answer-line strong { color: var(--i900); font-weight: 800; }
.answer-body .answer-list { margin: 0 0 8px; padding-left: 20px; }
.answer-body .answer-list li { margin-bottom: 4px; line-height: 1.75; }
.answer-body .answer-list li strong { color: var(--i900); font-weight: 800; }

/* ==========================================================================
   规范依据区（§16 线上乱码修复）
   --------------------------------------------------------------------------
   原来把整段检索原文倒出来，JGJ59 的评分表碎片淹没了答案。
   现在收进 details 默认收起，正文只给清理后的预览。
   ========================================================================== */
.src-details { margin-top: 4px; }
.src-details > summary {
  cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px;
}
.src-details > summary::-webkit-details-marker { display: none; }
.src-details > summary::before {
  content: ""; width: 0; height: 0; flex: 0 0 auto;
  border-left: 5px solid currentColor;
  border-top: 4px solid transparent; border-bottom: 4px solid transparent;
  transition: transform .15s ease;
}
.src-details[open] > summary::before { transform: rotate(90deg); }
.source-excerpt {
  font-size: var(--fs-sm); line-height: 1.75; color: var(--i600);
  max-width: 42em;
}
.source-excerpt.is-empty { color: var(--i400); font-style: normal; }
.source-list { margin-top: 12px; }

/* ==========================================================================
   等待提示（第 20 轮 §2）
   ========================================================================== */
.thinking-hint {
  margin-top: 8px; font-size: var(--fs-xs); color: var(--i500);
  font-variant-numeric: tabular-nums;
}
.thinking-hint.is-slow { color: var(--risk-mid-text); font-weight: 700; }

/* ==========================================================================
   §3 渐进披露（第 20 轮）
   --------------------------------------------------------------------------
   手机端页面过长：首页 3310px、班前 5129px、学习资料 6000px。
   用原生 details 收起次要内容，首屏只留主任务。
   ========================================================================== */
.disclosure {
  border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--surface); margin-top: 16px; overflow: hidden;
}
.disclosure > summary {
  cursor: pointer; list-style: none; padding: 14px 16px;
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  font-size: var(--fs-md); font-weight: 800; color: var(--i800);
}
.disclosure > summary::-webkit-details-marker { display: none; }
.disclosure > summary::before {
  content: ""; width: 0; height: 0; flex: 0 0 auto;
  border-left: 6px solid currentColor;
  border-top: 5px solid transparent; border-bottom: 5px solid transparent;
  transition: transform .15s ease;
}
.disclosure[open] > summary::before { transform: rotate(90deg); }
.disclosure > summary:hover { color: var(--brand); }
.disclosure-hint {
  margin-left: auto; font-size: var(--fs-xs); font-weight: 400; color: var(--i500);
}
.disclosure-body { padding: 0 16px 16px; }

/* 手机端：折叠区更省空间 */
@media (max-width: 640px) {
  .disclosure > summary { padding: 12px; font-size: var(--fs-base); }
  .disclosure-body { padding: 0 12px 12px; }
}

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
.call-button.is-fire { background: #bf4a1a; color: #fff; }
.call-button.is-fire:hover { background: #a33d13; color: #fff; }
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

/* ==========================================================================
   §5-1 KPI 指标条（第 21 轮）
   --------------------------------------------------------------------------
   原来 4 个格子等权，看不出哪个和自己有关。
   现在：主格（我的安全知识，带环形图）+ 3 个支撑格。
   环形图只用真实分母，不编造百分比。
   ========================================================================== */
.tier-l2 { align-items: stretch; }
.l2-cell.is-primary {
  /* 基础 .l2-cell 是 column，主格要横向排列环形图与文字 */
  display: flex; flex-direction: row; align-items: center; gap: 16px;
  flex: 1 1 260px;
  background: linear-gradient(135deg, var(--brand-050), var(--surface) 62%);
  border-color: var(--brand-100);
}
.l2-ring-wrap { position: relative; width: 64px; height: 64px; flex: 0 0 auto; }
.l2-ring { width: 64px; height: 64px; display: block; transform: rotate(-90deg); }
.l2-ring-track {
  fill: none; stroke: var(--brand-100); stroke-width: 6;
}
.l2-ring-fill {
  fill: none; stroke: var(--accent); stroke-width: 6; stroke-linecap: round;
  transition: stroke-dashoffset .6s cubic-bezier(.22,.61,.36,1);
}
.l2-ring-center {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-variant-numeric: tabular-nums; pointer-events: none;
}
.l2-ring-pct { font-size: var(--fs-md); font-weight: 800; color: var(--brand); }
.l2-ring-unit { font-size: var(--fs-xs); color: var(--i500); margin-left: 0; }
.l2-primary-text { min-width: 0; }
.l2-num-sm { font-size: var(--fs-xl); }

@media (max-width: 640px) {
  .l2-cell.is-primary { flex: 1 1 100%; }
  .l2-ring-wrap, .l2-ring { width: 56px; height: 56px; }
}

@media (prefers-reduced-motion: reduce) {
  .l2-ring-fill { transition: none; }
}

/* ==========================================================================
   §5-3 案例对照卡（第 21 轮）
   --------------------------------------------------------------------------
   桌面双栏对照，移动端上下堆叠。
   左「错误做法」用克制的危险色，右「正确做法」用成功色，
   但两侧都有图标 + 文字标签，不单纯依赖颜色表意。
   ========================================================================== */
.case-compare {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
  margin: 12px 0 4px;
}
.case-side {
  border-radius: var(--r-sm); padding: 12px 16px;
  border: 1px solid var(--line); background: var(--surface);
  min-width: 0;
}
.case-side.is-wrong { border-left: 4px solid var(--risk-high); background: var(--risk-high-bg); }
.case-side.is-right { border-left: 4px solid var(--risk-low); background: var(--risk-low-bg); }
.case-side-head {
  display: flex; align-items: center; gap: 8px;
  font-size: var(--fs-sm); margin-bottom: 8px;
}
.case-side.is-wrong .case-side-head { color: var(--risk-high-text); }
.case-side.is-right .case-side-head { color: var(--risk-low-text); }
.case-side-body {
  margin: 0; font-size: var(--fs-sm); line-height: 1.7; color: var(--i700);
}
.case-side-body.is-empty { color: var(--i500); }
.case-why {
  display: flex; gap: 8px; align-items: flex-start;
  margin-top: 12px; padding-top: 12px;
  border-top: 1px dashed var(--line);
  font-size: var(--fs-xs); line-height: 1.7; color: var(--i600);
}
.case-outcome {
  margin-top: 12px; padding-top: 12px;
  border-top: 1px dashed var(--line);
  font-size: var(--fs-xs); line-height: 1.7; color: var(--i600);
}

@media (max-width: 720px) {
  .case-compare { grid-template-columns: 1fr; gap: 12px; }
}

/* 微交互：案例卡展开（§5-5） */
.case-detail {
  animation: caseReveal .22s ease-out;
}
@keyframes caseReveal {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  .case-detail { animation: none; }
}

/* ==========================================================================
   §5-4 线稿插画（第 21 轮）
   --------------------------------------------------------------------------
   四张统一风格工程线稿：临边防护 / 脚手架 / PPE 六件套 / 应急三步骤。
   全部 currentColor，随主题变色，无外部图片依赖。
   ========================================================================== */
.ill-figure {
  margin: 0; padding: 12px 16px;
  border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--surface-soft);
  color: var(--brand-600);
}
.ill-figure > svg {
  display: block; width: 100%; height: auto;
  max-width: 420px; margin: 0 auto;
  fill: none; stroke: currentColor; stroke-width: 1.6;
  stroke-linecap: round; stroke-linejoin: round;
}
.ill-figure figcaption {
  margin-top: 8px; font-size: var(--fs-xs); line-height: 1.6;
  color: var(--i600); text-align: center;
}
.ill-figure.is-compact > svg { max-width: 300px; }

/* 插画内的文字不要描边 */
.ill-figure > svg text { stroke: none; fill: currentColor; }

@media (max-width: 640px) {
  .ill-figure { padding: 12px; }
}

.ill-figure.ill-ppe { color: var(--brand-600); }
.ill-figure.ill-edge { color: var(--brand-500); }
.ill-figure.ill-scaffold { color: var(--brand-500); }
/* 修：应急插画原来被套上红边框 + 粉底，看起来像「报警框」。
   插画就是插画，用中性容器，不抢红警带的语义。 */
.ill-figure.ill-emergency {
  color: var(--brand-700);
  border: 1px solid var(--line);
  border-left-width: 1px;
  background: var(--surface-soft);
}

/* ==========================================================================
   §5-5 微交互（第 21 轮）
   --------------------------------------------------------------------------
   轻量、只动 transform / opacity，<=300ms，全部尊重 prefers-reduced-motion。
   勾选状态本身由业务逻辑写入，动画只做视觉确认，不代替状态。
   ========================================================================== */
.check-item { transition: background-color .18s ease, border-color .18s ease; }
.check-item.checked { background: var(--risk-low-bg); border-color: var(--risk-low); }
.check-item .check-box,
.check-item input[type="checkbox"] {
  transition: transform .16s cubic-bezier(.34,1.56,.64,1), background-color .16s ease;
}
.check-item.checked .check-box { transform: scale(1.06); }

/* 进度条 / 进度环数字变化时的轻推 */
.step-item.is-done .step-order { transition: background-color .2s ease; }

@media (prefers-reduced-motion: reduce) {
  .check-item, .check-item .check-box, .check-item input[type="checkbox"],
  .step-item.is-done .step-order { transition: none; }
  .check-item.checked .check-box { transform: none; }
}

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
  border: 2px solid var(--accent); color: var(--risk-mid-text);
  background: var(--accent-050);
}
.workbench-primary:hover {
  background: var(--accent-100); border-color: var(--accent-600); color: var(--risk-mid-text);
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

/* ==========================================================================
   第 24 轮 A · 识别结果结构化渲染
   --------------------------------------------------------------------------
   后端一直返回 structured，前端却只显示纯文本。这里按真实字段分四段呈现：
   结论 / 风险位置与现象 / 整改建议 / 待确认，并保留免责声明。
   ========================================================================== */
.ins-result { display: flex; flex-direction: column; gap: 16px; }
.ins-block {
  border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--surface); padding: 16px;
}
.ins-block-title {
  margin: 0 0 12px; font-size: var(--fs-md); font-weight: 800; color: var(--brand);
  display: flex; align-items: center; gap: 8px;
}

/* A 结论 */
.ins-summary { background: var(--brand-050); border-color: var(--brand-100); }
.ins-worktype { margin: 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
.ins-worktype-label {
  flex: 0 0 auto; padding: 2px 8px; border-radius: var(--r-sm);
  background: var(--brand); color: #fff; font-size: var(--fs-xs); font-weight: 800;
}
.ins-worktype-value { font-size: var(--fs-base); font-weight: 800; color: var(--i900); }
.ins-worktype.is-empty { font-size: var(--fs-sm); color: var(--i600); line-height: 1.7; }
.ins-metric { margin-top: 12px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.ins-metric-num {
  font-family: var(--mono); font-size: 34px; font-weight: 800; color: var(--brand);
  line-height: 1;
}
.ins-metric-unit { font-size: var(--fs-sm); color: var(--i600); }
.ins-metric-note {
  padding: 2px 8px; border-radius: var(--r-sm);
  background: var(--accent-100); color: var(--risk-mid-text);
  font-size: var(--fs-xs); font-weight: 800;
}

/* B 风险条目 */
.ins-risk-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.ins-risk {
  border-left: 4px solid var(--risk-mid); border-radius: var(--r-sm);
  background: var(--surface-soft); padding: 12px 16px;
}
.ins-risk-where {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--fs-xs); font-weight: 800; color: var(--brand-600);
  background: var(--brand-050); border-radius: var(--r-sm);
  padding: 2px 8px; margin-bottom: 8px;
}
.ins-risk-what { margin: 0; font-size: var(--fs-base); line-height: 1.7; color: var(--i800); }
.ins-risk-action {
  display: flex; align-items: flex-start; gap: 6px;
  margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--line);
  font-size: var(--fs-sm); line-height: 1.7; color: var(--risk-low-text);
}
.ins-note { margin: 12px 0 0; font-size: var(--fs-xs); line-height: 1.7; color: var(--i600); }
.ins-clean { border-left: 4px solid var(--risk-low); }
.ins-pending { border-left: 4px solid var(--risk-mid); background: var(--risk-mid-bg); }
.ins-pending-list {
  margin: 0; padding-left: 20px;
  font-size: var(--fs-sm); line-height: 1.7; color: var(--i700);
}
.ins-disclaimer {
  margin: 0; padding: 12px 16px; border-radius: var(--r-sm);
  background: var(--i100); font-size: var(--fs-xs); line-height: 1.7; color: var(--i600);
}

@media (max-width: 640px) {
  .ins-block { padding: 12px; }
  .ins-metric-num { font-size: 27px; }
}

/* ==========================================================================
   第 24 轮 B · 首页 Hero 双栏（左价值 / 右 AI 工作台）
   --------------------------------------------------------------------------
   评委打开首页第一眼就要看到核心能力：上传照片 → AI 识别风险。
   工作台是从「问安全」页整体搬来的同一套 DOM，逻辑不分叉。
   ========================================================================== */
.hero-split {
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  gap: 32px; align-items: stretch;
}
/* 左栏文案在工作台旁边垂直居中，避免下方留出大片空白 */
.hero-copy {
  min-width: 0; display: flex; flex-direction: column; justify-content: center;
}
.hero-workbench { min-width: 0; align-self: start; }
/* 拍照提示压实，缩短工作台高度 */
.hero-workbench .photo-tip { padding: 6px 0; }
.hero-workbench .photo-tips { margin-top: 12px; }
/* 工作台里的面板本来就是卡片，Hero 内不再套一层边框 */
.hero-workbench > .panel {
  margin: 0; border-radius: var(--r-lg);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(12, 43, 74, .08));
}

@media (max-width: 1040px) {
  .hero-split { grid-template-columns: 1fr; gap: 24px; }
}
@media (max-width: 640px) {
  .hero-split { gap: 20px; }
}

/* 工作台搬进深色 Hero 后，.tier-l1 h2{color:#fff} 会覆盖标题导致白底白字。
   这里把工作台内部文字色恢复为浅色主题的语义色。 */
.hero-workbench .panel-head h2,
.hero-workbench h2,
.hero-workbench h3 { color: var(--brand); }
.hero-workbench .panel-head h2 .ico { color: var(--brand-600); }
.hero-workbench .lead,
.hero-workbench .answer-meta { color: var(--i600); }
.hero-workbench .head-note { color: var(--i500); }
/* Hero 内工作台不重复外层深色底 */
.hero-workbench .panel { background: var(--surface); }

/* 拍照提示收进折叠，避免工作台过高 */
.hero-workbench .shot-tips { margin-top: 12px; }
/* Hero 内工作台压缩高度，避免比左栏高出一大截 */
.hero-workbench .composer-grid textarea { min-height: 48px; }
.hero-workbench .shot-tips { margin-top: 12px; }
.hero-workbench .dropzone { padding: 20px 16px; }
.hero-workbench .dropzone-art { width: 40px; height: 40px; }
.hero-workbench .lead { font-size: var(--fs-sm); }
/* ===== V16 TIERS END ===== */

/* ===== V17 PALETTE BEGIN ===== */
/* ==========================================================================
   V17 色彩层：深蓝 + 琥珀（政务工程感）
   --------------------------------------------------------------------------
   变更依据：第 16 轮指令 §5 —— 保留深蓝 #0c2b4a + 琥珀 #f2a33c + 风险三色。
   取代 V15 的安全橙 #b23a0a 主色（V15 配色存档于 _deprecated-css/ 的说明里）。

   关键设计决定（都经对比度核算）：
     · 主按钮 = 深蓝底白字（14.38:1）。琥珀配白字只有 2.08:1，**绝不能做按钮底色**，
       琥珀只做强调、斜纹、徽标。
     · 风险色分「展示色」与「文字安全色」两套：
         展示色用于圆点/色条/环（不承载文字）
         文字安全色用于风险标签文字
       因为 #e0a92b 在白底上只有 2.13:1、#dc3f2e 是 4.38:1、#1f8a53 是 4.36:1，
       后两者做文字略欠 4.5:1，所以各派生一个加深版本。
     · 深色主题底用深蓝灰 #0f1b2a 而非近黑，橙色系只做强调不做整块底色。
   ========================================================================== */
:root {
  /* ---------- 页面与容器 ---------- */
  --canvas:#f5f7fa;
  --surface:#ffffff;
  --surface-soft:#f8fafc;
  --line:#e3e9f0;

  /* ---------- 主色：深蓝 ---------- */
  --brand:#0c2b4a;
  --brand-700:#081f37;
  --brand-600:#123a61;
  --brand-500:#1d4d7a;
  --brand-100:#dce7f2;
  --brand-050:#eff4f9;

  /* ---------- 强调色：琥珀 ---------- */
  --accent:#f2a33c;
  --accent-700:#b87718;
  --accent-600:#d98f22;
  --accent-100:#fdf1dd;
  --accent-050:#fffaf0;

  /* ---------- 中性：蓝灰阶（与深蓝同族，比纯灰更协调） ---------- */
  --i950:#0c2b4a;
  --i900:#16395c;
  --i800:#1f2d3d;
  --i700:#2f3d4d;
  --i600:#3d4c5c;
  --i500:#62748a;
  --i400:#8b9cb0;
  --i300:#c3cfdc;
  --i200:#e3e9f0;
  --i100:#eef3f8;
  --i50:#f8fafc;

  /* ---------- 风险三色：展示色 ---------- */
  --risk-high:#dc3f2e;
  --risk-mid:#e0a92b;
  --risk-low:#1f8a53;
  /* ---------- 风险三色：文字安全色（≥4.5:1 on 白卡） ---------- */
  --risk-high-text:#c0321c;
  --risk-mid-text:#8a6410;
  --risk-low-text:#1a7a49;
  /* ---------- 风险浅底 ---------- */
  --risk-high-bg:#fdecea;
  --risk-mid-bg:#fdf5e3;
  --risk-low-bg:#e9f5ee;

  /* ---------- 功能色（文字版都过 4.5:1） ---------- */
  --red:var(--risk-high-text);
  --red-bg:var(--risk-high-bg);
  --amber:var(--risk-mid-text);
  --amber-bg:var(--risk-mid-bg);
  --green:var(--risk-low-text);
  --green-bg:var(--risk-low-bg);
  --signal:var(--accent);
  --signal-100:var(--accent-100);
  --signal-50:var(--accent-050);

  /* ---------- 旧令牌全部重指到新体系 ----------
     V15 把主色命名为 --safety；这里让安全橙名指向深蓝，
     这样 V15 层里所有 var(--safety) 立刻跟着变色。 */
  --safety:var(--brand);
  --safety-700:var(--brand-700);
  --safety-500:var(--brand-500);
  --safety-100:var(--brand-100);
  --safety-50:var(--brand-050);

  --b900:var(--brand-700);
  --b800:var(--brand-600);
  --b700:var(--brand);
  --b600:var(--brand-500);
  --b500:var(--brand-500);
  --b300:var(--brand-100);
  --b100:var(--brand-100);
  --b050:var(--brand-050);
  --orange:var(--brand);
  --orange-bg:var(--brand-100);

  --gold-700:var(--accent-700);
  --gold-500:var(--accent);
  --gold-100:var(--accent-100);
  --gold-50:var(--accent-050);
  --warn-700:var(--amber);
  --warn-100:var(--amber-bg);
  --ok-700:var(--green);
  --ok-100:var(--green-bg);
  --danger-700:var(--red);
  --danger-600:var(--red);
  --danger-100:#f0c4bc;
  --danger-50:var(--red-bg);
  --amber-dark:var(--amber);
  --amber-soft:var(--amber-bg);
  --risk-high-soft:var(--risk-high-bg);
  --risk-mid-soft:var(--risk-mid-bg);
  --risk-low-soft:var(--risk-low-bg);
  --navy-900:#071c30;
  --navy-800:var(--brand);
  --navy-700:var(--brand-600);
  --navy-600:var(--brand-500);
  --navy-100:var(--brand-100);
  --navy-050:var(--brand-050);
  --ink:var(--i800);
  --body:var(--i600);
  --muted:var(--i500);
  --paper:var(--canvas);
  --panel:var(--surface);
  --panel-soft:var(--surface-soft);
  --line-strong:var(--i300);

  /* ---------- 形状（§5：卡片 10 / 按钮 8 / 大容器 14） ---------- */
  --r-sm:8px;
  --r-md:10px;
  --r-lg:10px;
  --r-xl:14px;
  --radius:var(--r-md);
  --radius-sm:var(--r-sm);

  /* ---------- 阴影：只两级（§5） ---------- */
  --shadow-1:0 1px 3px rgba(12,43,74,.06);
  --shadow-2:0 4px 14px rgba(12,43,74,.10);
  --shadow-3:var(--shadow-2);  /* 只有两级：3 号指向 2 号 */
  --shadow-sm:var(--shadow-1);
  --shadow:var(--shadow-1);
  --shadow-lg:var(--shadow-2);

  /* ---------- 字阶：7 级（§5） ---------- */
  --fs-xs:12px;
  --fs-sm:13px;
  --fs-md:15px;
  --fs-base:15px;
  --fs-lg:17px;
  --fs-xl:21px;
  --fs-2xl:27px;
  --fs-3xl:34px;

  /* 正文行高与行宽（§5：1.7、32~42 汉字） */
  --line-ui:1.7;
  --prose-width:34em;
}

/* ==========================================================================
   组件覆盖：把 V15 里以橙色为主色的地方改为深蓝 / 琥珀
   ========================================================================== */

/* 顶栏：深蓝底 + 琥珀斜纹（施工现场警戒带） */
header { background:var(--brand); }
.top-band {
  background:repeating-linear-gradient(
    135deg, var(--accent) 0 10px, var(--brand-700) 10px 20px
  );
}
.brand-mark { background:var(--accent); color:var(--brand-700); }
.brand-text h1 { color:#fff; }
.brand-text h1 span { color:var(--accent); }
.brand-text p { color:#a8bdd4; }
.version-tag { border-color:rgba(255,255,255,.22); color:#a8bdd4; }
.status-pill {
  background:rgba(255,255,255,.10); border-color:rgba(255,255,255,.22); color:#dce7f2;
}
.status-pill.offline {
  background:rgba(242,163,60,.18); border-color:rgba(242,163,60,.46); color:#ffd79a;
}
.theme-toggle {
  background:rgba(255,255,255,.12); border-color:rgba(255,255,255,.24); color:#fff;
}
.theme-toggle:hover { background:rgba(255,255,255,.22); }

/* 导航：深蓝下划线 */
.nav { background:var(--surface); border-bottom:1px solid var(--line); }
.nav-button { color:var(--i500); }
.nav-button:hover { color:var(--brand); background:var(--brand-050); }
.nav-button.active { color:var(--brand); border-bottom-color:var(--brand); }
.nav-button.emergency-tab { color:var(--red); }
.nav-button.emergency-tab.active { border-bottom-color:var(--red); }

/* L1 Hero 带：深蓝底 + 琥珀斜纹顶边 */
.tier-l1 { background:var(--brand); }
.tier-l1::before {
  background:repeating-linear-gradient(
    135deg, var(--accent) 0 10px, var(--brand-700) 10px 20px
  );
}
.tier-l1 h2 { color:#fff; }
.tier-l1 h2 em { color:var(--accent); }
.tier-l1 .l1-kicker { color:var(--accent); }
.tier-l1 .l1-lead { color:#c3d3e4; }
.tier-l1 .l1-foot { border-top-color:rgba(255,255,255,.16); }
.tier-l1 .l1-foot .hint { color:#a8bdd4; }
.l1-rolehint { color:#a8bdd4; }
.l1-rolehint.is-set { color:var(--accent); }
.tier-l1 .secondary-button {
  background:rgba(255,255,255,.10); border-color:rgba(255,255,255,.28); color:#fff;
}
.tier-l1 .secondary-button:hover {
  background:rgba(255,255,255,.20); border-color:var(--accent); color:#fff;
}
.tier-l1 .ghost-button { background:transparent; border-color:rgba(255,255,255,.28); color:#fff; }
.tier-l1 .ghost-button:hover { background:rgba(255,255,255,.16); color:#fff; }
.tier-l1 .ghost-button.is-emergency-link {
  color:#ffc9c0; border-color:rgba(220,63,46,.55);
}
.tier-l1 .ghost-button.is-emergency-link:hover {
  background:rgba(220,63,46,.22); border-color:var(--risk-high); color:#fff;
}
.tier-l1 .role-chip {
  background:rgba(255,255,255,.10); border-color:rgba(255,255,255,.26); color:#e4edf6;
}
.tier-l1 .role-chip:hover { background:rgba(242,163,60,.22); border-color:var(--accent); color:#fff; }
.tier-l1 .role-chip.active {
  background:var(--accent); border-color:var(--accent); color:var(--brand-700);
}

/* L2 指标条：深蓝大数字 */
.tier-l2 { background:var(--surface); border-color:var(--line); }
.tier-l2 .l2-cell { border-right-color:var(--line); }
.tier-l2 .l2-num { color:var(--brand); }
.tier-l2 .l2-num .unit { color:var(--i500); }
.tier-l2 .l2-label { color:var(--i700); }
.tier-l2 .l2-note { color:var(--i500); }
.tier-l2 .l2-cell.is-risk .l2-num { color:var(--risk-high-text); }
.tier-l2 .l2-cell.is-ok .l2-num { color:var(--risk-low-text); }

/* L3 主行动卡：深蓝描边 + 深蓝实心按钮（琥珀做徽标） */
.tier-l3 {
  background:var(--surface); border-color:var(--brand);
  box-shadow:0 1px 3px rgba(12,43,74,.08);
}
.tier-l3::before { background:var(--brand); }
.tier-l3 h2 { color:var(--brand); }
.tier-l3 .l3-badge { background:var(--accent); color:var(--brand-700); }
.tier-l3 .l3-lead { color:var(--i600); }
.tier-l3 .l3-action { border-top-color:var(--line); }
.tier-l3 .l3-count { color:var(--brand); }

/* L4 内容卡 */
.tier-l4 { background:var(--surface); border-color:var(--line); }
.tier-l4 > .l4-head { border-bottom-color:var(--line); }
.tier-l4 > .l4-head h2, .tier-l4 > .l4-head h3 { color:var(--brand); }
.tier-l4 > .l4-head .ico { color:var(--brand); }
.tier-l4 > .l4-head .l4-note { color:var(--i500); }
.tier-l4 .l4-sub { color:var(--i700); }

/* L5 引用块：深蓝左条 + 等宽编号 */
.tier-l5 { background:var(--surface-soft); border-color:var(--line); border-left-color:var(--brand); }
.tier-l5 .l5-code {
  color:var(--brand); background:var(--surface); border-color:var(--i300);
}
.tier-l5 .l5-quote { color:var(--i700); }
.tier-l5 .l5-source { color:var(--i500); }
.tier-l5.is-caution {
  border-left-color:var(--accent); background:var(--accent-050);
}
.tier-l5.is-caution .l5-quote { color:#6b4a10; }
.tier-l5.is-danger { border-left-color:var(--risk-high); background:var(--risk-high-bg); }
.tier-l5.is-danger .l5-quote { color:#8f2110; }

/* 按钮体系：实心按钮只有深蓝一种 */
.primary-button, .amber-button { background:var(--brand); color:#fff; }
.primary-button:hover:not(:disabled), .amber-button:hover:not(:disabled) {
  background:var(--brand-600); color:#fff;
}
.secondary-button, .voice-button, .quick-button, .filter-chip, .role-chip {
  background:var(--surface); border:1px solid var(--i300); color:var(--i700);
}
.secondary-button:hover, .voice-button:hover, .quick-button:hover,
.filter-chip:hover, .role-chip:hover {
  border-color:var(--brand); color:var(--brand); background:var(--brand-050);
}
.filter-chip.active, .role-chip.active {
  background:var(--brand); border-color:var(--brand); color:#fff;
}
.ghost-button { border:1px solid var(--line); color:var(--i600); background:transparent; }
.ghost-button:hover { border-color:var(--brand); color:var(--brand); background:var(--brand-050); }
.danger-button { background:var(--risk-high-text); color:#fff; }
.danger-button:hover:not(:disabled) { background:#9a2a17; }

/* 输入控件：聚焦用深蓝描边 + 浅底光环 */
textarea, input[type="text"], input[type="search"] {
  background:var(--surface); border:1.5px solid var(--i300); color:var(--i800);
}
textarea:focus, input:focus {
  border-color:var(--brand); box-shadow:0 0 0 3px var(--brand-100); background:var(--surface);
}
textarea::placeholder, input::placeholder { color:var(--i400); }
:focus-visible { outline:3px solid var(--brand); outline-offset:2px; border-radius:var(--r-sm); }

/* 清单条目 */
.todo-item, .check-item, .quiz-stat, .role-block, .option, .training-card,
.source-card, .doc-group, .step-item, .case-card, .photo-tip, .result-box {
  border-bottom-color:var(--line);
}
.todo-item b, .check-item b { color:var(--i800); }
.todo-item span, .check-item small { color:var(--i500); }
.todo-item:hover { background:var(--brand-050); }
.todo-item.done, .check-item.checked, .step-item.is-done {
  background:var(--risk-low-bg); border-color:#c6e6d3;
}
.todo-item.done b, .check-item.checked b, .step-item.is-done h3 { color:var(--risk-low-text); }

/* 进度条（§5：主色填充 + 轨道 #e3e9f0 + 右侧等宽数字） */
.tier-progress, .progress-track, .domain-bar .dtrack {
  background:var(--line); border-radius:3px;
}
.tier-progress > i, .progress-fill, .domain-bar .dfill {
  background:var(--brand); border-radius:3px;
}
.tier-progress.is-ok > i { background:var(--risk-low); }
.progress-label, .progress-row { color:var(--brand); }

/* 表格（§5：对照类信息用表格） */
.table-wrap { border-color:var(--line); border-radius:var(--r-md); }
th { background:var(--brand); color:#fff; }
td { border-color:var(--line); color:var(--i600); }
tbody tr:hover { background:var(--brand-050); }

/* 检索高亮：琥珀 */
mark.hit { background:#ffe9a8; color:#5c4200; border-radius:2px; padding:0 2px; }

/* 会话 */
.chat-stream { background:var(--surface-soft); }
.avatar { background:var(--brand); color:#fff; }
.msg-row.from-user .avatar { background:var(--accent); color:var(--brand-700); }
.bubble { background:var(--surface); border-color:var(--line); }
.msg-row.from-user .bubble { background:var(--brand); border-color:var(--brand); }
.bubble-title { color:var(--brand); }
.msg-row.from-user .bubble-title { color:#fff; }
.bubble-meta, .answer-meta { color:var(--i400); }
.answer-body { color:var(--i600); }
.source-card h5, .src-title { color:var(--brand); }
.source-meta { color:var(--i400); }

/* 应急区：深蓝底 + 琥珀/红强调 */
.emergency-hero { background:var(--brand); color:#c3d3e4; }
.emergency-hero h2 { color:#fff; }
.emergency-hero p { color:#a8bdd4; }
.emergency-card { background:var(--surface); border-color:var(--line); }
.emergency-card:hover { border-color:var(--risk-high); box-shadow:var(--shadow-2); }
.emergency-card strong { color:var(--brand); }
.emergency-guide, .guide { border-left-color:var(--risk-high); border-color:var(--line); }
.em-step .em-num { background:var(--risk-high-text); color:#fff; }
.em-never { background:var(--risk-high-bg); border-left-color:var(--risk-high); color:#8f2110; }
.call-btn { background:var(--risk-high-text); color:#fff; }
.call-btn:hover { background:#9a2a17; }

/* 提示条 */
.warn-box {
  background:var(--accent-050); border-color:#f0dcb4; border-left-color:var(--accent);
  color:#6b4a10;
}
.warn-box b { color:#6b4a10; }
.error-card {
  background:var(--risk-high-bg); border-color:#f0c4bc; border-left-color:var(--risk-high);
  color:#8f2110;
}
.error-card b { color:#8f2110; }

/* 证书 */
.certificate { border-color:var(--brand); }
.cert-kicker { color:var(--accent-700); }
.certificate h3 { color:var(--brand); }
.cert-rule { background:var(--accent); }

/* 状态徽标 */
.status-badge.is-active { color:var(--risk-low-text); background:var(--risk-low-bg); border-color:#b7dfc6; }
.status-badge.is-soon { color:var(--risk-mid-text); background:var(--risk-mid-bg); border-color:#e8d5a4; }
.status-badge.is-dead { color:var(--risk-high-text); background:var(--risk-high-bg); border-color:#f0c4bc; }

/* 风险环与分布图 */
.ring-figure .ring-bg { stroke:var(--line); }
.ring-figure .ring-fg { stroke:var(--brand); }
.ring-figure .ring-num { color:var(--brand); }
.ring-figure .ring-seg.is-high { stroke:var(--risk-high); }
.ring-figure .ring-seg.is-mid { stroke:var(--risk-mid); }
.ring-figure .ring-seg.is-low { stroke:var(--risk-low); }
.ring-legend .dot.is-high { background:var(--risk-high); }
.ring-legend .dot.is-mid { background:var(--risk-mid); }
.ring-legend .dot.is-low { background:var(--risk-low); }
.domain-row:hover { background:var(--brand-050); border-color:var(--brand-100); }
.domain-row.is-selected { background:var(--brand-100); border-color:var(--brand); }
.domain-row .dfill { background:var(--brand); }
.domain-row .dtrack { background:var(--line); }
.domain-row.is-selected .dname, .domain-row.is-selected .dval { color:var(--brand); }

/* 热力格：用琥珀色相（学习行为，不是风险） */
.heat-cell { background:var(--i100); border-color:var(--line); color:var(--i600); }
.heat-cell[data-level="1"] { background:#fdf1dd; border-color:#f0dcb4; color:#7a5a1a; }
.heat-cell[data-level="2"] { background:#f8dcae; border-color:#e8c684; color:#6b4a10; }
.heat-cell[data-level="3"] { background:var(--accent-600); border-color:var(--accent-700); color:#3d2a06; }
/* L4 用 --accent-600 + 近黑字（5.16:1）；--accent-700 配白字只有 3.69:1 */
.heat-cell[data-level="4"] { background:var(--accent-600); border-color:var(--accent-700); color:#3d2a06; }

/* 趋势线 */
.trend-figure .axis { stroke:var(--line); }
.trend-figure .line { stroke:var(--brand); }
.trend-figure .area { fill:var(--brand-100); }
.trend-figure .pt { fill:var(--brand); stroke:#fff; }

/* 时间轴 */
.tl-step::before { background:var(--line); }
.tl-step .tl-no { background:var(--surface); color:var(--i500); border-color:var(--i300); }
.tl-step.is-current .tl-no { background:var(--risk-high-text); color:#fff; border-color:var(--risk-high-text); }
.tl-step.is-done .tl-no { background:var(--risk-low); color:#fff; border-color:var(--risk-low); }
.tl-step .tl-body h4 { color:var(--brand); }

/* 阶段分隔线：斜纹用琥珀 */
.phase-rule {
  background:repeating-linear-gradient(135deg, var(--i300) 0 5px, transparent 5px 10px);
}
.phase-title { color:var(--brand); }
.phase-desc { color:var(--i500); }

/* 页脚 */
footer { color:var(--i500); }
.footer-line { border-top-color:var(--brand); }
.footer-line b { color:var(--i700); }

/* 图标与正文行宽 */
.ico { stroke-width:1.5; }
.tier-l4 .l5-quote, .tier-l1 .l1-lead, .answer-body, .panel-body p {
  max-width:var(--prose-width);
}

/* ==========================================================================
   暗色主题：深蓝灰底（#0f1b2a 系），不是近黑
   ========================================================================== */
[data-theme="dark"] {
  --canvas:#0f1b2a;
  --surface:#16263a;
  --surface-soft:#1b2d43;
  --line:#27394f;

  --i950:#e8eef5;
  --i900:#dce7f2;
  --i800:#dce7f2;
  --i700:#c3d3e4;
  --i600:#a8bdd4;
  --i500:#8b9cb0;
  --i400:#62748a;
  --i300:#3d5169;
  --i200:#27394f;
  --i100:#1e2f45;
  --i50:#1b2d43;

  --brand:#7fb2e5;
  --brand-700:#a8c9ec;
  --brand-600:#5f97d0;
  --brand-500:#4a86c4;
  --brand-100:#1e3550;
  --brand-050:#182b40;

  --accent:#f2a33c;
  --accent-700:#ffc46b;
  --accent-600:#e0a92b;
  --accent-100:#3a2a12;
  --accent-050:#2a1f0e;

  --risk-high:#ef6a58;
  --risk-mid:#f0c05a;
  --risk-low:#5cbd85;
  --risk-high-text:#ef6a58;
  --risk-mid-text:#f0c05a;
  --risk-low-text:#5cbd85;
  --risk-high-bg:#2e1a17;
  --risk-mid-bg:#2e2716;
  --risk-low-bg:#12291d;

  --red:#ef6a58;
  --amber:#f0c05a;
  --green:#5cbd85;
  --red-bg:#2e1a17;
  --amber-bg:#2e2716;
  --green-bg:#12291d;

  --shadow-1:0 1px 3px rgba(0,0,0,.35);
  --shadow-2:0 4px 14px rgba(0,0,0,.45);
  --shadow-3:var(--shadow-2);  /* 只有两级：3 号指向 2 号 */
}

[data-theme="dark"] header { background:#0a1524; }
[data-theme="dark"] .top-band {
  background:repeating-linear-gradient(135deg, var(--accent) 0 10px, #0a1524 10px 20px);
}
[data-theme="dark"] .tier-l1 { background:#122032; }
[data-theme="dark"] .tier-l1::before {
  background:repeating-linear-gradient(135deg, var(--accent) 0 10px, #0a1524 10px 20px);
}
[data-theme="dark"] .brand-mark { background:var(--accent); color:#0a1524; }
[data-theme="dark"] .emergency-hero { background:#122032; }
[data-theme="dark"] th { background:#122032; }
[data-theme="dark"] .nav { background:var(--surface); border-bottom-color:var(--line); }

/* 深色下实心按钮用琥珀底 + 深字（深蓝在深底上对比不足） */
[data-theme="dark"] .primary-button,
[data-theme="dark"] .amber-button { background:var(--accent); color:#1a1206; }
[data-theme="dark"] .primary-button:hover:not(:disabled),
[data-theme="dark"] .amber-button:hover:not(:disabled) { background:var(--accent-700); color:#1a1206; }
[data-theme="dark"] .filter-chip.active,
[data-theme="dark"] .role-chip.active { background:var(--accent); border-color:var(--accent); color:#1a1206; }
[data-theme="dark"] .tier-l1 .role-chip.active { background:var(--accent); color:#1a1206; }
[data-theme="dark"] .tier-l3 { border-color:var(--brand); }
[data-theme="dark"] .tier-l3::before { background:var(--brand); }
[data-theme="dark"] .tier-l3 h2 { color:var(--brand-700); }
[data-theme="dark"] .tier-l3 .l3-badge { background:var(--accent); color:#1a1206; }
[data-theme="dark"] .tier-l4 > .l4-head h2 { color:var(--brand-700); }
[data-theme="dark"] .tier-l4 > .l4-head .ico { color:var(--accent); }
[data-theme="dark"] .tier-l2 .l2-num { color:var(--brand-700); }
[data-theme="dark"] .tier-l5 { background:var(--surface-soft); }
[data-theme="dark"] .tier-l5 .l5-code { background:var(--surface); color:var(--brand-700); }
[data-theme="dark"] .tier-l5.is-caution { background:var(--accent-050); }
[data-theme="dark"] .tier-l5.is-caution .l5-quote { color:#f0c05a; }
[data-theme="dark"] .tier-l5.is-danger { background:var(--risk-high-bg); }
[data-theme="dark"] .tier-l5.is-danger .l5-quote { color:#f4a396; }
[data-theme="dark"] .warn-box { background:var(--accent-050); border-color:#4a3a1e; color:#f0c05a; }
[data-theme="dark"] .warn-box b { color:#f0c05a; }
[data-theme="dark"] .error-card { background:var(--risk-high-bg); border-color:#5a2b2b; color:#f4a396; }
[data-theme="dark"] .error-card b { color:#f4a396; }
[data-theme="dark"] .em-never { background:var(--risk-high-bg); border-color:#5a2b2b; color:#f4a396; }
[data-theme="dark"] .msg-row.from-user .bubble { background:#1e3550; border-color:#2a4260; }
[data-theme="dark"] .msg-row.from-user .bubble-title { color:#ffd79a; }
[data-theme="dark"] .msg-row.from-user .avatar { background:var(--accent); color:#1a1206; }
[data-theme="dark"] .todo-item.done,
[data-theme="dark"] .check-item.checked { background:var(--risk-low-bg); border-color:#2c5a3d; }
[data-theme="dark"] mark.hit { background:#4a3a10; color:#ffe9b0; }
[data-theme="dark"] .certificate { background:#fff; border-color:#0a1524; }
[data-theme="dark"] .certificate h3, [data-theme="dark"] .certificate dd { color:#0c2b4a; }
[data-theme="dark"] .certificate dt { color:#62748a; }
[data-theme="dark"] .certificate .cert-kicker { color:#b87718; }
[data-theme="dark"] .footer-line { border-top-color:var(--brand); }

/* 打印始终浅色 */
@media print {
  :root { --canvas:#fff; --surface:#fff; --line:#ccc; }
}

/* ==========================================================================
   小尺寸实心徽标的对比度修正
   --------------------------------------------------------------------------
   §5 的风险展示色 #dc3f2e / #1f8a53 落在对比度死区：
     白字 4.38 / 4.36，近黑字 4.34 / 3.95 —— 两边都过不了 4.5:1。
   所以小尺寸徽标不能只靠「实心展示色 + 白字」，
   改用同色系的浅底 + 深字（语义不变，可读性达标）。
   ========================================================================== */
.option.is-correct .opt-key,
.step-item.is-done .step-order,
.tl-step.is-done .tl-no {
  background:var(--risk-low-bg); color:var(--risk-low-text);
  border-color:var(--risk-low);
}
.option.is-wrong .opt-key {
  background:var(--risk-high-bg); color:var(--risk-high-text);
  border-color:var(--risk-high);
}

/* ASR 可疑结果：输入框标黄，提示用户核对再提交。
   依据实测：静音/纯音输入会让 ASR 凭空返回"嗯。"这类单字。 */
textarea.is-suspect,
input.is-suspect {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-100);
  background: var(--accent-050);
}

/* ==========================================================================
   §5 权威令牌默认值（放在文件最末，确保审计与层叠都取到这里）
   --------------------------------------------------------------------------
   前面 @media print 里覆盖过底色；这里重申浅色默认值。
   这里显式重申浅色默认值，既表达意图也消除歧义。
   ========================================================================== */
:root {
  --canvas:#f5f7fa;
  --surface:#ffffff;
  --line:#e3e9f0;
  /* 阴影只两级：其余别名一律指向这两条，不新增第三、第四种配方 */
  --shadow-1:0 1px 3px rgba(12,42,74,.06);
  --shadow-2:0 4px 14px rgba(12,42,74,.10);
  --shadow-3:var(--shadow-2);  /* 只有两级：3 号指向 2 号 */
  --shadow-sm:var(--shadow-1);
  --shadow:var(--shadow-1);
  --shadow-lg:var(--shadow-2);
  /* 字阶 7 级 */
  --fs-xs:12px;
  --fs-sm:13px;
  --fs-md:15px;
  --fs-base:15px;
  --fs-lg:17px;
  --fs-xl:21px;
  --fs-2xl:27px;
  --fs-3xl:34px;
  --line-ui:1.7;
}

/* 对照类信息用表格（§5），不用长段落 */
.tier-table {
  width: 100%; border-collapse: collapse; margin-top: 14px;
  font-size: var(--fs-sm); border: 1px solid var(--line);
  border-radius: var(--r-md); overflow: hidden;
}
.tier-table caption {
  text-align: left; padding: 10px 12px; color: var(--i500);
  font-size: var(--fs-xs); caption-side: top;
}
.tier-table th {
  background: var(--brand); color: #fff; text-align: left;
  padding: 9px 12px; font-weight: 700; white-space: nowrap;
}
.tier-table td {
  padding: 9px 12px; border-top: 1px solid var(--line); color: var(--i600);
  line-height: 1.6;
}
.tier-table tbody tr:nth-child(even) { background: var(--i50); }
.tier-table td:nth-child(2) {
  font-family: var(--mono); text-align: right; white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.tier-table tbody tr:hover { background: var(--brand-050); }
@media (max-width: 640px) {
  .tier-table { font-size: var(--fs-xs); }
  .tier-table th, .tier-table td { padding: 7px 8px; }
}

/* 应急拨号是 sos 页的唯一主行动，保留红色语义但计入主行动口径 */
.primary-button.danger-button.is-call {
  background: var(--risk-high-text); color: #fff;
  min-height: 48px; font-size: var(--fs-base); font-weight: 800;
}
.primary-button.danger-button.is-call:hover { background: #9a2a17; color: #fff; }

/* ==========================================================================
   头像与步骤序号的对比度（重新声明）
   --------------------------------------------------------------------------
   基础层里写着 var(--amber) on var(--i800)，对比度只有 3.21:1。
   之前修过一次，但被后续分片的字号/间距重写冲掉了，这里放在所有分片之后，
   确保它是最终生效值。
   ========================================================================== */
.avatar {
  background: var(--i800); color: #ffffff; font-weight: 800;
}
.msg-row.from-user .avatar {
  background: var(--accent); color: var(--brand-700);
}
.step-order {
  background: var(--brand); color: #ffffff; font-weight: 800;
}
.step-item.is-done .step-order {
  background: var(--risk-low-bg); color: var(--risk-low-text);
  border-color: var(--risk-low);
}
[data-theme="dark"] .avatar { background: #3a434e; color: #ffffff; }
[data-theme="dark"] .msg-row.from-user .avatar { background: var(--accent); color: #1a1206; }
[data-theme="dark"] .step-order { background: var(--brand); color: #10151a; }

/* ==========================================================================
   ask 页输入区收敛（§6）：状态条 + 折叠区
   ========================================================================== */
.composer-status {
  display: flex; align-items: flex-start; gap: 8px;
  background: var(--brand-050); border: 1px solid var(--brand-100);
  border-radius: var(--r-sm); padding: 10px 12px; margin-bottom: 12px;
  font-size: var(--fs-sm); color: var(--i600); line-height: 1.6;
}
.composer-kbd { margin-left: auto; }
.composer-more {
  margin-top: 12px; border-top: 1px solid var(--line); padding-top: 10px;
}
.composer-more > summary {
  cursor: pointer; font-size: var(--fs-sm); font-weight: 700;
  color: var(--i600); list-style: none; padding: 4px 0;
  display: flex; align-items: center; gap: 6px;
}
.composer-more > summary::-webkit-details-marker { display: none; }
.composer-more > summary::before {
  content: "; width: 0; height: 0; flex: 0 0 auto;
  border-left: 5px solid currentColor;
  border-top: 4px solid transparent; border-bottom: 4px solid transparent;
  transition: transform .15s ease;
}
.composer-more[open] > summary::before { transform: rotate(90deg); }
.composer-more > summary:hover { color: var(--brand); }
.composer-more-body { padding: 10px 0 2px; display: flex; flex-direction: column; gap: 10px; }
.composer-more-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.composer-more-body .voice-row { margin-top: 0; }

@media (max-width: 640px) {
  .composer-kbd { margin-left: 0; width: 100%; }
  .composer-more-row .ico-button { width: 100%; min-height: 44px; }
}

/* ==========================================================================
   快捷提问按场景分组（§6：每组 ≤4 个，超出折叠）
   ========================================================================== */
.quick-group { margin-bottom: 14px; }
.quick-group:last-child { margin-bottom: 0; }
.quick-group-head {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
  margin-bottom: 8px;
}
.quick-group-title {
  font-size: var(--fs-sm); font-weight: 800; color: var(--brand);
  letter-spacing: .02em;
}
.quick-group-hint { font-size: var(--fs-xs); color: var(--i500); }
.quick-group-more { margin-top: 4px; }
.quick-group-more > summary {
  cursor: pointer; font-size: var(--fs-sm); font-weight: 700;
  color: var(--i600); list-style: none; padding: 5px 0;
  display: flex; align-items: center; gap: 6px;
}
.quick-group-more > summary::-webkit-details-marker { display: none; }
.quick-group-more > summary::before {
  content: "; width: 0; height: 0; flex: 0 0 auto;
  border-left: 5px solid currentColor;
  border-top: 4px solid transparent; border-bottom: 4px solid transparent;
  transition: transform .15s ease;
}
.quick-group-more[open] > summary::before { transform: rotate(90deg); }
.quick-group-more > summary:hover { color: var(--brand); }
.quick-button.is-role-match {
  border-color: var(--accent); background: var(--accent-050); color: var(--brand);
  font-weight: 700;
}
[data-theme="dark"] .quick-button.is-role-match {
  background: var(--accent-050); border-color: var(--accent); color: var(--accent);
}

/* ==========================================================================
   learn 页知识库状态的折叠区（§6 收敛：五合一后不再平铺）
   ========================================================================== */
.kb-sub {
  border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--surface-soft); margin-bottom: 14px; overflow: hidden;
}
.kb-sub > summary {
  cursor: pointer; list-style: none; padding: 12px 16px;
  font-size: var(--fs-sm); font-weight: 700; color: var(--i700);
  display: flex; align-items: center; gap: 8px;
}
.kb-sub > summary::-webkit-details-marker { display: none; }
.kb-sub > summary::before {
  content: "; width: 0; height: 0; flex: 0 0 auto;
  border-left: 5px solid currentColor;
  border-top: 4px solid transparent; border-bottom: 4px solid transparent;
  transition: transform .15s ease;
}
.kb-sub[open] > summary::before { transform: rotate(90deg); }
.kb-sub > summary:hover { color: var(--brand); }
.kb-sub-body { padding: 0 12px 12px; display: flex; flex-direction: column; gap: 12px; }
.kb-sub .panel { margin: 0; }

/* ==========================================================================
   learn 页过长区块的高度上限（§6 收尾）
   --------------------------------------------------------------------------
   实测：案例块 2288px + 标准库块 2196px，把整页撑到 8831px。
   设上限 + 滚动，信息不删，只是不再把页面拉长。
   ========================================================================== */
.case-grid {
  max-height: 640px; overflow-y: auto;
  padding-right: 6px;
  scrollbar-width: thin;
}
.case-grid::-webkit-scrollbar { width: 8px; }
.case-grid::-webkit-scrollbar-thumb {
  background: var(--i300); border-radius: 4px;
}
.case-grid::-webkit-scrollbar-track { background: transparent; }

/* 标准库表格：表头吸顶，表格区滚动（容器是 #standardsTable 里的 table） */
#standardsTable {
  max-height: 560px; overflow-y: auto;
  scrollbar-width: thin;
  border: 1px solid var(--line); border-radius: var(--r-md);
}
#standardsTable::-webkit-scrollbar { width: 8px; }
#standardsTable::-webkit-scrollbar-thumb {
  background: var(--i300); border-radius: 4px;
}
#standardsTable thead th {
  position: sticky; top: 0; z-index: 2;
}
#standardsTable table { border: 0; border-radius: 0; }

/* 滚动区底部加一点渐隐提示，让人知道还有内容 */
.case-grid::after {
  content: ""; display: block; height: 1px;
}

@media (max-width: 640px) {
  .case-grid { max-height: 520px; }
  .table-wrap.is-scroll { max-height: 440px; }
}

/* ==========================================================================
   learn 页紧凑化（§6 收尾）
   --------------------------------------------------------------------------
   实测：五步路线块 1419px 是 learn 里最大的单块。
   步骤条目之间留白过多，收紧节奏即可显著缩短，不需要折叠（步骤要一眼看全）。
   ========================================================================== */
.step-list { display: flex; flex-direction: column; gap: 0; }
.step-item {
  padding: 12px 2px; border-bottom: 1px solid var(--line);
  display: flex; align-items: flex-start; gap: 12px;
}
.step-item:last-child { border-bottom: 0; }
.step-item h3 {
  font-size: var(--fs-md); font-weight: 700; color: var(--i900);
  margin-bottom: 2px; line-height: 1.5;
}
.step-item p { font-size: var(--fs-sm); color: var(--i500); line-height: 1.6; }
.step-item .step-order {
  flex: 0 0 26px; width: 26px; height: 26px;
  font-size: var(--fs-sm); margin-top: 1px;
}
.step-item .step-link {
  margin-top: 6px; font-size: var(--fs-sm);
}
.step-item .tick,
.step-item .untick {
  font-size: var(--fs-base); color: var(--i400); flex: 0 0 auto;
}

/* 积分块紧凑 */
.points-head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 18px; }
.points-total { display: flex; flex-direction: column; }
.points-total b { font-family: var(--mono); font-size: 27px; font-weight: 700; color: var(--brand); line-height: 1.1; }
.points-total span { font-size: var(--fs-xs); color: var(--i500); }
.points-breakdown { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: var(--fs-sm); color: var(--i600); }
.points-breakdown > div { display: flex; align-items: baseline; gap: 6px; }
.points-breakdown .num { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--brand); }

/* 培训路线的进度概览压成一行 */
.panel .metric-grid { display: flex; flex-wrap: wrap; gap: 14px 28px; }

/* ==========================================================================
   对勾由 CSS 呈现（§3.1：不再把 SVG 当文本传给 make()）
   ========================================================================== */
.tick, .untick {
  display: inline-grid; place-items: center;
  width: 18px; height: 18px; flex: 0 0 18px;
  border-radius: 50%; font-size: 12px; line-height: 1;
}
/* 对勾底色用更深的绿：--risk-low 配白字只有 4.36:1 */
.tick { background: #1a7a49; color: #fff; }
.tick::before { content: "; width: 8px; height: 4px;
  border-left: 2px solid currentColor; border-bottom: 2px solid currentColor;
  transform: rotate(-45deg) translate(1px, -1px); }
.untick { border: 1.5px solid var(--i300); color: transparent; }

/* ==========================================================================
   [hidden] 必须真的隐藏（§5 残留状态 bug 的根因）
   --------------------------------------------------------------------------
   实测：cameraStage / photoStage / photoProgress / recordingRow 都带 hidden，
   但 computed display 分别是 grid / grid / flex / flex —— 作者样式
   .camera-stage{display:grid} 覆盖了浏览器默认的 [hidden]{display:none}
   （特异性相同，作者样式在后）。
   结果：未开摄像头时一个 950x208 的黑方块常驻、录音行常驻、上传进度常驻。

   一条规则修掉这三处症状。用 !important 是因为要压过后续所有组件样式。
   ========================================================================== */
[hidden] { display: none !important; }

/* 预览图没有 src 时不占空间（原本 alt 文本会撑出 22px 高的一条） */
#photoPreview:not([src]) { display: none; }

/* 顶栏状态胶囊（§5 第 5 条）：只在真正需要提示时出现 */
.status-pill {
  font-size: var(--fs-xs); font-weight: 700;
  padding: 4px 10px; border-radius: 999px;
  border: 1px solid transparent; white-space: nowrap;
}
.status-pill.offline {
  background: var(--risk-mid-bg); color: var(--risk-mid-text);
  border-color: var(--risk-mid);
}
/* ===== V17 PALETTE END ===== */
</style>

</head>
<body>
<!-- ===== V16 ICONS BEGIN ===== -->
<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true" focusable="false">
  <defs>
    <!-- 线条统一：24×24 网格，stroke 1.8，圆头圆角 -->
    <style>
      symbol { fill: none; stroke: currentColor; stroke-width: 1.8;
               stroke-linecap: round; stroke-linejoin: round; }
    </style>
  </defs>

  <!-- ===== 事故类型 ===== -->
  <symbol id="i-fall" viewBox="0 0 24 24">
    <path d="M12 3v9"/><path d="M9 6l3-3 3 3"/>
    <circle cx="12" cy="16.5" r="2.2"/>
    <path d="M4 21h16"/>
    <path d="M8 21l1.6-3.2M16 21l-1.6-3.2"/>
  </symbol>

  <symbol id="i-shock" viewBox="0 0 24 24">
    <path d="M13.5 2 5 13h5l-1 9 8.5-11h-5z"/>
  </symbol>

  <symbol id="i-collapse" viewBox="0 0 24 24">
    <path d="M3 8h7V3H3zM14 8h7V3h-7z"/>
    <path d="M10 8l2 3 2-3"/>
    <path d="M5 21h14"/>
    <path d="M7 21l2-6M17 21l-2-6M12 21v-5"/>
  </symbol>

  <symbol id="i-machine" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="3.2"/>
    <path d="M12 3v2.4M12 18.6V21M3 12h2.4M18.6 12H21"/>
    <path d="M5.6 5.6l1.7 1.7M16.7 16.7l1.7 1.7M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7"/>
    <circle cx="12" cy="12" r="8.6"/>
  </symbol>

  <symbol id="i-impact" viewBox="0 0 24 24">
    <path d="M12 2v6"/><path d="M9 5l3 3 3-3"/>
    <rect x="7" y="10" width="10" height="7" rx="1.5"/>
    <path d="M4 21h16"/>
    <path d="M10 17l-1 4M14 17l1 4"/>
  </symbol>

  <symbol id="i-fire" viewBox="0 0 24 24">
    <path d="M12 2c2.6 3 4.4 5 4.4 8a4.4 4.4 0 0 1-8.8 0c0-1 .2-1.8.6-2.6"/>
    <path d="M12 22a6 6 0 0 0 6-6c0-2.6-1.6-4.4-3-6"/>
    <path d="M12 22a6 6 0 0 1-6-6c0-1.4.5-2.6 1.2-3.6"/>
  </symbol>

  <symbol id="i-firstaid" viewBox="0 0 24 24">
    <rect x="3" y="7" width="18" height="13" rx="2"/>
    <path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7"/>
    <path d="M12 11v5M9.5 13.5h5"/>
  </symbol>

  <symbol id="i-alert" viewBox="0 0 24 24">
    <path d="M12 3.5 21.5 20h-19z"/>
    <path d="M12 10v4"/><circle cx="12" cy="17" r=".9" style="fill:currentColor;stroke:none"/>
  </symbol>

  <!-- ===== 防护与作业 ===== -->
  <symbol id="i-helmet" viewBox="0 0 24 24">
    <path d="M3 16h18"/>
    <path d="M5 16v-2a7 7 0 0 1 14 0v2"/>
    <path d="M10 7.4V4.6A1.6 1.6 0 0 1 11.6 3h.8A1.6 1.6 0 0 1 14 4.6v2.8"/>
  </symbol>

  <symbol id="i-harness" viewBox="0 0 24 24">
    <path d="M8 4v6a4 4 0 0 0 8 0V4"/>
    <path d="M8 6h8"/>
    <path d="M12 14v3"/>
    <circle cx="12" cy="19.5" r="2"/>
    <path d="M6 4h2M16 4h2"/>
  </symbol>

  <symbol id="i-ladder" viewBox="0 0 24 24">
    <path d="M7 3v18M17 3v18"/>
    <path d="M7 7h10M7 12h10M7 17h10"/>
  </symbol>

  <symbol id="i-scaffold" viewBox="0 0 24 24">
    <path d="M4 3v18M20 3v18"/>
    <path d="M4 8h16M4 15h16"/>
    <path d="M4 3l16 5M4 13l16 5"/>
  </symbol>

  <symbol id="i-edge" viewBox="0 0 24 24">
    <path d="M3 4v16h18"/>
    <path d="M3 4h8"/>
    <path d="M7 4v9h4"/>
    <path d="M7 13v7"/>
  </symbol>

  <symbol id="i-machinery" viewBox="0 0 24 24">
    <path d="M3 20h18"/>
    <path d="M5 20v-6h9l3-5h3v11"/>
    <circle cx="8" cy="20" r="1.6"/><circle cx="17" cy="20" r="1.6"/>
    <path d="M9 14V9h4"/>
  </symbol>

  <symbol id="i-electric" viewBox="0 0 24 24">
    <rect x="5" y="3" width="14" height="18" rx="2"/>
    <path d="M9 7h6M9 11h2M13 11h2"/>
    <path d="M12 14l-1.5 3h3L12 20"/>
  </symbol>

  <!-- ===== 动作 ===== -->
  <symbol id="i-camera" viewBox="0 0 24 24">
    <path d="M3 8.5A1.5 1.5 0 0 1 4.5 7h2.2l1.1-2h8.4l1.1 2h2.2A1.5 1.5 0 0 1 21 8.5v9A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z"/>
    <circle cx="12" cy="13" r="3.4"/>
  </symbol>

  <symbol id="i-mic" viewBox="0 0 24 24">
    <rect x="9" y="3" width="6" height="11" rx="3"/>
    <path d="M5 11a7 7 0 0 0 14 0"/>
    <path d="M12 18v3M9 21h6"/>
  </symbol>

  <symbol id="i-keyboard" viewBox="0 0 24 24">
    <rect x="2.5" y="6" width="19" height="12" rx="2"/>
    <path d="M7 10h.01M11 10h.01M15 10h.01M8 14h8"/>
  </symbol>

  <symbol id="i-speaker" viewBox="0 0 24 24">
    <path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4z"/>
    <path d="M15.5 9a4 4 0 0 1 0 6"/>
    <path d="M18 6.5a7.5 7.5 0 0 1 0 11"/>
  </symbol>

  <symbol id="i-print" viewBox="0 0 24 24">
    <path d="M7 9V3h10v6"/>
    <rect x="3.5" y="9" width="17" height="7" rx="1.5"/>
    <path d="M7 13h10v8H7z"/>
  </symbol>

  <symbol id="i-search" viewBox="0 0 24 24">
    <circle cx="10.5" cy="10.5" r="6.5"/>
    <path d="M15.5 15.5 21 21"/>
  </symbol>

  <symbol id="i-phone" viewBox="0 0 24 24">
    <path d="M6.5 3.5h3l1.5 4-2 1.5a11 11 0 0 0 5 5l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16 16 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5z"/>
  </symbol>

  <symbol id="i-image" viewBox="0 0 24 24">
    <rect x="3" y="4.5" width="18" height="15" rx="2"/>
    <circle cx="8.5" cy="10" r="1.6"/>
    <path d="M3.5 17l5-4.5 4 3.5 3-2.5 5 4"/>
  </symbol>

  <symbol id="i-refresh" viewBox="0 0 24 24">
    <path d="M20 11a8 8 0 0 0-13.7-5.2L4 8"/>
    <path d="M4 4v4h4"/>
    <path d="M4 13a8 8 0 0 0 13.7 5.2L20 16"/>
    <path d="M20 20v-4h-4"/>
  </symbol>

  <symbol id="i-close" viewBox="0 0 24 24">
    <path d="M6 6l12 12M18 6 6 18"/>
  </symbol>

  <symbol id="i-check" viewBox="0 0 24 24">
    <path d="M4.5 12.5 9 17 19.5 6.5"/>
  </symbol>

  <symbol id="i-clock" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="8.6"/>
    <path d="M12 7.5V12l3 1.8"/>
  </symbol>

  <symbol id="i-doc" viewBox="0 0 24 24">
    <path d="M6 3h8l4 4v14H6z"/>
    <path d="M14 3v4h4"/>
    <path d="M9 12h6M9 16h6"/>
  </symbol>

  <symbol id="i-chart" viewBox="0 0 24 24">
    <path d="M4 20V4"/>
    <path d="M4 20h16"/>
    <rect x="7.5" y="12" width="3" height="5"/>
    <rect x="13" y="8" width="3" height="9"/>
    <rect x="18" y="14" width="3" height="3"/>
  </symbol>

  <symbol id="i-shield" viewBox="0 0 24 24">
    <path d="M12 3l7 3v6c0 4.4-3 8-7 9-4-1-7-4.6-7-9V6z"/>
    <path d="M9 12.2l2.2 2.2L15.5 10"/>
  </symbol>

  <symbol id="i-clipboard" viewBox="0 0 24 24">
    <rect x="5" y="5" width="14" height="16" rx="2"/>
    <path d="M9 5V3.8A1.3 1.3 0 0 1 10.3 2.5h3.4A1.3 1.3 0 0 1 15 3.8V5"/>
    <path d="M9 11h6M9 15h4"/>
  </symbol>

  <symbol id="i-award" viewBox="0 0 24 24">
    <circle cx="12" cy="9" r="5.5"/>
    <path d="M9 13.5 7.5 21l4.5-2.5L16.5 21 15 13.5"/>
  </symbol>

  <symbol id="i-route" viewBox="0 0 24 24">
    <circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/>
    <path d="M8.5 6H14a3.5 3.5 0 0 1 0 7h-4a3.5 3.5 0 0 0 0 7h5.5"/>
  </symbol>

  <!-- ===== 示意图用（较大、线稿） ===== -->
    <symbol id="ill-edge" viewBox="0 0 240 130">
    <path d="M8 96h140v18H8z"/>
    <path d="M8 96h140"/>
    <circle cx="52" cy="64" r="6"/>
    <path d="M52 70v14M52 76l-8 6M52 76l8 6M52 84l-6 12M52 84l6 12"/>
    <path d="M124 38v76M200 38v76"/>
    <path d="M112 44h96"/>
    <path d="M112 68h96"/>
    <path d="M112 88h96M112 96h96"/>
    <path d="M216 44v52"/>
    <path d="M210 44h12M210 96h12"/>
    <text x="18" y="90" font-size="10" fill="currentColor">作业面</text>
    <text x="126" y="32" font-size="10" fill="currentColor">临边防护栏杆 1.2m</text>
    <text x="112" y="124" font-size="10" fill="currentColor">挡脚板 ≥180mm</text>
  </symbol>

<symbol id="ill-scaffold" viewBox="0 0 240 130">
    <path d="M10 122h220"/>
    <path d="M40 122V18M124 122V18M208 122V18"/>
    <path d="M40 40h168M40 72h168M40 104h168"/>
    <path d="M40 18l84 22M124 40l84 22M40 72l84 22M124 94l84 22"/>
    <path d="M28 122h192"/>
    <text x="46" y="14" font-size="11" fill="currentColor">立杆</text>
    <text x="132" y="14" font-size="11" fill="currentColor">剪刀撑</text>
    <text x="150" y="118" font-size="11" fill="currentColor">扫地杆</text>
  </symbol>

    <symbol id="ill-emergency" viewBox="0 0 240 130">
    <path d="M10 106h220"/>
    <path d="M36 100V78h5V62a3.5 3.5 0 0 1 7 0v16h4V58a3.5 3.5 0 0 1 7 0v20h4V64a3.5 3.5 0 0 1 7 0v14h4V72a3.5 3.5 0 0 1 7 0v14a16 16 0 0 1-16 16H52a16 16 0 0 1-16-16z"/>
    <path d="M26 50h46"/>
    <text x="27" y="40" font-size="10" fill="currentColor">1 停手</text>
    <text x="26" y="124" font-size="10" fill="currentColor">停止作业</text>

    <circle cx="112" cy="56" r="6"/>
    <path d="M112 62v17M112 68l-10 7M112 68l10 7M112 79l-8 12M112 79l8 12"/>
    <path d="M130 74h28"/>
    <path d="M150 66l9 8-9 8"/>
    <text x="104" y="40" font-size="10" fill="currentColor">2 撤离</text>
    <text x="100" y="124" font-size="10" fill="currentColor">撤到安全区</text>

    <rect x="182" y="70" width="36" height="30" rx="5"/>
    <path d="M191 86h18"/>
    <circle cx="200" cy="60" r="6"/>
    <path d="M200 66v-4"/>
    <text x="180" y="40" font-size="10" fill="currentColor">3 报告</text>
    <text x="176" y="124" font-size="10" fill="currentColor">报告负责人</text>
  </symbol>

<symbol id="ill-ppe" viewBox="0 0 240 130">
    <path d="M24 46a20 20 0 0 1 40 0"/>
    <path d="M15 46h58"/>
    <path d="M44 26v20"/>
    <path d="M31 29v17M57 29v17"/>
    <text x="20" y="64" font-size="10" fill="currentColor">安全帽</text>

    <rect x="96" y="33" width="21" height="17" rx="7"/>
    <rect x="125" y="33" width="21" height="17" rx="7"/>
    <path d="M117 41h8"/>
    <path d="M96 39l-11-6M146 39l11-6"/>
    <text x="98" y="64" font-size="10" fill="currentColor">护目镜</text>

    <path d="M180 47V33a4 4 0 0 1 8 0v14"/>
    <path d="M188 45V30a4 4 0 0 1 8 0v15"/>
    <path d="M196 45V32a4 4 0 0 1 8 0v13"/>
    <path d="M204 47V36a4 4 0 0 1 8 0v11"/>
    <path d="M180 47h32v5a13 13 0 0 1-13 13h-6a13 13 0 0 1-13-13z"/>
    <path d="M180 51l-8 3a4 4 0 0 0 2 7l6-2"/>
    <text x="182" y="76" font-size="10" fill="currentColor">防护手套</text>

    <path d="M31 88h26"/>
    <path d="M31 88l-5 7v31h36V95l-5-7"/>
    <path d="M38 88l7 9 7-9"/>
    <path d="M26 104h36M26 114h36"/>
    <text x="22" y="128" font-size="10" fill="currentColor">反光背心</text>

    <path d="M104 102h32v8h-32z"/>
    <path d="M108 102l6-16M132 102l-6-16"/>
    <path d="M112 94h16"/>
    <path d="M108 110v4a7 7 0 0 0 7 7M132 110v4a7 7 0 0 1-7 7"/>
    <text x="106" y="128" font-size="10" fill="currentColor">安全带</text>

    <path d="M182 114V92h13v10h13a9 9 0 0 1 9 9v3z"/>
    <path d="M182 109h35"/>
    <path d="M187 94h5M187 99h5"/>
    <text x="184" y="128" font-size="10" fill="currentColor">安全鞋</text>
  </symbol>

</svg>
<!-- ===== V16 ICONS END ===== -->

  <div class="top-band"></div>



  <header>

    <div class="header-inner">

      <div class="brand">

        <div class="brand-mark" aria-hidden="true">筑</div>

        <div class="brand-text">

          <h1>筑安智培 · 新工人安全助手</h1>

          <p>让安全规范更容易理解，让现场操作更有依据</p>

        </div>

      </div>

      <div class="header-right">

        <div id="headerRole" class="status-pill offline">工种未选择</div>

        <div id="modelStatus" class="status-pill offline" role="status" aria-live="polite">正在检测在线模型</div>

        <button id="themeToggle" class="theme-toggle" type="button"
                aria-pressed="false" title="切换白天 / 夜间配色"><svg class="ico" aria-hidden="true"><use href="#i-clock"/></svg> 夜间</button>

        <div class="version-tag">V16.0.0</div>

      </div>

    </div>

  </header>



  



  <nav aria-label="主导航">
    <div class="nav-inner">
      <button class="nav-button active" data-view="home">首页</button>
      <button class="nav-button" data-view="ask">问安全</button>
      <button class="nav-button emergency-tab" data-view="sos">应急处置</button>
      <button class="nav-button" data-view="pre">班前准备</button>
      <button class="nav-button" data-view="learn">学习与资料</button>
    </div>
  </nav>



  <main>

    <!-- ================= 首页 ================= -->

    <section id="home" class="view active" aria-label="首页">

      <!-- ============ L1 Hero 带：视图开场，一行结论 ============ -->
      <div class="tier-l1 hero-split">
        <div class="hero-copy">
        <div class="l1-kicker">
          <svg class="ico" aria-hidden="true"><use href="#i-shield"/></svg>
          新工人入场安全助手
        </div>
                <h2>拍照识别现场安全风险</h2>
        <p class="l1-lead">把作业面、防护设施和周边环境拍进一张照片，几十秒内得到：<em>识别到的作业场景、可见风险的位置与现象、每条风险的立即动作、以及需要你补充确认的内容</em>。不想拍照也可以直接打字问安全。</p>
        <div class="l1-foot">
          <button class="secondary-button ico-button" data-jump="voice" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-mic"/></svg>说句话问安全
          </button>
          <button class="secondary-button ico-button" data-jump="photo" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg>拍照识别风险
          </button>
          <button class="ghost-button ico-button is-emergency-link" data-jump="emergency" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg>应急求助
          </button>
          <span class="hint">选工种：</span>
          <div id="homeRoleChips" class="role-chips is-inline" role="group" aria-label="选择工种"></div>
        </div>
        <div id="homeRoleHint" class="l1-rolehint">还没有选择工种 —— 未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。</div>
        </div><!-- /hero-copy -->

        <div class="hero-workbench" id="heroWorkbench">
          <!-- AI 识别工作台：从「问安全」页整体搬来，全站共用一套逻辑 -->
  <div class="panel">

          <div class="panel-head">

            <h2><svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg> 拍照问安全</h2>

            <span class="head-spacer"></span>

            <span class="head-note">仅辅助识别肉眼可见风险</span>

          </div>

          <div class="panel-body">

            <p class="lead">拍一张现场照片，辅助识别肉眼可见的安全风险。照片不能替代现场安全员检查，也不会证明现场完全合规。</p>

            <!-- ===== AI 识别工作台：上传区（竞赛级改造） ===== -->
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

              <button id="cameraButton" class="secondary-button" type="button"><svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg> 打开摄像头拍照</button>

              <button id="filePickButton" class="secondary-button" type="button"><svg class="ico" aria-hidden="true"><use href="#i-image"/></svg> 从相册 / 文件选择</button>

              <button id="captureButton" class="secondary-button" type="button" hidden><svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg> 拍下这一张</button>

              <button id="cameraStopButton" class="secondary-button" type="button" hidden><svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg> 关闭摄像头</button>

              <button id="photoRetakeButton" class="secondary-button" type="button" hidden><svg class="ico" aria-hidden="true"><use href="#i-refresh"/></svg> 重拍 / 换一张</button>

            </div>

            <input id="sitePhoto" class="sr-only" type="file" accept="image/*" capture="environment"

                   aria-label="选择或拍摄现场照片" />

            <input id="sitePhotoCamera" class="sr-only" type="file" accept="image/*"

                   aria-label="从相册或文件选择现场照片" />



            <div id="cameraStage" class="camera-stage" hidden>

              <video id="cameraVideo" playsinline muted aria-label="摄像头实时预览"></video>

              <div class="camera-hint" id="cameraHint">把作业面、防护设施和周边环境一起拍进去；光线不足时先补光再拍。</div>

            </div>



            <div id="photoStage" class="photo-stage" hidden>

              <img id="photoPreview" alt="待分析的现场照片预览" />

              <div class="photo-facts" id="photoFacts"></div>

              <div class="progress-inline" id="photoProgress" hidden>

                <span>上传中</span>

                <span class="bar"><i id="photoProgressBar"></i></span>

                <span id="photoProgressText" class="num">0%</span>

                <button id="photoCancelButton" class="ghost-button" type="button"><svg class="ico" aria-hidden="true"><use href="#i-close"/></svg> 取消</button>

              </div>

            </div>



            <div class="composer-grid" style="margin-top:11px">

              <label class="sr-only" for="photoQuestion">补充说明（可选）</label>

              <textarea id="photoQuestion" style="min-height:74px" placeholder="可选：例如“这个脚手架看起来安全吗？我准备上去作业。”"></textarea>

              <button id="photoButton" class="secondary-button workbench-primary ico-button" type="button"><svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg>开始识别风险</button>

            </div>

            <div id="photoError" class="error-card" hidden></div>

            <div id="photoResult" class="result-box" hidden></div>

            <div class="photo-tips">

              <div class="photo-tip"><b>拍全一点</b>把作业面、防护设施和周边环境一起拍进去。</div>

              <div class="photo-tip"><b>光线要够</b>避免逆光和严重抖动，暗处细节模型看不出来。</div>

              <div class="photo-tip"><b>说清要干什么</b>补充一句你准备做什么，回答会更贴合。</div>

            </div>

            <p class="lead" id="visionNote" hidden></p>

          </div>

        </div>
        </div>
      </div>

      <!-- ============ L2 指标条：主指标 + 支撑指标 ============ -->
      <div class="tier-l2" role="group" aria-label="知识库与学习状态">

        <!-- 主指标：用户自己的安全知识水平（唯一有真实分母的指标） -->
        <div class="l2-cell is-primary">
          <div class="l2-ring-wrap">
            <svg class="l2-ring" id="kpiRing" viewBox="0 0 48 48" role="img"
                 aria-labelledby="kpiRingLabel">
              <title id="kpiRingLabel">安全知识测验最佳成绩</title>
              <circle class="l2-ring-track" cx="24" cy="24" r="20"/>
              <circle class="l2-ring-fill" id="kpiRingFill" cx="24" cy="24" r="20"
                      stroke-dasharray="125.66" stroke-dashoffset="125.66"/>
            </svg>
            <div class="l2-ring-center">
              <span class="l2-ring-pct" id="kpiRingPct">--</span>
              <span class="l2-ring-unit">%</span>
            </div>
          </div>
          <div class="l2-primary-text">
            <div class="l2-label">我的安全知识</div>
            <div class="l2-num l2-num-sm"><span id="kpiQuiz">0/20</span></div>
            <div class="l2-note" id="kpiQuizNote">还没有测验记录</div>
          </div>
        </div>

        <!-- 支撑指标：系统知识库规模（无有效分母，不画环） -->
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiChunks">--</span><span class="unit">条</span></div>
          <div class="l2-label">知识片段</div>
          <div class="l2-note" id="kpiChunksNote">正在读取知识库</div>
        </div>
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiDocs">--</span><span class="unit">份</span></div>
          <div class="l2-label">入库文档</div>
          <div class="l2-note" id="kpiDocsNote">安全法规 / 项目制度 / 培训资料</div>
        </div>
        <div class="l2-cell">
          <div class="l2-num"><span id="kpiCases">--</span><span class="unit">例</span></div>
          <div class="l2-label">真实案例</div>
          <div class="l2-note">事故与隐患通报整理</div>
        </div>
      </div>

      <!-- ============ L3 主行动卡：这一屏要我干什么 ============ -->
      <div class="tier-l3">
        <div class="l3-head">
          <svg class="ico ico-lg" aria-hidden="true"><use href="#i-clipboard"/></svg>
          <h2>班前 5 分钟：四步走完</h2>
          <span class="l3-badge">每班必做</span>
        </div>
        <p class="l3-lead">按顺序走：进门先过关 → 先弄清风险 → 再检查机具 → 不确定就停。勾选结果保存在本机，刷新后仍在；发现不满足条件时先停下来报告，不要硬上。</p>
        <div id="todoList" class="todo-list"></div>
        <div class="l3-action">
          <div class="l3-progress">
            <div class="tier-progress"><i id="todoFill" style="width:0%"></i></div>
            <span id="todoLabel" class="l3-count">0 / 5</span>
          </div>
          <button id="todoReset" class="ghost-button ico-button" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-refresh"/></svg>重置
          </button>
          <button id="todoStart" class="primary-button ico-button" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-check"/></svg>开始逐条确认
          </button>
        </div>
      </div>

      <!-- ============ L4 内容卡：每日警示案例 ============ -->
      <details class="disclosure">
  <summary>安全底线（三条，必读）<span class="disclosure-hint">展开看全部</span></summary>
  <div class="disclosure-body">
<div class="tier-l4">
        <div class="l4-head">
          <svg class="ico" aria-hidden="true"><use href="#i-alert"/></svg>
          <h2>每日警示案例</h2>
          <span class="l4-note">每天轮换一条，看完再上工</span>
        </div>
        <div class="l4-body" id="homeDailyCase">
          <div class="tier-skeleton" style="height:74px"></div>
        </div>
      </div>
  </div>
</details>

      <!-- ============ §5-4 引导图：PPE 六件套 ============ -->
      <figure class="ill-figure ill-ppe">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illPpeLabel">
          <title id="illPpeLabel">个人防护用品：安全帽、安全带、防护手套、护目镜、反光背心、安全鞋</title>
          <use href="#ill-ppe"/>
        </svg>
        <figcaption>上工前对照检查个人防护用品是否齐全、完好。</figcaption>
      </figure>

      <!-- ============ L5 引用块：安全底线（6 条必须保留） ============ -->
      <div class="tier-l4">
        <div class="l4-head">
          <svg class="ico" aria-hidden="true"><use href="#i-shield"/></svg>
          <h2>安全底线</h2>
        </div>
        <div class="l4-body">
          <div class="tier-l5 is-danger">
            <div class="l5-ref"><span class="l5-code">底线 1</span></div>
            <div class="l5-quote"><b>先停、先撤、先报。</b>发现异常先停工撤离并报告，不擅自拆改防护、维修设备或冒险施救。</div>
          </div>
          <div class="tier-l5 is-caution">
            <div class="l5-ref"><span class="l5-code">底线 2</span></div>
            <div class="l5-quote"><b>安全底线优先于进度和评分。</b>进度和评分不能让位于安全；<b>不接受未经训练人员冒险施救</b>，高后果决策由现场安全员、交底和作业许可确认。</div>
          </div>
          <div class="tier-l5">
            <div class="l5-ref"><span class="l5-code">底线 3</span></div>
            <div class="l5-quote">本页指引<b>不替代正式规范、项目制度、作业许可和现场判断</b>，也<b>不替代现场安全管理和专项方案</b>；测验结果<b>不作为上岗资格或考核合格判定依据</b>。</div>
            <div class="l5-source">
              <svg class="ico ico-sm" aria-hidden="true"><use href="#i-doc"/></svg>
              来源：安全生产法规与标准库（可在「学习与资料 → 标准库」查条款原文）
            </div>
          </div>
        </div>
      </div>

    </section><section id="ask" class="view" aria-label="现场问答">

      <div class="panel">

        <div class="chat-toolbar">

          <span class="tb-label">当前工种</span>

          <div id="assistantRoleChips" class="role-chips"></div>

          <span class="head-spacer"></span>

          <button id="chatClear" class="ghost-button" type="button">清空对话</button>

        </div>

        <div class="panel-body">

          <div id="composerStatus" class="composer-status" role="status">

            <span id="composerStatusText">回答由安全知识库与已配置模型共同生成，会显示依据和来源，不用推测内容补全。</span>

          </div>

          <h2 class="sec-title">可以这样问</h2>

          <div id="quickList" class="quick-list"></div>

        </div>

        <div id="chatStream" class="chat-stream" aria-live="polite">

          <div class="msg-row">

            <div class="avatar" aria-hidden="true">筑</div>

            <div class="bubble">

              <div class="bubble-title">我是筑安智培，新工人安全助手。</div>

              <div class="bubble-meta">先在上面选好你的工种，再问下面的问题会更准。</div>

              <div class="answer-body">你不用记专业术语。告诉我你准备做什么、看到什么、哪里不确定，我会尽量用现场能听懂的话说。</div>

            </div>

          </div>

        </div>

        <div class="chat-composer">

          <div class="composer-grid">

            <label class="sr-only" for="question">输入你的安全问题</label>

            <textarea id="question" placeholder="例如：塔吊吊装时哪些区域不能站人？"></textarea>

            <button id="askButton" class="primary-button" type="button">查询安全依据</button>

          </div>

          <div class="composer-tools">

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

          </details>

          <div id="recordingRow" class="recording-row" hidden>

            <span class="rec-dot" aria-hidden="true"></span>

            <span>正在录音</span>

            <span id="recordTimer" class="record-timer num">0.0s</span>

            <span class="answer-meta">最长 60 秒；安静环境下靠近手机说话更准</span>

          </div>

          <div id="asrNotice" class="notice" style="margin-top:11px;margin-bottom:0" hidden></div>

          <span id="voiceHint" class="answer-meta" hidden>正在检测可用的语音通道…</span>

        </div>

      </div>



            <div class="panel">
        <div class="panel-head"><h2>需要看图判断？</h2><span class="head-spacer"></span><span class="head-note">用首页的识别工作台</span></div>
        <div class="panel-body">
          <p class="lead">照片识别需要上传图片，在首页的 AI 工作台完成。文字问答不受影响，可以继续在这里提问。</p>
          <button class="secondary-button ico-button" data-jump="home" type="button">
            <svg class="ico" aria-hidden="true"><use href="#i-camera"/></svg>去首页拍照识别
          </button>
        </div>
      </div>

    </section>



    <!-- ================= 安全培训 ================= -->

    <section id="learn" class="view" aria-label="安全培训">

<div class="panel">

        <div class="panel-head">

          <h2>培训路线</h2>

          <span class="head-spacer"></span>

          <span class="head-note">进度与成绩只保存在本机浏览器</span>

        </div>

        <div class="panel-body">

          <div class="quiz-meta-row">

            <div class="quiz-stat"><b id="trainStepDone" class="num">0/5</b><span>培训路线已完成步骤</span></div>

            <div class="quiz-stat"><b id="trainQuizScore" class="num">未测</b><span>最近一次测验得分</span></div>

          </div>

          <div class="progress-row" style="margin-top:14px">

            <div class="progress-track"><div id="trainFill" class="progress-fill"></div></div>

            <span id="trainLabel" class="progress-label">0%</span>

          </div>

          <p class="lead">培训路线来自新工人入场培训要求，用于班组自主学习和岗前提醒，不替代项目三级安全教育与交底。</p>

        </div>

      </div>

      <figure class="ill-figure ill-scaffold">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illScaffoldLabel">
          <title id="illScaffoldLabel">脚手架安全做法：立杆、剪刀撑、扫地杆、作业层防护齐全</title>
          <use href="#ill-scaffold"/>
        </svg>
        <figcaption>脚手架要点：立杆与剪刀撑齐全、设扫地杆、作业层防护完整。搭拆必须由持证人员按方案进行。</figcaption>
      </figure>

<div class="panel" id="trainPathPanel">

        <div class="panel-head"><h2>新人 5 步培训路线</h2><span class="head-spacer"></span><span class="head-note">逐条打勾，记录自己学到哪一步</span></div>

        <div class="panel-body"><div id="stepList" class="step-list"></div></div>

      </div>

<details class="disclosure">
  <summary>学习积分与培训记录<span class="disclosure-hint">积分 / 记录单</span></summary>
  <div class="disclosure-body">
<div class="panel" id="pointsPanel">

        <div class="panel-head">

          <h2><svg class="ico" aria-hidden="true"><use href="#i-award"/></svg> 学习积分与培训记录</h2>

          <span class="head-spacer"></span>

          <span class="head-note">只统计本机学习行为，不上传</span>

        </div>

        <div class="panel-body">

          <p class="lead">积分来自你在本机的学习行为：完成培训步骤、做对测验题、完成班前确认。达标后可生成一张可打印的 A4 培训记录单。</p>

          <div class="points-head">

            <div class="points-total">

              <b id="pointsTotal" class="num">0</b>

              <span>累计积分</span>

            </div>

            <div class="points-breakdown" id="pointsBreakdown"></div>

          </div>

          <div class="progress-row" style="margin-top:6px">

            <div class="progress-track"><div id="pointsFill" class="progress-fill"></div></div>

            <span id="pointsLabel" class="progress-label">0 / 120</span>

          </div>

          <p class="lead" id="pointsHint">还差 120 分可以生成培训记录单。</p>

          <div class="quiz-actions" style="margin-top:14px">

            <button id="certificateButton" class="secondary-button" type="button" disabled>生成培训记录单</button>

            <button id="certificatePrint" class="secondary-button" type="button" hidden><svg class="ico" aria-hidden="true"><use href="#i-print"/></svg> 打印 / 存为 PDF</button>

            <button id="pointsReset" class="ghost-button" type="button">清除本机学习记录</button>

          </div>

          <div id="certificateArea" hidden></div>

        </div>

      </div>
  </div>
</details>

<div class="panel" id="trainRolesPanel">

        <div class="panel-head"><h2>工种专项风险要点</h2><span class="head-spacer"></span><span class="head-note">共 6 个工种</span></div>

        <div class="panel-body">

          <div id="roleChips" class="role-chips"></div>

          <div id="roleDetail" class="role-detail"></div>

        </div>

      </div>

<div class="panel" id="trainQuizPanel">

        <div class="panel-head"><h2>新工人安全知识测验</h2><span class="head-spacer"></span><span class="head-note">20 题 · 单选题</span></div>

        <div class="panel-body">

          <p class="lead" id="quizIntro"></p>

          <div class="notice">本测验用于培训自检，不作为上岗资格或考核合格判定依据；上岗条件以项目安全教育、交底和持证要求为准。答题结果只保存在你自己的浏览器里，不会上传到服务端。</div>

          <div class="quiz-actions" style="margin-top:14px">

            <button id="quizStart" class="amber-button" type="button">开始测验</button>

            <button id="quizReset" class="secondary-button" type="button">清除我的记录</button>

          </div>



          <div id="quizHome" style="margin-top:16px">

            <div class="quiz-status">

              <div class="ring-wrap">

                <svg class="ring" width="132" height="132" viewBox="0 0 132 132" role="img" aria-label="测验掌握度">

                  <circle class="ring-bg" cx="66" cy="66" r="55" stroke-width="12"></circle>

                  <circle id="ringFg" class="ring-fg" cx="66" cy="66" r="55" stroke-width="12"></circle>

                </svg>

                <div style="margin-top:-88px;text-align:center">

                  <div id="ringNum" class="ring-num">0%</div>

                  <div class="ring-cap">历史最佳掌握度</div>

                </div>

                <div style="height:56px"></div>

              </div>

              <div>

                <h3 class="sec-title">我的掌握情况</h3>

                <p class="lead" id="quizHomeNote">还没有测验记录。点“开始测验”做一遍，看看哪些风险域还没掌握。</p>

                <div id="domainBars" class="domain-bars"></div>

          <div class="chart-block">
            <h3 class="l4-sub">近 7 天学习记录</h3>
            <div id="studyHeat" class="heat-grid" role="img" aria-label="近 7 天学习热力格"></div>
            <div class="heat-legend">
              <span>少</span>
              <span class="heat-cell" data-level="0"></span>
              <span class="heat-cell" data-level="1"></span>
              <span class="heat-cell" data-level="2"></span>
              <span class="heat-cell" data-level="3"></span>
              <span class="heat-cell" data-level="4"></span>
              <span>多</span>
              <span id="studyHeatNote" class="answer-meta"></span>
            </div>
          </div>

          <div class="chart-block">
            <h3 class="l4-sub">测验正确率趋势</h3>
            <div id="quizTrend"></div>
          </div>

              </div>

            </div>

          </div>



          <div id="quizPlay" hidden></div>

          <div id="quizResult" hidden></div>

        </div>

      </div>

<details class="disclosure">
  <summary>案例库<span class="disclosure-hint">6 例 · 含分类筛选</span></summary>
  <div class="disclosure-body">
<div class="panel">

        <div class="panel-head">

          <h2><svg class="ico" aria-hidden="true"><use href="#i-doc"/></svg> 真实事故 / 隐患案例</h2>

          <span class="head-spacer"></span>

          <span class="head-note" id="caseCountNote">加载中…</span>

        </div>

        <div class="panel-body">

          <p class="lead">通过真实事故与隐患案例，帮助作业人员识别典型风险、理解事故成因，并掌握正确的防范措施。</p>

          <div id="caseFilters" class="filter-row" style="margin-top:14px"></div>

          <div class="case-search">

            <label class="sr-only" for="caseSearch">按关键词搜索案例</label>

            <input id="caseSearch" type="search" aria-label="按关键词搜索案例" placeholder="例如：吊装、安全带、临边、坠落" />

            <button id="caseSearchButton" class="secondary-button" type="button">查案例</button>

          </div>

          <div id="caseGrid" class="case-grid"></div>

        </div>

      </div>
  </div>
</details>

<details class="disclosure">
  <summary>标准现行状态<span class="disclosure-hint">46 部 · 现行 / 即将实施</span></summary>
  <div class="disclosure-body">
<div class="panel" id="standardsPanel">

        <div class="panel-head">

          <h2><svg class="ico" aria-hidden="true"><use href="#i-chart"/></svg> 标准现行状态</h2>

          <span class="head-spacer"></span>

          <span class="head-note" id="standardsNote">加载中…</span>

        </div>

        <div class="panel-body">

          <p class="lead">来自国家标准全文公开系统的公开元数据：只登记标准编号、名称、状态与官方入口，不复制受限全文。使用前请以官方发布版本为准。</p>

          <div class="search-row" style="margin-top:14px">

            <label class="sr-only" for="standardsSearch">检索标准编号或名称</label>

            <input id="standardsSearch" type="search" placeholder="检索标准：例如 JGJ 59、安全带、临时用电" />

            <button id="standardsSearchClear" class="secondary-button" type="button">清除</button>

          </div>

          <div id="standardsTable" aria-busy="true">

            <div class="skeleton skeleton-line w80" aria-hidden="true"></div>

            <div class="skeleton skeleton-card" aria-hidden="true"></div>

          </div>

        </div>

      </div>
  </div>
</details>

<details class="disclosure">
  <summary>在线模型与培训上下文<span class="disclosure-hint">技术信息</span></summary>
  <div class="disclosure-body">
<div class="panel">

        <div class="panel-head"><h2>在线模型与培训上下文</h2></div>

        <div class="panel-body">

          <p class="lead">提问时会把你选择的工种和培训阶段作为上下文一起交给模型，让回答更贴合你的作业内容；未选择工种时按通用要点回答。</p>

          <div class="kv-list">

            <div><dt>当前工种</dt><dd id="kvRole">未选择</dd></div>

            <div><dt>培训路线完成</dt><dd id="kvSteps">0 / 5</dd></div>

            <div><dt>最近测验</dt><dd id="kvQuiz">无记录</dd></div>

            <div><dt>学习积分</dt><dd id="kvPoints">0</dd></div>

            <div><dt>进度存储</dt><dd>浏览器本地</dd></div>

          </div>

          <p class="lead">未连接模型时自动返回检索摘要，仍会显示规范依据与来源。</p>

          <pre id="modelCommand"></pre>

        </div>

      </div>
  </div>
</details>

<details class="disclosure">
  <summary>知识库状态<span class="disclosure-hint">文档 / 片段 / 服务</span></summary>
  <div class="disclosure-body">
<div class="panel">
  <div class="panel-head"><h2>知识库状态</h2><span class="head-spacer"></span><span class="head-note">服务端实时统计</span></div>
  <div class="panel-body">
    <div class="metric-grid">
      <div class="metric"><strong id="documentCount" class="num">0</strong><span>知识片段</span></div>
      <div class="metric"><strong id="chunkCount" class="num">0</strong><span>入库文档</span></div>
      <div class="metric"><strong id="caseCount" class="num">0</strong><span>真实案例</span></div>
      <div class="metric"><strong id="roleCount" class="num">0</strong><span>工种专项</span></div>
    </div>
    <p class="lead" id="kbNote">正在读取服务端知识库…</p>
  </div>
</div>
  </div>
</details>

<details class="kb-sub">
  <summary>已入库文档 / 领域分布 / 最近入库 / 服务状态</summary>
  <div class="kb-sub-body">
<div class="panel">

        <div class="panel-head">

          <h2><svg class="ico" aria-hidden="true"><use href="#i-doc"/></svg> 已入库文档</h2>

          <span class="head-spacer"></span>

          <span class="head-note" id="libraryNote">加载中…</span>

        </div>

        <div class="panel-body">

          <p class="lead">内容和全文索引保存在服务端 SQLite 数据库中，按类别分组展示。输入关键词会高亮匹配到的文字，便于班组培训选题。</p>

          <div class="search-row" style="margin-top:14px">

            <label class="sr-only" for="docSearch">在文档标题、来源与类别中检索</label>

            <input id="docSearch" type="search" placeholder="检索文档：例如 安全帽、高处作业、JGJ" />

            <button id="docSearchClear" class="secondary-button" type="button">清除</button>

          </div>

          <div id="docFilterRow" class="doc-cat-bar"></div>

          <div id="docCountLine" class="doc-count-line"></div>

          <div id="docGroups" style="margin-top:6px" aria-busy="true">

            <div class="skeleton skeleton-line w80" aria-hidden="true"></div>

            <div class="skeleton skeleton-line w60" aria-hidden="true"></div>

            <div class="skeleton skeleton-card" aria-hidden="true"></div>

          </div>

        </div>

      </div>
<div class="panel">

            <div class="panel-head"><h2>知识领域分布</h2></div>

            <div class="panel-body">

              <div id="sideDomains" class="side-hot" aria-busy="true">

                <div class="skeleton skeleton-line w80" aria-hidden="true"></div>

                <div class="skeleton skeleton-line w60" aria-hidden="true"></div>

                <div class="skeleton skeleton-line w80" aria-hidden="true"></div>

              </div>

              <p class="lead">按量统计当前入库文档覆盖的风险领域，可用于班组培训选题。</p>

            </div>

          </div>
<div class="panel">
  <div class="panel-head"><h2>最近入库</h2><span class="head-spacer"></span><span class="head-note">最新 10 篇</span></div>
  <div class="panel-body">
    <ul id="sideDocuments" class="side-doc-list" aria-busy="true">
      <li class="skeleton skeleton-line" aria-hidden="true"></li>
      <li class="skeleton skeleton-line" aria-hidden="true"></li>
    </ul>
    <p class="lead">完整检索、按类别筛选与关键词高亮请在「知识库」页使用。</p>
    <button class="secondary-button" type="button" data-goto="library">打开知识库 →</button>
  </div>
</div>
<div class="panel">

        <div class="panel-head"><h2 class="side-title">服务状态</h2></div>

        <div class="panel-body">

          <div class="kv-list">

            <div><dt>版本</dt><dd>V16.0.0</dd></div>

            <div><dt>问答模式</dt><dd id="kvMode">检测中</dd></div>

            <div><dt>照片识别</dt><dd id="kvVision">检测中</dd></div>

            <div><dt>语音识别</dt><dd id="kvAsr">检测中</dd></div>

            <div><dt>访问控制</dt><dd id="kvAccess">未启用</dd></div>

          </div>

        </div>

      </div>
  </div>
</details>

<details class="disclosure">
  <summary>检索与合规说明<span class="disclosure-hint">使用边界</span></summary>
  <div class="disclosure-body">
<div class="panel">

        <div class="panel-head"><h2>检索与合规说明</h2></div>

        <div class="panel-body">

          <div class="callout is-amber">

            <b>标准化内容仍需核对</b>

            <code>data/knowledge/</code> 是演示摘要，<code>data/sources/normalized/</code> 是已标准化文本。正式使用前应核对现行版本、项目适用性和授权范围。

          </div>

          <div class="callout is-danger" style="margin-top:11px">

            <b>高后果决策不由模型决定</b>

            模型输出仅作辅助，不替代正式规范、项目制度、作业许可、安全交底和现场安全员判断。

          </div>

        </div>

      </div>
  </div>
</details>

    </section>

    <section id="pre" class="view" aria-label="开工前检查">

      <!-- ========== §11 当班条件 ========== -->
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
      <details class="disclosure">
  <summary>导入项目自有清单<span class="disclosure-hint">csv / txt / md / xlsx</span></summary>
  <div class="disclosure-body">
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
  </div>
</details>

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


<div class="panel">

        <figure class="ill-figure ill-edge">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illEdgeLabel">
          <title id="illEdgeLabel">临边防护做法：防护栏杆高度 1.2 米、中间栏杆、挡脚板不低于 180 毫米</title>
          <use href="#ill-edge"/>
        </svg>
        <figcaption>临边防护要点：栏杆 1.2m、设中间防护、挡脚板 ≥180mm。数值以适用规范与现场交底为准。</figcaption>
      </figure>

      <details class="disclosure">
  <summary>检查项目索引（参考，不代替标准检查表）<span class="disclosure-hint">9 类 · 按 JGJ 59-2011 整理</span></summary>
  <div class="disclosure-body">
<div class="panel-head">

          <h2>检查项目索引</h2>

          <span class="head-spacer"></span>

          <span class="head-note">JGJ 59-2011 场景索引 · 9 类</span>

        </div>
  </div>
</details>

        <div class="panel-body">

          <p class="lead">按场景整理的索引，便于班前对照，不代替标准检查评分表和项目适用性判定。</p>

          <div id="inspectionChecks"></div>
          <table class="tier-table">
            <caption>检查项目索引说明 —— 按 JGJ 59-2011 的场景分类整理，便于班前对照</caption>
            <thead>
              <tr><th scope="col">类别</th><th scope="col">条数</th><th scope="col">覆盖内容</th></tr>
            </thead>
            <tbody>
              <tr><td>安全管理</td><td>3</td><td>责任制度、专项方案、安全技术交底、检查教育、应急救援</td></tr>
              <tr><td>文明施工</td><td>3</td><td>围挡封闭、场地道路、材料堆放、消防、办公住宿、标牌</td></tr>
              <tr><td>脚手架</td><td>3</td><td>扣件式、门式、碗扣式、盘扣式、满堂、悬挑、附着式升降</td></tr>
              <tr><td>基坑工程</td><td>3</td><td>支护、排水、临边防护、监测、坑边荷载</td></tr>
              <tr><td>模板支架</td><td>3</td><td>支架基础、立杆、水平杆、剪刀撑、验收与混凝土浇筑监护</td></tr>
            </tbody>
          </table>

        </div>

      </div>

    </section>



    <!-- ================= 知识库 ================= -->

    



    <!-- ================= 应急求助 ================= -->

    <section id="sos" class="view" aria-label="应急求助">

      <!-- ========== §6 红警带：进页面第一眼就要看到 ========== -->
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
      </div>

      <figure class="ill-figure ill-emergency">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illEmergencyLabel">
          <title id="illEmergencyLabel">应急处置三步骤：停手、撤离到安全区、报告负责人</title>
          <use href="#ill-emergency"/>
        </svg>
        <figcaption>出事先做这三步：停手 → 撤到安全区 → 报告负责人。具体以项目应急预案和现场指挥为准。</figcaption>
      </figure>

      <div class="panel">

        <div class="panel-head"><h2>选择发生的情况</h2><span class="head-spacer"></span><span class="head-note">点一下看处置步骤</span></div>

        <div class="panel-body">

          <div id="emergencyGrid" class="emergency-grid"></div>

          <div id="emergencyGuide" class="emergency-guide" hidden></div>

        </div>

      </div>

      <div class="panel">

        <div class="panel-head"><h2>应急电话与报告</h2></div>

        <div class="panel-body">

          <div class="em-call-bar" id="emCallBar">

            <a id="call120" class="call-button is-medical" href="tel:120"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 120 急救</a>

            <a id="call119" class="call-button is-fire" href="tel:119"><svg class="ico" aria-hidden="true"><use href="#i-phone"/></svg> 119 火警</a>

            <button id="sosPrint" class="call-button is-print" type="button"><svg class="ico" aria-hidden="true"><use href="#i-print"/></svg> 打印这张卡</button>

          </div>

          <div class="kv-list">

            <div><dt>现场负责人 / 安全员电话</dt><dd>按项目公示填写</dd></div>

            <div><dt>紧急集合点</dt><dd>按项目平面布置确认</dd></div>

            <div><dt>撤离路线</dt><dd>按现场疏散标识</dd></div>

          </div>

          <p class="lead">以上电话与集合点请以项目现场公示、应急预案和班前交底为准。本页指引用于快速提醒，不替代项目应急预案与专业救援指挥。</p>

        </div>

      </div>

    </section>



    <!-- ================= 侧栏 ================= -->

    

  </main>



  <footer>

    <div class="footer-inner">

      <div class="footer-line">

        <b>安全底线优先于进度和评分。</b>

        <span>紧急情况先撤离、报警和报告，不接受未经训练人员冒险施救。</span>

      </div>

      <div class="footer-line">

        <span>筑安智培 · 新工人安全培训问答智能体 · V16.0.0</span>

        <span>模型输出仅作辅助，不替代正式规范、项目制度、作业许可和现场判断。</span>

      </div>

    </div>

  </footer>


  <!-- ========== §6 全站常驻 SOS 入口 ========== -->
  <a id="sosFab" class="sos-fab" href="?view=sos" aria-label="紧急情况，去应急处置页">
    <svg class="ico ico-xl" aria-hidden="true"><use href="#i-phone"/></svg>
    <span class="sos-fab-text">应急</span>
  </a>
  <script>
  (function () {
    "use strict";

    /* ===== THEME BOOT BEGIN ===== */
    /* 主题：默认白天（方案 C：纯白 + 单一蓝），可切夜间（方案 B：深蓝黑 + 明黄）。
       这段必须在 <head> 里同步执行——放到文件末尾的话，
       夜间用户会先看到一帧亮色界面再被切暗（闪白）。 */
    (function () {
      var KEY = "sitesaha-theme-v1";

      /* URL 上的 ?theme=dark / ?theme=light 只影响本次访问，不写入 localStorage。
         用于演示、截图核对和排查配色问题。
         注意：这里刻意不用正则，也不用任何反斜杠转义——
         分片文件必须保持零反斜杠，否则 inject.py 无法安全地写入 Python 字符串。 */
      function fromQuery() {
        try {
          var query = String(window.location.search || "");
          if (query.charAt(0) === "?") query = query.slice(1);
          if (!query) return "";
          var parts = query.split("&");
          for (var i = 0; i < parts.length; i += 1) {
            var pair = parts[i].split("=");
            if (decodeURIComponent(pair[0] || "") !== "theme") continue;
            var value = decodeURIComponent(pair[1] || "").toLowerCase();
            if (value === "dark" || value === "light") return value;
          }
          return "";
        } catch (e) {
          return "";
        }
      }

      function preferred() {
        var forced = fromQuery();
        if (forced) return forced;
        var saved = "";
        try { saved = window.localStorage.getItem(KEY) || ""; } catch (e) { saved = ""; }
        if (saved === "dark" || saved === "light") return saved;
        try {
          if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
            return "dark";
          }
        } catch (e) { /* 不支持 matchMedia 时按白天处理 */ }
        return "light";
      }

      function paint(theme) {
        var root = document.documentElement;
        if (theme === "dark") root.setAttribute("data-theme", "dark");
        else root.removeAttribute("data-theme");
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", theme === "dark" ? "#0e1c28" : "#17385c");
        var button = document.getElementById("themeToggle");
        if (button) {
          button.replaceChildren(iconText("i-clock", theme === "dark" ? "白天" : "夜间"));
          button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
        }
      }

      window.__sitesahaTheme = {
        preferred: preferred,
        paint: paint,
        toggle: function () {
          var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
          paint(next);
          try { window.localStorage.setItem(KEY, next); } catch (e) { /* 隐私模式忽略 */ }
        },
      };

      // 立即上色，不等 DOMContentLoaded
      paint(preferred());
      // 顶栏按钮在页面主体里，解析到之后补一次文案
      // （注意：注释里不要写尖括号标签，assemble.py 的标签计数会把它算进去）
      document.addEventListener("DOMContentLoaded", function () {
        paint(preferred());
      });
    })();
    /* ===== THEME BOOT END ===== */

    /* ==================================================================
       1. 常量与本地存储
       ================================================================== */
    var ACCESS_CODE_KEY = "sitesaha-access-code";
    var PROFILE_KEY = "sitesaha-profile-v1";
    var CHECKLIST_KEY = "sitesaha-checklist-v1";
    var QUIZ_KEY = "sitesaha-quiz-v1";
    var PRACTICAL_KEY = "sitesaha-practical-v1";
    var EMPTY_QUIZ = { attempts: 0, bestPercent: 0, bestCorrect: 0, total: 20, lastCorrect: 0, lastAt: "", wrongDomains: {}, seen: {} };

    /* 今天上工前的三件事（第一条为入场三件事合并项，共 5 条） */
    var PRACTICAL_ITEMS = [
      { id: "entry", step: 1, label: "入口三件事已完成", hint: "实名进场、安全教育、班前交底都确认过" },
      { id: "ppe", step: 1, label: "安全帽下颚带、防护鞋和必要防护用品已到位", hint: "按当天作业风险选用，破损失效立即更换" },
      { id: "hazard", step: 2, label: "知道今天的风险点、禁区和撤离路线", hint: "临边洞口、吊装区、配电区、基坑边在哪里" },
      { id: "machine", step: 3, label: "设备和工具开机前检查过防护、限位和急停", hint: "有异常先停机断电挂牌，不自己拆修" },
      { id: "stop", step: 4, label: "不确定的事不硬上，先停工问负责人", hint: "赶工和评分不能替代安全底线" },
    ];

    /* 班前动线的四步（§7 方向 2）。
       分组参照旧版手册：进门 → 风险 → 机具 → 停。
       注意：勾选项一条都没减少（用户要求"不合并"），只是按步骤归位。 */
    var PRACTICAL_STEPS = [
      { n: 1, title: "进门先过关", note: "没交底、没防护，不上岗" },
      { n: 2, title: "先弄清风险", note: "知道哪里危险、往哪撤" },
      { n: 3, title: "再检查机具", note: "设备带病不上手" },
      { n: 4, title: "不确定就停", note: "停下来问，比硬上便宜" },
    ];

    /* 现场问答快捷问题：带工种标签，按工种高亮 */
    /* 快捷提问按场景分组（第 16 轮 §6：每组 ≤4 个，超出折叠）。
       分组按新工人实际会遇到的场景，不是按专业分类。 */
    var QUICK_GROUPS = [
      {
        title: "第一天上工",
        hint: "刚进场，先弄清这几件",
        items: [
          { text: "我是第一次上工地，入场后先做什么？", roles: [] },
          { text: "进入施工现场必须做哪些防护？", roles: [] },
        ],
      },
      {
        title: "常见高风险",
        hint: "这些场景出事最多",
        items: [
          { text: "高处作业前要检查什么？", roles: ["架子工", "钢筋工", "木工", "焊工", "电工", "普工/杂工"] },
          { text: "吊物下方为什么不能站人？", roles: [] },
          { text: "基坑出现裂缝和渗水怎么处理？", roles: ["普工/杂工", "钢筋工"] },
          { text: "动火作业前要做哪些确认？", roles: ["焊工"] },
        ],
      },
      {
        title: "本工种专项",
        hint: "按你选的工种出题",
        collapsed: true,
        items: [
          { text: "脚手架验收牌有什么作用？", roles: ["架子工"] },
          { text: "发现配电箱进水怎么办？", roles: ["电工"] },
          { text: "钢筋加工机械清理前要做什么？", roles: ["钢筋工"] },
          { text: "圆盘锯的防护罩能拆掉吗？", roles: ["木工"] },
        ],
      },
    ];


    var QUIZ_OPTION_KEYS = ["A", "B", "C", "D", "E"];

    /* ==================================================================
       2. 应急场景数据
       ================================================================== */
    var EMERGENCY_DATA = [
      {
        key: "受伤", icon: "i-firstaid", label: "有人受伤",
        headline: "先确认自己安全，再呼救，不随意搬动重伤人员。",
        steps: [
          "立即停止相关作业，先确认自己不会进入二次危险区域。",
          "立即通知现场负责人和安全员，说明位置、人数和伤情。",
          "需要急救时拨打 120；现场有急救器材的按交底取用。",
          "重伤人员不要随意搬动，除非现场仍有立即危险。",
        ],
        never: "不要为了把人拖出来而让自己进入危险区域，也不要围在伤者周围影响救援和通风。",
        calls: ["120"],
      },
      {
        key: "火灾", icon: "i-fire", label: "发生火灾",
        headline: "先撤离、再报警，未受训练不返回火场。",
        steps: [
          "立即停止作业，远离烟气和火源，沿疏散路线撤离。",
          "在安全位置拨打 119，说清项目名称、位置和燃烧物。",
          "通知现场负责人，按现场要求启动疏散和清点人员。",
          "在集合点等待清点，听从现场应急指挥。",
        ],
        never: "未受过训练不要返回火场救人或取物；不要乘坐施工升降机逃生。",
        calls: ["119"],
      },
      {
        key: "触电", icon: "i-shock", label: "触电了",
        headline: "先断电、再救人，绝不徒手拉触电者。",
        steps: [
          "不要直接用手拉触电者，避免自己一起触电。",
          "能安全断电就立即切断电源或用绝缘物分离电源。",
          "远离带电设备并呼叫现场负责人和安全员。",
          "拨打 120；只有受过急救训练的人按现场要求实施救护。",
        ],
        never: "不要徒手接触触电者和带电设备，不要用水去浇电气火灾。",
        calls: ["120"],
      },
      {
        key: "坍塌", icon: "i-collapse", label: "坍塌 / 被困",
        headline: "立即撤离到安全区，不进入坍塌体盲目施救。",
        steps: [
          "马上撤离危险区域，撤到稳定地面和上方无堆载的位置。",
          "不要进入坍塌体内部或坑边盲目救人，避免二次坍塌。",
          "设置警戒并劝阻其他人员靠近，通知项目负责人。",
          "需要救援时拨打 119，等待专业救援力量到场。",
        ],
        never: "不要在不稳定的边坡、堆载或结构物下方停留和施救。",
        calls: ["119"],
      },
      {
        key: "高处坠落", icon: "i-fall", label: "高处坠落",
        headline: "先控制现场、防止二次坠落，再呼救。",
        steps: [
          "停止相关作业，防止其他人继续靠近临边和洞口。",
          "通知现场负责人和安全员，拨打 120。",
          "在专业人员指导下设置警戒，避免二次坠落和落物伤人。",
          "未受训练不要随意搬动重伤人员。",
        ],
        never: "不要为了查看伤情而自己站到没有防护的临边或洞口。",
        calls: ["120"],
      },
      {
        key: "其他危险", icon: "i-alert", label: "其他危险",
        headline: "不确定怎么处理时，先停下来、先离开、先报告。",
        steps: [
          "立即离开危险区域，站到稳定安全的位置。",
          "提醒附近工友，避免更多人进入。",
          "通知班组长、安全员或项目值班人员说明情况。",
          "紧急情况拨打 119 或 120，听现场指挥行动。",
        ],
        never: "不要为了赶工继续试、继续干，也不要自己拆改或维修不熟悉的设备。",
        calls: ["119", "120"],
      },
    ];

    var VIEW_ALIAS = { cases: "cases", voice: "ask", photo: "ask" };

    /* ==================================================================
       3. 存储与通用工具
       ================================================================== */
    function readStore(key, fallback) {
      try {
        var raw = window.localStorage.getItem(key);
        if (!raw) return fallback;
        var parsed = JSON.parse(raw);
        return parsed === null || parsed === undefined ? fallback : parsed;
      } catch (error) {
        return fallback;
      }
    }

    function writeStore(key, value) {
      try {
        window.localStorage.setItem(key, JSON.stringify(value));
      } catch (error) {
        /* 隐私模式或存储已满时静默降级，不影响本次使用 */
      }
    }

    function $(id) { return document.getElementById(id); }

    function make(tag, className, value) {
      var node = document.createElement(tag);
      if (className) node.className = className;
      if (value !== undefined && value !== null) node.textContent = String(value);
      return node;
    }

    /* 建一个真实的 svg/use 图标节点。
       为什么单独一个函数：make() 用 textContent，传 HTML 字符串会被转义成
       可见文本（页面上直接显示 <svg ...>）。图标必须走这里，契约才清楚。 */
    function makeIcon(symbolId, className) {
      var NS = "http://www.w3.org/2000/svg";
      var svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", className || "ico");
      svg.setAttribute("aria-hidden", "true");
      var use = document.createElementNS(NS, "use");
      use.setAttribute("href", "#" + symbolId);
      svg.appendChild(use);
      return svg;
    }

    /* 图标 + 文字的片段：返回 DocumentFragment，便于 appendChild 一次挂上 */
    function iconText(symbolId, text, className) {
      var frag = document.createDocumentFragment();
      frag.appendChild(makeIcon(symbolId, className));
      frag.appendChild(document.createTextNode(" " + text));
      return frag;
    }

    /* make() 的图标版：建 div/button 并把「图标 + 文字」一次性挂上 */
    function makeIconText(tag, className, symbolId, iconClass, text) {
      var node = make(tag, className);
      node.appendChild(makeIcon(symbolId, iconClass));
      node.appendChild(document.createTextNode(" " + text));
      return node;
    }

    function makeButtonWithIcon(className, symbolId, text) {
      var button = make("button", className);
      button.type = "button";
      button.appendChild(makeIcon(symbolId));
      button.appendChild(document.createTextNode(" " + text));
      return button;
    }

    /* ==================================================================
       回答正文的极简 Markdown 渲染
       ------------------------------------------------------------------
       只支持回答里真实出现的三种标记：**加粗**、无序列表、有序列表。
       安全前提：先把 HTML 全转义，再替换白名单标记 ——
       模型输出属于不可信内容，绝不能直接 innerHTML。

       注意：分片里不能写反斜杠，所以正则都用 RegExp 构造器拼。
       ================================================================== */
    /* 分片禁止出现反斜杠字符，所以正则里的转义用 fromCharCode(92) 拼出来。
       星号在正则里是量词，必须转义成「反斜杠 + 星号」才能匹配字面量。 */
    var ESC = String.fromCharCode(92);
    var STAR = String.fromCharCode(42);
    var RE_BOLD = new RegExp(ESC + STAR + ESC + STAR + "([^" + STAR + "]+)" +
      ESC + STAR + ESC + STAR, "g");
    var RE_BULLET = new RegExp("^[" + String.fromCharCode(45, 42, 8226) + "]" +
      String.fromCharCode(32) + "+(.*)$");
    var RE_SPACE = new RegExp("^" + String.fromCharCode(32) + "+");

    /* 有序列表手写解析，不用正则 —— 数字类会引入反斜杠 d。 */
    function matchNumbered(line) {
      var index = 0;
      while (index < line.length) {
        var code = line.charCodeAt(index);
        if (code < 48 || code > 57) break;
        index += 1;
      }
      if (index === 0 || index >= line.length) return null;
      var sep = line.charAt(index);
      if (sep !== "." && sep !== ")" && sep !== String.fromCharCode(12289)) return null;
      var rest = line.slice(index + 1);
      if (!rest.length) return null;
      if (rest.charAt(0) !== String.fromCharCode(32)) return null;
      return [rest.replace(RE_SPACE, "")];
    }

    function escapeHtml(text) {
      return String(text == null ? "" : text)
        .split("&").join("&amp;")
        .split("<").join("&lt;")
        .split(">").join("&gt;")
        .split(String.fromCharCode(34)).join("&quot;");
    }

    function stripTrailingSpaces(line) {
      var end = line.length;
      while (end > 0) {
        var code = line.charCodeAt(end - 1);
        if (code === 32 || code === 9 || code === 13 || code === 160) end -= 1;
        else break;
      }
      return line.slice(0, end);
    }

    function renderAnswerBody(text) {
      var host = document.createDocumentFragment();
      var lines = String(text == null ? "" : text).split(String.fromCharCode(10));
      var list = null;
      var listKind = "";

      function closeList() {
        if (list) {
          host.appendChild(list);
          list = null;
          listKind = "";
        }
      }

      function inline(raw) {
        /* 先转义，再把 **x** 换成 strong。顺序不能反。 */
        return escapeHtml(raw).replace(RE_BOLD, "<strong>$1</strong>");
      }

      lines.forEach(function (rawLine) {
        var line = stripTrailingSpaces(rawLine);
        if (!line.trim()) {
          closeList();
          return;
        }
        var bullet = line.match(RE_BULLET);
        var numbered = bullet ? null : matchNumbered(line);
        var kind = bullet ? "ul" : (numbered ? "ol" : "");

        if (kind) {
          if (listKind !== kind) {
            closeList();
            list = document.createElement(kind);
            list.className = "answer-list";
            listKind = kind;
          }
          var item = document.createElement("li");
          item.innerHTML = inline(bullet ? bullet[1] : numbered[1]);
          list.appendChild(item);
          return;
        }

        closeList();
        var para = document.createElement("p");
        para.className = "answer-line";
        para.innerHTML = inline(line);
        host.appendChild(para);
      });

      closeList();
      return host;
    }

    function clear(node) {
      if (node) node.replaceChildren();
      return node;
    }

    /* 访问码：兼容服务端可选的访问码保护 */
    function accessCode() {
      try { return window.localStorage.getItem(ACCESS_CODE_KEY) || ""; }
      catch (error) { return ""; }
    }

    async function apiFetch(url, options) {
      var opts = Object.assign({}, options || {});
      var headers = new Headers(opts.headers || {});
      var code = accessCode();
      if (code) headers.set("X-Access-Code", code);
      opts.headers = headers;
      var response = await fetch(url, opts);
      if (response.status === 401) {
        var entered = window.prompt("请输入管理员提供的访问码：", "");
        if (entered && entered.trim()) {
          try { window.localStorage.setItem(ACCESS_CODE_KEY, entered.trim()); } catch (error) { /* 忽略 */ }
          headers.set("X-Access-Code", entered.trim());
          response = await fetch(url, opts);
        }
      }
      return response;
    }

    async function getJson(url) {
      var response = await apiFetch(url, { method: "GET" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }

    /* POST JSON。走 apiFetch 而不是裸 fetch —— 它带访问码重试逻辑。 */
    async function postJson(url, body) {
      var response = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }

    function modeLabel(mode) {
      if (mode === "local-llm") return "在线大模型生成";
      if (mode === "extractive") return "SQLite 检索摘要";
      if (mode === "error") return "查询失败";
      return mode || "未知模式";
    }

    function fmtTime(value) {
      if (!value) return "";
      var date = new Date(value);
      if (isNaN(date.getTime())) return String(value);
      function pad(n) { return n < 10 ? "0" + n : String(n); }
      return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate())
        + " " + pad(date.getHours()) + ":" + pad(date.getMinutes());
    }

    /* ==================================================================
       4. 视图切换
       ================================================================== */
    function showView(name) {
      var target = VIEW_ALIAS[name] || name;
      var buttons = document.querySelectorAll(".nav-button");
      var known = false;
      for (var i = 0; i < buttons.length; i += 1) {
        if (buttons[i].dataset.view === target) known = true;
      }
      if (!known) target = "home";

      var views = document.querySelectorAll(".view");
      for (var j = 0; j < views.length; j += 1) {
        views[j].classList.toggle("active", views[j].id === target);
      }
      for (var k = 0; k < buttons.length; k += 1) {
        buttons[k].classList.toggle("active", buttons[k].dataset.view === target);
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    document.querySelectorAll(".nav-button").forEach(function (button) {
      button.addEventListener("click", function () { showView(button.dataset.view); });
    });

    /* 视图深链：?view=ask 之类的链接直接打开对应页。
       用途：现场分享某个页面的链接；截图脚本也依赖它（外部拿不到 IIFE 里的 showView）。
       放在这里同步执行 —— 脚本在 body 末尾，此时 DOM 已解析完，切页会先于首帧绘制。
       注意：必须逐层判断存在性。run_dom_sim.js 的沙箱没有 window.location，
       直接取 .search 会抛错并中断整个脚本（踩过，且模拟器当时静默吞掉了异常）。 */
    (function deepLinkView() {
      var loc = window.location;
      if (!loc || typeof loc.search !== "string") return;
      var query = loc.search;
      var found = null;
      var parts = query.replace(/^[?]/, "").split("&");
      for (var i = 0; i < parts.length; i += 1) {
        var pair = parts[i].split("=");
        if (decodeURIComponent(pair[0] || "") === "view") {
          found = decodeURIComponent(pair[1] || "");
          break;
        }
      }
      if (!found) return;
      var name = found.toLowerCase();
      var known = ["home", "ask", "sos", "pre", "learn"];
      if (known.indexOf(name) < 0) return;
      showView(name);
    })();

    /* 支持 data-jump（滚动到页内区域）与 data-goto（切换模块） */
    document.querySelectorAll("[data-jump]").forEach(function (button) {
      button.addEventListener("click", function () {
        var name = button.dataset.jump;
        if (name === "voice") {
          showView("ask");
          var input = $("question");
          if (input) input.focus();
          return;
        }
        if (name === "photo") {
          showView("ask");
          var file = $("sitePhoto");
          if (file) file.scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }
        showView(name);
      });
    });

    document.querySelectorAll("[data-goto]").forEach(function (button) {
      button.addEventListener("click", function () {
        var view = button.dataset.goto;
        showView(view);
        var train = button.dataset.train;
        if (!train) return;
        if (train === "quiz") {
          var panel = $("trainQuizPanel");
          if (panel) panel.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          var target = $("trainPathPanel");
          if (train === "check") target = $("pre");
          if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });

    /* ==================================================================
       5. 首页：班前 5 分钟四步动线（§7 方向 2）
       ------------------------------------------------------------------
       勾选项一条都没减少（用户要求"不合并"），只是按步骤归位：
       进门过关 → 弄清风险 → 检查机具 → 不确定就停。
       ================================================================== */
    function renderPractical() {
      var done = readStore(PRACTICAL_KEY, {});
      var host = clear($("todoList"));
      if (!host) return;

      PRACTICAL_STEPS.forEach(function (group) {
        var items = PRACTICAL_ITEMS.filter(function (item) { return item.step === group.n; });
        if (!items.length) return;

        var bucket = make("section", "flow-step");
        var head = make("div", "flow-step-head");
        head.appendChild(make("span", "flow-step-num", String(group.n)));
        var titles = make("div", "flow-step-titles");
        titles.appendChild(make("b", "flow-step-title", group.title));
        if (group.note) titles.appendChild(make("span", "flow-step-note", group.note));
        head.appendChild(titles);
        bucket.appendChild(head);

        var list = make("div", "todo-list");
        items.forEach(function (item) {
          var label = make("label", "todo-item" + (done[item.id] ? " done" : ""));
          var input = document.createElement("input");
          input.type = "checkbox";
          input.checked = Boolean(done[item.id]);
          input.setAttribute("aria-label", item.label);
          input.addEventListener("change", function () {
            var state = readStore(PRACTICAL_KEY, {});
            state[item.id] = input.checked;
            writeStore(PRACTICAL_KEY, state);
            label.classList.toggle("done", input.checked);
            if (input.checked) logActivity();
            updatePracticalProgress();
          });
          label.appendChild(input);
          var text = make("span");
          text.appendChild(make("b", "", item.label));
          text.appendChild(make("span", "", item.hint));
          label.appendChild(text);
          list.appendChild(label);
        });
        bucket.appendChild(list);
        host.appendChild(bucket);
      });
      updatePracticalProgress();
    }
    function updatePracticalProgress() {
      var done = readStore(PRACTICAL_KEY, {});
      var count = PRACTICAL_ITEMS.filter(function (item) { return Boolean(done[item.id]); }).length;
      var percent = Math.round((count / PRACTICAL_ITEMS.length) * 100);
      var fill = $("todoFill");
      if (fill) fill.style.width = percent + "%";
      var label = $("todoLabel");
      if (label) label.textContent = count + " / " + PRACTICAL_ITEMS.length;
    }

    var todoReset = $("todoReset");
    if (todoReset) {
      todoReset.addEventListener("click", function () {
        writeStore(PRACTICAL_KEY, {});
        renderPractical();
      });
    }

    /* ==================================================================
       6. 工种选择（贯穿问答与培训）
       ================================================================== */
    var profile = readStore(PROFILE_KEY, { role: "" });
    var roleHosts = [$("homeRoleChips"), $("assistantRoleChips"), $("roleChips")];
    var trainingData = { roles: [], worker_roles: {}, questions: [], quiz: {}, training_steps: [] };

    function currentRole() { return profile.role || ""; }

    function setRole(role) {
      profile.role = role || "";
      writeStore(PROFILE_KEY, profile);
      renderRoleChips();
      renderRoleDetail();
      renderQuickQuestions();
      renderProfileMeta();
    }

    function renderRoleChips() {
      roleHosts.forEach(function (host) {
        if (!host) return;
        clear(host);
        var roles = (trainingData.roles && trainingData.roles.length)
          ? trainingData.roles
          : Object.keys(trainingData.worker_roles || {});
        roles.forEach(function (role) {
          var chip = make("button", "role-chip" + (role === currentRole() ? " active" : ""), role);
          chip.type = "button";
          chip.setAttribute("aria-pressed", role === currentRole() ? "true" : "false");
          chip.addEventListener("click", function () { setRole(role === currentRole() ? "" : role); });
          host.appendChild(chip);
        });
      });
    }

    function renderRoleDetail() {
      var host = clear($("roleDetail"));
      if (!host) return;
      var role = currentRole();
      var data = (trainingData.worker_roles || {})[role];
      if (!role || !data) {
        host.appendChild(make("p", "empty-state", "先选一个工种，这里会显示该工种的常见风险、必守规矩和典型违规。"));
        return;
      }
      var head = make("h3");
      head.appendChild(make("span", "", role));
      head.appendChild(make("span", "q-role-tag", "专项要点"));
      host.appendChild(head);
      host.appendChild(make("p", "role-summary", data.summary || ""));

      /* ---- 常见风险：背景资料，独立一行 ---- */
      var haz = make("div", "role-block is-danger role-block-wide");
      haz.appendChild(iconText("i-alert", "常见风险"));
      var hazList = make("ul", "role-chip-list");
      var hazards = data.hazards || [];
      if (hazards.length) {
        hazards.forEach(function (text) {
          hazList.appendChild(make("li", "role-chip", text));
        });
      } else {
        hazList.appendChild(make("li", "role-chip", "本工种暂无单独列出的风险条目。"));
      }
      haz.appendChild(hazList);
      host.appendChild(haz);

      /* ---- ✗ 典型违规 / ✓ 必守规矩：左右对照（§7 方向 5）----
         这两块讲的是同一件事的两面，并排才看得出对应关系。
         左边红底、右边绿底，视觉上直接对撞。 */
      var compare = make("div", "role-compare");
      var wrong = make("div", "role-compare-col is-wrong");
      wrong.appendChild(make("b", "role-compare-head", "✗ 典型违规"));
      var wrongList = make("ul");
      var violations = data.violations || [];
      if (violations.length) {
        violations.forEach(function (text) { wrongList.appendChild(make("li", "", text)); });
      } else {
        wrongList.appendChild(make("li", "", "本工种暂无单独列出的典型违规。"));
      }
      wrong.appendChild(wrongList);
      compare.appendChild(wrong);

      var right = make("div", "role-compare-col is-right");
      right.appendChild(make("b", "role-compare-head", "✓ 必守规矩"));
      var rightList = make("ul");
      var rules = data.rules || [];
      if (rules.length) {
        rules.forEach(function (text) { rightList.appendChild(make("li", "", text)); });
      } else {
        rightList.appendChild(make("li", "", "本工种暂无单独列出的必守规矩。"));
      }
      right.appendChild(rightList);
      compare.appendChild(right);
      host.appendChild(compare);

      /* ---- 防护用品：清单，独立一行 ---- */
      var ppe = make("div", "role-block role-block-wide");
      ppe.appendChild(iconText("i-helmet", "防护用品"));
      var ppeList = make("ul", "role-chip-list");
      var ppeItems = data.ppe || [];
      if (ppeItems.length) {
        ppeItems.forEach(function (text) {
          ppeList.appendChild(make("li", "role-chip", text));
        });
      } else {
        ppeList.appendChild(make("li", "role-chip", "按项目交底配备，以现场要求为准。"));
      }
      ppe.appendChild(ppeList);
      host.appendChild(ppe);

      if (data.questions && data.questions.length) {
        var box = make("div", "related-row");
        data.questions.forEach(function (text) {
          var button = make("button", "quick-button", "问：" + text);
          button.type = "button";
          button.addEventListener("click", function () {
            showView("ask");
            var input = $("question");
            if (input) { input.value = text; input.focus(); }
          });
          box.appendChild(button);
        });
        host.appendChild(box);
      }
    }

    function renderQuickQuestions() {
      var host = clear($("quickList"));
      if (!host) return;
      var role = currentRole();

      function buildButtons(group, container) {
        var shown = 0;
        group.items.forEach(function (item) {
          var matched = !!(role && item.roles.indexOf(role) >= 0);
          /* 折叠组只显示命中当前工种的题；未选工种时先不展开 */
          if (group.collapsed && role && !matched) return;
          var button = make("button", "quick-button", item.text);
          button.type = "button";
          if (matched) button.classList.add("is-role-match");
          button.addEventListener("click", function () {
            var input = $("question");
            if (!input) return;
            input.value = item.text;
            input.focus();
            setVoiceHint("");
          });
          container.appendChild(button);
          shown += 1;
        });
        return shown;
      }

      QUICK_GROUPS.forEach(function (group) {
        /* collapsed 组的内容完全依赖工种：没选工种时整块不渲染。
           注意要在**循环这一层**跳过 —— 只在 buildButtons 里 return 的话，
           外层 details 与占位文案仍会渲染出一个空壳。 */
        if (group.collapsed && !role) return;

        var bucket = make("div", "quick-group");
        var head = make("div", "quick-group-head");
        head.appendChild(make("span", "quick-group-title", group.title));
        if (group.hint) head.appendChild(make("span", "quick-group-hint", group.hint));
        bucket.appendChild(head);

        var list = make("div", "quick-list");

        if (group.collapsed) {
          var details = make("details", "quick-group-more");
          details.appendChild(make("summary", "", "本工种专项问题"));
          var count = buildButtons(group, list);
          if (!count) {
            list.appendChild(make(
              "span", "answer-meta",
              "当前工种没有专属问题，可以从上面两组里挑一个问。"
            ));
          }
          details.appendChild(list);
          bucket.appendChild(details);
        } else {
          buildButtons(group, list);
          bucket.appendChild(list);
        }
        host.appendChild(bucket);
      });
    }
    function renderProfileMeta() {
      var role = currentRole();
      var head = $("headerRole");
      if (head) {
        /* 未选工种时不显示"工种未选择"——空状态不该做成常驻标签（§5 第 5 条） */
        head.hidden = !role;
        head.textContent = role ? "当前工种：" + role : "";
        head.classList.toggle("offline", !role);
        head.setAttribute("style", role
          ? "background:var(--brand);color:#fff;border-color:var(--brand)"
          : "");
      }
      var hint = $("homeRoleHint");
      if (hint) {
        clear(hint);
        var data = (trainingData.worker_roles || {})[role];
        if (role && data) {
          hint.appendChild(make("b", "", "已选择：" + role));
          hint.appendChild(document.createTextNode((data.summary || "") + " 提问时会自动带上这个工种的要点。"));
        } else {
          hint.appendChild(make("b", "", "还没有选择工种"));
          hint.appendChild(document.createTextNode("未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。"));
        }
      }
      var kvRole = $("kvRole");
      if (kvRole) kvRole.textContent = role || "未选择";
    }

    /* ==================================================================
       7. 首页：知识领域分布与警示案例
       ================================================================== */
    var DOMAIN_TOKENS = [
      { name: "高处作业", tokens: ["高处", "坠落", "安全带", "临边", "洞口", "脚手架", "攀登"] },
      { name: "起重吊装", tokens: ["吊装", "起重", "塔吊", "吊索", "钢丝绳", "升降机", "物料提升"] },
      { name: "临时用电", tokens: ["用电", "配电", "电气", "漏电", "接地", "电缆"] },
      { name: "基坑与边坡", tokens: ["基坑", "支护", "边坡", "土方", "降水"] },
      { name: "模板支架", tokens: ["模板", "支架", "浇筑", "支撑"] },
      { name: "施工机具", tokens: ["机具", "机械", "焊机", "气瓶", "搅拌", "钢筋机械", "木工"] },
      { name: "动火消防", tokens: ["消防", "动火", "火灾", "灭火", "燃烧"] },
      { name: "应急与急救", tokens: ["应急", "急救", "撤离", "救援", "事故"] },
      { name: "安全管理", tokens: ["管理", "制度", "交底", "教育", "检查", "责任"] },
      { name: "文明施工", tokens: ["文明", "围挡", "场地", "材料堆放", "标牌", "住宿"] },
    ];

    function renderDomainDistribution(documents) {
      var host = clear($("sideDomains"));
      if (!host) return;
      host.setAttribute("aria-busy", "false");

      // 按「文档标题 + 来源文件名」匹配风险领域。
      // 早先版本拿"类别名"当 haystack，而类别只有「公开标准 / 演示摘要」两个词，
      // 一个领域关键词都命中不了，导致这一栏永远显示空态。
      var list = documents || [];
      var rows = DOMAIN_TOKENS.map(function (item) {
        var total = 0;
        var docs = 0;
        list.forEach(function (document) {
          var haystack = ((document.title || "") + " " + (document.source || "")).toLowerCase();
          for (var i = 0; i < item.tokens.length; i += 1) {
            if (haystack.indexOf(item.tokens[i].toLowerCase()) >= 0) {
              total += (document.chunk_count || 0);
              docs += 1;
              return;
            }
          }
        });
        return { name: item.name, count: total, docs: docs };
      }).filter(function (row) { return row.docs > 0; });

      rows.sort(function (a, b) {
        if (b.docs !== a.docs) return b.docs - a.docs;
        return b.count - a.count;
      });

      if (!rows.length) {
        host.appendChild(make("li", "", "知识库中还没有可归类的文档"));
        return;
      }
      rows.slice(0, 6).forEach(function (row) {
        var li = make("li");
        li.appendChild(make("span", "", row.name));
        li.appendChild(make("span", "hot-count", row.docs + " 篇 / " + row.count + " 段"));
        host.appendChild(li);
      });
    }

    /* ==================================================================
       §5-3 案例对照卡（第 21 轮）
       ------------------------------------------------------------------
       左「✗ 错误做法」= 真实经过 + 真实致险因素
       右「✓ 正确做法」= 真实防控要点（+ 结果）

       只用案例里已有的字段，不编造条文、数据或标准号。
       图标 + 标签 + 文字共同表意，不单纯依赖红绿。
       ================================================================== */
    function caseCompare(item) {
      var grid = make("div", "case-compare");

      /* ---- 左：错误做法 ---- */
      var wrong = make("section", "case-side is-wrong");
      var wrongHead = make("div", "case-side-head");
      wrongHead.appendChild(makeIcon("i-close", "ico ico-sm"));
      wrongHead.appendChild(make("b", "", "错误做法"));
      wrong.appendChild(wrongHead);

      if (item.what_happened) {
        wrong.appendChild(make("p", "case-side-body", item.what_happened));
      }
      if (item.why_dangerous) {
        var why = make("div", "case-why");
        why.appendChild(makeIcon("i-alert", "ico ico-sm"));
        var whyText = make("span");
        whyText.appendChild(make("b", "", "为什么危险："));
        whyText.appendChild(document.createTextNode(item.why_dangerous));
        why.appendChild(whyText);
        wrong.appendChild(why);
      }
      grid.appendChild(wrong);

      /* ---- 右：正确做法 ---- */
      var right = make("section", "case-side is-right");
      var rightHead = make("div", "case-side-head");
      rightHead.appendChild(makeIcon("i-check", "ico ico-sm"));
      rightHead.appendChild(make("b", "", "正确做法"));
      right.appendChild(rightHead);

      if (item.lesson) {
        right.appendChild(make("p", "case-side-body", item.lesson));
      } else {
        /* 没有防控要点就不硬编 —— 如实说明 */
        right.appendChild(make("p", "case-side-body is-empty",
          "这条通报没有给出防控要点，请以现场安全交底和适用规范为准。"));
      }
      if (item.consequence) {
        var outcome = make("div", "case-outcome");
        outcome.appendChild(make("b", "", "结果："));
        outcome.appendChild(document.createTextNode(item.consequence));
        right.appendChild(outcome);
      }
      grid.appendChild(right);

      return grid;
    }

    function caseCard(item, compact) {
      var card = make("article", "case-card");
      card.dataset.category = item.category || "";
      card.appendChild(make("span", "case-tag", item.category || "未分类"));
      card.appendChild(make("h3", "", item.title || ""));
      card.appendChild(caseCompare(item));
      if (!compact) {
        card.appendChild(make("div", "case-source",
          "来源：" + (item.source_name || "未标注") + " · " + (item.date || "")));
      }
      return card;
    }

    function renderSteps() {
      var host = clear($("stepList"));
      if (!host) return;
      var steps = trainingData.training_steps || [];
      if (!steps.length) {
        host.appendChild(make("p", "empty-state", "培训路线数据未读取到。"));
        return;
      }
      steps.forEach(function (step) {
        var item = make("section", "step-item");
        item.appendChild(make("div", "step-order", String(step.order)));
        var main = make("div");
        var head = make("h3");
        head.appendChild(make("span", "", step.title));
        head.appendChild(make("span", "step-meta", step.duration || ""));
        main.appendChild(head);
        main.appendChild(make("p", "role-summary", step.summary || ""));
        var points = make("ul", "step-points");
        (step.key_points || []).forEach(function (text) { points.appendChild(make("li", "", text)); });
        main.appendChild(points);
        if (step.checkpoint) main.appendChild(make("div", "step-check", "自检标准：" + step.checkpoint));
        item.appendChild(main);

        var side = make("div", "step-side");
        var done = readStore("sitesaha-steps-v1", {});
        var label = make("label", "check-item" + (done[step.order] ? " checked" : ""));
        var box = document.createElement("input");
        box.type = "checkbox";
        box.checked = Boolean(done[step.order]);
        box.setAttribute("aria-label", "标记“" + step.title + "”已完成");
        box.addEventListener("change", function () {
          var state = readStore("sitesaha-steps-v1", {});
          state[step.order] = box.checked;
          writeStore("sitesaha-steps-v1", state); if (box.checked) logActivity();
          label.classList.toggle("checked", box.checked);
          item.classList.toggle("is-done", box.checked);
          renderTrainingProgress();
        });
        label.appendChild(box);
        label.appendChild(make("span", "", "已完成"));
        side.appendChild(label);
        if (step.link_view) {
          var jump = make("button", "ghost-button", "去看相关模块");
          jump.type = "button";
          jump.addEventListener("click", function () { showView(step.link_view); });
          side.appendChild(jump);
        }
        item.appendChild(side);
        item.classList.toggle("is-done", Boolean(done[step.order]));
        if (done[step.order]) {
          label.classList.add("checked");
          item.querySelector(".step-order").replaceChildren(makeIcon("i-check", "ico ico-sm"));
        }
        host.appendChild(item);
      });
      renderTrainingProgress();
    }

    /* ==================================================================
       §5-1 KPI 环形进度（第 21 轮）
       ------------------------------------------------------------------
       只用真实比例。没有测验记录时（best 为 null）显示 "--" 且不画环，
       不编造百分比。

       周长 = 2 * PI * 20 = 125.66，与 markup 里的 stroke-dasharray 一致。
       ================================================================== */
    var KPI_RING_LENGTH = 125.66;
    var kpiRingShown = -1;

    function updateKpiRing(best, total) {
      var ring = $("kpiRing");
      var fill = $("kpiRingFill");
      var pctLabel = $("kpiRingPct");
      if (!ring || !fill || !pctLabel) return;

      if (best === null || best === undefined || !total) {
        /* 没有有效分母 —— 不画环 */
        if (kpiRingShown !== -1) {
          fill.style.strokeDashoffset = String(KPI_RING_LENGTH);
          pctLabel.textContent = "--";
          ring.setAttribute("aria-label", "安全知识测验还没有记录");
          kpiRingShown = -1;
        }
        return;
      }

      var percent = Math.max(0, Math.min(100, Math.round((best / total) * 100)));
      /* 值没变就不重设，避免重复渲染闪烁 */
      if (percent === kpiRingShown) return;
      kpiRingShown = percent;

      fill.style.strokeDashoffset = String(KPI_RING_LENGTH * (1 - percent / 100));
      pctLabel.textContent = String(percent);
      ring.setAttribute("aria-label",
        "安全知识测验最佳成绩 " + best + " / " + total + "，正确率 " + percent + "%");
    }

    function renderTrainingProgress() {
      var steps = (trainingData.training_steps || []).length || 5;      var done = readStore("sitesaha-steps-v1", {});
      var count = 0;
      Object.keys(done).forEach(function (key) { if (done[key]) count += 1; });
      if (count > steps) count = steps;
      var percent = Math.round((count / steps) * 100);
      var fill = $("trainFill");
      if (fill) fill.style.width = percent + "%";
      var label = $("trainLabel");
      if (label) label.textContent = percent + "%";
      var stat = $("trainStepDone");
      if (stat) stat.textContent = count + "/" + steps;
      var kv = $("kvSteps");
      if (kv) kv.textContent = count + " / " + steps;
      var kpiQuiz = $("kpiQuiz");
      if (kpiQuiz) {
        var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
        var quizTotal = quiz.total || 20;
        var quizBest = quiz.bestCorrect || 0;
        kpiQuiz.textContent = quizBest + "/" + quizTotal;
        var note = $("kpiQuizNote");
        if (note) {
          note.textContent = quiz.attempts
            ? ("已测 " + quiz.attempts + " 次 · 历史最佳")
            : "还没有测验记录";
        }
        updateKpiRing(quiz.attempts ? quizBest : null, quizTotal);
      }
    }

    /* ==================================================================
       9. 测验引擎
       ================================================================== */
    var quizState = { active: false, index: 0, order: [], answered: false, correct: 0, wrong: [] };

    function shuffledIndexes(total) {
      var list = [];
      for (var i = 0; i < total; i += 1) list.push(i);
      for (var j = list.length - 1; j > 0; j -= 1) {
        var k = Math.floor(Math.random() * (j + 1));
        var tmp = list[j]; list[j] = list[k]; list[k] = tmp;
      }
      return list;
    }

    function renderQuizIntro() {
      var meta = trainingData.quiz || {};
      var intro = $("quizIntro");
      if (intro) intro.textContent = meta.intro || "答一遍看看哪些风险域还没掌握，结果只保存在你自己的浏览器里。";
      var note = $("quizHomeNote");
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      if (note && quiz.attempts) {
        note.textContent = "已测验 " + quiz.attempts + " 次，最近一次 "
          + quiz.lastCorrect + " / " + (quiz.total || 20) + " 题（" + fmtTime(quiz.lastAt) + "）。薄弱项见下方分布。";
      }
    }

    function renderRing(percent) {
      var ring = $("ringFg");
      if (ring) {
        var offset = 345.58 * (1 - Math.min(100, Math.max(0, percent)) / 100);
        ring.style.setProperty("--ring-offset", offset.toFixed(2));
        ring.setAttribute("stroke", percent >= 80 ? "var(--risk-low)" : (percent >= 60 ? "var(--risk-mid)" : "var(--risk-high)"));
      }
      var num = $("ringNum");
      if (num) num.textContent = percent + "%";
    }

    /* ==================================================================
       §7 图形语言：近 7 天学习热力格 + 测验正确率趋势
       ------------------------------------------------------------------
       数据全部来自本机 localStorage，不上传。
       没有数据就画空状态 —— 不编造趋势线。
       ================================================================== */
    var ACTIVITY_KEY = "sitesaha-activity-v1";

    function dayKey(date) {
      function pad(n) { return n < 10 ? "0" + n : String(n); }
      return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
    }

    /* 记一次学习动作。renderStudyHeat 会读它画热力格。 */
    function logActivity() {
      var store = readStore(ACTIVITY_KEY, {});
      var key = dayKey(new Date());
      store[key] = (store[key] || 0) + 1;
      /* 只留最近 30 天，避免无限增长 */
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 30);
      var kept = {};
      Object.keys(store).forEach(function (item) {
        if (item >= dayKey(cutoff)) kept[item] = store[item];
      });
      writeStore(ACTIVITY_KEY, kept);
    }

    function renderStudyHeat() {
      var host = clear($("studyHeat"));
      if (!host) return;
      var store = readStore(ACTIVITY_KEY, {});
      var today = new Date();
      var values = [];
      for (var back = 6; back >= 0; back -= 1) {
        var day = new Date(today.getTime());
        day.setDate(day.getDate() - back);
        values.push({ key: dayKey(day), count: store[dayKey(day)] || 0, back: back });
      }
      var max = 1;
      values.forEach(function (item) { if (item.count > max) max = item.count; });

      values.forEach(function (item) {
        var level = item.count === 0 ? 0 : Math.min(4, Math.ceil((item.count / max) * 4));
        var cell = make("span", "heat-cell");
        cell.setAttribute("data-level", String(level));
        cell.setAttribute("title", item.key + "：" + item.count + " 次学习动作");
        cell.textContent = item.back === 0 ? "今" : String(item.back + 1);
        host.appendChild(cell);
      });

      var note = $("studyHeatNote");
      if (note) {
        var total = values.reduce(function (sum, item) { return sum + item.count; }, 0);
        note.textContent = total
          ? ("近 7 天共 " + total + " 次学习动作")
          : "还没有记录。完成培训步骤、做测验或班前确认后会出现在这里。";
      }
    }

    function renderQuizTrend() {
      var host = clear($("quizTrend"));
      if (!host) return;
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      var history = (quiz.history || []).filter(function (item) {
        return item && typeof item.percent === "number";
      });

      if (history.length < 2) {
        host.appendChild(make(
          "p", "trend-empty",
          history.length === 1
            ? "目前只有 1 次记录（" + history[0].percent + "%）。再做一次就能看到趋势线。"
            : "还没有测验记录。点上面的「开始测验」做一遍，这里会画出正确率变化。"
        ));
        return;
      }

      var recent = history.slice(-8);
      var width = 420;
      var height = 108;
      var padX = 26;
      var padY = 18;
      var stepX = recent.length > 1 ? (width - padX * 2) / (recent.length - 1) : 0;

      function pointX(index) { return padX + index * stepX; }
      function pointY(percent) {
        return height - padY - (Math.max(0, Math.min(100, percent)) / 100) * (height - padY * 2);
      }

      var points = recent.map(function (item, index) {
        return pointX(index) + "," + pointY(item.percent).toFixed(1);
      });
      var areaPath = "M" + pointX(0) + "," + (height - padY)
        + " L" + points.join(" L")
        + " L" + pointX(recent.length - 1) + "," + (height - padY) + " Z";

      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "trend-figure");
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label",
        "最近 " + recent.length + " 次测验正确率趋势，最新 " + recent[recent.length - 1].percent + "%");

      function add(tag, attrs, text) {
        var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
        Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
        if (text) node.textContent = text;
        svg.appendChild(node);
        return node;
      }

      add("line", { class: "axis", x1: padX, y1: height - padY, x2: width - padX, y2: height - padY });
      add("path", { class: "area", d: areaPath });
      add("polyline", { class: "line", points: points.join(" ") });

      recent.forEach(function (item, index) {
        add("circle", { class: "pt", cx: pointX(index), cy: pointY(item.percent).toFixed(1), r: 3.5 });
      });
      add("text", { class: "pt-label", x: padX, y: height - 4 }, "60%");
      add("text", { class: "pt-label", x: width - padX - 26, y: height - 4 },
        recent[recent.length - 1].percent + "%");

      host.appendChild(svg);
      host.appendChild(make(
        "p", "answer-meta",
        "最近 " + recent.length + " 次记录，最新 " + recent[recent.length - 1].percent + "%（及格线 80%）。"
      ));
    }

    function renderDomainBars() {
      var host = clear($("domainBars"));
      if (!host) return;
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      var wrong = quiz.wrongDomains || {};
      var seen = quiz.seen || {};
      var domains = (trainingData.quiz && trainingData.quiz.domains) || [];
      if (!domains.length) {
        (trainingData.questions || []).forEach(function (q) {
          if (domains.indexOf(q.domain) < 0) domains.push(q.domain);
        });
      }
      var shown = 0;
      domains.forEach(function (name) {
        var total = seen[name] || 0;
        if (!total) return;
        var bad = wrong[name] || 0;
        var rate = Math.round(((total - bad) / total) * 100);
        var row = make("div", "domain-bar" + (rate >= 80 ? "" : (rate >= 60 ? " warn" : " bad")));
        row.appendChild(make("span", "dname", name));
        var track = make("div", "dtrack");
        var fill = make("div", "dfill");
        fill.style.width = rate + "%";
        track.appendChild(fill);
        row.appendChild(track);
        row.appendChild(make("span", "dval", rate + "%"));
        host.appendChild(row);
        shown += 1;
      });
      if (!shown) {
        host.appendChild(make("p", "empty-state", "测验后这里会按风险域显示你的掌握情况。"));
      }
    }

    function renderHomeQuiz() {
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      renderRing(quiz.bestPercent || 0);
      renderDomainBars(); renderStudyHeat(); renderQuizTrend();
      renderQuizIntro();
      var stat = $("trainQuizScore");
      if (stat) stat.textContent = quiz.attempts ? (quiz.lastCorrect + " / " + (quiz.total || 20)) : "未测";
      var kv = $("kvQuiz");
      if (kv) kv.textContent = quiz.attempts ? (quiz.bestPercent + "%（历史最佳）") : "无记录";
      // 积分依赖测验与路线进度，测验任何变化都要刷新
      renderPoints();
      renderTrainingProgress();
    }

    function startQuiz() {
      var total = (trainingData.questions || []).length;
      if (!total) return;
      quizState = { active: true, index: 0, order: shuffledIndexes(total), answered: false, correct: 0, wrong: [] };
      $("quizHome").hidden = true;
      $("quizResult").hidden = true;
      $("quizPlay").hidden = false;
      renderQuizQuestion();
    }

    function renderQuizQuestion() {
      var host = clear($("quizPlay"));
      var questions = trainingData.questions || [];
      var qIndex = quizState.order[quizState.index];
      var item = questions[qIndex];
      if (!item) return;

      var bar = make("div", "quiz-progress");
      bar.appendChild(make("span", "qcount", "第 " + (quizState.index + 1) + " / " + quizState.order.length + " 题"));
      var tags = make("span");
      tags.appendChild(make("span", "q-role-tag", item.domain || item.category || "安全知识"));
      tags.appendChild(document.createTextNode(" "));
      tags.appendChild(make("span", "answer-meta", "适用：" + (item.role || "全部工种")));
      bar.appendChild(tags);
      host.appendChild(bar);

      var track = make("div", "progress-track");
      var fill = make("div", "progress-fill");
      fill.style.width = Math.round((quizState.index / quizState.order.length) * 100) + "%";
      track.appendChild(fill);
      host.appendChild(track);

      host.appendChild(make("h3", "q-head", item.q || ""));
      var options = make("div", "options");
      var buttons = [];
      (item.options || []).forEach(function (text, idx) {
        var button = make("button", "option");
        button.type = "button";
        button.appendChild(make("span", "opt-key", QUIZ_OPTION_KEYS[idx] || String(idx + 1)));
        button.appendChild(make("span", "", text));
        button.addEventListener("click", function () { answerQuiz(idx, buttons, item); });
        buttons.push(button);
        options.appendChild(button);
      });
      host.appendChild(options);

      var foot = make("div", "quiz-actions");
      foot.style.marginTop = "14px";
      var next = make("button", "amber-button", quizState.index + 1 >= quizState.order.length ? "提交并看结果" : "下一题");
      next.type = "button";
      next.id = "quizNext";
      next.disabled = true;
      next.addEventListener("click", function () { nextQuizQuestion(); });
      foot.appendChild(next);
      var quit = make("button", "secondary-button", "退出测验");
      quit.type = "button";
      quit.addEventListener("click", function () {
        quizState.active = false;
        $("quizPlay").hidden = true;
        $("quizHome").hidden = false;
        renderHomeQuiz();
      });
      foot.appendChild(quit);
      host.appendChild(foot);
    }

    function answerQuiz(choice, buttons, item) {
      if (quizState.answered) return;
      quizState.answered = true;
      var correct = item.answer;
      buttons.forEach(function (button, idx) {
        button.disabled = true;
        if (idx === correct) button.classList.add("is-correct");
        else if (idx === choice) button.classList.add("is-wrong");
        else button.classList.add("is-dim");
      });
      var isRight = choice === correct;
      if (isRight) {
        quizState.correct += 1;
      } else {
        quizState.wrong.push({ q: item.q, domain: item.domain || item.category || "综合", chose: (item.options || [])[choice] || "", right: (item.options || [])[correct] || "", why: item.why || "" });
      }
      var box = make("div", "explain");
      box.appendChild(make("b", "", isRight ? "回答正确。" : "回答错误。"));
      box.appendChild(document.createTextNode((item.why || "") + (isRight ? "" : " 正确答案是 " + (QUIZ_OPTION_KEYS[correct] || "") + "。")));
      $("quizPlay").appendChild(box);
      var next = $("quizNext");
      if (next) next.disabled = false;
    }

    function nextQuizQuestion() {
      quizState.answered = false;
      quizState.index += 1;
      if (quizState.index >= quizState.order.length) {
        finishQuiz();
        return;
      }
      renderQuizQuestion();
      var host = $("quizPlay");
      if (host) host.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function finishQuiz() {
      var total = quizState.order.length;
      var percent = Math.round((quizState.correct / total) * 100);
      var stored = readStore(QUIZ_KEY, EMPTY_QUIZ);
      var wrong = stored.wrongDomains || {};
      var seen = stored.seen || {};
      quizState.wrong.forEach(function (row) {
        wrong[row.domain] = (wrong[row.domain] || 0) + 1;
      });
      var questions = trainingData.questions || [];
      var touched = {};
      quizState.order.forEach(function (qIndex) {
        var item = questions[qIndex];
        if (!item) return;
        var name = item.domain || item.category || "综合";
        touched[name] = (touched[name] || 0) + 1;
      });
      Object.keys(touched).forEach(function (name) {
        seen[name] = (seen[name] || 0) + touched[name];
      });
      var record = {
        attempts: (stored.attempts || 0) + 1,
        bestPercent: Math.max(stored.bestPercent || 0, percent),
        bestCorrect: Math.max(stored.bestCorrect || 0, quizState.correct),
        total: total,
        lastCorrect: quizState.correct,
        lastAt: new Date().toISOString(),
        wrongDomains: wrong,
        seen: seen,
      };
      writeStore(QUIZ_KEY, record);

      logActivity();

      var host = clear($("quizResult"));
      $("quizPlay").hidden = true;
      $("quizHome").hidden = true;
      host.hidden = false;
      var pass = (trainingData.quiz && trainingData.quiz.pass_score) || Math.ceil(total * 0.8);
      var card = make("div", "quiz-result");
      card.appendChild(make("h3", "", quizState.correct >= pass ? "完成测验：掌握情况良好" : "完成测验：还有需要补的地方"));
      var score = make("div", "score-big " + (quizState.correct >= pass ? "pass" : "fail"), quizState.correct + " / " + total);
      card.appendChild(score);
      card.appendChild(make("p", "lead", "正确率 " + percent + "%。参考达标线 " + pass + " / " + total + " 题。成绩与薄弱项已保存在本机浏览器。"));
      card.appendChild(make("p", "lead", (trainingData.quiz && trainingData.quiz.notice) || ""));

      var actions = make("div", "quiz-actions");
      actions.style.marginTop = "13px";
      var again = make("button", "amber-button", "再测一次");
      again.type = "button";
      again.addEventListener("click", function () { startQuiz(); });
      actions.appendChild(again);
      var back = make("button", "secondary-button", "返回掌握情况");
      back.type = "button";
      back.addEventListener("click", function () {
        host.hidden = true;
        $("quizHome").hidden = false;
        renderHomeQuiz();
      });
      actions.appendChild(back);
      card.appendChild(actions);

      if (quizState.wrong.length) {
        card.appendChild(make("h3", "sec-title", "错题与解析（" + quizState.wrong.length + " 题）"));
        var list = make("div", "wrong-list");
        quizState.wrong.forEach(function (row) {
          var box = make("div", "wrong-item");
          box.appendChild(make("b", "", row.q));
          box.appendChild(make("p", "", "你的选择：" + row.chose + "　|　正确答案：" + row.right));
          box.appendChild(make("p", "", "解析：" + row.why));
          list.appendChild(box);
        });
        card.appendChild(list);
      } else {
        card.appendChild(make("p", "lead", "全部答对，没有错题。建议再做一遍其他工种的专项要点，或者去开工前检查走一遍班前确认。"));
      }
      host.appendChild(card);
      renderHomeQuiz();
    }

    var quizStart = $("quizStart");
    if (quizStart) quizStart.addEventListener("click", function () { startQuiz(); });
    var quizReset = $("quizReset");
    if (quizReset) {
      quizReset.addEventListener("click", function () {
        writeStore(QUIZ_KEY, EMPTY_QUIZ);
        writeStore("sitesaha-steps-v1", {});
        renderSteps();
        renderHomeQuiz();
      });
    }
    /* ==================================================================

       10. 现场问答：会话流

       ================================================================== */

    function appendUserMessage(text, role) {

      var stream = $("chatStream");

      if (!stream) return null;

      var row = make("div", "msg-row from-user");

      row.appendChild(make("div", "avatar", "我"));

      var bubble = make("div", "bubble");

      bubble.appendChild(make("div", "bubble-title", text));

      bubble.appendChild(make("div", "bubble-meta", role ? "我的工种：" + role : "未选择工种 · 通用要点"));

      row.appendChild(bubble);

      stream.appendChild(row);

      row.scrollIntoView({ behavior: "smooth", block: "center" });

      return row;

    }



    /* 等待期间的计时器句柄（第 20 轮 §2：让用户知道要等多久） */

    var thinkingTimer = null;

    var thinkingStartedAt = 0;

    var ASK_TIMEOUT_MS = 45000;



    function updateThinkingHint() {

      var hint = $("chatThinkingHint");

      if (!hint) return;

      var seconds = Math.round((Date.now() - thinkingStartedAt) / 1000);

      if (seconds < 20) {

        hint.textContent = "通常需要 10~20 秒 · 已等待 " + seconds + " 秒";

      } else {

        hint.textContent = "网络可能较慢，仍在生成… 已等待 " + seconds + " 秒";

      }

      hint.classList.toggle("is-slow", seconds >= 20);

    }



    function appendThinking() {

      var stream = $("chatStream");

      if (!stream) return null;

      var row = make("div", "msg-row");

      row.id = "chatThinking";

      row.appendChild(make("div", "avatar", "筑"));

      var bubble = make("div", "bubble");

      bubble.appendChild(make("div", "bubble-title", "正在检索知识库并组织回答…"));

      var dots = make("div", "thinking");

      dots.appendChild(make("i"));

      dots.appendChild(make("i"));

      dots.appendChild(make("i"));

      bubble.appendChild(dots);

      /* 预期时长 + 实时计时，避免用户以为卡死 */

      var hint = make("div", "thinking-hint");

      hint.id = "chatThinkingHint";

      hint.textContent = "通常需要 10~20 秒 · 已等待 0 秒";

      bubble.appendChild(hint);

      row.appendChild(bubble);

      stream.appendChild(row);

      row.scrollIntoView({ behavior: "smooth", block: "center" });

      thinkingStartedAt = Date.now();

      if (thinkingTimer) clearInterval(thinkingTimer);

      thinkingTimer = setInterval(updateThinkingHint, 1000);

      return row;

    }



    function removeThinking() {

      if (thinkingTimer) { clearInterval(thinkingTimer); thinkingTimer = null; }

      var node = $("chatThinking");

      if (node && node.parentNode) node.parentNode.removeChild(node);

    }



    /* 用 fromCharCode 拼换行，让整份模板不含反斜杠转义序列 */

    var NL2 = String.fromCharCode(10) + String.fromCharCode(10);



    var lastAnswerText = "";



    /* ==================================================================
       规范依据的正文清理
       ------------------------------------------------------------------
       检索到的原文来自标准 PDF，含大量评分表碎片与页码：
         「物从人的正上方」「通过，扣10 分」「10」「8」「高处」「作业」
       直接倒出来会淹没答案，所以先清理再截断。

       注意：分片禁止反斜杠，正则一律用字符类/fromCharCode 拼。
       ================================================================== */
    var RE_ONLY_DIGITS = new RegExp("^[0-9]+$");
    var RE_LEAD_DIGITS = new RegExp("^[0-9]{1,4}[ 、.．)）]");
    var RE_SCORE = new RegExp("扣[ " + String.fromCharCode(12288) + "]*[0-9]");
    var RE_GETSCORE = new RegExp("(应得|实得|评分)[ " +
      String.fromCharCode(12288) + "]*分");
    var RE_SPACES = new RegExp("[" + String.fromCharCode(9, 10, 13, 32, 12288) +
      "]+", "g");
    var RE_LEAD_PUNCT = new RegExp("^[" + String.fromCharCode(65292, 12289, 65307, 65306, 12290) + "]+");
    var RE_ENDS_PUNCT = new RegExp("[" + String.fromCharCode(12290, 65307, 65281, 65311) + "]$");

    function cleanSourceText(text) {
      var raw = String(text == null ? "" : text);
      var kept = [];
      raw.split(String.fromCharCode(10)).forEach(function (line) {
        var item = line.replace(RE_SPACES, " ").trim();
        if (!item) return;
        if (RE_ONLY_DIGITS.test(item)) return;          /* 页码或评分列 */
        if (RE_SCORE.test(item)) return;                /* 扣X分 */
        if (RE_GETSCORE.test(item)) return;             /* 应得分 */
        if (RE_LEAD_DIGITS.test(item) && item.length < 12) return;
        if (item.length < 6) return;                    /* 过短碎片 */
        kept.push(item);
      });
      var joined = kept.join(" ").replace(RE_SPACES, " ").trim();

      /* 剥掉起首标点：标准片段常从「，单台起重机…」这种半句开始 */
      joined = joined.replace(RE_LEAD_PUNCT, "").trim();

      /* 不成句的残片不如不给：长度不足、或没有句读收尾，就返回空，
         由调用方显示「主要是评分表，已省略」 */
      var hasEnd = RE_ENDS_PUNCT.test(joined);
      if (joined.length < 24 || (!hasEnd && joined.length < 60)) {
        return "";
      }

      if (joined.length > 180) {
        joined = joined.slice(0, 180) + "…";
      }
      return joined;
    }

    function sourceBlock(answer) {

      var sources = answer.sources || [];

      var cases = answer.related_cases || [];

      if (!sources.length && !cases.length) return null;

      var block = make("div", "src-block");

      if (sources.length) {

        /* 依据区收进 details：默认收起，避免原始条文淹没答案 */
        var details = make("details", "src-details");
        details.appendChild(make("summary", "src-title",
          "规范 / 知识依据（" + sources.length + " 条，点击展开）"));

        var list = make("div", "source-list");

        sources.forEach(function (source, index) {

          var card = make("article", "source-card");

          card.appendChild(make("h4", "", "依据 [" + (index + 1) + "]：" + (source.title || "")));

          if (source.heading) card.appendChild(make("div", "source-meta", source.heading));

          /* 清理后再显示：只给一段可读的预览，不再整段倒出条文 */
          var preview = cleanSourceText(source.content);
          if (preview) {
            card.appendChild(make("p", "source-excerpt", preview));
          } else {
            card.appendChild(make("p", "source-excerpt is-empty",
              "这一条检索到的主要是标准评分表，文字不适合直接阅读，已省略。"));
          }

          card.appendChild(make("div", "source-meta",

            "来源：" + (source.source || "") + " " + (source.version || "")

            + (source.category ? " · " + source.category : "")));

          list.appendChild(card);

        });

        details.appendChild(list);
        block.appendChild(details);

      }

      if (cases.length) {

        block.appendChild(make("div", "src-title", "相关真实案例"));

        var row = make("div", "related-row");

        cases.slice(0, 3).forEach(function (item) {

          var button = makeButtonWithIcon("quick-button", "i-doc", item.title || "案例");

          button.type = "button";

          button.addEventListener("click", function () {

            showView("cases");

            var search = $("caseSearch");

            if (search) search.value = item.title || "";

            activeCaseFilter = "";

            renderCaseFilters();

            loadCases(item.title || "");

          });

          row.appendChild(button);

        });

        block.appendChild(row);

      }

      return block;

    }



    function appendAnswer(question, answer, role) {

      var stream = $("chatStream");

      if (!stream) return;

      var row = make("div", "msg-row");

      row.appendChild(make("div", "avatar", "筑"));

      var bubble = make("div", "bubble");

      bubble.appendChild(make("div", "bubble-title", question));

      var meta = "回答模式：" + modeLabel(answer.mode);

      if (role) meta += " · 已结合「" + role + "」工种要点";

      if (answer.worker_role) meta += " · 服务端已识别工种";

      bubble.appendChild(make("div", "bubble-meta", meta));

      var body = make("div", "answer-body");
      body.appendChild(renderAnswerBody(answer.text || ""));
      bubble.appendChild(body);



      (answer.warnings || []).forEach(function (warning) {

        bubble.appendChild(makeIconText("div", "warn-box", "i-alert", "ico ico-sm", warning));

      });

      var block = sourceBlock(answer);

      if (block) bubble.appendChild(block);



      lastAnswerText = answer.text || "";

      var speak = $("speakButton");

      if (speak) speak.disabled = !lastAnswerText || !("speechSynthesis" in window);

      row.appendChild(bubble);

      stream.appendChild(row);

      row.scrollIntoView({ behavior: "smooth", block: "start" });

      /* 返回气泡，便于调用方追加内容（如超时后的重试按钮） */
      return bubble;

    }



    async function askQuestion() {

      var input = $("question");

      var button = $("askButton");

      if (!input || !button) return;

      var question = input.value.trim();

      if (!question) { input.focus(); return; }

      if (button.disabled) return;

      var role = currentRole();

      appendUserMessage(question, role);

      button.disabled = true;

      button.textContent = "检索中";

      appendThinking();

      try {

        var payload = { question: question, access_code: accessCode() };

        if (role) payload.worker_role = role;

        /* 45 秒超时：到点主动中止，不让用户无限等 */

        var controller = new AbortController();

        var timeoutId = setTimeout(function () { controller.abort(); }, ASK_TIMEOUT_MS);

        var response;

        try {

          response = await apiFetch("/api/ask", {

            method: "POST",

            headers: {

              "Content-Type": "application/json",

              "X-Access-Code": accessCode(),

            },

            body: JSON.stringify(payload),

            signal: controller.signal,

          });

        } finally {

          clearTimeout(timeoutId);

        }

        removeThinking();

        if (!response.ok) {

          var data = await response.json().catch(function () { return {}; });

          throw new Error(data.error || ("HTTP " + response.status));

        }

        var answer = await response.json();

        appendAnswer(question, answer, role);

        input.value = "";

      } catch (error) {

        removeThinking();

        var waited = Math.round((Date.now() - thinkingStartedAt) / 1000);

        var aborted = error && (error.name === "AbortError" || error.code === 20);

        var failText = aborted

          ? ("这次没等到结果（已等待 " + waited + " 秒）。可能是网络较慢或模型繁忙，"

             + "你的问题还在下面，点一下就能原样重试。")

          : "查询失败，请稍后重试或联系管理员。已保留你的问题，可以再试一次。";

        var failBox = appendAnswer(question, {

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

      } finally {

        button.disabled = false;

        button.textContent = "查询安全依据";

      }

    }



    var askButton = $("askButton");

    if (askButton) askButton.addEventListener("click", askQuestion);

    var questionInput = $("question");

    if (questionInput) {

      questionInput.addEventListener("keydown", function (event) {

        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {

          event.preventDefault();

          askQuestion();

        }

      });

    }

    var chatClear = $("chatClear");

    if (chatClear) {

      chatClear.addEventListener("click", function () {

        var stream = clear($("chatStream"));

        if (!stream) return;

        var row = make("div", "msg-row");

        row.appendChild(make("div", "avatar", "筑"));

        var bubble = make("div", "bubble");

        bubble.appendChild(make("div", "bubble-title", "对话已清空。"));

        bubble.appendChild(make("div", "bubble-meta", "可以继续问新的现场安全问题。"));

        row.appendChild(bubble);

        stream.appendChild(row);

        lastAnswerText = "";

        var speak = $("speakButton");

        if (speak) speak.disabled = true;

      });

    }



    /* ==================================================================

       11b. 语音提问与朗读

       优先走服务端 ASR（/api/transcribe），未配置时降级浏览器识别，

       两条通道都不可用时给出可操作的提示，而不是静默失败。

       ================================================================== */

    var ASR_MAX_MS = 60000;



    /* 短录音下限：低于这个长度基本没说话，识别结果不可信 */



    var ASR_MIN_MS = 1500;



    /* 结果过短而录音也短 —— 实测这种情况最可能是 ASR 凭空猜字 */



    var ASR_SUSPECT_CHARS = 4;



    var ASR_SUSPECT_MS = 8000;

    var recordState = {

      recorder: null, chunks: [], stream: null, startedAt: 0,

      timer: null, sending: false, cancelled: false,

    };

    var serverAsrReady = false;

    var browserRecognition = null;

    var recordButton = $("recordButton");

    var recordStopButton = $("recordStopButton");

    var recordingRow = $("recordingRow");

    var recordTimer = $("recordTimer");

    var asrNotice = $("asrNotice");



    function setVoiceHint(text) {

      var hint = $("voiceHint");

      if (hint) hint.textContent = text;

    }



    function showAsrNotice(text) {

      if (!asrNotice) return;

      asrNotice.hidden = !text;

      asrNotice.textContent = text || "";

    }



    var SPEECH_ERROR_HINTS = {

      "not-allowed": "麦克风权限被拒绝。点地址栏左侧的锁形图标，把“麦克风”改为允许；http 且非 127.0.0.1 / localhost 的地址浏览器会直接禁用麦克风，请改用 HTTPS。",

      "service-not-allowed": "浏览器语音服务被禁用或不可用。可以改用“录音提问”（走服务端识别），或直接键盘输入。",

      "network": "浏览器语音识别需要连接语音服务，当前网络不可达。可以改用“录音提问”，或直接键盘输入。",

      "no-speech": "没有听到说话内容。靠近麦克风、在安静处再说一次。",

      "audio-capture": "没有检测到麦克风设备。请检查设备连接和系统输入设置。",

      "aborted": "语音识别被中断。可以重新点一次。",

      "language-not-supported": "当前浏览器不支持中文语音识别。建议改用“录音提问”或键盘输入。",

    };



    function speechErrorHint(code) {

      return SPEECH_ERROR_HINTS[code] || ("语音识别失败（" + (code || "未知错误") + "）。可以改用“录音提问”或键盘输入。");

    }



    function mediaSupported() {

      return Boolean(

        navigator.mediaDevices &&

        navigator.mediaDevices.getUserMedia &&

        typeof window.MediaRecorder !== "undefined"

      );

    }



    function pickAudioMime() {

      if (typeof window.MediaRecorder === "undefined" || !window.MediaRecorder.isTypeSupported) return "";

      var candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

      for (var i = 0; i < candidates.length; i += 1) {

        if (window.MediaRecorder.isTypeSupported(candidates[i])) return candidates[i];

      }

      return "";

    }



    function startRecordTimer() {

      stopRecordTimer();

      recordState.startedAt = Date.now();

      recordState.timer = window.setInterval(function () {

        var seconds = (Date.now() - recordState.startedAt) / 1000;

        if (recordTimer) recordTimer.textContent = seconds.toFixed(1) + "s";

        if (seconds * 1000 >= ASR_MAX_MS) stopRecording(false);

      }, 100);

    }



    function stopRecordTimer() {

      if (recordState.timer) {

        window.clearInterval(recordState.timer);

        recordState.timer = null;

      }

    }



    function resetRecordUi() {

      stopRecordTimer();

      if (recordingRow) recordingRow.hidden = true;

      if (recordStopButton) recordStopButton.hidden = true;

      /* 班前准备主行动：把「生成当班清单」接到索引区。
       当班条件输入（天气、作业类型）将在 §8 接入，当前先按全量清单对照。 */
    (function bindPreGenerate() {
      var button = $("preGenerate");
      if (!button) return;
      button.addEventListener("click", function () {
        var host = $("inspectionChecks");
        if (host && host.scrollIntoView) {
          host.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        var notice = $("asrNotice");
        if (notice) {
          notice.hidden = false;
          notice.textContent = "下方是标准检查项目索引。当班条件输入功能正在接入，当前先按全量清单对照。";
        }
      });
    })();

    /* §6 全站 SOS 浮动按钮：优先走 SPA 切换，避免整页刷新；
       href="?view=sos" 作为 JS 未加载时的兜底。 */
    /* §4 应急卡打印（第 20 轮） */
    (function bindSosPrint() {
      var button = $("sosPrint");
      if (!button) return;
      button.addEventListener("click", function () { window.print(); });
    })();

    /* ==================================================================
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

    (function bindSosFab() {
      var fab = $("sosFab");
      if (!fab) return;
      fab.addEventListener("click", function (event) {
        if (event && event.preventDefault) event.preventDefault();
        showView("sos");
      });
    })();

    if (recordButton) {

        recordButton.hidden = false;

        recordButton.disabled = false;

        recordButton.replaceChildren(iconText("i-mic", serverAsrReady ? "录音提问（最长 60 秒）" : "录音提问"));

      }

      if (recordState.stream) {

        recordState.stream.getTracks().forEach(function (track) { track.stop(); });

        recordState.stream = null;

      }

    }



    async function startRecording() {

      if (!serverAsrReady) {

        showAsrNotice("服务端未配置语音识别，正在使用浏览器识别通道。");

        if (browserRecognition) {

          try { browserRecognition.start(); } catch (error) { /* 重复启动时忽略 */ }

        }

        return;

      }

      if (!mediaSupported()) {

        showAsrNotice("当前浏览器不支持录音（需要 MediaRecorder）。请直接键盘输入。");

        return;

      }

      showAsrNotice("");

      try {

        var stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        recordState.stream = stream;

        recordState.chunks = [];

        recordState.cancelled = false;

        var mime = pickAudioMime();

        var recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);

        recordState.recorder = recorder;

        recorder.ondataavailable = function (event) {

          if (event.data && event.data.size) recordState.chunks.push(event.data);

        };

        recorder.onerror = function () {

          showAsrNotice("录音过程中出错，请重试或改用键盘输入。");

          resetRecordUi();

        };

        recorder.onstop = function () {

          var chunks = recordState.chunks;

          recordState.chunks = [];

          resetRecordUi();

          if (recordState.cancelled || !chunks.length) return;

          var blob = new Blob(chunks, { type: mime || "audio/webm" });

          sendAudioForTranscription(blob, mime || "audio/webm");

        };

        recorder.start();

        if (recordingRow) recordingRow.hidden = false;

        if (recordStopButton) recordStopButton.hidden = false;

        if (recordButton) recordButton.hidden = true;

        startRecordTimer();

      } catch (error) {

        resetRecordUi();

        showAsrNotice(speechErrorHint(error && error.name === "NotAllowedError" ? "not-allowed" : "audio-capture"));

      }

    }



    function stopRecording(cancelled) {

      recordState.cancelled = Boolean(cancelled);

      var recorder = recordState.recorder;

      if (recorder && recorder.state !== "inactive") {

        try { recorder.stop(); } catch (error) { /* 已停止时忽略 */ }

        return;

      }

      resetRecordUi();

    }



    async function sendAudioForTranscription(blob, mime) {

      if (blob.size < 1200) {

        showAsrNotice("录到的声音太短了，按住多说几个字再试一次。");

        return;

      }

      /* 记录本次录音时长：结果过短时用来判断是否可疑 */

      var recordedMs = recordState.startedAt ? (Date.now() - recordState.startedAt) : 0;

      var button = $("askButton");

      setVoiceHint("正在识别语音…");

      if (recordButton) recordButton.disabled = true;

      var form = new FormData();

      var extension = mime.indexOf("ogg") >= 0 ? "ogg" : (mime.indexOf("mp4") >= 0 ? "m4a" : "webm");

      form.append("audio", blob, "speech." + extension);

      form.append("access_code", accessCode());

      try {

        var response = await apiFetch("/api/transcribe", { method: "POST", body: form });

        var data = {};

        try { data = await response.json(); } catch (error) { data = {}; }

        if (!response.ok) {

          if (response.status === 503) {

            serverAsrReady = false;

            showAsrNotice((data.error || "服务端语音识别不可用。") + " 已切换到浏览器识别通道。");

            resetRecordUi();

            return;

          }

          throw new Error(data.error || ("HTTP " + response.status));

        }

        var text = (data.text || "").trim();

        if (!text) {

          showAsrNotice("没有识别出文字，请靠近麦克风再说一次。");

          return;

        }

        var input = $("question");

        if (input) {

          input.value = text;

          input.focus();

        }

        /* 结果过短、且录音也短 —— 实测这种情况最可能是 ASR 凭空猜字，

           所以要标出来让用户核对，不能当正常结果直接提交。 */

        var suspect = text.length <= ASR_SUSPECT_CHARS && recordedMs > 0 && recordedMs < ASR_SUSPECT_MS;

        if (input) {

          if (suspect) {

            input.classList.add("is-suspect");

            showAsrNotice("只识别出「" + text + "」，可能是没听清。请确认，或点录音重说一次。");

            setVoiceHint("识别结果待确认");

          } else {

            input.classList.remove("is-suspect");

            showAsrNotice("识别结果已填入输入框，确认后点“查询安全依据”。");

            setVoiceHint("识别完成，可以提交提问");

          }

        }

      } catch (error) {

        showAsrNotice("语音识别失败：" + String(error && error.message ? error.message : error) + "。可以直接键盘输入。");

      } finally {

        if (button) button.disabled = false;

        if (recordButton) recordButton.disabled = false;

        resetRecordUi();

      }

    }



    /* 首页 L3 主行动：把视线引到清单第一条并聚焦，不代替勾选 */

    (function bindTodoStart() {

      var start = $("todoStart");

      if (!start) return;

      start.addEventListener("click", function () {

        var host = $("todoList");

        if (!host) return;

        var first = host.querySelector("input[type=checkbox]");

        if (first && !first.checked) {

          first.focus();

          if (first.scrollIntoView) {

            first.scrollIntoView({ behavior: "smooth", block: "center" });

          }

          setVoiceHint("");

          return;

        }

        var remaining = host.querySelector("input[type=checkbox]:not(:checked)");

        if (remaining) {

          remaining.focus();

          if (remaining.scrollIntoView) {

            remaining.scrollIntoView({ behavior: "smooth", block: "center" });

          }

          return;

        }

        showAsrNotice("五项都确认过了。发现不满足条件时先停下来报告，不要硬上。");

      });

    })();



    if (recordButton) {

      recordButton.addEventListener("click", startRecording);

    }

    if (recordStopButton) {

      recordStopButton.addEventListener("click", function () { stopRecording(false); });

    }



    /* 浏览器识别通道（Chrome / Edge），保留作为降级方案 */

    var SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

    var voiceButton = $("voiceButton");

    if (SpeechRecognitionCtor) {

      browserRecognition = new SpeechRecognitionCtor();

      browserRecognition.lang = "zh-CN";

      browserRecognition.interimResults = false;

      browserRecognition.continuous = false;

      browserRecognition.onstart = function () {

        if (voiceButton) voiceButton.replaceChildren(iconText("i-mic", "正在听…"));

        setVoiceHint("说完会自动提交安全问题");

      };

      browserRecognition.onresult = function (event) {

        var transcript = event.results[0][0].transcript;

        var input = $("question");

        if (input) input.value = transcript;

        showAsrNotice("");

        askQuestion();

      };

      browserRecognition.onerror = function (event) {

        showAsrNotice(speechErrorHint(event && event.error));

      };

      browserRecognition.onend = function () {

        if (voiceButton) voiceButton.textContent = "⌨️ 浏览器识别";

      };

      if (voiceButton) {

        voiceButton.disabled = false;

        voiceButton.addEventListener("click", function () {

          try { browserRecognition.start(); } catch (error) { /* 重复启动时忽略 */ }

        });

      }

    } else if (voiceButton) {

      voiceButton.disabled = true;

      voiceButton.title = "当前浏览器不支持 SpeechRecognition";

    }



    /* 朗读：音色选择 + 暂停 / 继续 / 停止 */

    var speakPauseButton = null;

    function buildVoiceControl() {

      if (!("speechSynthesis" in window)) return;

      var host = $("speakVoiceRow");

      if (!host) return;

      var voices = window.speechSynthesis.getVoices().filter(function (voice) {

        return voice.lang && voice.lang.toLowerCase().indexOf("zh") === 0;

      });

      host.replaceChildren();

      if (!voices.length) {

        host.appendChild(make("span", "answer-meta", "系统未安装中文语音包，朗读可能不准或无声。"));

        return;

      }

      var select = make("select", "voice-select");

      select.setAttribute("aria-label", "选择朗读音色");

      voices.forEach(function (voice) {

        var option = document.createElement("option");

        option.value = voice.name;

        option.textContent = voice.name + "（" + voice.lang + "）";

        select.appendChild(option);

      });

      select.addEventListener("change", function () { preferredVoiceName = select.value; });

      host.appendChild(select);

      speakPauseButton = make("button", "ghost-button", "⏸ 暂停");

      speakPauseButton.type = "button";

      speakPauseButton.addEventListener("click", function () {

        if (window.speechSynthesis.paused) {

          window.speechSynthesis.resume();

          speakPauseButton.textContent = "⏸ 暂停";

        } else {

          window.speechSynthesis.pause();

          speakPauseButton.textContent = "▶ 继续";

        }

      });

      host.appendChild(speakPauseButton);

    }

    var preferredVoiceName = "";

    if ("speechSynthesis" in window) {

      buildVoiceControl();

      if (typeof window.speechSynthesis.onvoiceschanged !== "undefined") {

        window.speechSynthesis.onvoiceschanged = buildVoiceControl;

      }

    }



    var speakButton = $("speakButton");

    if (speakButton) {

      speakButton.addEventListener("click", function () {

        if (!lastAnswerText || !("speechSynthesis" in window)) return;

        window.speechSynthesis.cancel();

        var utterance = new SpeechSynthesisUtterance(lastAnswerText);

        utterance.lang = "zh-CN";

        utterance.rate = 0.9;

        var voices = window.speechSynthesis.getVoices();

        var chosen = null;

        for (var i = 0; i < voices.length; i += 1) {

          if (preferredVoiceName && voices[i].name === preferredVoiceName) chosen = voices[i];

        }

        if (!chosen) {

          for (var j = 0; j < voices.length; j += 1) {

            if (voices[j].lang && voices[j].lang.toLowerCase().indexOf("zh") === 0) { chosen = voices[j]; break; }

          }

        }

        if (chosen) utterance.voice = chosen;

        utterance.onend = function () {

          var stopButton = $("speakStopButton");

          if (stopButton) stopButton.hidden = true;

          if (speakPauseButton) speakPauseButton.textContent = "⏸ 暂停";

        };

        window.speechSynthesis.speak(utterance);

        var stopButton = $("speakStopButton");

        if (stopButton) stopButton.hidden = false;

      });

    }

    bindClick("speakStopButton", function () {

      if ("speechSynthesis" in window) window.speechSynthesis.cancel();

      var stopButton = $("speakStopButton");

      if (stopButton) stopButton.hidden = true;

      if (speakPauseButton) speakPauseButton.textContent = "⏸ 暂停";

    });



    window.addEventListener("beforeunload", function () {

      if (recordState.recorder && recordState.recorder.state !== "inactive") {

        try { recordState.recorder.stop(); } catch (error) { /* 忽略 */ }

      }

      if (recordState.stream) {

        recordState.stream.getTracks().forEach(function (track) { track.stop(); });

      }

      if (cameraStream) cameraStream.getTracks().forEach(function (track) { track.stop(); });

    });



    /* ==================================================================

       11. 拍照问安全（拍照 / 预览 / 本机压缩 / 分类错误 / 可取消上传）

       ================================================================== */

    var MAX_IMAGE_BYTES = 8 * 1024 * 1024;

    var COMPRESS_MAX_EDGE = 1600;

    var COMPRESS_QUALITY = 0.82;

    var photoState = { blob: null, name: "", width: 0, height: 0, source: "" };

    var cameraStream = null;

    var photoAbort = null;



    var photoErrorBox = $("photoError");

    var cameraStage = $("cameraStage");

    var cameraVideo = $("cameraVideo");

    var photoStage = $("photoStage");

    var photoPreview = $("photoPreview");

    var photoFacts = $("photoFacts");

    var photoProgress = $("photoProgress");

    var photoProgressBar = $("photoProgressBar");

    var photoProgressText = $("photoProgressText");



    function humanSize(bytes) {

      if (bytes === null || bytes === undefined) return "";

      if (bytes < 1024) return bytes + " B";

      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";

      return (bytes / (1024 * 1024)).toFixed(2) + " MB";

    }



    function hidePhotoError() {

      if (photoErrorBox) {

        photoErrorBox.hidden = true;

        photoErrorBox.replaceChildren();

      }

    }



    function showPhotoError(title, lines) {

      if (!photoErrorBox) return;

      photoErrorBox.hidden = false;

      photoErrorBox.replaceChildren();

      photoErrorBox.appendChild(make("b", "", title));

      if (lines && lines.length) {

        var list = make("ul");

        lines.forEach(function (line) { list.appendChild(make("li", "", line)); });

        photoErrorBox.appendChild(list);

      }

      photoErrorBox.scrollIntoView({ behavior: "smooth", block: "center" });

    }



    function friendlyMediaError(error) {

      var name = error && error.name ? error.name : "";

      if (name === "NotAllowedError" || name === "SecurityError") {

        return [

          "浏览器没有授予权限，或当前页面不是安全上下文。",

          "点地址栏左侧的锁形图标，把“摄像头 / 麦克风”改为允许后重试。",

          "如果地址是 http:// 且不是 127.0.0.1 / localhost，浏览器会直接拒绝；请改用 HTTPS 访问，或用“从相册 / 文件选择”。",

        ];

      }

      if (name === "NotFoundError" || name === "OverconstrainedError") {

        return ["没有找到可用的摄像头。", "可以改用“从相册 / 文件选择”上传已有的现场照片。"];

      }

      if (name === "NotReadableError") {

        return ["摄像头被其他程序占用（例如视频会议、相机应用）。", "关掉占用摄像头的程序后重试。"];

      }

      return ["浏览器没有提供摄像头能力，或调用被拒绝。", "可以改用“从相册 / 文件选择”。"];

    }



    function stopCamera() {

      if (cameraStream) {

        cameraStream.getTracks().forEach(function (track) { track.stop(); });

        cameraStream = null;

      }

      if (cameraVideo) cameraVideo.srcObject = null;

      if (cameraStage) cameraStage.hidden = true;

      var stopButton = $("cameraStopButton");

      if (stopButton) stopButton.hidden = true;

      var shotButton = $("captureButton");

      if (shotButton) shotButton.hidden = true;

    }



    async function openCamera() {

      hidePhotoError();

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {

        showPhotoError("当前浏览器不支持直接调用摄像头。", [

          "请改用“从相册 / 文件选择”上传现场照片。",

          "旧版浏览器，或 http 且非 127.0.0.1 / localhost 的地址，都会禁用摄像头。",

        ]);

        return;

      }

      try {

        stopCamera();

        cameraStream = await navigator.mediaDevices.getUserMedia({

          video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } },

          audio: false,

        });

        if (cameraVideo) {

          cameraVideo.srcObject = cameraStream;

          var played = cameraVideo.play();

          if (played && played.catch) played.catch(function () { /* 自动播放被拦截时忽略 */ });

        }

        if (cameraStage) cameraStage.hidden = false;

        var stopButton = $("cameraStopButton");

        if (stopButton) stopButton.hidden = false;

        var shotButton = $("captureButton");

        if (shotButton) shotButton.hidden = false;

      } catch (error) {

        stopCamera();

        showPhotoError("无法打开摄像头", friendlyMediaError(error));

      }

    }



    function canvasToBlob(canvas, type, quality) {

      return new Promise(function (resolve) {

        canvas.toBlob(function (blob) { resolve(blob); }, type, quality);

      });

    }



    /* 去掉扩展名，统一输出 .jpg */

    function stripExtension(name) {

      var text = String(name || "site-photo");

      var dot = text.lastIndexOf(".");

      return dot > 0 ? text.slice(0, dot) : text;

    }



    async function compressImage(source, name, sourceLabel) {

      var width = source.videoWidth || source.naturalWidth || source.width;

      var height = source.videoHeight || source.naturalHeight || source.height;

      if (!width || !height) throw new Error("图片信息读取失败");

      var scale = Math.min(1, COMPRESS_MAX_EDGE / Math.max(width, height));

      var targetWidth = Math.max(1, Math.round(width * scale));

      var targetHeight = Math.max(1, Math.round(height * scale));

      var canvas = document.createElement("canvas");

      canvas.width = targetWidth;

      canvas.height = targetHeight;

      var context = canvas.getContext && canvas.getContext("2d");

      if (!context) throw new Error("当前浏览器不支持图片压缩");

      context.drawImage(source, 0, 0, targetWidth, targetHeight);

      var blob = await canvasToBlob(canvas, "image/jpeg", COMPRESS_QUALITY);

      if (!blob) throw new Error("图片压缩失败");

      if (blob.size > MAX_IMAGE_BYTES) {

        throw new Error("压缩后仍超过 8 MB，请靠近目标重拍或降低分辨率");

      }

      return {

        blob: blob,

        name: stripExtension(name) + ".jpg",

        width: targetWidth,

        height: targetHeight,

        source: sourceLabel,

      };

    }



    function showPhotoStage(meta) {

      photoState = {

        blob: meta.blob,

        name: meta.name,

        width: meta.width,

        height: meta.height,

        source: meta.source,

      };

      if (!photoStage || !photoPreview) return;

      if (photoPreview.dataset.url) URL.revokeObjectURL(photoPreview.dataset.url);

      var url = URL.createObjectURL(meta.blob);

      photoPreview.dataset.url = url;

      photoPreview.src = url;

      photoStage.hidden = false;

      var retake = $("photoRetakeButton");

      if (retake) retake.hidden = false;

      if (photoFacts) {

        photoFacts.replaceChildren();

        photoFacts.appendChild(make("span", "", meta.source));

        photoFacts.appendChild(make("span", "", meta.width + " × " + meta.height));

        photoFacts.appendChild(make("span", "", humanSize(meta.blob.size)));

        photoFacts.appendChild(make("span", "", "已压缩为 JPEG"));

      }

      var button = $("photoButton");

      if (button) button.disabled = false;

    }



    function resetPhoto() {

      photoState = { blob: null, name: "", width: 0, height: 0, source: "" };

      stopCamera();

      if (photoStage) photoStage.hidden = true;

      if (photoPreview && photoPreview.dataset.url) {

        URL.revokeObjectURL(photoPreview.dataset.url);

        photoPreview.removeAttribute("src");

        delete photoPreview.dataset.url;

      }

      var retake = $("photoRetakeButton");

      if (retake) retake.hidden = true;

      var result = $("photoResult");

      if (result) { result.hidden = true; result.textContent = ""; }

      hidePhotoError();

      var cameraPick = $("sitePhoto");

      if (cameraPick) cameraPick.value = "";

      var filePick = $("sitePhotoCamera");

      if (filePick) filePick.value = "";

    }



    async function capturePhoto() {

      if (!cameraVideo || !cameraVideo.videoWidth) {

        showPhotoError("摄像头还没准备好。", ["稍等一秒再点“拍下这一张”。"]);

        return;

      }

      hidePhotoError();

      try {

        var meta = await compressImage(cameraVideo, "site-photo", "摄像头拍摄");

        stopCamera();

        showPhotoStage(meta);

      } catch (error) {

        showPhotoError("照片处理失败", [String(error && error.message ? error.message : error)]);

      }

    }



    async function usePhotoFile(file, sourceLabel) {

      if (!file) return;

      hidePhotoError();

      if (file.size > MAX_IMAGE_BYTES) {

        showPhotoError("照片超过 8 MB。", [

          "当前大小 " + humanSize(file.size) + "。",

          "可以重拍，或用手机相册自带的压缩功能处理后再上传。",

        ]);

        return;

      }

      /* 优先用 createImageBitmap 并开启 imageOrientation: "from-image"：

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

            file.name.toLowerCase().indexOf(".heic") >= 0 ||

            file.name.toLowerCase().indexOf(".heif") >= 0;

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

    }



    function setPhotoProgress(percent) {

      if (!photoProgress) return;

      photoProgress.hidden = false;

      if (photoProgressBar) {

        photoProgressBar.style.width = Math.max(0, Math.min(100, percent)) + "%";

      }

      if (photoProgressText) photoProgressText.textContent = Math.round(percent) + "%";

    }



    function classifyPhotoFailure(status, payload, message) {

      var code = payload && payload.error_code ? payload.error_code : "";

      if (code === "vision_not_configured" || status === 503) {

        return {

          title: "当前未配置图像识别服务，照片检查暂不可用。",

          lines: [

            (payload && payload.error) || "服务端没有配置视觉模型。",

            "可以先用文字提问，知识库检索和文字问答不受影响。",

            "联系管理员在服务端配置视觉模型后即可恢复。",

          ],

        };

      }

      if (status === 401) {

        return { title: "访问码不正确。", lines: ["请重新输入管理员提供的访问码。"] };

      }

      if (status === 429) {

        return {

          title: "请求过于频繁或当前使用人数较多。",

          lines: ["等 1 分钟后再试，或先改用文字提问。"],

        };

      }

      if (status === 413) {

        return { title: "照片超过服务端限制。", lines: ["请重拍或压缩后重试。"] };

      }

      if (status === 400) {

        return {

          title: "照片不符合要求。",

          lines: [

            (payload && payload.error) || "请确认格式为 JPG / PNG / WEBP。",

            "重新拍摄或换一张再试。",

          ],

        };

      }

      if (!status) {

        return {

          title: "上传没有完成。",

          lines: [

            message || "可能是网络中断，或你点了取消。",

            "检查网络后重新点“分析照片”。",

          ],

        };

      }

      return {

        title: "照片分析失败（服务端错误 " + status + "）。",

        lines: [

          (payload && payload.error) || String(message || "未知错误"),

          "可以稍后重试，或改用文字提问。",

        ],

      };

    }



    function uploadWithProgress(url, form, onProgress) {

      return new Promise(function (resolve, reject) {

        var request = new XMLHttpRequest();

        photoAbort = request;

        request.open("POST", url, true);

        var code = accessCode();

        if (code) request.setRequestHeader("X-Access-Code", code);

        if (request.upload && onProgress) {

          request.upload.onprogress = function (event) {

            if (event.lengthComputable) onProgress((event.loaded / event.total) * 96);

          };

        }

        request.onload = function () {

          var payload = {};

          try { payload = JSON.parse(request.responseText || "{}"); } catch (error) { payload = {}; }

          if (request.status >= 200 && request.status < 300) {

            if (onProgress) onProgress(100);

            resolve(payload);

            return;

          }

          var failure = new Error(payload.error || ("HTTP " + request.status));

          failure.status = request.status;

          failure.payload = payload;

          reject(failure);

        };

        request.onerror = function () {

          var failure = new Error("网络错误，上传未完成");

          failure.status = 0;

          reject(failure);

        };

        request.onabort = function () {

          var failure = new Error("上传已取消");

          failure.status = 0;

          reject(failure);

        };

        request.send(form);

      });

    }



    /* ==================================================================

       第 24 轮 A：识别结果结构化渲染

       ------------------------------------------------------------------

       后端一直返回 structured，但前端只用了 text，结构化数据全被浪费。

       这里按真实字段分四段渲染：



         A 作业场景与风险结论   work_type + 真实风险条数

         B 图片证据与风险位置   risks[].where（位置）+ risks[].what（现象）

         C 整改建议             risks[].action（关联关系来自数据本身）

         D 待确认信息           uncertain[]



       容错：structured 不可用就回退到原始文本，绝不让结果区崩掉。

       不伪造坐标、置信度、检测框或任何后端没给的字段。

       ================================================================== */

    function isNonEmptyString(value) {

      return typeof value === "string" && value.trim().length > 0;

    }



    function renderPhotoResult(payload, host) {

      var data = payload && payload.structured;

      if (!data || typeof data !== "object") return false;



      var risks = Array.isArray(data.risks) ? data.risks.filter(function (item) {

        return item && (isNonEmptyString(item.what) || isNonEmptyString(item.where));

      }) : [];

      var uncertain = Array.isArray(data.uncertain) ? data.uncertain.filter(isNonEmptyString) : [];

      var actions = risks.filter(function (item) { return isNonEmptyString(item.action); });

      var workType = isNonEmptyString(data.work_type) ? data.work_type.trim() : "";



      /* 三段全空 —— 如实说明，不硬凑 */

      if (!workType && !risks.length && !uncertain.length) return false;



      var wrap = make("div", "ins-result");



      /* ---- A 作业场景与风险结论 ---- */

      var head = make("section", "ins-block ins-summary");

      head.appendChild(make("h3", "ins-block-title", "识别结论"));

      if (workType) {

        var wt = make("p", "ins-worktype");

        wt.appendChild(make("span", "ins-worktype-label", "作业场景"));

        wt.appendChild(make("span", "ins-worktype-value", workType));

        head.appendChild(wt);

      } else {

        head.appendChild(make("p", "ins-worktype is-empty",

          "未能从这张照片确定作业场景。请把作业面、防护设施和周边环境一起拍进去。"));

      }

      var metric = make("div", "ins-metric");

      metric.appendChild(make("span", "ins-metric-num", String(risks.length)));

      metric.appendChild(make("span", "ins-metric-unit", "条可见风险"));

      if (uncertain.length) {

        metric.appendChild(make("span", "ins-metric-note",

          "另有 " + uncertain.length + " 项待确认"));

      }

      head.appendChild(metric);

      wrap.appendChild(head);



      /* ---- B 图片证据与风险位置 ---- */

      if (risks.length) {

        var section = make("section", "ins-block");

        section.appendChild(make("h3", "ins-block-title",

          "风险位置与现象（" + risks.length + " 条）"));

        var list = make("ol", "ins-risk-list");

        risks.forEach(function (item) {

          var row = make("li", "ins-risk");

          if (isNonEmptyString(item.where)) {

            /* 位置标签：模型给的是画面方位描述，如实展示，不换算成坐标 */

            var where = make("span", "ins-risk-where");

            where.appendChild(makeIcon("i-search", "ico ico-sm"));

            where.appendChild(document.createTextNode(item.where));

            row.appendChild(where);

          }

          row.appendChild(make("p", "ins-risk-what",

            isNonEmptyString(item.what) ? item.what : "（这一条没有文字描述）"));

          /* C 整改建议紧跟在对应风险下 —— 关联关系来自数据本身 */

          if (isNonEmptyString(item.action)) {

            var fix = make("div", "ins-risk-action");

            fix.appendChild(makeIcon("i-check", "ico ico-sm"));

            var fixText = make("span");

            fixText.appendChild(make("b", "", "立即动作："));

            fixText.appendChild(document.createTextNode(item.action));

            fix.appendChild(fixText);

            row.appendChild(fix);

          }

          list.appendChild(row);

        });

        section.appendChild(list);

        if (!actions.length) {

          section.appendChild(make("p", "ins-note",

            "这张照片的识别结果没有给出逐条整改动作，请以现场安全交底和项目制度为准。"));

        }

        wrap.appendChild(section);

      } else {

        var clean = make("section", "ins-block ins-clean");

        clean.appendChild(make("h3", "ins-block-title", "未识别到可报告的风险"));

        clean.appendChild(make("p", "ins-note",

          "这不代表现场安全。换个角度多拍几张，或请现场安全员确认。"));

        wrap.appendChild(clean);

      }



      /* ---- D 待确认信息 ---- */

      if (uncertain.length) {

        var pending = make("section", "ins-block ins-pending");

        var title = make("h3", "ins-block-title");

        title.appendChild(makeIcon("i-alert", "ico ico-sm"));

        title.appendChild(document.createTextNode("待确认（" + uncertain.length + " 项）"));

        pending.appendChild(title);

        var ul = make("ul", "ins-pending-list");

        uncertain.forEach(function (text) { ul.appendChild(make("li", "", text)); });

        pending.appendChild(ul);

        pending.appendChild(make("p", "ins-note",

          "以上内容模型无法确认，需要你补充现场信息或请安全员人工复核。"));

        wrap.appendChild(pending);

      }



      /* ---- 免责声明（与页面既有口径一致） ---- */

      wrap.appendChild(make("p", "ins-disclaimer",

        "本结果仅辅助识别照片中肉眼可见的风险，不替代现场安全员检查，也不证明现场完全合规。"));



      /* 服务端告警（如模型降级）如实透出 */

      (payload.warnings || []).forEach(function (warning) {

        wrap.appendChild(makeIconText("div", "warn-box", "i-alert", "ico ico-sm", warning));

      });



      host.textContent = "";

      host.appendChild(wrap);

      return true;

    }



    async function inspectPhoto() {

      var button = $("photoButton");

      var result = $("photoResult");

      if (!button || !result) return;

      if (!photoState.blob) {

        showPhotoError("还没有照片。", [

          "点“打开摄像头拍照”，或点“从相册 / 文件选择”。",

          "拍完会先在本机压缩到长边 " + COMPRESS_MAX_EDGE + "px，再上传。",

        ]);

        return;

      }

      var question = ($("photoQuestion") || {}).value || "";

      hidePhotoError();

      button.disabled = true;

      button.textContent = "分析中";

      result.hidden = false;

      result.textContent = "正在结合照片与安全知识库分析，请稍候…";

      setPhotoProgress(6);



      var form = new FormData();

      form.append("image", photoState.blob, photoState.name || "site-photo.jpg");

      form.append("question", question.trim());

      form.append("access_code", accessCode());



      try {

        var payload = await uploadWithProgress("/api/inspect-image", form, function (percent) {

          setPhotoProgress(percent);

        });

        setPhotoProgress(100);

        /* 优先结构化渲染；structured 不可用时回退到原始文本 */

        result.textContent = "";

        if (!renderPhotoResult(payload, result)) {

          var text = payload.text || "";

          (payload.warnings || []).forEach(function (warning) { text += NL2 + "⚠ " + warning; });

          if (payload.sources && payload.sources.length) {

            text += NL2 + "参考依据：" + payload.sources.slice(0, 3).map(function (item) {

              return item.title;

            }).join("；");

          }

          result.textContent = text || "服务端没有返回内容。";

        }

      } catch (error) {

        result.hidden = true;

        var info = classifyPhotoFailure(error.status, error.payload, error.message);

        showPhotoError(info.title, info.lines);

      } finally {

        button.disabled = false;

        button.textContent = "开始识别风险";

        if (photoProgress) photoProgress.hidden = true;

        if (photoProgressBar) photoProgressBar.style.width = "0%";

        photoAbort = null;

      }

    }



    bindClick("cameraButton", openCamera);

    bindClick("captureButton", capturePhoto);

    bindClick("cameraStopButton", stopCamera);

    bindClick("photoRetakeButton", resetPhoto);

    bindClick("photoButton", inspectPhoto);

    bindClick("photoCancelButton", function () {

      if (photoAbort) photoAbort.abort();

    });



    var cameraInput = $("sitePhoto");

    if (cameraInput) {

      cameraInput.addEventListener("change", function () {

        var file = cameraInput.files && cameraInput.files[0];

        if (file) usePhotoFile(file, "摄像头拍摄");

      });

    }

    var pickButton = $("filePickButton");

    var filePickInput = $("sitePhotoCamera");

    if (pickButton && filePickInput) {

      pickButton.addEventListener("click", function () { filePickInput.click(); });

      filePickInput.addEventListener("change", function () {

        var file = filePickInput.files && filePickInput.files[0];

        if (file) usePhotoFile(file, "相册 / 文件");

      });

    }



    /* ==================================================================

       12. 开工前检查清单（含本地勾选保存）

       ================================================================== */

    function buildCheckItem(text, key) {

      var state = readStore(CHECKLIST_KEY, {});

      var label = make("label", "check-item" + (state[key] ? " checked" : ""));

      var box = document.createElement("input");

      box.type = "checkbox";

      box.checked = Boolean(state[key]);

      box.setAttribute("aria-label", text);

      box.addEventListener("change", function () {

        var current = readStore(CHECKLIST_KEY, {});

        current[key] = box.checked;

        writeStore(CHECKLIST_KEY, current); if (box.checked) logActivity();

        label.classList.toggle("checked", box.checked);

        updateCheckProgress();

      });

      label.appendChild(box);

      label.appendChild(make("span", "", text));

      return label;

    }











    var checkReset = $("checkReset");

    if (checkReset) {

      checkReset.addEventListener("click", function () {

        writeStore(CHECKLIST_KEY, {});

        document.querySelectorAll("#checklist input[type=checkbox]").forEach(function (box) { box.checked = false; });

        document.querySelectorAll("#checklist .check-item").forEach(function (item) { item.classList.remove("checked"); });

        updateCheckProgress();

      });

    }



    /* ==================================================================

       13. 真实案例

       ================================================================== */

    var allCases = [];

    var activeCaseFilter = "";



    function renderCaseFilters() {

      var host = clear($("caseFilters"));

      if (!host) return;

      var categories = [];

      allCases.forEach(function (item) {

        var name = item.category || "未分类";

        if (categories.indexOf(name) < 0) categories.push(name);

      });

      var options = ["全部"].concat(categories);

      options.forEach(function (name) {

        var value = name === "全部" ? "" : name;

        var chip = make("button", "filter-chip" + (value === activeCaseFilter ? " active" : ""), name);

        chip.type = "button";

        chip.addEventListener("click", function () {

          activeCaseFilter = value;

          renderCaseFilters();

          renderCases(allCases);

        });

        host.appendChild(chip);

      });

    }



    function renderCases(items) {

      var host = clear($("caseGrid"));

      if (!host) return;

      var filtered = (items || []).filter(function (item) {

        return !activeCaseFilter || (item.category || "") === activeCaseFilter;

      });

      var note = $("caseCountNote");

      if (note) note.textContent = "共 " + (items || []).length + " 个案例，当前显示 " + filtered.length + " 个";

      if (!filtered.length) {

        host.appendChild(make("p", "empty-state", "没有匹配的案例，换个关键词或切换分类试试。"));

        return;

      }

      filtered.forEach(function (item) { host.appendChild(caseCard(item, false)); });

    }



    async function loadCases(query) {

      try {

        var data = await getJson("/api/cases?q=" + encodeURIComponent(query || ""));

        allCases = data.cases || [];

        if (!query) renderCaseFilters();

        renderCases(allCases);

        

        return allCases;

      } catch (error) {

        allCases = [];

        renderCases([]);

        return [];

      }

    }



    var caseSearchButton = $("caseSearchButton");

    if (caseSearchButton) {

      caseSearchButton.addEventListener("click", function () {

        var input = $("caseSearch");

        loadCases(input ? input.value.trim() : "");

      });

    }

    var caseSearchInput = $("caseSearch");

    if (caseSearchInput) {

      caseSearchInput.addEventListener("keydown", function (event) {

        if (event.key === "Enter") loadCases(event.target.value.trim());

      });

    }



    /* ==================================================================

       14. 应急求助

       ================================================================== */

    /* ==================================================================
       每日警示案例（首页 L4）
       ------------------------------------------------------------------
       数据来自 /api/cases，按日期取模轮换，同一天稳定显示同一条。
       案例的 date 是事故/通报日期，不是"今天发生"，所以文案用
       「每日警示案例」而不是「今日」，避免内容失真。
       ================================================================== */
    function renderDailyCase() {
      var host = $("homeDailyCase");
      if (!host) return;

      function paint(cases) {
        if (!cases || !cases.length) {
          host.innerHTML = "";
          var empty = make("div", "case-empty");
          empty.appendChild(make("p", "", "案例库暂时是空的。"));
          var hint = make("p", "case-empty-hint", "案例来自公开事故与隐患通报，管理员导入后会在这里轮换显示。");
          empty.appendChild(hint);
          host.appendChild(empty);
          return;
        }
        var stamp = new Date();
        var seed = stamp.getFullYear() * 10000 + (stamp.getMonth() + 1) * 100 + stamp.getDate();
        var pick = cases[seed % cases.length];

        host.innerHTML = "";
        var wrap = make("div", "case-daily");

        var meta = make("div", "case-daily-meta");
        if (pick.category) meta.appendChild(make("span", "case-tag", pick.category));
        if (pick.date) meta.appendChild(make("span", "case-daily-date", pick.date));
        wrap.appendChild(meta);

        wrap.appendChild(make("h3", "case-daily-title", pick.title || "未命名案例"));

        if (pick.what_happened) {
          var what = make("p", "case-daily-what");
          what.appendChild(make("b", "", "发生了什么："));
          what.appendChild(document.createTextNode(pick.what_happened));
          wrap.appendChild(what);
        }
        if (pick.why_dangerous) {
          var why = make("p", "case-daily-why");
          why.appendChild(make("b", "", "为什么危险："));
          why.appendChild(document.createTextNode(pick.why_dangerous));
          wrap.appendChild(why);
        }
        if (pick.lesson) {
          var lesson = make("div", "case-daily-lesson");
          lesson.appendChild(make("b", "", "记住这一条："));
          lesson.appendChild(document.createTextNode(pick.lesson));
          wrap.appendChild(lesson);
        }

        var foot = make("div", "case-daily-foot");
        if (pick.source_name) {
          foot.appendChild(make("span", "case-daily-source", "来源：" + pick.source_name));
        }
        var more = make("button", "ghost-button ico-button", "看全部案例");
        more.type = "button";
        more.addEventListener("click", function () { showView("learn"); });
        foot.appendChild(more);
        wrap.appendChild(foot);

        host.appendChild(wrap);
      }

      getJson("/api/cases")
        .then(function (data) { paint((data && data.cases) || []); })
        .catch(function () {
          host.innerHTML = "";
          var box = make("div", "case-empty");
          box.appendChild(make("p", "", "案例读取失败。"));
          box.appendChild(make("p", "case-empty-hint", "检查网络后刷新重试；也可以先看「学习与资料」里的案例库。"));
          host.appendChild(box);
        });
    }

    /* ==================================================================
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
        /* 只有「当班必查」默认展开；常规项与我的导入收进 details，
           否则手机端一屏看不到重点（第 20 轮 §3） */
        var collapsible = group.key !== "required";
        var bucket;
        var box = null;
        if (collapsible) {
          box = make("details", "disclosure check-group-more");
          var summary = make("summary", "", group.title + "（" + group.items.length + " 条）");
          summary.appendChild(make("span", "disclosure-hint", group.note));
          box.appendChild(summary);
          bucket = make("div", "disclosure-body");
          box.appendChild(bucket);
          host.appendChild(box);
        } else {
          bucket = make("section", "check-group");
          var head = make("div", "check-group-head");
          head.appendChild(make("b", "check-group-title", group.title));
          head.appendChild(make("span", "check-group-note", group.note));
          bucket.appendChild(head);
        }

        if (!group.items.length) {
          bucket.appendChild(make("p", "empty-state",
            group.key === "import"
              ? "还没有导入项目自己的检查表。可以在下面「导入项目自有清单」里添加。"
              : "这一组暂时没有内容。"));
          if (box) box.appendChild(bucket);

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
      var isXlsx = file.name.toLowerCase().indexOf(".xlsx") >= 0;
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
        return (text.indexOf(",") >= 0 || text.indexOf(String.fromCharCode(34)) >= 0 || text.indexOf(String.fromCharCode(10)) >= 0) ? '"' + text.replace(/"/g, '""') + '"' : text;
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
      var blob = new Blob([String.fromCharCode(65279) + lines.join(String.fromCharCode(13, 10))], { type: "text/csv;charset=utf-8" });
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

    /* 检查项目索引：按类别列出场景条目，配 §5 的对照表格。
       与主清单分开 —— 主清单随当班条件变化，索引是固定参考资料。 */
    function renderInspectionIndex() {
      var host = $("inspectionChecks");
      if (!host) return;
      getJson("/api/checklists")
        .then(function (data) {
          clear(host);
          var groups = data.categories || [];
          if (!groups.length) {
            host.appendChild(make("p", "empty-state", "索引暂时读不到，刷新后再试。"));
            return;
          }
          groups.forEach(function (group) {
            var bucket = make("section", "index-cat");
            var head = make("div", "index-cat-head");
            head.appendChild(make("b", "index-cat-name", group.name || "未命名"));
            if (group.scope) {
              head.appendChild(make("span", "index-cat-scope", group.scope));
            }
            bucket.appendChild(head);
            var list = make("ul", "index-cat-list");
            (group.worker_checks || []).forEach(function (text) {
              list.appendChild(make("li", "", text));
            });
            bucket.appendChild(list);
            host.appendChild(bucket);
          });
        })
        .catch(function () {
          clear(host);
          host.appendChild(make("p", "empty-state", "索引读取失败，刷新页面重试。"));
        });
    }

    function initPrePanels() {
      var stored = readStore(IMPORT_KEY, { rows: [] });
      importRows = stored.rows || [];
      bindPrePanels();

      renderInspectionIndex();
      getJson("/api/checklists/conditions")
        .then(function (data) { renderConditions(data); })
        .catch(function () { renderConditions(null); })
        .then(function () { return generateChecklist(true); });
    }

    function renderEmergencyGrid() {

      var host = clear($("emergencyGrid"));

      if (!host) return;

      EMERGENCY_DATA.forEach(function (scene) {

        var card = make("button", "emergency-card");

        card.type = "button";

        /* 描边分级按**场景致命速度**，不是按号码 ——
           实测五张卡都打 120，按号码分级结果全红，等于没分级。
           红（立即致命）：火灾 / 触电 / 坍塌
           琥珀（需尽快）：受伤 / 坠落 / 其他 */

        var CRITICAL = ["火灾", "触电", "坍塌"];

        card.classList.add(CRITICAL.indexOf(scene.key) >= 0 ? "is-critical" : "is-urgent");

        card.appendChild(makeIcon(scene.icon, "ico ico-2xl"));

        card.appendChild(make("strong", "em-card-title", scene.label));

        card.appendChild(make("p", "em-card-lead", scene.headline));

        var dial = make("span", "em-card-dial");

        dial.appendChild(makeIcon("i-phone", "ico ico-sm"));

        dial.appendChild(document.createTextNode(" " + (scene.calls || []).join(" / ")));

        card.appendChild(dial);

        card.addEventListener("click", function () { showEmergencyGuide(scene.key); });

        host.appendChild(card);

      });

    }



    function showEmergencyGuide(key) {

      var scene = null;

      EMERGENCY_DATA.forEach(function (item) { if (item.key === key) scene = item; });

      if (!scene) scene = EMERGENCY_DATA[EMERGENCY_DATA.length - 1];

      var host = clear($("emergencyGuide"));

      if (!host) return;

      host.hidden = false;

      var head = make("h3");

      head.appendChild(iconText(scene.icon, scene.label));

      head.appendChild(make("span", "q-role-tag", "现场处置步骤"));

      host.appendChild(head);

      host.appendChild(make("p", "role-summary", scene.headline));



      var steps = make("div", "em-steps");

      scene.steps.forEach(function (text, index) {

        var row = make("div", "em-step");

        row.appendChild(make("span", "em-num", String(index + 1)));

        row.appendChild(make("span", "", text));

        steps.appendChild(row);

      });

      host.appendChild(steps);



      var never = make("div", "em-never");

      never.appendChild(make("b", "", "绝对不能做"));

      never.appendChild(document.createTextNode(scene.never));

      host.appendChild(never);



      var calls = make("div", "em-calls");

      scene.calls.forEach(function (phone) {

        var link = makeButtonWithIcon("primary-button danger-button is-call", "i-phone", phone === "120" ? "拨打 120 急救" : "拨打 119 火警 / 救援");

        link.setAttribute("href", "tel:" + phone);

        calls.appendChild(link);

      });

      var speak = makeButtonWithIcon("secondary-button", "i-speaker", "朗读处置步骤");

      speak.type = "button";

      speak.addEventListener("click", function () {

        if (!("speechSynthesis" in window)) return;

        window.speechSynthesis.cancel();

        var text = scene.label + "。" + scene.headline + " " + scene.steps.join(" ") + " 绝对不能做：" + scene.never;

        var utterance = new SpeechSynthesisUtterance(text);

        utterance.lang = "zh-CN";

        utterance.rate = 0.9;

        window.speechSynthesis.speak(utterance);

      });

      calls.appendChild(speak);

      host.appendChild(calls);

      host.appendChild(make("p", "em-note", "以上步骤用于快速提醒。现场应以项目应急预案、现场负责人、安全员和当地紧急救援要求为准。"));



      var call120 = $("call120");

      var call119 = $("call119");

      if (call120) call120.style.display = scene.calls.indexOf("120") >= 0 ? "inline-block" : "none";

      if (call119) call119.style.display = scene.calls.indexOf("119") >= 0 ? "inline-block" : "none";

      host.scrollIntoView({ behavior: "smooth", block: "center" });

    }



    /* ==================================================================

       15. 知识库与状态

       ================================================================== */

    function bindClick(id, handler) {

      var node = $(id);

      if (node) node.addEventListener("click", handler);

      return node;

    }



    /* ==================================================================

       15b. 学习积分与可打印培训记录单

       只统计本机学习行为；记录单是"培训参与记录"，不是资格证明。

       ================================================================== */

    var CERT_THRESHOLD = 120;

    var POINTS_PER_STEP = 5;

    var POINTS_PER_CORRECT = 4;

    var POINTS_PER_PRACTICAL = 2;



    function computePoints() {

      var practicalDone = 0;

      var practical = readStore(PRACTICAL_KEY, {});

      PRACTICAL_ITEMS.forEach(function (item) { if (practical[item.id]) practicalDone += 1; });

      var stepDone = 0;

      var steps = readStore("sitesaha-steps-v1", {});

      Object.keys(steps).forEach(function (key) { if (steps[key]) stepDone += 1; });

      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);

      var correct = quiz.bestCorrect || 0;

      var practicalPoints = practicalDone * POINTS_PER_PRACTICAL;

      var stepPoints = stepDone * POINTS_PER_STEP;

      var quizPoints = correct * POINTS_PER_CORRECT;

      return {

        total: practicalPoints + stepPoints + quizPoints,

        practicalDone: practicalDone,

        stepDone: stepDone,

        correct: correct,

        practicalPoints: practicalPoints,

        stepPoints: stepPoints,

        quizPoints: quizPoints,

      };

    }



    function renderPoints() {

      var points = computePoints();

      var total = $("pointsTotal");

      if (total) total.textContent = String(points.total);

      var fill = $("pointsFill");

      if (fill) {

        fill.style.width = Math.min(100, Math.round((points.total / CERT_THRESHOLD) * 100)) + "%";

      }

      var label = $("pointsLabel");

      if (label) label.textContent = points.total + " / " + CERT_THRESHOLD;

      var kv = $("kvPoints");

      if (kv) kv.textContent = String(points.total);



      var breakdown = clear($("pointsBreakdown"));

      if (breakdown) {

        [

          ["培训路线步骤 ×" + points.stepDone, "+" + points.stepPoints],

          ["测验答对 ×" + points.correct, "+" + points.quizPoints],

          ["班前自检 ×" + points.practicalDone, "+" + points.practicalPoints],

        ].forEach(function (row) {

          var line = make("div");

          line.appendChild(make("span", "pb-label", row[0]));

          line.appendChild(make("span", "pb-value", row[1]));

          breakdown.appendChild(line);

        });

      }

      var hint = $("pointsHint");

      if (hint) {

        hint.textContent = points.total >= CERT_THRESHOLD

          ? "已达到生成条件，可以生成培训记录单并打印或存为 PDF。"

          : ("还差 " + (CERT_THRESHOLD - points.total) + " 分可以生成培训记录单。");

      }

      var button = $("certificateButton");

      if (button) button.disabled = points.total < CERT_THRESHOLD;

    }



    function certId(seed) {

      var text = String(seed || "") + "|" + new Date().toISOString().slice(0, 10);

      var hash = 0;

      for (var i = 0; i < text.length; i += 1) {

        hash = (hash * 31 + text.charCodeAt(i)) % 1000000007;

      }

      return "SITESAHA-" + String(hash).padStart(9, "0");

    }



    function buildCertificate() {

      var host = clear($("certificateArea"));

      if (!host) return;

      var points = computePoints();

      if (points.total < CERT_THRESHOLD) {

        host.hidden = false;

        host.appendChild(make("p", "empty-state", "积分不足，暂时不能生成记录单。"));

        return;

      }

      var role = currentRole() || "未选择工种";

      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);

      var steps = readStore("sitesaha-steps-v1", {});

      var now = new Date();

      var dateText = now.getFullYear() + "-"

        + String(now.getMonth() + 1).padStart(2, "0") + "-"

        + String(now.getDate()).padStart(2, "0");



      var card = make("div", "certificate");

      card.appendChild(make("div", "cert-kicker", "SITESAHA AI · NEW WORKER SAFETY TRAINING"));

      card.appendChild(make("h3", "cert-title", "新工人安全培训学习记录单"));

      card.appendChild(make("p", "cert-sub",

        "本记录单由筑安智培学习模块根据本机学习行为自动生成，用于班组培训留痕与自我检查。"));



      var rule = make("div", "cert-rule");

      card.appendChild(rule);



      var grid = make("dl", "cert-grid");

      [

        ["工种", role],

        ["累计学习积分", String(points.total) + " / " + CERT_THRESHOLD],

        ["测验最好成绩", (quiz.bestCorrect || 0) + " / " + (quiz.total || 20) + " 题"],

        ["培训路线完成", points.stepDone + " / " + ((trainingData.training_steps || []).length || 5) + " 步"],

        ["班前自检完成", points.practicalDone + " / " + PRACTICAL_ITEMS.length + " 项"],

        ["生成日期", dateText],

        ["记录单编号", certId(role + "|" + points.total)],

        ["学习平台", "筑安智培（SiteSaha AI）V15.0.0"],

      ].forEach(function (row) {

        var line = make("div");

        line.appendChild(make("dt", "", row[0]));

        line.appendChild(make("dd", "", row[1]));

        grid.appendChild(line);

      });

      card.appendChild(grid);



      var stepBox = make("div", "cert-steps");

      (trainingData.training_steps || []).forEach(function (step) {

        var row = make("div");

        var ok = Boolean(steps[step.order]);

        row.appendChild(make("span", ok ? "tick" : "untick"));

        row.appendChild(make("span", "", "第 " + step.order + " 步 · " + step.title + "（" + (step.duration || "") + "）"));

        stepBox.appendChild(row);

      });

      card.appendChild(stepBox);



      var sign = make("div", "cert-sign");

      sign.appendChild(make("div", "", "本人签名 / 日期"));

      sign.appendChild(make("div", "", "班组长或安全员确认 / 日期"));

      card.appendChild(sign);



      card.appendChild(make("div", "cert-foot",

        "说明：本记录单只反映在本机浏览器中完成的学习行为，不能替代项目三级安全教育、"

        + "安全技术交底、特种作业持证要求和现场安全员检查，也不作为上岗资格或考核合格证明。"

        + "积分与进度仅保存在本机，未上传服务端。"));



      host.hidden = false;

      host.appendChild(card);

    }



    bindClick("certificateButton", function () {

      buildCertificate();

      var printButton = $("certificatePrint");

      if (printButton) printButton.hidden = false;

      var area = $("certificateArea");

      if (area) area.scrollIntoView({ behavior: "smooth", block: "start" });

    });

    bindClick("certificatePrint", function () { window.print(); });

    bindClick("pointsReset", function () {

      writeStore(QUIZ_KEY, EMPTY_QUIZ);

      writeStore("sitesaha-steps-v1", {});

      writeStore(PRACTICAL_KEY, {});

      var area = clear($("certificateArea"));

      if (area) area.hidden = true;

      var printButton = $("certificatePrint");

      if (printButton) printButton.hidden = true;

      renderSteps();

      renderPractical();

      renderHomeQuiz();

      renderPoints();

    });



    /* 把 > 标准状态：现行 之类的引用行渲染成徽标 */

    function referenceLine(line) {

      var text = String(line || "");

      if (text.charAt(0) === ">") {

        text = text.slice(1);

        while (text.charAt(0) === " ") text = text.slice(1);

      }

      var index = text.indexOf("：");

      if (index <= 0) return null;

      return { label: text.slice(0, index), value: text.slice(index + 1) };

    }



    /* 关键词高亮：用 textContent + <mark> 构造，不注入任何 HTML */

    function appendHighlighted(node, text, keyword) {

      var source = String(text === null || text === undefined ? "" : text);

      var term = String(keyword || "").trim();

      if (!term) {

        node.appendChild(document.createTextNode(source));

        return;

      }

      var lowerSource = source.toLowerCase();

      var lowerTerm = term.toLowerCase();

      var cursor = 0;

      var guard = 0;

      while (cursor < source.length && guard < 200) {

        guard += 1;

        var hit = lowerSource.indexOf(lowerTerm, cursor);

        if (hit < 0) break;

        if (hit > cursor) node.appendChild(document.createTextNode(source.slice(cursor, hit)));

        node.appendChild(make("mark", "hit", source.slice(hit, hit + term.length)));

        cursor = hit + term.length;

      }

      if (cursor < source.length) node.appendChild(document.createTextNode(source.slice(cursor)));

    }



    var allDocuments = [];

    var activeDocCategory = "";



    function renderDocFilters() {

      var host = clear($("docFilterRow"));

      if (!host) return;

      var counts = {};

      allDocuments.forEach(function (document) {

        var name = document.category || "未分类";

        counts[name] = (counts[name] || 0) + 1;

      });

      var names = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });

      var options = [{ label: "全部（" + allDocuments.length + "）", value: "" }];

      names.forEach(function (name) {

        options.push({ label: name + "（" + counts[name] + "）", value: name });

      });

      options.forEach(function (option) {

        var chip = make("button", "filter-chip" + (option.value === activeDocCategory ? " active" : ""), option.label);

        chip.type = "button";

        chip.addEventListener("click", function () {

          activeDocCategory = option.value;

          renderDocFilters();

          renderDocumentGroups();

        });

        host.appendChild(chip);

      });

    }



    function renderDocumentGroups() {

      var groupHost = clear($("docGroups"));

      var sideHost = clear($("sideDocuments"));

      if (!groupHost || !sideHost) return;

      groupHost.setAttribute("aria-busy", "false");



      var keyword = ($("docSearch") || {}).value || "";

      var term = keyword.trim().toLowerCase();

      var matched = allDocuments.filter(function (document) {

        var category = document.category || "未分类";

        if (activeDocCategory && category !== activeDocCategory) return false;

        if (!term) return true;

        var haystack = [document.title, document.source, document.category, document.version]

          .join(" ").toLowerCase();

        return haystack.indexOf(term) >= 0;

      });



      var line = clear($("docCountLine"));

      if (line) {

        line.appendChild(document.createTextNode("匹配 "));

        line.appendChild(make("b", "", String(matched.length)));

        line.appendChild(document.createTextNode(" / 共 " + allDocuments.length + " 篇"));

        if (term) line.appendChild(document.createTextNode(" · 关键词「" + keyword.trim() + "」"));

      }



      if (!matched.length) {

        groupHost.appendChild(make("p", "empty-state", "没有匹配的文档。换个关键词或点“全部”。"));

        renderSideDocuments(allDocuments);

        return;

      }



      var groups = {};

      matched.forEach(function (document) {

        var name = document.category || "未分类";

        if (!groups[name]) groups[name] = [];

        groups[name].push(document);

      });

      Object.keys(groups)

        .sort(function (a, b) { return groups[b].length - groups[a].length; })

        .forEach(function (name) {

          var group = make("section", "doc-group");

          var head = make("h3");

          var title = make("span");

          appendHighlighted(title, name, keyword.trim());

          head.appendChild(title);

          head.appendChild(make("span", "count-badge", groups[name].length + " 篇"));

          group.appendChild(head);



          var list = make("ul", "document-list");

          groups[name].forEach(function (document) {

            var li = make("li");

            var strong = make("strong");

            appendHighlighted(strong, document.title || "", keyword.trim());

            li.appendChild(strong);

            var meta = make("div", "source-meta");

            appendHighlighted(meta, (document.source || "未标注来源")

              + (document.version ? " · " + document.version : "")

              + " · " + (document.chunk_count || 0) + " 个片段", keyword.trim());

            li.appendChild(meta);

            list.appendChild(li);

          });

          group.appendChild(list);

          groupHost.appendChild(group);

        });



      renderSideDocuments(allDocuments);

      var note = $("libraryNote");

      if (note) note.textContent = "共 " + allDocuments.length + " 篇 · " + Object.keys(groups).length + " 个类别匹配";

    }



    function renderSideDocuments(documents) {

      var sideHost = clear($("sideDocuments"));

      if (!sideHost) return;

      var key = ($("docSearch") || {}).value || "";

      (documents || []).slice(0, 10).forEach(function (document) {

        var li = make("li");

        var strong = make("strong");

        appendHighlighted(strong, document.title || "", key.trim());

        li.appendChild(strong);

        li.appendChild(make("div", "source-meta",

          (document.category || "未分类") + " · " + (document.chunk_count || 0) + " 个片段"));

        sideHost.appendChild(li);

      });

      if ((documents || []).length > 10) {

        sideHost.appendChild(make("li", "source-meta",

          "另有 " + (documents.length - 10) + " 篇，请在“知识库”模块查看"));

      }

    }



    function renderDocuments(documents, categories) {

      allDocuments = documents || [];

      renderDocFilters();

      renderDocumentGroups();

      renderDomainDistribution(documents);

    }



    /* 标准现行状态表（数据来自 /api/standards；接口不可用时降级为提示） */

    var allStandards = [];



    function statusClass(status) {

      if (status === "现行") return "active";

      if (status === "即将实施") return "pending";

      return "unknown";

    }



    function renderStandardsTable() {

      var host = clear($("standardsTable"));

      if (!host) return;

      host.setAttribute("aria-busy", "false");

      var keyword = (($("standardsSearch") || {}).value || "").trim();

      var term = keyword.toLowerCase();

      var items = allStandards.filter(function (item) {

        if (!term) return true;

        return [item.code, item.title, item.status, item.type]

          .join(" ").toLowerCase().indexOf(term) >= 0;

      });

      var note = $("standardsNote");

      if (note) {

        note.textContent = allStandards.length

          ? ("匹配 " + items.length + " / 共 " + allStandards.length + " 部")

          : "无标准数据";

      }

      if (!allStandards.length) {

        host.appendChild(make("p", "empty-state",

          "暂时没有读到标准元数据。可运行 scripts/fetch_public_standards.py 采集后重建索引。"));

        return;

      }

      if (!items.length) {

        host.appendChild(make("p", "empty-state", "没有匹配的标准，换个编号或关键词试试。"));

        return;

      }

      var wrap = make("div", "table-wrap");

      var table = make("table");

      var caption = make("caption", "", "共 " + items.length + " 部标准 · 只登记公开元数据，不包含受限全文");

      table.appendChild(caption);

      var thead = make("thead");

      var headRow = make("tr");

      ["标准编号", "名称", "状态", "实施日期", "官方入口"].forEach(function (label) {

        headRow.appendChild(make("th", "", label));

      });

      thead.appendChild(headRow);

      table.appendChild(thead);

      var tbody = make("tbody");

      items.forEach(function (item) {

        var row = make("tr");

        var codeCell = make("td");

        codeCell.setAttribute("data-label", "标准编号");

        appendHighlighted(codeCell, item.code || "", keyword);

        row.appendChild(codeCell);

        var titleCell = make("td");

        titleCell.setAttribute("data-label", "名称");

        appendHighlighted(titleCell, item.title || "", keyword);

        row.appendChild(titleCell);

        var statusCell = make("td");

        statusCell.setAttribute("data-label", "状态");

        statusCell.appendChild(make("span", "std-status " + statusClass(item.status), item.status || "未知"));

        row.appendChild(statusCell);

        var dateCell = make("td");

        dateCell.setAttribute("data-label", "实施日期");

        dateCell.textContent = item.implemented || "—";

        row.appendChild(dateCell);

        var linkCell = make("td");

        linkCell.setAttribute("data-label", "官方入口");

        if (item.source_url) {

          var link = make("a", "", "官方详情");

          link.setAttribute("href", item.source_url);

          link.setAttribute("target", "_blank");

          link.setAttribute("rel", "noopener noreferrer");

          linkCell.appendChild(link);

        } else {

          linkCell.textContent = "—";

        }

        row.appendChild(linkCell);

        tbody.appendChild(row);

      });

      table.appendChild(tbody);

      wrap.appendChild(table);

      host.appendChild(wrap);

    }



    async function loadStandards() {

      try {

        var data = await getJson("/api/standards");

        allStandards = data.items || [];

        var counts = data.counts || {};

        var note = $("standardsNote");

        if (note && allStandards.length) {

          note.textContent = "共 " + (counts.total || allStandards.length) + " 部 · 现行 "

            + (counts.active || 0) + " · 即将实施 " + (counts.pending || 0);

        }

      } catch (error) {

        allStandards = [];

      }

      renderStandardsTable();

    }



    bindClick("docSearchClear", function () {

      var input = $("docSearch");

      if (input) input.value = "";

      renderDocumentGroups();

    });

    bindClick("standardsSearchClear", function () {

      var input = $("standardsSearch");

      if (input) input.value = "";

      renderStandardsTable();

    });

    var docSearchInput = $("docSearch");

    if (docSearchInput) {

      docSearchInput.addEventListener("input", function () { renderDocumentGroups(); });

    }

    var standardsSearchInput = $("standardsSearch");

    if (standardsSearchInput) {

      standardsSearchInput.addEventListener("input", function () { renderStandardsTable(); });

    }



    async function loadStatus() {

      try {

        var data = await getJson("/api/status");

        var model = data.model || {};

        var stats = data.stats || {};

        var documents = data.documents || [];



        var pill = $("modelStatus");

        /* 语义修正（§5 第 5 条）：这不是功能标签，而是模型没连上的降级状态。
           模型可用时退场，不占位；不可用时说清影响与下一步。 */

        if (model.available) {

          pill.hidden = true;

          pill.textContent = "";

          pill.classList.remove("offline");

        } else {

          pill.hidden = false;

          pill.textContent = "未连接模型 · 当前为检索摘要";

          pill.classList.add("offline");

          pill.title = (model.detail || "未配置模型服务地址")

            + "；检索摘要仍可用，成段解释需管理员配置 SITESHAHA_LLM_*";

        }




        var categories = {};

        documents.forEach(function (document) {

          var name = document.category || "未分类";

          categories[name] = (categories[name] || 0) + (document.chunk_count || 0);

        });



        var kpiDocs = $("kpiDocs");

        if (kpiDocs) kpiDocs.textContent = stats.documents || documents.length || 0;

        var kpiChunks = $("kpiChunks");

        if (kpiChunks) kpiChunks.textContent = stats.chunks || 0;

        var note = $("kpiChunksNote");

        if (note) note.textContent = (Object.keys(categories).length || 0) + " 个类别 · 全文索引可用";

        var docNote = $("kpiDocsNote");

        if (docNote && Object.keys(categories).length) {

          docNote.textContent = Object.keys(categories).slice(0, 3).join(" / ");

        }



        var documentCount = $("documentCount");

        if (documentCount) documentCount.textContent = stats.documents || documents.length || 0;

        var chunkCount = $("chunkCount");

        if (chunkCount) chunkCount.textContent = stats.chunks || 0;

        var kbNote = $("kbNote");

        if (kbNote) {

          kbNote.textContent = model.available

            ? "在线模型已连接，回答由模型结合检索结果生成。"

            : "未连接在线模型，当前返回检索摘要与规范依据。";

        }

        var kvMode = $("kvMode");

        if (kvMode) kvMode.textContent = model.available ? "在线大模型" : "离线检索";

        var kvVision = $("kvVision");

        if (kvVision) kvVision.textContent = data.vision_configured ? "已配置" : "未配置";

        var visionNote = $("visionNote");

        if (visionNote && !data.vision_configured) {

          visionNote.hidden = false;

          visionNote.textContent = "提示：服务端未配置视觉模型，照片入口会返回明确的未配置说明，文字问答不受影响。";

        }



        var kvAsr = $("kvAsr");

        if (kvAsr) kvAsr.textContent = data.asr_configured ? "已配置" : "未配置";

        serverAsrReady = Boolean(data.asr_configured);

        resetRecordUi();

        if (serverAsrReady) {

          setVoiceHint("服务端语音识别已就绪：点“录音提问”，说完点“停止并识别”。");

        } else if (browserRecognition) {

          setVoiceHint("服务端未配置语音识别，已降级为浏览器识别（需要 Chrome / Edge 且能连上语音服务）。");

        } else {

          setVoiceHint("当前没有可用的语音通道，请直接键盘输入。");

        }



        renderDocuments(documents, categories);

      } catch (error) {

        var pill = $("modelStatus");

        if (pill) { pill.textContent = "服务状态读取失败"; pill.classList.add("offline"); }

        var host = clear($("sideDomains"));

        if (host) host.appendChild(make("li", "", "分类统计读取失败"));

      }

    }



    var modelCommand = $("modelCommand");

    if (modelCommand) {

      modelCommand.textContent = [

        '$env:SITESHAHA_LLM_MODE="on"',

        '$env:SITESHAHA_LLM_BASE_URL="https://api.deepseek.com/v1"',

        '$env:SITESHAHA_LLM_MODEL="deepseek-chat"',

        "python webapp.py",

      ].join(String.fromCharCode(10));

    }



    /* ==================================================================

       16. 初始化

       ================================================================== */

    async function init() {

      renderPractical();

      renderQuickQuestions();

      renderRoleChips();

      renderRoleDetail();

      renderProfileMeta();

      renderEmergencyGrid();

      renderDailyCase();

      initPrePanels();

      renderHomeQuiz();

      showEmergencyGuide("受伤");



      try {

        trainingData = await getJson("/api/training");

      } catch (error) {

        trainingData = { roles: [], worker_roles: {}, questions: [], quiz: {}, training_steps: [] };

      }

      renderRoleChips();

      renderRoleDetail();

      renderProfileMeta();

      renderQuickQuestions();

      renderSteps();

      renderHomeQuiz();



      var roleCount = $("roleCount");

      if (roleCount) roleCount.textContent = (trainingData.roles || []).length;



      await loadStatus();

      await loadStandards();

      var cases = await loadCases("");

      var kpiCases = $("kpiCases");

      if (kpiCases) kpiCases.textContent = cases.length;

      var caseCount = $("caseCount");

      if (caseCount) caseCount.textContent = cases.length;



      /* 清单由 initPrePanels 生成 */

      var kvAccess = $("kvAccess");

      if (kvAccess) kvAccess.textContent = accessCode() ? "已输入访问码" : "未启用或未输入";

    }



    init();

    /* ==================================================================
       主题切换按钮：上色逻辑在 <head> 的 theme_boot.js 里（避免闪白），
       这里只负责把点击接到切换函数上。
       ================================================================== */
    function initTheme() {
      var api = window.__sitesahaTheme;
      if (!api) return;
      api.paint(api.preferred());
      bindClick("themeToggle", function () { api.toggle(); });
    }

    initTheme();

  })();

  </script>

</body>

</html>"""





_TIMING_RING = 200          # 每个路由保留的最近样本数
_timing_lock = threading.Lock()
_timings: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_TIMING_RING))


def _probe_png() -> bytes:
    """生成一张 8x8 的合法 PNG，用作视觉服务连通性探针。

    手写 PNG 结构，不读磁盘、不依赖 Pillow —— 保证离线与零依赖。
    """
    import struct
    import zlib

    width = height = 8
    row = b"\x00" + b"\x80\x90\xa0" * width
    raw = row * height

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _probe_wav(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """生成一小段静音 WAV，用作语音服务连通性探针。"""
    import struct

    data = b"\x00\x00" * int(seconds * sample_rate)
    header = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
              + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate,
                                      sample_rate * 2, 2, 16)
              + b"data" + struct.pack("<I", len(data)))
    return header + data


def record_timing(path: str, started: float, status_code: int) -> None:
    """记录一次请求耗时（秒）。

    为什么需要：craft-guard 的 PERF-01 要求把等待反馈按 <300ms / 300ms–2s /
    >2s / >10s 四档核对，而这需要真实的 P50/P95 —— 没有测量就没法判定该不该出骨架屏。
    """
    elapsed = time.perf_counter() - started
    key = f"{path} {status_code}"
    with _timing_lock:
        _timings[key].append(elapsed)


def timing_snapshot() -> dict[str, Any]:
    """返回各路由的耗时分布，供 /api/timings 与本机自检脚本使用。"""

    def percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, int(round(ratio * (len(ordered) - 1))))
        return ordered[index]

    with _timing_lock:
        rows = {key: list(samples) for key, samples in _timings.items()}

    out: dict[str, Any] = {}
    for key, samples in sorted(rows.items()):
        out[key] = {
            "count": len(samples),
            "p50_ms": round(percentile(samples, 0.50) * 1000, 1),
            "p95_ms": round(percentile(samples, 0.95) * 1000, 1),
            "max_ms": round(max(samples) * 1000, 1),
        }
    return out


def timing_tier(p95_ms: float) -> str:
    """把耗时映射到 craft-guard 的等待反馈档位。"""
    if p95_ms < 300:
        return "no-indicator"      # < 300ms：不出指示器
    if p95_ms <= 2000:
        return "skeleton"          # 300ms–2s：骨架屏，布局稳定
    if p95_ms <= 10000:
        return "loader"            # > 2s：加载器 + 说明在做什么
    return "timeout"               # > 10s：超时 + 重试或取消


@dataclass(slots=True)
class Services:

    config: AppConfig

    kb: KnowledgeBase

    engine: RAGEngine





def build_services() -> Services:

    config = AppConfig.from_env()

    kb = KnowledgeBase(config.db_path)

    seed_default_knowledge(

        kb,

        config.knowledge_dir,

        normalized_sources_dir=config.normalized_sources_dir,

    )

    return Services(config=config, kb=kb, engine=RAGEngine(kb, config))





def image_geometry(data: bytes) -> tuple[int, int, str]:
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
    if data[:8] == b"\x89PNG\r\n\x1a\n":
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
    if data[:2] == b"\xff\xd8":
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


def answer_payload(question: str, answer: Answer) -> dict[str, Any]:

    return {

        "question": question,

        "text": answer.text,

        "mode": answer.mode,

        "warnings": answer.warnings,

        "sources": [asdict(source) for source in answer.sources],

        "related_cases": find_cases(question)[:3],

    }






def summary_text(question: str, sources: list[Any]) -> str:
    """把检索结果拼成一段可读摘要（模型不可用时的兜底）。

    依据 §3.2：/api/status 已有"未配置模型服务地址，当前使用检索摘要"的能力，
    这里复用它，保证任何情况下用户都能拿到有用的东西。
    """
    if not sources:
        return (
            "当前未连接文字模型，知识库里也没有检索到相关条目。\n"
            "可以把问题换个说法再问，或联系现场安全员确认。"
        )
    lines = ["当前未连接文字模型，下面是知识库里与你的问题最相关的条目：", ""]
    for index, source in enumerate(sources[:4], 1):
        title = getattr(source, "title", "") or "未命名"
        heading = getattr(source, "heading", "")
        content = (getattr(source, "content", "") or "").strip().replace("\n", " ")
        lines.append(f"[{index}] {title}" + (f" / {heading}" if heading else ""))
        if content:
            lines.append("    " + content[:180])
        lines.append("")
    lines.append("需要成段的解释时，请让管理员配置文字模型。")
    return "\n".join(lines)


class RequestThrottle:

    def __init__(self, limit_per_minute: int):

        self.limit = limit_per_minute

        self._requests: dict[str, deque[float]] = defaultdict(deque)

        self._lock = threading.Lock()



    def allow(self, client: str) -> bool:

        if self.limit <= 0:

            return True

        now = time.monotonic()

        cutoff = now - 60

        with self._lock:

            timestamps = self._requests[client]

            while timestamps and timestamps[0] < cutoff:

                timestamps.popleft()

            if len(timestamps) >= self.limit:

                return False

            timestamps.append(now)

            return True





class SiteSahaHandler(BaseHTTPRequestHandler):

    server_version = f"SiteSahaAI/{APP_VERSION}"

    protocol_version = "HTTP/1.1"



    def setup(self) -> None:

        super().setup()

        self.connection.settimeout(

            self.server.services.config.request_timeout_seconds  # type: ignore[attr-defined]

        )



    @property

    def services(self) -> Services:

        return self.server.services  # type: ignore[attr-defined]



    def _add_common_headers(self) -> None:

        self.send_header("X-Content-Type-Options", "nosniff")

        self.send_header("X-Frame-Options", "DENY")

        self.send_header("Referrer-Policy", "no-referrer")

        self.send_header("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")

        self.send_header("Cross-Origin-Opener-Policy", "same-origin")

        self.send_header(

            "Content-Security-Policy",

            "default-src 'self'; script-src 'self' 'unsafe-inline'; "

            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "

            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",

        )

        self.send_header("X-Robots-Tag", "noindex, nofollow")



    def _write_json(

        self,

        payload: Any,

        status: HTTPStatus = HTTPStatus.OK,

        extra_headers: dict[str, str] | None = None,

    ) -> None:

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)

        for name, value in (extra_headers or {}).items():

            self.send_header(name, value)

        self.send_header("Content-Type", "application/json; charset=utf-8")

        self.send_header("Content-Length", str(len(body)))

        self.send_header("Cache-Control", "no-store")

        self._add_common_headers()

        self.end_headers()

        self.wfile.write(body)

        # 计时埋点：所有 JSON 响应都经过这里，一个点就够，不必改路由
        record_timing(self._timing_path or self.path, self._request_started, int(status))



    def _handle_selftest(self) -> None:
        """POST /api/selftest —— 三个模型服务的配置与连通性自检。

        为什么需要：视觉与语音"配了但用不了"的情况（余额不足、密钥无效、
        模型名不对）只有在真正调用时才会暴露。这个接口把三态与**服务商原始
        错误**一次性回显给管理员，前端据此在点击前就给出明确状态。

        body: {"probe": true|false}  probe=true 时对每个已配置服务发一次真实请求。
        """
        import json as _json

        payload: dict = {}
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 0:
                body = self.rfile.read(length)
                parsed = _json.loads(body.decode("utf-8") or "{}")
                if isinstance(parsed, dict):
                    payload = parsed
        except (ValueError, _json.JSONDecodeError):
            payload = {}

        # 两种触发方式：POST body {"probe": true}，或 GET 的 ?probe=1
        query = urllib.parse.urlparse(self.path).query
        want_probe = bool(payload.get("probe")) or ("probe=1" in (query or ""))
        config = self.services.config
        model = getattr(self.services.engine, "model", None)
        report: dict[str, Any] = {
            "schema": "sitesaha-selftest/v1",
            "probe": want_probe,
            "services": {},
        }

        def record(name: str, configured: bool, detail: str) -> dict[str, Any]:
            entry = {"configured": configured, "ok": None, "detail": detail}
            report["services"][name] = entry
            return entry

        # ---- 生成模型 ----
        llm = record("llm", bool(config.model_configured),
                     f"模式 {config.llm_mode} · 模型 {config.llm_model or '未设置'}")
        # ---- 视觉 ----
        vision = record("vision", bool(config.vision_configured),
                        f"模型 {config.vision_model or '未设置'} · 接口风格 {config.vision_api_style}")
        # ---- 语音 ----
        asr = record("asr", bool(config.asr_configured),
                     f"模型 {config.asr_model or '未设置'} · 端点 {config.asr_endpoint_path}")

        if want_probe and model is not None:
            if llm["configured"]:
                try:
                    model.generate("自检：请回复两个字以内的确认。", [], mode="自检")
                    llm["ok"] = True
                    llm["detail"] += " · 实测通过"
                except ProviderError as exc:
                    llm["ok"] = False
                    llm["error_code"] = exc.code
                    llm["detail"] = exc.message
                    if exc.hint:
                        llm["hint"] = exc.hint
                    if exc.raw:
                        llm["upstream_message"] = exc.raw[:300]
                except Exception as exc:  # noqa: BLE001
                    llm["ok"] = False
                    llm["detail"] = f"实测异常：{type(exc).__name__}"

            if vision["configured"]:
                try:
                    model.inspect_image(_probe_png(), "image/png", "自检", [])
                    vision["ok"] = True
                    vision["detail"] += " · 实测通过"
                except ProviderError as exc:
                    vision["ok"] = False
                    vision["error_code"] = exc.code
                    vision["detail"] = exc.message
                    if exc.hint:
                        vision["hint"] = exc.hint
                    if exc.raw:
                        vision["upstream_message"] = exc.raw[:300]
                except Exception as exc:  # noqa: BLE001
                    vision["ok"] = False
                    vision["detail"] = f"实测异常：{type(exc).__name__}"

            if asr["configured"]:
                try:
                    model.transcribe_audio(_probe_wav(), mime_type="audio/wav",
                                           filename="selftest.wav")
                    asr["ok"] = True
                    asr["detail"] += " · 实测通过"
                except ProviderError as exc:
                    # 静音音频识别不出文字属正常，说明服务其实是通的
                    if exc.code == "audio_no_text":
                        asr["ok"] = True
                        asr["detail"] += " · 实测连通（静音探针无文字属正常）"
                    else:
                        asr["ok"] = False
                        asr["error_code"] = exc.code
                        asr["detail"] = exc.message
                        if exc.hint:
                            asr["hint"] = exc.hint
                        if exc.raw:
                            asr["upstream_message"] = exc.raw[:300]
                except Exception as exc:  # noqa: BLE001
                    asr["ok"] = False
                    asr["detail"] = f"实测异常：{type(exc).__name__}"

        self._write_json(report)

    def _answer_or_summary(
        self, question: str, worker_role: str = "", training_context: str = ""
    ) -> dict[str, Any]:
        """调模型生成回答；模型不可用时退回检索摘要，而不是抛异常给用户。"""
        engine = self.services.engine
        try:
            answer = engine.answer(
                question, worker_role=worker_role, training_context=training_context
            )
            return answer_payload(question, answer)
        except ProviderError as exc:
            summary = engine.retrieve(question)
            payload = answer_payload(
                question,
                Answer(
                    text=summary_text(question, summary),
                    mode="retrieve-only",
                    warnings=[exc.message + (" " + exc.hint if exc.hint else "")],
                    sources=summary,
                ),
            )
            payload["error_code"] = exc.code
            payload["degraded"] = True
            return payload
        except (RuntimeError, ValueError) as exc:
            summary = engine.retrieve(question)
            payload = answer_payload(
                question,
                Answer(
                    text=summary_text(question, summary),
                    mode="retrieve-only",
                    warnings=["模型暂时不可用，下面是知识库里的相关条目。"],
                    sources=summary,
                ),
            )
            payload["error_code"] = "model_unavailable"
            payload["degraded"] = True
            payload["hint"] = "联系管理员配置 SITESHAHA_LLM_*；在此之前检索摘要仍可用。"
            payload["detail"] = type(exc).__name__
            return payload

    def _write_provider_error(self, exc: ProviderError) -> None:
        """把服务商错误映射成可操作的 HTTP 响应。

        关键点：不再让 RuntimeError 原文冒到 500，用户看到的应该是
        中文说明 + 下一步动作 + 错误码（便于管理员定位）。
        """
        status = {
            "provider_unauthorized": HTTPStatus.BAD_GATEWAY,
            "provider_insufficient_balance": HTTPStatus.SERVICE_UNAVAILABLE,
            "provider_forbidden": HTTPStatus.BAD_GATEWAY,
            "provider_model_missing": HTTPStatus.BAD_GATEWAY,
            "provider_rate_limited": HTTPStatus.TOO_MANY_REQUESTS,
            "provider_payload_too_large": HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "vision_not_configured": HTTPStatus.SERVICE_UNAVAILABLE,
            "asr_not_configured": HTTPStatus.SERVICE_UNAVAILABLE,
            "audio_empty": HTTPStatus.BAD_REQUEST,
            "audio_no_text": HTTPStatus.UNPROCESSABLE_ENTITY,
        }.get(exc.code, HTTPStatus.BAD_GATEWAY)
        self._write_json(exc.as_payload(), status)

    def _start_timing(self) -> str:
        """在请求入口调用：记录起点并返回归一化后的路径（去掉查询串）。"""
        self._request_started = time.perf_counter()
        self._timing_path = urlparse(self.path).path
        return self._timing_path

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))

        if length > 1_000_000:

            raise ValueError("请求体过大")

        raw = self.rfile.read(length)

        if not raw:

            return {}

        payload = json.loads(raw.decode("utf-8"))

        if not isinstance(payload, dict):

            raise ValueError("请求格式应为 JSON 对象")

        return payload



    @staticmethod

    def _parse_multipart(content_type: str, raw: bytes) -> Any:

        """解析 multipart/form-data 请求体。



        顶层 BytesParser 返回的是 EmailMessage，它没有 get_name()/get_filename()，

        只有迭代出来的 MIMEPart 才有。这里统一在迭代结果上做字段读取。

        """

        return BytesParser(policy=policy.default).parsebytes(

            (f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode() + raw

        )



    @classmethod

    def _iter_parts(cls, msg: Any) -> list[Any]:

        """取出真正的 multipart 表单字段。



        实测（CPython 3.12）：BytesParser 解析出的顶层是 EmailMessage，

        Message.iter_parts() 在这里返回空序列；get_payload() 才是可靠来源。

        每个 part 也是 EmailMessage 而非 MIMEPart —— 因此**没有**

        get_name()/get_filename()（那两个便捷方法要 3.13+ 才有），

        字段名必须从 Content-Disposition 头里解析。

        """

        payload = msg.get_payload()

        if not isinstance(payload, list):

            return []

        return [

            part

            for part in payload

            if hasattr(part, "get_content_type") and hasattr(part, "get_payload")

        ]



    @staticmethod

    def _part_param(part: Any, param: str) -> str:

        """从 Content-Disposition 头里取 name / filename 参数。"""

        header = part.get("Content-Disposition") if hasattr(part, "get") else None

        if not header:

            return ""

        value = part.get_param(param, header="content-disposition")

        if isinstance(value, tuple):

            value = value[2] if len(value) > 2 else ""

        return str(value or "").strip()



    @classmethod

    def _find_part(cls, msg: Any, names: tuple[str, ...]) -> Any:

        for part in cls._iter_parts(msg):

            if cls._part_param(part, "name") in names:

                return part

        return None



    def do_GET(self) -> None:

        path = self._start_timing()

        if path in {"/", "/index.html"}:

            body = INDEX_HTML.encode("utf-8")

            self.send_response(HTTPStatus.OK)

            self.send_header("Content-Type", "text/html; charset=utf-8")

            self.send_header("Content-Length", str(len(body)))

            self.send_header("Cache-Control", "no-cache")

            self._add_common_headers()

            self.end_headers()

            self.wfile.write(body)

            return



        if path == "/api/status":

            model = self.services.engine.model.status()

            documents = [

                asdict(document) for document in self.services.kb.list_documents()

            ]

            self._write_json(

                {

                    "stats": self.services.kb.stats(),

                    "model": asdict(model),

                    "documents": documents,

                    "vision_configured": self.services.config.vision_configured,

                    "asr_configured": self.services.config.asr_configured,

                    # 为什么某项不可用 —— 让「静默关闭」可诊断
                    "model_reason": self.services.config.unavailable_reason("model"),

                    "vision_reason": self.services.config.unavailable_reason("vision"),

                }

            )

            return



        if path == "/api/cases":

            query = urlparse(self.path).query

            from urllib.parse import parse_qs

            q = parse_qs(query).get("q", [""])[0]

            self._write_json({"cases": find_cases(q)})

            return



        if path == "/api/checklists":

            self._write_json(

                {

                    "priority_checks": PRIORITY_START_CHECKS,

                    "categories": INSPECTION_CATEGORIES,

                }

            )

            return



        if path == "/api/checklists/conditions":

            self._write_json(

                {

                    "weather": checklists_mod.WEATHER_CONDITIONS,

                    "work": checklists_mod.WORK_CONDITIONS,

                }

            )

            return


        if path == "/api/training":

            self._write_json(training_payload())

            return



        if path == "/api/standards":

            self._write_json(load_standards(self.services.config.project_root))

            return



        if path == "/api/timings":

            self._write_json(
                {"schema": "sitesaha-timings/v1", "routes": timing_snapshot()}
            )

            return



        if path == "/api/selftest":

            self._handle_selftest()

            return

        if path == "/healthz":

            self._write_json(

                {

                    "status": "ok",

                    "version": APP_VERSION,

                    "model_configured": self.services.config.model_configured,

                    "vision_configured": self.services.config.vision_configured,

                    "asr_configured": self.services.config.asr_configured,

                    # 为什么某项不可用 —— 让「静默关闭」可诊断
                    "model_reason": self.services.config.unavailable_reason("model"),

                    "vision_reason": self.services.config.unavailable_reason("vision"),

                }

            )

            return



        self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)



    def do_POST(self) -> None:

        path = self._start_timing()

        protected = path in {"/api/ask", "/api/inspect-image", "/api/transcribe"}

        semaphore_acquired = False

        if protected:

            client = self._client_identifier()

            throttle: RequestThrottle = self.server.throttle  # type: ignore[attr-defined]

            if not throttle.allow(client):

                self._write_json(

                    {"error": "请求过于频繁，请稍后再试"},

                    HTTPStatus.TOO_MANY_REQUESTS,

                    {"Retry-After": "60"},

                )

                return

            semaphore: threading.BoundedSemaphore = self.server.request_semaphore  # type: ignore[attr-defined]

            semaphore_acquired = semaphore.acquire(blocking=False)

            if not semaphore_acquired:

                self._write_json(

                    {"error": "当前使用人数较多，请稍后重试"},

                    HTTPStatus.TOO_MANY_REQUESTS,

                )

                return

        try:

            if path == "/api/ask":

                payload = self._read_json()

                supplied_code = str(payload.get("access_code", "")).strip()

                if not self._access_allowed(

                    self.headers.get("X-Access-Code", "") or supplied_code

                ):

                    self._write_json({"error": "访问码不正确"}, HTTPStatus.UNAUTHORIZED)

                    return

                question = str(payload.get("question", "")).strip()

                if not question:

                    self._write_json({"error": "question is required"}, HTTPStatus.BAD_REQUEST)

                    return

                worker_role = str(payload.get("worker_role", "") or "").strip()

                worker_role = worker_role if worker_role in WORKER_ROLES else ""

                training_context = build_training_context(worker_role)

                try:

                    response_payload = self._answer_or_summary(

                        question, worker_role, training_context

                    )

                except ProviderError as exc:

                    self._write_provider_error(exc)

                    return

                if worker_role:

                    response_payload["worker_role"] = worker_role

                self._write_json(response_payload)

                return



            if path == "/api/checklists/generate":

                payload = self._read_json()

                conditions = payload.get("conditions") or []

                if not isinstance(conditions, list):

                    self._write_json(

                        {

                            "error": "conditions 需要是数组。",

                            "error_code": "bad_request",

                            "hint": "例如 {\"conditions\": [\"hotwork\", \"heat\"]}",

                        },

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                self._write_json(checklists_mod.generate(conditions))

                return

            if path == "/api/checklists/import":

                content_type = self.headers.get("Content-Type", "")

                length = int(self.headers.get("Content-Length", "0"))

                if length <= 0:

                    self._write_json(

                        {"error": "没有收到文件内容。", "error_code": "empty_body"},

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                if length > 4 * 1024 * 1024:

                    self._write_json(

                        {

                            "error": "文件不能超过 4 MB。",

                            "error_code": "file_too_large",

                            "hint": "检查项清单通常很小；如果文件很大，先只保留需要的那部分。",

                        },

                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,

                    )

                    return

                raw = self.rfile.read(length)

                # 复用项目里的 multipart 解析（inspect-image 用的同一套），
                # 不能直接拿 body 当文件内容 —— filename 也在 body 里，不在头上。
                filename = ""

                payload = raw

                if "multipart/form-data" in content_type:

                    try:

                        parts = self._parse_multipart(content_type, raw)

                        part = self._find_part(parts, ("file", "upload", "data"))

                        if part is not None:

                            filename = str(self._part_param(part, "filename") or "")

                            payload = part.get_payload(decode=True) or b""

                    except Exception:  # noqa: BLE001

                        self._write_json(

                            {

                                "error": "文件内容解析失败，可能上传不完整。",

                                "error_code": "multipart_unreadable",

                                "hint": "重新选一次文件；如果仍然失败，改成 CSV 再试。",

                            },

                            HTTPStatus.BAD_REQUEST,

                        )

                        return

                is_xlsx = filename.lower().endswith(".xlsx") or payload[:2] == b"PK"

                try:

                    text = xlsx_to_text(payload) if is_xlsx else payload.decode("utf-8", "replace")

                except XlsxError as exc:

                    self._write_json(

                        {

                            "error": str(exc),

                            "error_code": "xlsx_unreadable",

                            "hint": "可以另存为 CSV 再导入，或者检查文件是否损坏。",

                        },

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                rows = checklists_mod.parse_delimited(text)

                result = checklists_mod.normalize_import(rows)

                result["filename"] = filename

                result["parsed"] = len(rows)

                self._write_json(result)

                return

            if path == "/api/inspect-image":

                content_type = self.headers.get("Content-Type", "")

                length = int(self.headers.get("Content-Length", "0"))

                if length <= 0:

                    self._write_json({"error": "图片为空"}, HTTPStatus.BAD_REQUEST)

                    return

                if length > self.services.config.max_image_bytes + 200_000:

                    # 先把请求体读掉再回复：否则连接会在客户端读响应前被重置
                    # （实测 9MB 上传时客户端拿到 ConnectionResetError 而不是 413）。
                    try:

                        remaining = length

                        while remaining > 0:

                            chunk = self.rfile.read(min(remaining, 256 * 1024))

                            if not chunk:

                                break

                            remaining -= len(chunk)

                    except OSError:

                        pass

                    limit_mb = self.services.config.max_image_bytes // (1024 * 1024)

                    self._write_json(

                        {

                            "error": f"图片不能超过 {limit_mb} MB",

                            "error_code": "image_too_large",

                            "hint": "请压缩后重试；手机拍照时可先用相册的裁剪功能改小再上传。",

                        },

                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,

                    )

                    return

                    self._write_json({"error": "图片为空或超过大小限制"}, HTTPStatus.BAD_REQUEST)

                    return

                raw = self.rfile.read(length)

                if "multipart/form-data" not in content_type:

                    self._write_json({"error": "需要 multipart/form-data 图片上传"}, HTTPStatus.BAD_REQUEST)

                    return

                msg = self._parse_multipart(content_type, raw)

                image_part = self._find_part(msg, ("image",))

                if image_part is None:

                    self._write_json({"error": "未找到 image 字段"}, HTTPStatus.BAD_REQUEST)

                    return

                image_bytes = image_part.get_payload(decode=True) or b""

                if len(image_bytes) > self.services.config.max_image_bytes:

                    self._write_json({"error": "图片不能超过 8 MB"}, HTTPStatus.BAD_REQUEST)

                    return

                mime_type = image_part.get_content_type()

                if mime_type not in {"image/jpeg", "image/png", "image/webp"}:

                    self._write_json({"error": "仅支持 JPG、PNG、WEBP"}, HTTPStatus.BAD_REQUEST)

                    return

                question = ""

                supplied_code = ""

                for part in self._iter_parts(msg):

                    field = self._part_param(part, "name")

                    if field == "question":

                        question = part.get_content().strip()

                    if field == "access_code":

                        supplied_code = part.get_content().strip()

                if not self._access_allowed(

                    self.headers.get("X-Access-Code", "") or supplied_code

                ):

                    self._write_json({"error": "访问码不正确"}, HTTPStatus.UNAUTHORIZED)

                    return

                if not self.services.config.vision_configured:

                    # 明确降级提示，而不是让前端看到 RuntimeError / HTTP 500

                    self._write_json(

                        {

                            "error": "当前未配置图像识别服务，照片检查暂不可用。请改用文字提问，或联系管理员配置视觉模型。",

                            "error_code": "vision_not_configured",

                            "hint": "文字问答与知识库检索不受影响。",

                        },

                        HTTPStatus.SERVICE_UNAVAILABLE,

                    )

                    return

                # 检索提示：把"帮我看看这张照片"这类泛问，富化成能命中规范条款的查询。
                # 实测原始问题只返回通用检查标准；加上作业类型与风险维度后能命中对照条款。
                retrieval_hint = " ".join(filter(None, [
                    question,
                    "施工现场 安全隐患 风险等级",
                    "基坑 边坡 支护 临边防护 高处作业",
                    "检查要点 依据",
                ]))
                # ---- §4 硬闸：退化图不送模型 ----
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

                sources = self.services.engine.retrieve(retrieval_hint)

                try:

                    text = with_retry(lambda: self.services.engine.model.inspect_image(

                        image_bytes, mime_type, question, sources

                    ))

                except ProviderError as exc:

                    self._write_provider_error(exc)

                    return

                structured = parse_inspection(text)

                # 图片质量：字节数与是否解析出作业类型都算信号。
                # 模型对退化图像会凭空编造场景（实测 1x1 像素图也能输出"深基坑"），
                # 所以这里给前端一个显式标记，让它能把"看不清的"置顶并提示重拍。
                quality = "ok"

                if len(image_bytes) < 8 * 1024 or not structured["work_type"]:

                    quality = "low"

                self._write_json(

                    {

                        "text": text,

                        "text_plain": strip_markdown(text),

                        "structured": structured,

                        "image_quality": quality,

                        "sources": [asdict(x) for x in sources],

                        "warnings": ["照片识别仅基于可见信息，不能证明现场完全合规。高风险情况请现场确认。"],

                    }

                )

                return



            if path == "/api/transcribe":

                if not self.services.config.asr_configured:

                    self._write_json(

                        {

                            "error": "当前未配置语音识别服务，请改用键盘输入，或联系管理员配置 ASR。",

                            "error_code": "asr_not_configured",

                            "hint": "浏览器自带的语音识别（Chrome / Edge + 可用网络）仍可尝试。",

                        },

                        HTTPStatus.SERVICE_UNAVAILABLE,

                    )

                    return

                content_type = self.headers.get("Content-Type", "")

                length = int(self.headers.get("Content-Length", "0"))

                limit = self.services.config.max_audio_bytes

                if length <= 0:

                    self._write_json(

                        {"error": "录音内容为空，请重新录制", "error_code": "audio_empty"},

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                if length > limit + 200_000:

                    self._write_json(

                        {

                            "error": f"录音文件过大，请控制在 {limit // (1024 * 1024)} MB 以内",

                            "error_code": "audio_too_large",

                        },

                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,

                    )

                    return

                if "multipart/form-data" not in content_type:

                    self._write_json(

                        {"error": "需要 multipart/form-data 音频上传", "error_code": "audio_bad_request"},

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                raw = self.rfile.read(length)

                msg = self._parse_multipart(content_type, raw)

                audio_part = self._find_part(msg, ("audio", "file"))

                if audio_part is None:

                    self._write_json(

                        {"error": "未找到 audio 字段", "error_code": "audio_field_missing"},

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                audio_bytes = audio_part.get_payload(decode=True) or b""

                if not audio_bytes:

                    self._write_json(

                        {"error": "录音内容为空，请重新录制", "error_code": "audio_empty"},

                        HTTPStatus.BAD_REQUEST,

                    )

                    return

                if len(audio_bytes) > limit:

                    self._write_json(

                        {

                            "error": f"录音文件过大，请控制在 {limit // (1024 * 1024)} MB 以内",

                            "error_code": "audio_too_large",

                        },

                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,

                    )

                    return

                audio_mime = audio_part.get_content_type()

                audio_filename = self._part_param(audio_part, "filename") or "speech.webm"

                supplied_code = ""

                for part in self._iter_parts(msg):

                    if self._part_param(part, "name") == "access_code":

                        supplied_code = part.get_content().strip()

                if not self._access_allowed(

                    self.headers.get("X-Access-Code", "") or supplied_code

                ):

                    self._write_json({"error": "访问码不正确"}, HTTPStatus.UNAUTHORIZED)

                    return

                try:

                    text = with_retry(lambda: self.services.engine.model.transcribe_audio(

                        audio_bytes, mime_type=audio_mime, filename=audio_filename

                    ))

                except ProviderError as exc:

                    self._write_provider_error(exc)

                    return

                except AttributeError:

                    # 引擎被替换为不含 ASR 的实现时给出明确提示

                    self._write_json(

                        {

                            "error": "当前服务端未启用语音识别",

                            "error_code": "asr_not_supported",

                        },

                        HTTPStatus.SERVICE_UNAVAILABLE,

                    )

                    return

                self._write_json({"text": text, "mode": "server-asr"})

                return



            self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        except (ValueError, json.JSONDecodeError):

            # 不把 Python 异常原文写进响应体（实测泄漏过
            # "Expecting value: line 1 column 1 (char 0)"）。
            self._write_json(

                {

                    "error": "请求格式不正确，没能解析你提交的内容。",

                    "error_code": "bad_request",

                    "hint": "刷新页面后重试；如果反复出现，请联系管理员。",

                },

                HTTPStatus.BAD_REQUEST,

            )

        except ProviderError as exc:

            self._write_provider_error(exc)

        except Exception as exc:

            self._write_json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

        finally:

            if semaphore_acquired:

                self.server.request_semaphore.release()  # type: ignore[attr-defined]



    def _access_allowed(self, supplied_code: str) -> bool:

        expected = self.services.config.access_code

        return not expected or supplied_code == expected



    def _client_identifier(self) -> str:

        if self.services.config.trust_proxy_headers:

            for header in ("CF-Connecting-IP", "X-Real-IP"):

                value = self.headers.get(header, "").strip()

                if value:

                    return value

            forwarded = self.headers.get("X-Forwarded-For", "")

            if forwarded:

                return forwarded.split(",", 1)[0].strip()

        return self.client_address[0]



    def log_message(self, format: str, *args: Any) -> None:

        print(f"{self.address_string()} - {format % args}")





class SiteSahaServer(ThreadingHTTPServer):

    daemon_threads = True



    def __init__(

        self,

        server_address: tuple[str, int],

        handler_class: type[BaseHTTPRequestHandler],

        services: Services,

    ):

        super().__init__(server_address, handler_class)

        self.services = services

        self.throttle = RequestThrottle(services.config.rate_limit_per_minute)

        self.request_semaphore = threading.BoundedSemaphore(

            services.config.max_concurrent_requests

        )





def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(description="启动 SiteSaha AI 在线安全问答服务")

    cloud_port = os.getenv("PORT")

    default_host = os.getenv("SITESHAHA_HOST") or ("0.0.0.0" if cloud_port else "127.0.0.1")

    default_port = int(cloud_port or os.getenv("SITESHAHA_PORT", "8501"))

    parser.add_argument("--host", default=default_host)

    parser.add_argument("--port", default=default_port, type=int)

    parser.add_argument("--open", action="store_true", help="启动后打开浏览器")

    parser.add_argument("--version", action="version", version=APP_VERSION)

    return parser.parse_args()





def main() -> int:

    args = parse_args()

    services = build_services()

    try:

        from sitesaha.config import _warn_about_disabled_ai

        _warn_about_disabled_ai(services.config)

    except Exception:

        pass

    server = SiteSahaServer((args.host, args.port), SiteSahaHandler, services)

    display_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host

    url = f"http://{display_host}:{args.port}"

    print(f"SiteSaha AI: {url}")

    print(f"Version: {APP_VERSION}")

    print(f"SQLite: {services.config.db_path}")

    if args.open:

        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        pass

    finally:

        server.server_close()

    return 0





if __name__ == "__main__":

    raise SystemExit(main())

