/* SoloTalk 听说练习前端
 * 纯原生 JS：浏览器语音合成（听）+ Web Speech 语音识别（说）+ 计时 + 评分报告
 * 不依赖任何 CDN / 第三方库，离线可用（语音识别需 Chrome/Edge 并联网）。
 */
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* 访问控制凭据：线上发布链接形如 https://xxx/?sharecode=ABC，
 * 该 sharecode 必须随**每一个**后续请求（API / 音频 / 下载）带上，否则返回 403。
 * 本地运行时 location.search 为空，withShare 原样返回，不受影响。 */
const SHARE_QS = location.search || '';
function withShare(url) {
  if (!SHARE_QS || /sharecode=/.test(url)) return url;
  return url + (url.includes('?') ? '&' : '?') + SHARE_QS.replace(/^\?/, '');
}

const CAT_CN = {official:'真题', recall:'回忆版', mock:'模拟题', user:'上传原题', original:'原创改编'};
const CAT_FULL = {official:'官方真题（网络公开整理版）', recall:'考生回忆版（非官方原卷）',
  mock:'公开模拟题 / 全真模拟', user:'用户上传原始题目包', original:'原创改编（依据公开题型样例）'};
let BANK = [], PAPER = null, CUR = null, STEP = 'a';
let filters = {level:'全部', cat:'全部', q:''};
let speech = {synth: window.speechSynthesis, utter: null, recog: null, active: null, timer: null, sec: 0};
const REC_KEY = 'solotalk_records_v1';

/* ───────── 通用 ───────── */
function toast(msg, ms = 2600) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, ms);
}
async function api(path, opt) {
  const r = await fetch(withShare(path), opt);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}
function switchView(v) {
  $$('.view').forEach(e => e.classList.toggle('active', e.id === 'view-' + v));
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  window.scrollTo({top:0, behavior:'smooth'});
  if (v === 'records') renderRecords();
  if (v === 'about' && !$('#scoring-info').dataset.loaded) loadScoringInfo();
  if (v === 'download') renderDownloads();
}
$$('.nav-btn').forEach(b => b.onclick = () => switchView(b.dataset.view));

/* ───────── 题库 ───────── */
async function loadBank() {
  try { BANK = (await api('/api/bank')).packages; }
  catch (e) { toast('题库加载失败：' + e.message); return; }
  $('#bank-stats').innerHTML = [
    ['18', '内置试题'], [BANK.filter(p=>p.category==='official').length, '真题整理版'],
    [BANK.filter(p=>p.category==='recall').length, '考生回忆版'],
    [BANK.filter(p=>p.category==='mock').length + BANK.filter(p=>p.category==='original').length, '模拟/改编'],
    [BANK.filter(p=>p.media_embedded).length, '套含真实听力音频'],
  ].map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('');
  buildFilters(); renderBank();
}
function buildFilters() {
  const levels = ['全部', ...new Set(BANK.map(p => p.level))];
  const cats = ['全部', ...Object.keys(CAT_CN)];
  $('#filter-level').innerHTML = levels.map(l =>
    `<button class="chip ${filters.level===l?'on':''}" data-lv="${esc(l)}">${esc(l)}</button>`).join('');
  $('#filter-cat').innerHTML = cats.map(c =>
    `<button class="chip ${filters.cat===c?'on':''}" data-ct="${c}">${c==='全部'?'全部类型':CAT_CN[c]}</button>`).join('');
  $$('[data-lv]').forEach(b => b.onclick = () => { filters.level = b.dataset.lv; buildFilters(); renderBank(); });
  $$('[data-ct]').forEach(b => b.onclick = () => { filters.cat = b.dataset.ct; buildFilters(); renderBank(); });
}
$('#search').oninput = e => { filters.q = e.target.value.trim().toLowerCase(); renderBank(); };

function renderBank() {
  const list = BANK.filter(p =>
    (filters.level === '全部' || p.level === filters.level) &&
    (filters.cat === '全部' || p.category === filters.cat) &&
    (!filters.q || (p.name + p.year + p.region + p.paper_code).toLowerCase().includes(filters.q)));
  if (!list.length) { $('#paper-list').innerHTML = '<div class="rec-empty">没有匹配的试题，试试清除筛选。</div>'; return; }
  $('#paper-list').innerHTML = list.map(p => `
    <div class="paper">
      <div class="paper-top">
        <span class="badge b-${p.category}">${CAT_CN[p.category]}</span>
        <span class="fid">${esc(p.paper_type)}</span>
      </div>
      <h3>${esc(p.name)}</h3>
      <div class="meta">
        <span>${p.year || '—'} ${esc(p.paper_code || '')}</span>
        <span>${esc(p.region || '')}</span>
        <span>A ${p.partA_words} 词 · C ${p.partC_words} 词 · ${p.key_points} 要点</span>
        ${p.media_embedded ? '<span>含听力音频</span>' : ''}
        ${p.fidelity === 'partial' ? '<span>部分原文</span>' : ''}
      </div>
      <div class="paper-foot">
        <button class="btn sm" data-practice="${p.id}">开始练习</button>
        <button class="btn ghost sm" data-src="${p.id}">出处</button>
        <button class="btn ghost sm" data-dl="${p.id}">下载 .solo</button>
      </div>
    </div>`).join('');
  $$('[data-practice]').forEach(b => b.onclick = () => openPractice(b.dataset.practice));
  $$('[data-src]').forEach(b => b.onclick = () => showSource(b.dataset.src));
  $$('[data-dl]').forEach(b => b.onclick = () => {
    const p = BANK.find(x => x.id === b.dataset.dl);
    location.href = withShare('/download/one/' + encodeURIComponent(p.id));
  });
}
function showSource(id) {
  const p = BANK.find(x => x.id === id); if (!p) return;
  const urls = (p.urls || []).length
    ? '<ul>' + p.urls.map(u => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></li>`).join('') + '</ul>'
    : '<p>（用户本地上传，无公开链接）</p>';
  $('#modal-content').innerHTML = `
    <h3>${esc(p.name)}</h3>
    <p><span class="badge b-${p.category}">${CAT_FULL[p.category]}</span></p>
    <h4>考试信息</h4>
    <p>${esc(p.paper_type)} · ${p.year || '—'} · ${esc(p.paper_code || '—')} · ${esc(p.region || '—')}
       · ${p.fidelity === 'full' ? '三部分原文与参考答案完整' : '仅部分原文/梗概，缺项已标注'}</p>
    <h4>来源链接（可点击核查）</h4>${urls}
    <h4>整理备注</h4><p>${esc(p.source_note || '—')}</p>
    <h4>包文件</h4><p><code>assets/question_bank/${esc(p.file || p.id + '.solo')}</code> · ${(p.bytes/1024).toFixed(1)} KB
      ${p.media_embedded ? ' · 含内置听力音频' : ' · 纯文本无音视频'}</p>
    <div class="disclaim"><b>声明：</b>广东省教育考试院不公开听说考试原卷与官方题库。本套为网络公开资料整理，
      ${p.category === 'official' ? '真题原文转录自上述公开链接的整理版' :
        p.category === 'recall' ? '属考生考后回忆版，内容不完整' :
        p.category === 'user' ? '为用户上传的原始题目包，原样保留' : '非官方真题，属模拟/改编内容'}；
      仅供个人备考练习，版权归原命题机构及整理者所有，请勿用于商业用途。</div>`;
  $('#modal').hidden = false;
}
$('#modal-close').onclick = () => $('#modal').hidden = true;
$('#modal').onclick = e => { if (e.target.id === 'modal') $('#modal').hidden = true; };

/* ───────── 语音合成（听）───────── */
function ttsRate() { return parseFloat($('#tts-rate')?.value || '0.9'); }
$('#tts-rate').oninput = e => { $('#rate-val').textContent = parseFloat(e.target.value).toFixed(2) + '×'; };
function speak(text, btn) {
  if (!speech.synth) { toast('当前浏览器不支持语音朗读，请改用 Chrome / Edge'); return; }
  if (!text || !text.trim()) { toast('本套题没有可朗读的文本'); return; }
  speech.synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-GB'; u.rate = ttsRate(); u.pitch = 1.0;
  const vs = speech.synth.getVoices().filter(v => /^en(-|_)(GB|US)/i.test(v.lang));
  if (vs.length) u.voice = vs.find(v => /GB/i.test(v.lang)) || vs[0];
  if (btn) { const old = btn.textContent; btn.textContent = '🔊 播放中…'; u.onend = u.onerror = () => btn.textContent = old; }
  speech.utter = u; speech.synth.speak(u);
}
$$('[data-tts-stop]').forEach(b => b.onclick = () => { if (speech.synth) speech.synth.cancel(); });
document.addEventListener('click', e => {
  const b = e.target.closest('[data-tts]'); if (!b) return;
  const id = b.dataset.tts;
  speak(($(id)?.textContent || '').trim(), b);
});
if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = () => {};

/* ───────── 语音识别（说）+ 计时 ───────── */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
function fmt(s) { return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0'); }
function stopTimer() { clearInterval(speech.timer); speech.timer = null; }
function startTimer(el) { stopTimer(); speech.sec = 0; el.textContent = '00:00';
  speech.timer = setInterval(() => { speech.sec++; el.textContent = fmt(speech.sec); }, 1000); }

function startRec(target, btn, statusEl, timerEl) {
  if (!SR) {
    toast('当前浏览器不支持语音识别（需 Chrome/Edge 且允许麦克风）；请直接在文本框输入你朗读的内容，评分照常可用。', 5000);
    return;
  }
  if (speech.active) { stopRec(); return; }
  const r = new SR();
  r.lang = 'en-US'; r.continuous = true; r.interimResults = true;
  let final = '';
  r.onresult = ev => {
    let interim = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) final += t + ' '; else interim += t;
    }
    target.value = (final + interim).trim();
    target.dispatchEvent(new Event('input'));
  };
  r.onerror = ev => { statusEl.textContent = '识别出错：' + ev.error; statusEl.classList.remove('live');
    toast('语音识别失败（' + ev.error + '）：可手动输入文本继续练习。', 4500); };
  r.onend = () => { if (speech.active === r) { speech.active = null; stopTimer();
    btn.classList.remove('recording'); btn.textContent = '🎤 开始录音';
    statusEl.textContent = '已停止 · 可编辑识别文本'; statusEl.classList.remove('live'); } };
  try { r.start(); } catch (e) { toast('无法启动识别：' + e.message); return; }
  speech.active = r;
  btn.classList.add('recording'); btn.textContent = '■ 停止录音';
  statusEl.textContent = '正在识别…'; statusEl.classList.add('live');
  startTimer(timerEl);
}
function stopRec() { if (speech.active) { try { speech.active.stop(); } catch(e){} } }

/* ───────── 练习页 ───────── */
async function openPractice(id) {
  stopRec(); if (speech.synth) speech.synth.cancel();
  try { PAPER = await api('/api/paper/' + encodeURIComponent(id)); }
  catch (e) { toast('加载试题失败：' + e.message); return; }
  CUR = id; STEP = 'a';
  $('#practice-empty').hidden = true; $('#practice-body').hidden = false;
  $('#report').hidden = true;
  const s = PAPER.source || {};
  $('#p-source-tag').textContent = CAT_FULL[s.category] || '';
  $('#p-title').textContent = PAPER.name;
  $('#p-meta').innerHTML = [s.year || '—', s.paper_code || '', s.region || '',
    s.fidelity === 'partial' ? '部分原文' : '原文完整'].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join('')
    + (s.urls && s.urls.length ? ` <a href="#" id="p-src-link">查看出处</a>` : '');
  if ($('#p-src-link')) $('#p-src-link').onclick = e => { e.preventDefault(); showSource(id); };

  $('#a-ref').textContent = PAPER.partA.tts_text || PAPER.partA.hidden_text || '（本套题未提供模仿朗读原文）';
  $('#a-ref').classList.add('collapsed');
  $('#a-toggle').textContent = '显示原文';
  $('#a-text').value = ''; $('#c-text').value = '';
  $('#a-wc').textContent = '0 词'; $('#c-wc').textContent = '0 词';
  $('#a-timer').textContent = '00:00'; $('#c-timer').textContent = '00:00';
  $('#a-rec-status').textContent = '未开始'; $('#c-rec-status').textContent = '未开始';

  $('#b-situation').textContent = PAPER.partB.situation || '（无情景介绍）';
  $('#b-listen').textContent = PAPER.partB.listening_text || '（无听力文本）';
  $('#c-summary').textContent = PAPER.partC.summary || '—';
  $('#c-keywords').textContent = PAPER.partC.keywords || '—';
  $('#c-story').textContent = PAPER.partC.tts_text || '（无故事原文）';

  renderBQuestions(); renderSteps(); gotoStep('a');
  // 用户上传原题：显示内嵌听力音频播放器
  const box = $('#a-audio-note');
  const p = BANK.find(x => x.id === id);
  if (p && p.media_embedded && p.media_files && p.media_files.length) {
    box.hidden = false;
    box.innerHTML = '<b>本套题含 ' + p.media_files.length + ' 段真实听力音频（已内置）：</b> '
      + p.media_files.map((f, i) => `<button class="btn ghost sm" data-aplay="${i}">▶ 第 ${i+1} 段</button>`).join(' ')
      + ' <audio id="a-player" controls style="vertical-align:middle;margin-left:8px;height:32px"></audio>';
    $$('[data-aplay]').forEach(b => b.onclick = () => {
      const pl = $('#a-player');
      pl.src = withShare('/api/audio/' + encodeURIComponent(id) + '/' + b.dataset.aplay);
      pl.play();
    });
  } else box.hidden = true;

  switchView('practice');
}
function renderSteps() {
  $('#p-steps').innerHTML = [
    ['a', 'Part A · 模仿朗读', '20 分'], ['b', 'Part B · 角色扮演问答', '16 分'],
    ['c', 'Part C · 故事复述', '24 分'],
  ].map(([k, t, s]) => `<button class="step-tab ${STEP===k?'on':''}" data-step="${k}">${t}<small>${s}</small></button>`).join('');
  $$('[data-step]').forEach(b => b.onclick = () => gotoStep(b.dataset.step));
}
function gotoStep(k) {
  STEP = k;
  $$('.step-panel').forEach(p => p.hidden = p.id !== 'step-' + k);
  $$('[data-step]').forEach(b => b.classList.toggle('on', b.dataset.step === k));
}
$('#p-back').onclick = () => { stopRec(); if (speech.synth) speech.synth.cancel(); switchView('bank'); };

function renderBQuestions() {
  const three = PAPER.partB.three_questions || [], five = PAPER.partB.five_answers || [];
  let h = '';
  three.forEach((q, i) => {
    h += `<div class="q-card">
      <div class="q-head"><span class="q-title">三问 ${i+1}</span><span class="q-kind">提问 · 语言1.5/信息0.5</span></div>
      <div class="q-cn">中文提示：${esc(q.cn_prompt || '—')}</div>
      <div class="q-actions">
        <button class="btn ghost sm" data-qrec="PartB_Q${i+1}">🎤 录音作答</button>
        <button class="btn ghost sm" data-qtts="${esc(q.en_answer || '')}">▶ 参考提问</button>
      </div>
      <input class="q-input" data-ans="PartB_Q${i+1}" placeholder="说出你的英文提问（或在此输入）…">
      <div class="muted" data-refq="PartB_Q${i+1}" style="margin-top:6px">参考：${esc(q.en_answer || '—')}</div>
    </div>`;
  });
  five.forEach((q, i) => {
    h += `<div class="q-card">
      <div class="q-head"><span class="q-title">五答 ${i+1}</span><span class="q-kind">回答 · 语言0.5/信息1.5</span></div>
      <div class="q-en">${esc(q.en_question || '—')}</div>
      <div class="q-actions">
        <button class="btn ghost sm" data-qrec="PartB_A${i+1}">🎤 录音作答</button>
        <button class="btn ghost sm" data-qtts="${esc(q.en_question || '')}">▶ 播放问题</button>
      </div>
      <input class="q-input" data-ans="PartB_A${i+1}" placeholder="说出你的英文回答（或在此输入）…">
    </div>`;
  });
  if (!three.length && !five.length) h = '<div class="muted">本套题无角色扮演题目。</div>';
  $('#b-questions').innerHTML = h;
  $$('[data-qtts]').forEach(b => b.onclick = () => speak(b.dataset.qtts, b));
  $$('[data-qrec]').forEach(b => b.onclick = () => recInto(b.dataset.qrec, b));
  $$('[data-ans]').forEach(i => i.oninput = () => { /* value 已在 input 上，提交时读取 */ });
}

/* 单题录音：复用主识别器，把结果写进对应 input */
function recInto(key, btn) {
  const inp = $(`[data-ans="${key}"]`); if (!inp) return;
  if (speech.active) { stopRec(); return; }
  $$('[data-qrec]').forEach(b => { b.textContent = '🎤 录音作答'; b.classList.remove('recording'); });
  if (!SR) { toast('浏览器不支持语音识别，请直接在输入框填写作答文本。', 4000); inp.focus(); return; }
  const r = new SR(); r.lang = 'en-US'; r.continuous = false; r.interimResults = true;
  let final = '';
  r.onresult = ev => { let it = ''; for (let i = ev.resultIndex; i < ev.results.length; i++) {
    const t = ev.results[i][0].transcript; if (ev.results[i].isFinal) final += t + ' '; else it += t; }
    inp.value = (final + it).trim(); };
  r.onend = () => { if (speech.active === r) { speech.active = null; btn.textContent = '🎤 录音作答'; btn.classList.remove('recording'); } };
  r.onerror = ev => { toast('识别失败（' + ev.error + '），请手动输入。'); btn.textContent = '🎤 录音作答'; btn.classList.remove('recording'); };
  try { r.start(); } catch (e) { toast('无法启动识别：' + e.message); return; }
  speech.active = r; btn.textContent = '■ 停止'; btn.classList.add('recording');
}

$('#a-toggle').onclick = () => { const e = $('#a-ref'); const c = e.classList.toggle('collapsed');
  $('#a-toggle').textContent = c ? '显示原文' : '隐藏原文'; };
$('#a-rec').onclick = () => startRec($('#a-text'), $('#a-rec'), $('#a-rec-status'), $('#a-timer'));
$('#c-rec').onclick = () => startRec($('#c-text'), $('#c-rec'), $('#c-rec-status'), $('#c-timer'));
$('#a-text').oninput = e => $('#a-wc').textContent = e.target.value.trim().split(/\s+/).filter(Boolean).length + ' 词';
$('#c-text').oninput = e => $('#c-wc').textContent = e.target.value.trim().split(/\s+/).filter(Boolean).length + ' 词';
$('#a-clear').onclick = () => { $('#a-text').value = ''; $('#a-wc').textContent = '0 词'; };
$('#c-clear').onclick = () => { $('#c-text').value = ''; $('#c-wc').textContent = '0 词'; };

/* ───────── 提交评分 ───────── */
$('#submit').onclick = async () => {
  if (!CUR) return;
  const answers = {
    partA: {text: $('#a-text').value, duration_sec: speech.sec || undefined},
    partC: {text: $('#c-text').value},
  };
  $$('[data-ans]').forEach(i => { const t = i.value.trim(); if (t) answers[i.dataset.ans] = {text: t}; });
  const btn = $('#submit'); btn.disabled = true; btn.textContent = '评分中…';
  try {
    const r = await api('/api/score', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({paper_id: CUR, answers})});
    renderReport(r); saveRecord(r);
    $('#report').hidden = false;
    $('#report').scrollIntoView({behavior:'smooth', block:'start'});
    toast('评分完成：折算 ' + r.final_score + ' / ' + r.final_max + ' 分');
  } catch (e) { toast('评分失败：' + e.message); }
  finally { btn.disabled = false; btn.textContent = '提交并评分'; }
};
const f2 = x => (Number(x) || 0).toFixed(2);
function dimBox(title, val, max, rows) {
  const pct = max ? Math.max(0, Math.min(100, val / max * 100)) : 0;
  return `<div class="dim-box"><h4>${title}</h4><div class="v">${f2(val)}<small> / ${max}</small></div>
    <div class="bar"><i style="width:${pct}%"></i></div>
    ${rows.map(([k, v]) => `<div class="dim-row"><span>${k}</span><span>${esc(v)}</span></div>`).join('')}
  </div>`;
}
function renderReport(r) {
  const a = r.partA, b = r.partB, c = r.partC;
  const items = [...(b.questions || []).map((x,i)=>['三问 '+(i+1), x]),
                 ...(b.answers || []).map((x,i)=>['五答 '+(i+1), x])];
  $('#report').innerHTML = `
    <div class="report">
      <div class="report-top">
        <div><div class="big-score">${r.final_score}<small> / ${r.final_max} 分</small></div>
          <div class="sub-score">折算后计入高考英语总分 · 卷面 ${f2(r.paper_score)} / ${r.paper_max} 分</div>
          <div class="sub-score">${esc(r.paper_name)}</div></div>
        <div style="text-align:right"><span class="band">档次 ${esc(r.band)}</span>
          <div class="sub-score" style="margin-top:8px">${r.online_used ? '在线精细评分' : '离线近似评分（发音维度为代理值）'}</div></div>
      </div>
      <div class="dim-grid">
        ${dimBox('Part A 模仿朗读', a.total, 20, [
          ['语音语调', f2(a.pronunciation)+' / 12'], ['语速与内容', f2(a.pace_content)+' / 8'],
          ['词级准确率', (a.word_accuracy*100).toFixed(1)+'%'], ['漏读词', a.omitted_words],
          ['语速', a.wpm ? Math.round(a.wpm)+' 词/分' : '—'], ['档次', a.band]])}
        ${dimBox('Part B 角色扮演', b.total, b.max_score || 16, [
          ['三问得分', f2((b.questions||[]).reduce((s,x)=>s+x.total,0))],
          ['五答得分', f2((b.answers||[]).reduce((s,x)=>s+x.total,0))],
          ['题数', items.length], ['档次', b.band]])}
        ${dimBox('Part C 故事复述', c.total, 24, [
          ['内容要点', f2(c.content)+' / 12'], ['语言', f2(c.language)+' / 4'],
          ['流利程度', f2(c.fluency)+' / 5'], ['语音语调', f2(c.pronunciation)+' / 3'],
          ['要点覆盖', c.coverage || '—'], ['档次', c.band]])}
      </div>
    </div>
    <div class="advice">
      <h4>改进建议</h4><ul>${(r.advice||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
      <h4 style="margin-top:16px">识别文本与逐题得分</h4>
      <div class="muted">Part A 识别：${esc(a.recognized || '（未作答）')}</div>
      <div class="muted" style="margin-top:6px">Part C 识别：${esc((c.recognized||'').slice(0,260) || '（未作答）')}${c.recognized && c.recognized.length>260?'…':''}</div>
      ${items.length ? `<table class="item-table"><tr><th>题目</th><th>你的作答</th><th style="text-align:right">语言</th><th style="text-align:right">信息</th><th style="text-align:right">得分</th></tr>
        ${items.map(([n,x])=>`<tr><td>${n}</td><td>${esc(x.recognized||'（未作答）')}</td>
          <td class="num">${f2(x.language)}</td><td class="num">${f2(x.information)}</td><td class="num"><b>${f2(x.total)}</b></td></tr>`).join('')}</table>` : ''}
      <p class="muted" style="margin-top:12px">评分依据：${esc(r.config?.convert || '卷面60分÷3四舍五入')}。
        浏览器识别仅提供文本，发音/语法维度使用离线近似并已封顶标注；配置在线音素级评测后可获得更准的语音语调分。</p>
    </div>`;
}

/* ───────── 练习记录（localStorage）───────── */
function getRecords() { try { return JSON.parse(localStorage.getItem(REC_KEY) || '[]'); } catch(e){ return []; } }
function saveRecord(r) {
  const recs = getRecords();
  recs.unshift({t: Date.now(), id: CUR, name: r.paper_name, paper: r.paper_score,
                final: r.final_score, band: r.band, a: r.partA.total, b: r.partB.total, c: r.partC.total});
  localStorage.setItem(REC_KEY, JSON.stringify(recs.slice(0, 100)));
}
function renderRecords() {
  const recs = getRecords(); const box = $('#records-body');
  if (!recs.length) { box.innerHTML = '<div class="rec-empty">还没有练习记录。去「题库」选一套开始吧。</div>'; return; }
  const last = recs.slice(0, 12).reverse();
  const max = 60;
  let h = `<div class="trend">${last.map(x=>`<div class="col" style="height:${Math.max(3,x.paper/max*100)}%"><span>${Math.round(x.paper)}</span></div>`).join('')}</div>
    <div style="display:flex;gap:9px;margin-bottom:12px;flex-wrap:wrap">
      <button class="btn ghost sm" id="rec-export">导出 JSON</button>
      <button class="btn ghost sm" id="rec-clear">清空记录</button>
      <span class="muted" style="align-self:center">共 ${recs.length} 条 · 最近 12 次卷面分趋势（满分 60）</span></div>
    <table class="rec-table"><tr><th>时间</th><th>试题</th><th>卷面</th><th>折算</th><th>档</th><th>A / B / C</th></tr>
    ${recs.map(x=>`<tr><td>${new Date(x.t).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})}</td>
      <td>${esc(x.name)}</td><td>${f2(x.paper)}</td><td><b>${x.final}</b> / 20</td><td>${esc(x.band)}</td>
      <td>${f2(x.a)} / ${f2(x.b)} / ${f2(x.c)}</td></tr>`).join('')}</table>`;
  box.innerHTML = h;
  $('#rec-export').onclick = () => {
    const blob = new Blob([JSON.stringify(getRecords(), null, 2)], {type:'application/json'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'solotalk_records.json'; a.click(); URL.revokeObjectURL(a.href);
  };
  $('#rec-clear').onclick = () => { if (confirm('确定清空全部练习记录？')) { localStorage.removeItem(REC_KEY); renderRecords(); } };
}

/* ───────── 下载 ───────── */
const DL = [
  ['question_bank', '内置题库（18 套 .solo）', '全部试题包 + bank_index.json 索引，可直接放进 SoloTalk 软件题库目录。含用户上传原题的真实听力音频。', '约 0.5 MB'],
  ['full', '完整优化工程', '评分引擎、Android Kotlin 内核、电脑版优化源码、题库、文档、验证脚本与报告，全部打包。', '约 0.9 MB'],
  ['scoring', '评分引擎（Python）', '零依赖 CELST 多维评分内核，可嵌入 PyQt / Chaquopy / 服务端。', '约 23 KB'],
  ['android', 'Android 评分内核（Kotlin）', '与 Python 逐字段一致的 Kotlin 实现、桥接层、一致性测试与 Gradle 瘦身配置。', '约 16 KB'],
  ['desktop', '电脑版优化源码', '保留原 7626 行 UI、仅替换评分内核与题库加载的可运行源码及 diff。', '约 205 KB'],
  ['docs', '全部文档', '评分标准与算法对照、集成指南、内存体积优化报告、现状核查结论、试题出处清单。', '约 23 KB'],
];
function renderDownloads() {
  // 固定下载入口统一指向 GitHub Release（链接恒定，后续优化复用）
  const link = $('#fixed-link');
  if (link && !/github\.com/.test(link.href || '')) {
    link.href = 'https://github.com/xdbzys/SoloTalk-Optimized/releases';
    link.textContent = link.href;
  }
  $('#download-list').innerHTML = DL.map(([k,t,d,s]) => `
    <div class="dl-card"><h3>${esc(t)}</h3><p>${esc(d)}</p>
      <div class="dl-foot"><span class="muted">${esc(s)}</span>
        <a class="btn sm" href="${withShare('/download/' + k)}">下载 ZIP</a></div></div>`).join('');
}

/* ───────── 关于：评分标准 ───────── */
async function loadScoringInfo() {
  try {
    const i = await api('/api/scoring-info');
    $('#scoring-info').dataset.loaded = '1';
    $('#scoring-info').innerHTML = `<div class="panel-head"><h3>${esc(i.scheme)}</h3></div>
      <div class="dim-grid" style="background:none">
      ${i.parts.map(p=>`<div class="dim-box" style="background:#f8fafc;border-color:var(--line);color:var(--ink)">
        <h4>${esc(p.name)}</h4><div class="v">${p.max}<small> 分</small></div>
        ${p.dims.map(d=>`<div class="dim-row" style="border-color:var(--line);color:var(--sub)"><span>${esc(d)}</span></div>`).join('')}
      </div>`).join('')}</div>
      <p class="muted" style="margin-top:14px"><b>折算：</b>${esc(i.convert)}。${esc(i.note)}</p>
      <p class="muted">参考：广东高考英语听说考试官方评分档次（语音语调/语速与内容、语言/信息、内容/语言/流利/语音），
        以及卷面 60 分 ÷ 3 四舍五入计入英语总分的折算规则。</p>`;
  } catch(e) { $('#scoring-info').textContent = '评分标准加载失败：' + e.message; }
}

/* ───────── 启动 ───────── */
loadBank();
