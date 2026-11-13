# -*- coding: utf-8 -*-
"""文本处理工具：归一化、分词、对齐、要点覆盖、轻量语法检查。

设计约束（内存优化目标）：
  * 纯标准库，零第三方依赖，不加载任何模型；
  * 所有函数 O(n) 或 O(n*m) 且 m 为短文本长度，不产生大中间对象；
  * 不使用 set(whole_corpus) 之类的全量缓存，停用词表为模块级 frozenset。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Sequence, Tuple

__all__ = [
    "normalize", "tokenize", "content_words", "stem", "is_stopword",
    "align_words", "Alignment", "keyphrase_coverage", "Coverage",
    "sentence_wellformedness", "speech_rate_wpm", "looks_like_question",
]

_PUNCT_RE = re.compile(r"[^a-z0-9'\s]+")
_WS_RE = re.compile(r"\s+")

# 高考听说高频功能词/填充词。评分时排除，避免「把 the/a/is 说对了」拿分。
STOPWORDS = frozenset("""
a an the and or but if then than so because although though while of in on at to for from with
by as into onto over under about above below up down out off again further once here there when
where why how all any both each few more most other some such no nor not only own same too very
can will just don should now i you he she it we they me him her us them my your his its our their
this that these those am is are was were be been being have has had having do does did doing
would could shall may might must shall will 's 't 're 've 'll 'd 'm
um uh er ah like well okay ok yeah
""".split())

# 轻量不规则动词/名词映射，避免引入 nltk/spacy（那是数百 MB 的内存开销）。
_IRREGULAR = {
    "was": "be", "were": "be", "is": "be", "are": "be", "am": "be", "been": "be", "being": "be",
    "had": "have", "has": "have", "having": "have",
    "did": "do", "does": "do", "doing": "do",
    "went": "go", "gone": "go", "going": "go",
    "got": "get", "gotten": "get", "getting": "get",
    "made": "make", "making": "make",
    "took": "take", "taken": "take", "taking": "take",
    "gave": "give", "given": "give", "giving": "give",
    "found": "find", "finding": "find",
    "told": "tell", "telling": "tell",
    "saw": "see", "seen": "see", "seeing": "see",
    "said": "say", "saying": "say",
    "bought": "buy", "brought": "bring", "thought": "think",
    "felt": "feel", "left": "leave", "kept": "keep", "slept": "sleep",
    "men": "man", "women": "woman", "children": "child", "people": "person",
    "mice": "mouse", "feet": "foot", "teeth": "tooth",
    "better": "good", "best": "good", "worse": "bad", "worst": "bad",
}

# 常见同义/近义归并（高考听说答案里高频的「用自己的语言复述」情形）。
# ⚠️ 显式写死 canon，不要用 min(set, key=len)：集合迭代顺序在 Python / Kotlin
# 之间不确定（例如 {"vase","jar","pot"} 里 jar 与 pot 同为 3 字符），
# 会让同一份作答在电脑版与安卓版得到不同分数。此表与
# android/GdCelstScoring.kt 的 SYNONYM_MAP 必须逐条保持一致。
_SYNONYM_MAP: dict = {
    "present": "gift", "gift": "gift",
    "buy": "buy", "purchase": "buy", "bought": "buy", "purchased": "buy",
    "poor": "poor", "broke": "poor",
    "rich": "rich", "wealthy": "rich", "well-off": "rich",
    "shop": "shop", "store": "shop", "market": "shop",
    "manager": "boss", "owner": "boss", "shopkeeper": "boss", "boss": "boss",
    "vase": "vase", "jar": "vase", "pot": "vase",
    "break": "break", "broken": "break", "smash": "break",
    "smashed": "break", "shatter": "break", "pieces": "break",
    "birthday": "birthday",
    "girlfriend": "girlfriend", "girl": "girlfriend",
    "surprise": "surprise", "surprised": "surprise",
    "amazed": "surprise", "shocked": "surprise",
    "help": "help", "helped": "help", "assist": "help", "assisted": "help",
    "plan": "plan", "planned": "plan", "idea": "plan", "scheme": "plan",
    "worker": "worker", "employee": "worker",
    "pack": "pack", "packed": "pack", "wrap": "pack",
    "wrapped": "pack", "package": "pack",
    "drop": "drop", "dropped": "drop", "fall": "drop", "fell": "drop",
    "guest": "guest", "guests": "guest", "visitor": "guest", "visitors": "guest",
    "expensive": "expensive", "costly": "expensive", "dear": "expensive",
    "decide": "decide", "decided": "decide", "decision": "decide",
    "want": "want", "wanted": "want", "wish": "want",
    "wished": "want", "hope": "want", "hoped": "want",
}


def normalize(text: str) -> str:
    """统一为小写英文词串，去标点、去重音、压缩空白。"""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def tokenize(text: str) -> List[str]:
    return normalize(text).split()


def is_stopword(word: str) -> bool:
    return word in STOPWORDS


def stem(word: str) -> str:
    """极轻量词形归一：先查不规则表/同义表，再做常见后缀剥离。"""
    w = word.lower().strip("'")
    if not w:
        return ""
    if w in _IRREGULAR:
        w = _IRREGULAR[w]
    if w in _SYNONYM_MAP:
        return _SYNONYM_MAP[w]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 5 and w.endswith("ing"):
        base = w[:-3]
        if len(base) > 2 and base[-1] == base[-2] and base[-1] not in "aeiou":
            base = base[:-1]
        return base
    if len(w) > 4 and w.endswith("ed"):
        base = w[:-2]
        if len(base) > 2 and base[-1] == base[-2] and base[-1] not in "aeiou":
            base = base[:-1]
        return base
    if len(w) > 4 and w.endswith("es") and not w.endswith(("ses", "xes", "ches", "shes")):
        return w[:-2] + ("s" if w[-3:-2] in "s" else "")
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def content_words(text: str) -> List[str]:
    """去停用词并做词形归一，保留顺序。"""
    return [stem(w) for w in tokenize(text) if w not in STOPWORDS]


class Alignment:
    """词级对齐结果（Levenshtein 回溯，仅记录统计量，不保存整条路径）。"""

    __slots__ = ("ref_len", "hyp_len", "hits", "substitutions", "deletions",
                 "insertions", "accuracy", "omitted", "omitted_ratio")

    def __init__(self, ref_len, hyp_len, hits, substitutions, deletions, insertions):
        self.ref_len = ref_len
        self.hyp_len = hyp_len
        self.hits = hits
        self.substitutions = substitutions
        self.deletions = deletions
        self.insertions = insertions
        # 关键修复：原实现 wer = edit / ref_len 未做上界约束，
        # 当识别文本远长于原文（重复、环境噪声）时 wer > 1 → accuracy 为负 → 负分。
        self.accuracy = max(0.0, 1.0 - (substitutions + deletions + insertions) / max(1, ref_len))
        self.omitted = deletions + substitutions
        self.omitted_ratio = self.omitted / max(1, ref_len)


def align_words(ref: str, hyp: str) -> Alignment:
    """参考文本 vs 识别文本的词级编辑对齐。

    与原 levenshtein_wer 的差异：
      1. 使用归一化文本（去标点/大小写），避免标点差异误判；
      2. accuracy 钳制在 [0,1]；
      3. 回溯统计「正确/替换/漏读/多读」，供 Part A 完整度与语音分使用。
    """
    r = tokenize(ref)
    h = tokenize(hyp)
    n, m = len(r), len(h)
    if n == 0:
        return Alignment(0, m, 0, 0, 0, m)
    # 滚动数组，内存 O(m) 而非 O(n*m)
    prev = list(range(m + 1))
    # 为回溯需要的操作类型，保留一个极小的 (n+1)*(m+1) 字节矩阵；
    # 单句通常 n<200、m<200，约 40KB，可忽略。
    ops = bytearray((n + 1) * (m + 1))
    W = m + 1
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            diag = prev[j - 1] + cost
            dele = prev[j] + 1
            ins = cur[j - 1] + 1
            best = min(diag, dele, ins)
            cur[j] = best
            ops[i * W + j] = 0 if best == diag else (1 if best == dele else 2)
        prev = cur
    hits = subs = dele = ins = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i == 0:
            ins += 1; j -= 1; continue
        if j == 0:
            dele += 1; i -= 1; continue
        op = ops[i * W + j]
        if op == 0:
            if r[i - 1] == h[j - 1]:
                hits += 1
            else:
                subs += 1
            i -= 1; j -= 1
        elif op == 1:
            dele += 1; i -= 1
        else:
            ins += 1; j -= 1
    return Alignment(n, m, hits, subs, dele, ins)


class Coverage:
    __slots__ = ("matched", "total", "ratio", "per_point", "spurious")

    def __init__(self, matched, total, ratio, per_point, spurious):
        self.matched = matched
        self.total = total
        self.ratio = ratio
        self.per_point = per_point
        self.spurious = spurious


def _phrase_hit(point: str, hyp_content: Sequence[str], hyp_raw: str) -> float:
    """单条要点命中度 0~1。

    与原实现 max(词袋命中率, BGE余弦) 的关键差异：
      * 原实现的 BGE 相似度被 `(x+1)/2` 映射到 [0,1]，导致两句完全无关的
        随机文本也稳定得到 ≈0.5 分，是「Part B/C 系统性虚高」的根因；
      * 这里用「词形归一后的内容词命中 + 短语整体出现 + 同义归并」，
        并设 0.5 的硬门槛：低于门槛记 0，杜绝随机文本刷分。
    """
    p_words = [stem(w) for w in tokenize(point) if w not in STOPWORDS]
    if not p_words:
        return 0.0
    # 整条短语原样出现（允许词形变化）→ 直接满分
    p_stem_join = " ".join(p_words)
    h_stem_join = " ".join(hyp_content)
    if p_stem_join and p_stem_join in h_stem_join:
        return 1.0
    hs = set(hyp_content)
    hit = sum(1 for w in set(p_words) if w in hs)
    ratio = hit / len(set(p_words))
    # 硬门槛：命中不足一半视为未覆盖；其余按 0.5→1 线性放大
    return 0.0 if ratio < 0.5 else min(1.0, (ratio - 0.5) * 2.0)


def keyphrase_coverage(key_points: str, recognized: str) -> Coverage:
    """按英文逗号分隔的要点串，逐条计算覆盖。"""
    points = [p.strip() for p in (key_points or "").split(",") if p.strip()]
    if not points:
        return Coverage(0, 0, 0.0, [], 0.0)
    hyp_content = content_words(recognized)
    hyp_raw = normalize(recognized)
    per = [_phrase_hit(p, hyp_content, hyp_raw) for p in points]
    matched = sum(1 for s in per if s >= 0.80)
    ratio = sum(per) / len(per) if per else 0.0
    # 无关信息比例：识别文本里既不在要点也不在常见功能词的内容词占比（用于「信息」维度扣分）
    ref_vocab = set()
    for p in points:
        ref_vocab.update(stem(w) for w in tokenize(p) if w not in STOPWORDS)
    extra = sum(1 for w in hyp_content if w not in ref_vocab)
    spurious = extra / max(1, len(hyp_content))
    return Coverage(matched, len(points), ratio, per, min(1.0, spurious))


_Q_WORDS = frozenset("what when where why who whom whose which how".split())
_AUX = frozenset("""
am is are was were do does did have has had can could will would shall should may might must
""".split())


def looks_like_question(text: str) -> Tuple[bool, float]:
    """三问的疑问句结构校验，返回 (是否合法疑问句, 结构分 0~1)。

    官方「提问-语言」扣分点：疑问词错误、结构不完整、助动词/系动词/情态动词
    误用或位置错乱、时态混乱、语序颠倒。这里逐项检查并给出可解释的结构分。
    """
    words = tokenize(text)
    if not words:
        return False, 0.0
    checks = []
    # 1) 疑问句必须以疑问词或助动词/系动词/情态动词开头
    first = words[0]
    checks.append(1.0 if (first in _Q_WORDS or first in _AUX) else 0.0)
    # 2) 含疑问词或为一般疑问句（不以陈述句主语起头）
    has_q = any(w in _Q_WORDS for w in words)
    checks.append(1.0 if (has_q or first in _AUX) else 0.0)
    # 3) 若以疑问词开头，其后应紧跟助动词/系动词/情态动词（特殊疑问句语序）
    if first in _Q_WORDS:
        checks.append(1.0 if len(words) > 1 and words[1] in _AUX else 0.35)
    else:
        checks.append(1.0)
    # 4) 长度合理（不少于 3 词、不多于 25 词）
    checks.append(1.0 if 3 <= len(words) <= 25 else 0.4)
    score = sum(checks) / len(checks)
    return (score >= 0.6), score


def sentence_wellformedness(text: str) -> float:
    """轻量语法/语言规范度 0~1（Part C「语言」维度、Part B「语言」维度兜底）。

    纯启发式，不依赖模型：句子长度分布、是否含谓语、时态一致性、重复词、
    以及是否只是零散单词堆砌。用于在没有在线语法评测时给出可解释的近似。
    """
    words = tokenize(text)
    if len(words) < 3:
        return 0.1 if words else 0.0
    score = 1.0
    # 零散堆砌：实词占比过高且无任何功能词 → 更像背单词而非复述
    func = sum(1 for w in words if w in STOPWORDS)
    if func / len(words) < 0.12:
        score -= 0.30
    # 过多重复
    uniq = len(set(words))
    if uniq / len(words) < 0.45:
        score -= 0.25
    # 超长无标点（识别文本通常无标点，故用长度软惩罚）
    if len(words) > 160:
        score -= 0.15
    return max(0.0, min(1.0, score))


def speech_rate_wpm(text: str, duration_sec: float | None) -> float | None:
    """语速（词/分钟）。duration 无效时返回 None。"""
    if not duration_sec or duration_sec <= 0:
        return None
    return len(tokenize(text)) * 60.0 / duration_sec
