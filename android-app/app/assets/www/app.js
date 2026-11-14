/* SoloTalk 优化版前端控制器 —— 纯前端，评分在本地 WebView 内完成（零服务器）。 */
(function () {
  "use strict";

  var bank = null;          // 题库索引
  var pkg = null;           // 当前试卷 data.json
  var pkgId = null;
  var stored = {};          // key -> 识别结果 asr 对象
  var recKeys = [];         // 可录音项 key 列表
  var recKeysB = { q: 3, a: 5 };

  // ───────── 工具 ─────────
  function $(s) { return document.querySelector(s); }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  var toastTimer;
  function toast(msg) {
    var t = $("#toast");
    t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("show"); }, 2600);
  }
  function tagClass(cat) {
    return { official: "official", recall: "recall", mock: "mock", user: "user", original: "original" }[cat] || "";
  }

  // ───────── 初始化 ─────────
  function init() {
    var meta = SoloBridge.getBankMeta();
    try { bank = JSON.parse(meta); } catch (e) { toast("题库索引解析失败"); return; }
    renderList();
    window.onSoloRecognize = function (key, asr) {
      stored[key] = asr;
      renderRecognized(key, asr);
      enableRec(key);
      if (asr && asr.error) toast("识别失败：" + asr.error + "（可手动输入）");
      else if (asr && asr.text) toast("已识别：" + asr.text.slice(0, 30) + (asr.text.length > 30 ? "…" : ""));
      else toast("未识别到内容，可手动输入");
    };
  }

  function renderList() {
    var box = $("#paperList");
    box.innerHTML = "";
    (bank.packages || []).forEach(function (p) {
      var div = document.createElement("div");
      div.className = "paper";
      div.setAttribute("data-id", p.id);
      var tags = '<span class="tag ' + tagClass(p.category) + '">' + esc(p.category_cn || p.category) + "</span>";
      if (p.year) tags += '<span class="tag">' + p.year + " " + esc(p.paper_code || "") + "</span>";
      if (p.region) tags += '<span class="tag">' + esc(p.region) + "</span>";
      div.innerHTML =
        '<div><div class="pname">' + esc(p.name) + "</div>" +
        '<div class="pmeta">' + tags + " <span>" + esc(p.level || "") + "</span></div></div>" +
        '<div style="font-size:22px">›</div>';
      div.addEventListener("click", function () { openPaper(p.id); });
      box.appendChild(div);
    });
  }

  // ───────── 打开试卷 ─────────
  function openPaper(id) {
    var raw = SoloBridge.getPackage(id);
    try { pkg = JSON.parse(raw); } catch (e) { toast("试卷读取失败"); return; }
    pkgId = id;
    stored = {};
    $("#listView").style.display = "none";
    $("#examView").style.display = "block";
    $("#backBtn").style.visibility = "visible";
    var m = pkg.meta || {};
    var cat = (bank.packages.find(function (x) { return x.id === id; }) || {});
    $("#examHeader").innerHTML =
      "<h2>" + esc(m.name || id) + "</h2>" +
      '<div class="src">' + (cat.category_cn ? esc(cat.category_cn) + " · " : "") +
      (m.level ? esc(m.level) + " · " : "") + "评分：" + esc(m.scoring_scheme || "CELST-2021") + "</div>";
    renderPartA();
    renderPartB();
    renderPartC();
    $("#report").style.display = "none";
    switchPart("A");
  }

  function back() {
    $("#examView").style.display = "none";
    $("#listView").style.display = "block";
    $("#backBtn").style.visibility = "hidden";
    SoloBridge.stopSpeak();
  }

  function switchPart(p) {
    ["A", "B", "C"].forEach(function (x) {
      $("#part" + x).style.display = (x === p) ? "block" : "none";
    });
    document.querySelectorAll(".tab").forEach(function (t) {
      t.classList.toggle("active", t.getAttribute("data-part") === p);
    });
  }

  // ───────── 朗读 / 播放 ─────────
  function speak(text, lang, rate) {
    if (!text) return;
    SoloBridge.speak(text, lang || "en-US", rate || 0.95);
  }
  function playAudio(rel) {
    if (!rel) return;
    var r = SoloBridge.playAudio(pkgId, rel);
    try { var o = JSON.parse(r); if (!o.ok) toast("音频不可用"); } catch (e) {}
  }

  // ───────── 录音 ─────────
  function startRec(key, ms) {
    disableRec(key, "识别中…");
    SoloBridge.recognize(key, ms);
  }
  function disableRec(key, label) {
    var b = document.querySelector('[data-rec="' + key + '"]');
    if (b) { b.classList.add("on"); b.disabled = true; b.textContent = label || "识别中…"; }
  }
  function enableRec(key) {
    var b = document.querySelector('[data-rec="' + key + '"]');
    if (b) { b.classList.remove("on"); b.disabled = false; b.textContent = "🎤 录音"; }
  }
  function renderRecognized(key, asr) {
    var box = document.getElementById("rec-" + key);
    if (!box) return;
    var txt = (asr && asr.text) || "";
    box.textContent = txt ? "识别：" + txt : "（空）";
    box.classList.toggle("empty", !txt);
  }

  // ───────── 渲染各 Part ─────────
  function recBlock(key, ms) {
    return '<div class="row">' +
      '<button class="btn rec" data-rec="' + key + '" onclick="startRec(\'' + key + "'," + ms + ')">🎤 录音</button>' +
      '<button class="btn" onclick="SoloBridge.stopSpeak()">■ 停止朗读</button></div>' +
      '<textarea class="manual" id="man-' + key + '" placeholder="识别失败时，可在此手动输入你的作答（英文）…"></textarea>' +
      '<div class="recognized empty" id="rec-' + key + '">（空）</div>';
  }

  function renderPartA() {
    var p = pkg.partA || {};
    var html = '<div class="card"><h3>Part A 模仿朗读（满分 20，含 语音语调12 + 语速内容8）</h3>';
    html += '<div class="passage">' + esc(p.hidden_text || p.tts_text || "（无文本）") + "</div>";
    html += '<div class="row">' +
      '<button class="btn" onclick="speak(\'' + escJs(p.hidden_text || p.tts_text || "") + "','en-US',0.92)\">🔊 朗读范文</button>";
    if (p.audio) html += '<button class="btn" onclick="playAudio(\'' + escJs(p.audio) + "')\">🎧 原声</button>";
    html += "</div>" + recBlock("partA", 15000) + "</div>";
    $("#partA").innerHTML = html;
  }

  function renderPartB() {
    var pb = pkg.partB || {};
    var secA = pkg.partB_secA || [];
    var html = '<div class="card"><h3>Part B 角色扮演（满分 16：三问语言1.5+信息0.5 / 五答语言0.5+信息1.5）</h3>';
    html += '<div class="passage">' + esc(pb.situation || (secA[0] && secA[0].tts_text) || "（无情景文本）") + "</div>";
    // 听力材料音频
    var hasAudio = secA.some(function (s) { return s.audio; });
    if (hasAudio) {
      html += '<div class="row">';
      secA.forEach(function (s, i) {
        if (s.audio) html += '<button class="btn" onclick="playAudio(\'' + escJs(s.audio) + "')\">🎧 听第" + (i + 1) + "段</button>";
      });
      html += "</div>";
    } else if (pb.listening_text) {
      html += '<div class="row"><button class="btn" onclick="speak(\'' + escJs(pb.listening_text) + "','zh-CN',0.95)\">🔊 朗读情景</button></div>";
    }
    var qs = pb.three_questions || [];
    qs.forEach(function (q, i) {
      var k = "PartB_Q" + (i + 1);
      html += '<div class="card" style="margin-top:10px"><div class="q"><span class="lab">三问 ' + (i + 1) + " 中文提示：</span>" + esc(q.cn_prompt || "") + "</div>";
      html += '<div class="ref">参考答案：' + esc(q.en_answer || q.hidden_answer || "") + "</div>";
      html += '<div class="row"><button class="btn" onclick="speak(\'' + escJs(q.en_answer || q.hidden_answer || "") + "','en-US',0.92)\">🔊 听答案</button></div>";
      html += recBlock(k, 10000) + "</div>";
    });
    var ans = pb.five_answers || [];
    ans.forEach(function (a, i) {
      var k = "PartB_A" + (i + 1);
      html += '<div class="card" style="margin-top:10px"><div class="q"><span class="lab">五答 ' + (i + 1) + " 英文问题：</span>" + esc(a.en_question || "") + "</div>";
      html += '<div class="ref">参考要点：' + esc(a.hidden_answer || "") + "</div>";
      html += recBlock(k, 10000) + "</div>";
    });
    html += "</div>";
    $("#partB").innerHTML = html;
  }

  function renderPartC() {
    var pc = pkg.partC || {};
    var html = '<div class="card"><h3>Part C 故事复述（满分 24：内容12 + 语言4 + 流利5 + 语音3）</h3>';
    html += '<div class="passage">' + esc(pc.tts_text || pc.summary || "（无文本）") + "</div>";
    html += '<div class="row"><button class="btn" onclick="speak(\'' + escJs(pc.tts_text || pc.summary || "") + "','en-US',0.9)\">🔊 听短文</button></div>";
    if (pc.key_points) html += '<div class="q" style="margin-top:8px">要点提示：<br>' + esc(pc.key_points).replace(/,/g, "，") + "</div>";
    html += recBlock("partC", 30000) + "</div>";
    $("#partC").innerHTML = html;
  }

  function escJs(s) {
    return String(s == null ? "" : s).replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/\n/g, " ");
  }

  // ───────── 评分 ─────────
  function asrFor(key) {
    if (stored[key]) return stored[key];
    var ta = document.getElementById("man-" + key);
    var txt = ta ? ta.value.trim() : "";
    if (txt) return { text: txt, duration_sec: 0, wpm: null, pause_ratio: null, pronunciation: null, grammar: null, source: "manual" };
    return { text: "", source: "empty" };
  }

  function runScoring() {
    recKeys = ["partA"];
    for (var i = 1; i <= 3; i++) recKeys.push("PartB_Q" + i);
    for (var j = 1; j <= 5; j++) recKeys.push("PartB_A" + j);
    recKeys.push("partC");

    var recordings = { partA: asrFor("partA"), partB: {}, partC: asrFor("partC") };
    for (var q = 1; q <= 3; q++) recordings.partB["PartB_Q" + q] = asrFor("PartB_Q" + q);
    for (var a = 1; a <= 5; a++) recordings.partB["PartB_A" + a] = asrFor("PartB_A" + a);

    var res = CELST.gradeExam(pkg, recordings, CELST.defaultConfig());
    renderReport(res.report);
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }

  function bandClass(b) { return b === "A" ? "bandA" : b === "B" ? "bandB" : "bandC"; }

  function renderReport(rep) {
    var A = rep.partA, B = rep.partB, C = rep.partC;
    var h = '<div class="report"><h2>评分报告 · 总档 <span class="' + bandClass(rep.band) + '">' + rep.band + "</span></h2>";
    h += '<div>卷面 <b>' + rep.paper_score.toFixed(1) + "/60</b> &nbsp;→&nbsp; 高考折算 <span class=\"bigscore\">" + rep.final_score + "</span> / 20</div>";
    h += '<div class="dim">' + esc(rep.config.convert) + ' 目标语速 ' + rep.config.target_wpm + ' wpm</div><hr style="border:0;border-top:1px solid #e3e8ef;margin:10px 0">'

    h += partScoreHtml("Part A 模仿朗读", A.total, 20, A.band,
      "语音语调 " + A.pronunciation.toFixed(1) + " · 语速内容 " + A.pace_content.toFixed(1) +
      (A.wpm ? " · " + Math.round(A.wpm) + "wpm" : "") + " · 漏读 " + A.omitted_words + " 词", A.notes);
    h += partScoreHtml("Part B 角色扮演", B.total, B.max_score, B.band,
      "三问 " + B.questions.length + " 题 · 五答 " + B.answers.length + " 题", null);
    B.questions.concat(B.answers).forEach(function (it, idx) {
      h += '<div class="note">· ' + (it.kind === "question" ? "三问" : "五答") + (idx < 3 ? idx + 1 : idx - 2) +
        "：语言 " + it.language.toFixed(1) + " / 信息 " + it.information.toFixed(1) +
        (it.recognized ? "（" + esc(it.recognized.slice(0, 40)) + "）" : "（未作答）") + "</div>";
    });
    h += partScoreHtml("Part C 故事复述", C.total, 24, C.band,
      "内容 " + C.content.toFixed(1) + " · 语言 " + C.language.toFixed(1) +
      " · 流利 " + C.fluency.toFixed(1) + " · 语音 " + C.pronunciation.toFixed(1) +
      " · 要点 " + C.coverage, C.notes);
    h += "</div>";
    var box = $("#report");
    box.innerHTML = h;
    box.style.display = "block";
  }

  function partScoreHtml(title, total, max, band, detail, notes) {
    return '<div class="partScore"><div><b>' + title + '</b><div class="dim">' + detail + "</div>" +
      (notes ? '<div class="note">' + notes.map(esc).join("；") + "</div>" : "") + "</div>" +
      '<div style="text-align:right"><span class="' + bandClass(band) + '" style="font-weight:700">' + total.toFixed(1) +
      "</span> <span class=\"dim\">/" + (typeof max === "number" ? max.toFixed(0) : max) + " · " + band + "</span></div></div>";
  }

  // 暴露给 WebView 内联调用
  window.openPaper = openPaper;
  window.back = back;
  window.switchPart = switchPart;
  window.speak = speak;
  window.playAudio = playAudio;
  window.startRec = startRec;
  window.runScoring = runScoring;

  document.addEventListener("DOMContentLoaded", function () {
    $("#backBtn").addEventListener("click", back);
    init();
  });
})();
