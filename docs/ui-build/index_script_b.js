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

        var text = payload.text || "";

        (payload.warnings || []).forEach(function (warning) { text += NL2 + "⚠ " + warning; });

        if (payload.sources && payload.sources.length) {

          text += NL2 + "参考依据：" + payload.sources.slice(0, 3).map(function (item) {

            return item.title;

          }).join("；");

        }

        result.textContent = text || "服务端没有返回内容。";

      } catch (error) {

        result.hidden = true;

        var info = classifyPhotoFailure(error.status, error.payload, error.message);

        showPhotoError(info.title, info.lines);

      } finally {

        button.disabled = false;

        button.textContent = "分析照片";

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

</html>

