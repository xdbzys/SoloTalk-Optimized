/* CELST 评分引擎 —— 纯 JavaScript 移植（零依赖、零模型）
 * 与 Python 版 scoring/gd_celst.py + text_utils.py 逐函数对齐。
 * 在 Android WebView 中离线运行，作为广东高考英语听说评分内核。
 */
(function (global) {
  "use strict";

  // ───────────────────────── 文本工具（对应 text_utils.py） ─────────────────────────
  const PUNCT_RE = /[^a-z0-9'\s]+/g;
  const WS_RE = /\s+/g;

  const STOPWORDS = new Set(
    `a an the and or but if then than so because although though while of in on at to for from with
     by as into onto over under about above below up down out off again further once here there when
     where why how all any both each few more most other some such no nor not only own same too very
     can will just don should now i you he she it we they me him her us them my your his its our their
     this that these those am is are was were be been being have has had having do does did doing
     would could shall may might must shall will 's 't 're 've 'll 'd 'm
     um uh er ah like well okay ok yeah`
      .split(/\s+/)
      .filter(Boolean)
  );

  const IRREGULAR = {
    was: "be", were: "be", is: "be", are: "be", am: "be", been: "be", being: "be",
    had: "have", has: "have", having: "have",
    did: "do", does: "do", doing: "do",
    went: "go", gone: "go", going: "go",
    got: "get", gotten: "get", getting: "get",
    made: "make", making: "make",
    took: "take", taken: "take", taking: "take",
    gave: "give", given: "give", giving: "give",
    found: "find", finding: "find",
    told: "tell", telling: "tell",
    saw: "see", seen: "see", seeing: "see",
    said: "say", saying: "say",
    bought: "buy", brought: "bring", thought: "think",
    felt: "feel", left: "leave", kept: "keep", slept: "sleep",
    men: "man", women: "woman", children: "child", people: "person",
    mice: "mouse", feet: "foot", teeth: "tooth",
    better: "good", best: "good", worse: "bad", worst: "bad"
  };

  // 显式写死 canon，与 Python _SYNONYM_MAP 逐条一致（避免集合迭代顺序导致双端差异）
  const SYNONYM_MAP = {
    present: "gift", gift: "gift",
    buy: "buy", purchase: "buy", bought: "buy", purchased: "buy",
    poor: "poor", broke: "poor",
    rich: "rich", wealthy: "rich", "well-off": "rich",
    shop: "shop", store: "shop", market: "shop",
    manager: "boss", owner: "boss", shopkeeper: "boss", boss: "boss",
    vase: "vase", jar: "vase", pot: "vase",
    break: "break", broken: "break", smash: "break",
    smashed: "break", shatter: "break", pieces: "break",
    birthday: "birthday",
    girlfriend: "girlfriend", girl: "girlfriend",
    surprise: "surprise", surprised: "surprise",
    amazed: "surprise", shocked: "surprise",
    help: "help", helped: "help", assist: "help", assisted: "help",
    plan: "plan", planned: "plan", idea: "plan", scheme: "plan",
    worker: "worker", employee: "worker",
    pack: "pack", packed: "pack", wrap: "pack",
    wrapped: "pack", package: "pack",
    drop: "drop", dropped: "drop", fall: "drop", fell: "drop",
    guest: "guest", guests: "guest", visitor: "guest", visitors: "guest",
    expensive: "expensive", costly: "expensive", dear: "expensive",
    decide: "decide", decided: "decide", decision: "decide",
    want: "want", wanted: "want", wish: "want",
    wished: "want", hope: "want", hoped: "want"
  };

  function normalize(text) {
    if (!text) return "";
    text = String(text)
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/’/g, "'")
      .replace(/‘/g, "'");
    text = text.replace(PUNCT_RE, " ");
    return text.replace(WS_RE, " ").trim();
  }

  function tokenize(text) {
    return normalize(text).split(/\s+/).filter(Boolean);
  }

  function isStopword(w) {
    return STOPWORDS.has(w);
  }

  function stripQuotes(w) {
    return w.replace(/^'+|'+$/g, "");
  }

  function stem(word) {
    let w = stripQuotes(String(word).toLowerCase());
    if (!w) return "";
    if (IRREGULAR[w] !== undefined) w = IRREGULAR[w];
    if (SYNONYM_MAP[w] !== undefined) return SYNONYM_MAP[w];
    if (w.length > 4 && w.endsWith("ies")) return w.slice(0, -3) + "y";
    if (w.length > 5 && w.endsWith("ing")) {
      let base = w.slice(0, -3);
      if (base.length > 2 && base[base.length - 1] === base[base.length - 2] && !"aeiou".includes(base[base.length - 1])) {
        base = base.slice(0, -1);
      }
      return base;
    }
    if (w.length > 4 && w.endsWith("ed")) {
      let base = w.slice(0, -2);
      if (base.length > 2 && base[base.length - 1] === base[base.length - 2] && !"aeiou".includes(base[base.length - 1])) {
        base = base.slice(0, -1);
      }
      return base;
    }
    if (w.length > 4 && w.endsWith("es") && !/(ses|xes|ches|shes)$/.test(w)) {
      return w.slice(0, -2) + (w[w.length - 3] === "s" ? "s" : "");
    }
    if (w.length > 3 && w.endsWith("s") && !/(ss|us|is)$/.test(w)) {
      return w.slice(0, -1);
    }
    return w;
  }

  function contentWords(text) {
    return tokenize(text)
      .filter((w) => !STOPWORDS.has(w))
      .map(stem);
  }

  // 词级编辑对齐（对应 align_words）
  function alignWords(ref, hyp) {
    const r = tokenize(ref);
    const h = tokenize(hyp);
    const n = r.length,
      m = h.length;
    if (n === 0) {
      return { ref_len: 0, hyp_len: m, hits: 0, substitutions: 0, deletions: 0, insertions: m, accuracy: 0, omitted: 0, omitted_ratio: 0 };
    }
    let prev = [];
    for (let j = 0; j <= m; j++) prev.push(j);
    const W = m + 1;
    const ops = new Uint8Array((n + 1) * W);
    for (let i = 1; i <= n; i++) {
      const cur = new Array(m + 1);
      cur[0] = i;
      for (let j = 1; j <= m; j++) {
        const cost = r[i - 1] === h[j - 1] ? 0 : 1;
        const diag = prev[j - 1] + cost;
        const dele = prev[j] + 1;
        const ins = cur[j - 1] + 1;
        const best = Math.min(diag, dele, ins);
        cur[j] = best;
        ops[i * W + j] = best === diag ? 0 : best === dele ? 1 : 2;
      }
      prev = cur;
    }
    let hits = 0,
      subs = 0,
      dele = 0,
      ins = 0;
    let i = n,
      j = m;
    while (i > 0 || j > 0) {
      if (i === 0) {
        ins++;
        j--;
        continue;
      }
      if (j === 0) {
        dele++;
        i--;
        continue;
      }
      const op = ops[i * W + j];
      if (op === 0) {
        if (r[i - 1] === h[j - 1]) hits++;
        else subs++;
        i--;
        j--;
      } else if (op === 1) {
        dele++;
        i--;
      } else {
        ins++;
        j--;
      }
    }
    const accuracy = Math.max(0, 1 - (subs + dele + ins) / Math.max(1, n));
    const omitted = subs + dele;
    return {
      ref_len: n,
      hyp_len: m,
      hits,
      substitutions: subs,
      deletions: dele,
      insertions: ins,
      accuracy,
      omitted,
      omitted_ratio: omitted / Math.max(1, n)
    };
  }

  // 要点覆盖（对应 keyphrase_coverage）
  function phraseHit(point, hypContent) {
    const pWords = tokenize(point).filter((w) => !STOPWORDS.has(w)).map(stem);
    if (pWords.length === 0) return 0;
    const pStemJoin = pWords.join(" ");
    const hStemJoin = hypContent.join(" ");
    if (pStemJoin && hStemJoin.indexOf(pStemJoin) !== -1) return 1.0;
    const hs = new Set(hypContent);
    const pSet = new Set(pWords);
    let hit = 0;
    pSet.forEach((w) => {
      if (hs.has(w)) hit++;
    });
    const ratio = hit / pSet.size;
    return ratio < 0.5 ? 0.0 : Math.min(1.0, (ratio - 0.5) * 2.0);
  }

  function keyphraseCoverage(keyPoints, recognized) {
    const points = (keyPoints || "")
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    if (points.length === 0) return { matched: 0, total: 0, ratio: 0, per_point: [], spurious: 0 };
    const hypContent = contentWords(recognized);
    const per = points.map((p) => phraseHit(p, hypContent));
    const matched = per.filter((s) => s >= 0.8).length;
    const ratio = per.reduce((a, b) => a + b, 0) / per.length;
    const refVocab = new Set();
    points.forEach((p) => {
      tokenize(p)
        .filter((w) => !STOPWORDS.has(w))
        .forEach((w) => refVocab.add(stem(w)));
    });
    let extra = 0;
    hypContent.forEach((w) => {
      if (!refVocab.has(w)) extra++;
    });
    const spurious = Math.min(1.0, extra / Math.max(1, hypContent.length));
    return { matched, total: points.length, ratio, per_point: per, spurious };
  }

  const Q_WORDS = new Set("what when where why who whom whose which how".split(" "));
  const AUX = new Set("am is are was were do does did have has had can could will would shall should may might must".split(" "));

  function looksLikeQuestion(text) {
    const words = tokenize(text);
    if (words.length === 0) return [false, 0.0];
    const checks = [];
    const first = words[0];
    checks.push(first in Q_WORDS || first in AUX ? 1.0 : 0.0);
    const hasQ = words.some((w) => Q_WORDS.has(w));
    checks.push(hasQ || first in AUX ? 1.0 : 0.0);
    if (Q_WORDS.has(first)) {
      checks.push(words.length > 1 && AUX.has(words[1]) ? 1.0 : 0.35);
    } else {
      checks.push(1.0);
    }
    checks.push(words.length >= 3 && words.length <= 25 ? 1.0 : 0.4);
    const score = checks.reduce((a, b) => a + b, 0) / checks.length;
    return [score >= 0.6, score];
  }

  function sentenceWellformedness(text) {
    const words = tokenize(text);
    if (words.length < 3) return words.length ? 0.1 : 0.0;
    let score = 1.0;
    let func = 0;
    words.forEach((w) => {
      if (STOPWORDS.has(w)) func++;
    });
    if (func / words.length < 0.12) score -= 0.3;
    const uniq = new Set(words).size;
    if (uniq / words.length < 0.45) score -= 0.25;
    if (words.length > 160) score -= 0.15;
    return Math.max(0, Math.min(1, score));
  }

  function speechRateWpm(text, durationSec) {
    if (!durationSec || durationSec <= 0) return null;
    return (tokenize(text).length * 60.0) / durationSec;
  }

  // ───────────────────────── 评分引擎（对应 gd_celst.py） ─────────────────────────
  function roundHalfUp(x) {
    return Math.floor(x + 0.5);
  }
  function clamp(x, lo, hi) {
    lo = lo === undefined ? 0.0 : lo;
    hi = hi === undefined ? 1.0 : hi;
    return Math.max(lo, Math.min(hi, x));
  }
  function band(score, maxScore) {
    const r = score / Math.max(1e-9, maxScore);
    return r >= 0.7 ? "A" : r >= 0.35 ? "B" : "C";
  }
  function officialBand(q, aLo, aHi, bLo, bHi, cHi) {
    const v = clamp(q);
    if (v >= 0.8) return aLo + ((v - 0.8) / 0.2) * (aHi - aLo);
    if (v >= 0.5) return bLo + ((v - 0.5) / 0.3) * (bHi - bLo);
    return (v / 0.5) * cHi;
  }

  function defaultConfig() {
    return {
      PAPER_MAX: 60,
      PART_A_MAX: 20,
      PART_B_MAX: 16,
      PART_C_MAX: 24,
      CONVERT_DIVISOR: 3.0,
      FINAL_MAX: 20,
      A_PRON_MAX: 12.0,
      A_PACE_MAX: 8.0,
      TARGET_WPM: 130.0,
      B_Q_LANG: 1.5,
      B_Q_INFO: 0.5,
      B_A_LANG: 0.5,
      B_A_INFO: 1.5,
      B_ITEM_MAX: 2.0,
      C_CONTENT_MAX: 12.0,
      C_LANG_MAX: 4.0,
      C_FLUENCY_MAX: 5.0,
      C_PRON_MAX: 3.0,
      INFO_HIT_FLOOR: 0.3,
      LANG_FLOOR: 0.28,
      MIN_RETELL_RATIO: 0.18
    };
  }

  function emptyAsr(asr) {
    return !asr.text || !asr.text.trim();
  }

  function scorePartA(reference, asr, cfg) {
    cfg = cfg || defaultConfig();
    if (emptyAsr(asr)) {
      return {
        recognized: "",
        pronunciation: 0,
        pace_content: 0,
        total: 0,
        band: "C",
        word_accuracy: 0,
        omitted_words: 0,
        wpm: null,
        source: asr.source || "empty",
        notes: ["未作答或识别为空，记 0 分"]
      };
    }
    const al = alignWords(reference, asr.text);
    const notes = [];
    let pronQ;
    if (asr.pronunciation !== null && asr.pronunciation !== undefined) {
      pronQ = clamp(asr.pronunciation);
      notes.push("发音分来自在线音素级评测");
    } else {
      const hitRatio = al.hits / Math.max(1, al.ref_len);
      pronQ = clamp(0.6 * al.accuracy + 0.4 * hitRatio);
      notes.push("离线近似：以词级对齐准确率代理发音分（建议联网启用发音评测）");
    }
    if (al.accuracy < 0.35) {
      pronQ = Math.min(pronQ, (al.accuracy / 0.35) * 0.4);
      notes.push("识别文本与原文不匹配，发音分随内容对齐一并降级");
    }
    const pronunciation = officialBand(pronQ, 8.0, cfg.A_PRON_MAX, 4.0, 7.0, 3.0);

    const omitted = al.omitted;
    let content;
    if (omitted <= 3) content = 6.0 + (1.0 - omitted / 4.0) * 2.0;
    else if (omitted <= 10) content = 3.0 + ((10 - omitted) / 7.0) * 2.0;
    else content = Math.max(0, 2.0 - (omitted - 10) * 0.15);
    if (al.accuracy < 0.35) {
      content = Math.min(content, 2.0 * Math.max(0, al.accuracy / 0.35));
      notes.push("识别文本与原文整体不匹配，内容完整度按 C 档封顶");
    }
    const wpm = asr.wpm !== null && asr.wpm !== undefined ? asr.wpm : speechRateWpm(asr.text, asr.duration_sec);
    const target = cfg.TARGET_WPM;
    let pace_content;
    if (wpm && wpm > 0) {
      const paceQ = clamp(1.0 - Math.abs(wpm - target) / target);
      pace_content = clamp(content + (paceQ - 0.5) * 1.2, 0.0, cfg.A_PACE_MAX);
      notes.push(`语速 ${Math.round(wpm)} wpm（目标 ${Math.round(target)}）`);
    } else {
      pace_content = content;
      notes.push("缺音频时长，语速维度不参与微调");
    }
    const total = clamp(pronunciation + pace_content, 0.0, cfg.PART_A_MAX);
    return {
      recognized: asr.text,
      pronunciation,
      pace_content,
      total,
      band: band(total, cfg.PART_A_MAX),
      word_accuracy: Math.round(al.accuracy * 10000) / 10000,
      omitted_words: omitted,
      wpm: wpm ? Math.round(wpm * 10) / 10 : null,
      source: asr.source || "offline",
      notes
    };
  }

  function infoHit(reference, recognized) {
    const r = contentWords(reference);
    const h = contentWords(recognized);
    if (r.length === 0) return [0, 0, 0];
    const rs = new Set(r);
    const hs = new Set(h);
    let inter = 0;
    rs.forEach((w) => {
      if (hs.has(w)) inter++;
    });
    const recall = inter / rs.size;
    const precision = hs.size ? inter / hs.size : 0;
    const spurious = 1.0 - precision;
    return [recall, precision, spurious];
  }

  function scorePartBItem(reference, asr, index, kind, cfg, cnPrompt) {
    cfg = cfg || defaultConfig();
    index = index || 0;
    kind = kind || "question";
    cnPrompt = cnPrompt || "";
    if (emptyAsr(asr)) {
      return {
        index,
        kind,
        recognized: "",
        language: 0,
        information: 0,
        total: 0,
        max_score: cfg.B_ITEM_MAX,
        structure_ok: false,
        content_hit: 0,
        spurious: 0,
        source: asr.source || "empty",
        notes: ["未作答或识别为空，记 0 分"]
      };
    }
    const isQ = kind === "question";
    const langMax = isQ ? cfg.B_Q_LANG : cfg.B_A_LANG;
    const infoMax = isQ ? cfg.B_Q_INFO : cfg.B_A_INFO;
    const notes = [];

    let structOk, structScore;
    if (isQ) {
      const lq = looksLikeQuestion(asr.text);
      structOk = lq[0];
      structScore = lq[1];
    } else {
      structOk = true;
      structScore = 1.0;
    }
    const well = sentenceWellformedness(asr.text);
    const al = alignWords(reference, asr.text);
    let langQ;
    if (asr.grammar !== null && asr.grammar !== undefined) {
      langQ = clamp(asr.grammar);
      notes.push("语言分来自在线语法评测");
    } else if (isQ) {
      langQ = clamp(0.5 * structScore + 0.3 * al.accuracy + 0.2 * well);
      if (!structOk) notes.push("疑问句结构有误（疑问词/助动词语序）");
    } else {
      langQ = clamp(0.55 * al.accuracy + 0.45 * well);
    }
    let language;
    if (langQ < cfg.LANG_FLOOR) {
      language = 0.0;
      notes.push("语言/选词错误导致不能理解，语言维度记 0");
    } else if (isQ) {
      language = langQ >= 0.85 ? 1.5 : langQ >= 0.55 ? 1.0 : 0.0;
    } else {
      language = langQ >= 0.5 ? 0.5 : 0.0;
    }

    const ih = infoHit(reference, asr.text);
    const recall = ih[0];
    const spurious = ih[2];
    let infoQ;
    if (recall >= 0.8 && spurious <= 0.55) infoQ = 1.0;
    else if (recall >= 0.45) {
      infoQ = 0.67;
      notes.push("基本传递信息：漏次要信息或含无关内容");
    } else {
      infoQ = 0.0;
      if (recall < cfg.INFO_HIT_FLOOR) notes.push("关键信息缺失");
    }
    let information;
    if (isQ) information = infoQ >= 0.67 ? infoMax : 0.0;
    else information = infoQ === 1.0 ? infoMax : infoQ >= 0.67 ? 1.0 : 0.0;

    const total = clamp(language + information, 0.0, cfg.B_ITEM_MAX);
    return {
      index,
      kind,
      recognized: asr.text,
      language,
      information,
      total,
      max_score: cfg.B_ITEM_MAX,
      structure_ok: structOk,
      content_hit: Math.round(recall * 1000) / 1000,
      spurious: Math.round(spurious * 1000) / 1000,
      source: asr.source || "offline",
      notes
    };
  }

  function buildPartB(items, cfg) {
    const q = items.filter((i) => i.kind === "question");
    const a = items.filter((i) => i.kind === "answer");
    const total = items.reduce((s, i) => s + i.total, 0);
    const mx = q.length * cfg.B_ITEM_MAX + a.length * cfg.B_ITEM_MAX;
    return { questions: q, answers: a, total, max_score: mx, band: band(total, mx || cfg.PART_B_MAX) };
  }

  function scorePartC(keyPoints, asr, cfg, sourceText) {
    cfg = cfg || defaultConfig();
    if (emptyAsr(asr)) {
      return {
        recognized: "",
        content: 0,
        language: 0,
        fluency: 0,
        pronunciation: 0,
        total: 0,
        band: "C",
        coverage: "0/0",
        point_scores: [],
        wpm: null,
        length_ratio: 0,
        source: asr.source || "empty",
        notes: ["未作答或识别为空，记 0 分"]
      };
    }
    const notes = [];
    const cov = keyphraseCoverage(keyPoints, asr.text);
    const cRatio = cov.ratio;
    let content = officialBand(cRatio, 8.0, cfg.C_CONTENT_MAX, 4.0, 7.0, 3.0);
    const srcLen = tokenize(sourceText || "").length;
    const hypLen = tokenize(asr.text).length;
    const lengthRatio = srcLen ? hypLen / srcLen : 1.0;
    if (srcLen && lengthRatio < cfg.MIN_RETELL_RATIO) {
      content *= Math.max(0, lengthRatio / cfg.MIN_RETELL_RATIO);
      notes.push(`复述过短（原文 ${srcLen} 词 / 作答 ${hypLen} 词），内容分按比例衰减`);
    }
    content = clamp(content, 0.0, cfg.C_CONTENT_MAX);

    const langQ = asr.grammar !== null && asr.grammar !== undefined ? clamp(asr.grammar) : sentenceWellformedness(asr.text);
    const language = officialBand(langQ, 3.0, cfg.C_LANG_MAX, 2.0, 2.0, 1.0);

    const wpm = asr.wpm !== null && asr.wpm !== undefined ? asr.wpm : speechRateWpm(asr.text, asr.duration_sec);
    let paceQ = 0.5;
    if (wpm && wpm > 0) paceQ = clamp(1.0 - Math.abs(wpm - cfg.TARGET_WPM) / cfg.TARGET_WPM);
    const pause = asr.pause_ratio;
    const pauseQ = pause !== null && pause !== undefined ? clamp(1.0 - pause) : 0.6;
    const words = tokenize(asr.text);
    const repeatQ = words.length ? clamp((new Set(words).size / words.length) * 1.4) : 0.0;
    const fluQ = clamp(0.45 * paceQ + 0.3 * pauseQ + 0.25 * repeatQ);
    if (pause === null || pause === undefined) notes.push("缺停顿特征，流利度按语速+重复率近似");
    const fluency = officialBand(fluQ, 4.0, cfg.C_FLUENCY_MAX, 2.0, 3.0, 1.0);

    let pronunciation;
    if (asr.pronunciation !== null && asr.pronunciation !== undefined) {
      pronunciation = officialBand(clamp(asr.pronunciation), 3.0, cfg.C_PRON_MAX, 2.0, 2.0, 1.0);
    } else {
      pronunciation = cRatio >= 0.5 ? 2.0 : 1.0;
      notes.push("语音分缺音素级评测，离线保守记 B/C 档（≤2 分）");
    }

    const total = clamp(content + language + fluency + pronunciation, 0.0, cfg.PART_C_MAX);
    return {
      recognized: asr.text,
      content,
      language,
      fluency,
      pronunciation,
      total,
      band: band(total, cfg.PART_C_MAX),
      coverage: `${cov.matched}/${cov.total}`,
      point_scores: cov.per_point.map((s) => Math.round(s * 1000) / 1000),
      wpm: wpm ? Math.round(wpm * 10) / 10 : null,
      length_ratio: Math.round(lengthRatio * 1000) / 1000,
      source: asr.source || "offline",
      notes
    };
  }

  function buildReport(a, b, c, cfg) {
    cfg = cfg || defaultConfig();
    const paper = clamp(a.total + b.total + c.total, 0.0, cfg.PAPER_MAX);
    const finalScore = Math.min(cfg.FINAL_MAX, roundHalfUp(paper / cfg.CONVERT_DIVISOR));
    return {
      partA: a,
      partB: b,
      partC: c,
      paper_score: paper,
      paper_max: cfg.PAPER_MAX,
      final_score: finalScore,
      final_max: cfg.FINAL_MAX,
      band: band(paper, cfg.PAPER_MAX),
      online_used: [a, c, ...b.questions, ...b.answers].some((x) => x.source === "online"),
      config: {
        convert: `÷${cfg.CONVERT_DIVISOR} 四舍五入`,
        target_wpm: cfg.TARGET_WPM,
        weights: {
          A: "语音语调12 + 语速与内容8",
          B: "三问(语言1.5+信息0.5) / 五答(语言0.5+信息1.5)",
          C: "内容12 + 语言4 + 流利5 + 语音3"
        }
      }
    };
  }

  /**
   * 统一批改入口。recordings 形如：
   * { partA: ASRResult, partB: {PartB_Q1: ASRResult, ...}, partC: ASRResult }
   * 返回 { report, legacy }
   */
  function gradeExam(spec, recordings, cfg) {
    cfg = cfg || defaultConfig();
    recordings = recordings || {};
    const paSpec = spec.partA || {};
    const pbSpec = spec.partB || {};
    const pcSpec = spec.partC || {};

    const aAsr = recordings.partA || { text: "", source: "empty" };
    const a = scorePartA(paSpec.hidden_text || "", aAsr, cfg);

    const pbRec = recordings.partB || {};
    const qs = pbSpec.three_questions || [];
    const answers = pbSpec.five_answers || [];
    const bItems = [];
    for (let i = 0; i < qs.length; i++) {
      const asr = pbRec["PartB_Q" + (i + 1)] || { text: "", source: "empty" };
      bItems.push(scorePartBItem(qs[i].hidden_answer || "", asr, i, "question", cfg, qs[i].cn_prompt || ""));
    }
    for (let i = 0; i < answers.length; i++) {
      const asr = pbRec["PartB_A" + (i + 1)] || { text: "", source: "empty" };
      bItems.push(scorePartBItem(answers[i].hidden_answer || "", asr, i, "answer", cfg));
    }
    const b = buildPartB(bItems, cfg);

    const cAsr = recordings.partC || { text: "", source: "empty" };
    const c = scorePartC(
      pcSpec.key_points || "",
      cAsr,
      cfg,
      pcSpec.tts_text || pcSpec.summary || ""
    );

    const report = buildReport(a, b, c, cfg);
    const legacy = {
      partA: {
        recognized: a.recognized,
        wer: Math.round((1.0 - a.word_accuracy) * 10000) / 10000,
        accuracy: Math.round((a.total / cfg.PART_A_MAX) * 10000) / 10000
      },
      partB_three: b.questions.map((i) => ({ recognized: i.recognized, similarity: Math.round((i.total / cfg.B_ITEM_MAX) * 10000) / 10000 })),
      partB_five: b.answers.map((i) => ({ recognized: i.recognized, similarity: Math.round((i.total / cfg.B_ITEM_MAX) * 10000) / 10000 })),
      partC: {
        recognized: c.recognized,
        coverage: c.coverage,
        semantic_sim: Math.round((c.total / cfg.PART_C_MAX) * 10000) / 10000,
        points: c.point_scores
      },
      score_report: report
    };
    return { report, legacy };
  }

  // 导出
  const CELST = {
    normalize,
    tokenize,
    contentWords,
    stem,
    alignWords,
    keyphraseCoverage,
    looksLikeQuestion,
    sentenceWellformedness,
    speechRateWpm,
    roundHalfUp,
    defaultConfig,
    scorePartA,
    scorePartBItem,
    scorePartC,
    buildReport,
    gradeExam
  };

  if (typeof module !== "undefined" && module.exports) module.exports = CELST;
  global.CELST = CELST;
})(typeof window !== "undefined" ? window : this);
