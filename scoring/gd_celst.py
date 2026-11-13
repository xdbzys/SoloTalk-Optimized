# -*- coding: utf-8 -*-
"""广东高考英语听说考试（CELST）评分引擎 v3.0

依据：
  * 《广东高考英语听说考试》评分标准（2011年3月版）三大部分档次表；
  * 2021 年起折算规则：卷面满分 60 分 ÷ 3，四舍五入取整 → 计入高考 20 分；
  * 机考实际评分维度：Part A 准确度/流畅度/完整度，
    Part B 语言维度/信息维度，Part C 内容维度/综合维度（语言·流利·语音）。

相对原 SoloTalk 评分逻辑的关键修正：
  1. Part A 由「单一 1-WER」拆为「语音语调 12 + 语速与内容 8」，
     并修复 WER 未钳制导致的负分；
  2. Part B 由「单一 BGE 余弦 ×2」拆为「语言 + 信息」双维度，
     三问(1.5+0.5) / 五答(0.5+1.5) 分别按官方权重计分；
     弃用 `(cos+1)/2` 归一化 —— 该映射使无关文本稳定得 ≈0.5 分，
     是原作者自述「B 偏高」的根因；
  3. Part C 由「要点相似度 ×24」拆为「内容 12 + 语言 4 + 流利 5 + 语音 3」，
     修复把 24 分全压在内容一维、以及 `(词数/20)^2` 拍脑袋长度惩罚；
  4. 新增 60→20 折算、A/B/C 档次、逐维度可解释报告；
  5. 全程零模型依赖（不再加载 130MB 的 BGE ONNX），内存占用从数百 MB 降到常数级。

兼容性：grade_exam() 返回的 `legacy_eval` 完全沿用原 evaluate_recordings()
的字典结构，可直接替换而不改动任何 UI 代码。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Sequence

from .asr_provider import ASRResult, ASRProvider
from .text_utils import (
    align_words, content_words, keyphrase_coverage, looks_like_question,
    normalize, sentence_wellformedness, speech_rate_wpm, stem, tokenize,
)

__all__ = [
    "ScoringConfig", "PartAResult", "PartBItemResult", "PartBResult",
    "PartCResult", "CELSTReport", "score_part_a", "score_part_b_item",
    "score_part_c", "build_report", "grade_exam", "round_half_up",
]


def round_half_up(x: float) -> int:
    """官方「四舍五入」，不能用 Python 内建 round（银行家舍入会让 2.5→2）。"""
    return int(math.floor(x + 0.5))


@dataclass
class ScoringConfig:
    # ── 卷面与折算 ──
    PAPER_MAX: int = 60
    PART_A_MAX: int = 20
    PART_B_MAX: int = 16
    PART_C_MAX: int = 24
    CONVERT_DIVISOR: float = 3.0
    FINAL_MAX: int = 20
    # ── Part A：语音语调 12 + 语速与内容 8 ──
    A_PRON_MAX: float = 12.0
    A_PACE_MAX: float = 8.0
    TARGET_WPM: float = 130.0
    # ── Part B：三问 语言1.5/信息0.5，五答 语言0.5/信息1.5 ──
    B_Q_LANG: float = 1.5
    B_Q_INFO: float = 0.5
    B_A_LANG: float = 0.5
    B_A_INFO: float = 1.5
    B_ITEM_MAX: float = 2.0
    # ── Part C：内容12 语言4 流利5 语音3 ──
    C_CONTENT_MAX: float = 12.0
    C_LANG_MAX: float = 4.0
    C_FLUENCY_MAX: float = 5.0
    C_PRON_MAX: float = 3.0
    # ── 判别阈值 ──
    INFO_HIT_FLOOR: float = 0.30      # 内容词命中低于此值视为「不能传递信息」
    LANG_FLOOR: float = 0.28          # 语言分低于此值记 0（避免随机文本刷分）
    MIN_RETELL_RATIO: float = 0.18    # 复述长度低于原文 18% 时按比例衰减


def _band(score: float, max_score: float) -> str:
    r = score / max(1e-9, max_score)
    return "A" if r >= 0.70 else ("B" if r >= 0.35 else "C")


def _official_band(q: float, a_lo: float, a_hi: float,
                   b_lo: float, b_hi: float, c_hi: float) -> float:
    """按官方 A/B/C 档次表把 0~1 质量分映射到官方分值区间，并在档内线性微调。

    A 档：[a_lo, a_hi]（q ≥ 0.80）
    B 档：[b_lo, b_hi]（0.50 ≤ q < 0.80）
    C 档：[0, c_hi]   （q < 0.50）
    这样既保留官方档次语义，又避免原实现「一个线性相似度乘满分」的失真。
    """
    v = _clamp(q)
    if v >= 0.80:
        return a_lo + (v - 0.80) / 0.20 * (a_hi - a_lo)
    if v >= 0.50:
        return b_lo + (v - 0.50) / 0.30 * (b_hi - b_lo)
    return v / 0.50 * c_hi


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _empty(asr: "ASRResult") -> bool:
    """未录音 / 识别为空 → 该题记 0 分（官方：未作答不得分）。"""
    return not asr.text or not asr.text.strip()


# ────────────────────────────── Part A ──────────────────────────────
@dataclass
class PartAResult:
    recognized: str = ""
    pronunciation: float = 0.0        # 语音语调 0~12
    pace_content: float = 0.0         # 语速与内容 0~8
    total: float = 0.0                # 0~20
    band: str = "C"
    word_accuracy: float = 0.0
    omitted_words: int = 0
    wpm: Optional[float] = None
    source: str = "offline"
    notes: List[str] = field(default_factory=list)


def score_part_a(reference: str, asr: ASRResult, cfg: ScoringConfig | None = None,
                 target_wpm: float | None = None) -> PartAResult:
    """模仿朗读评分。

    语音语调分：优先采用在线评测的 pronunciation（音素级置信度）；
    离线时用词级对齐结果作为可解释的代理，并明确标注为近似。
    语速与内容分：按官方「至多漏 3 词 / 漏几个 / 漏整句或 >10 词」三段式，
    再以语速与目标语速的接近度做微调。
    """
    cfg = cfg or ScoringConfig()
    if _empty(asr):
        return PartAResult(recognized="", source=asr.source,
                           notes=["未作答或识别为空，记 0 分"])
    al = align_words(reference, asr.text)
    notes: List[str] = []

    # ── 语音语调 0~12（官方 A:8-12 / B:4-7 / C:0-3）──
    if asr.pronunciation is not None:
        pron_q = _clamp(asr.pronunciation)
        notes.append("发音分来自在线音素级评测")
    else:
        # 离线近似：正确词占比 + 对齐准确率，二者加权
        hit_ratio = al.hits / max(1, al.ref_len)
        pron_q = _clamp(0.6 * al.accuracy + 0.4 * hit_ratio)
        notes.append("离线近似：以词级对齐准确率代理发音分（建议联网启用发音评测）")
    # 交叉校验：即便在线发音评测给了高分，若识别文本与原文整体对不上
    # （考生念的是别的内容 / 环境噪声），语音语调分也必须随内容对齐一起降级。
    # 否则会出现「朗读完全跑题却拿满 12 分发音分」的漏洞。
    if al.accuracy < 0.35:
        pron_q = min(pron_q, al.accuracy / 0.35 * 0.40)
        notes.append("识别文本与原文不匹配，发音分随内容对齐一并降级")
    pronunciation = _official_band(pron_q, 8.0, cfg.A_PRON_MAX, 4.0, 7.0, 3.0)

    # ── 语速与内容 0~8 ──
    omitted = al.omitted
    if omitted <= 3:
        content = 6.0 + (1.0 - omitted / 4.0) * 2.0        # 6~8
    elif omitted <= 10:
        content = 3.0 + (10 - omitted) / 7.0 * 2.0          # 3~5
    else:
        content = max(0.0, 2.0 - (omitted - 10) * 0.15)     # 0~2
    # 硬约束：整段与原文对不上（大量多读/噪声/背错课文）时，
    # 即便「漏词数」看起来不多，也必须落在官方 C 档（0~2 分）。
    if al.accuracy < 0.35:
        content = min(content, 2.0 * max(0.0, al.accuracy / 0.35))
        notes.append("识别文本与原文整体不匹配，内容完整度按 C 档封顶")
    wpm = asr.wpm if asr.wpm is not None else speech_rate_wpm(asr.text, asr.duration_sec)
    target = target_wpm or cfg.TARGET_WPM
    if wpm and wpm > 0:
        pace_q = _clamp(1.0 - abs(wpm - target) / target)
        # 语速只做 ±0.6 的微调，内容完整度仍是主项（官方表把「内容」列在主位）
        pace_content = _clamp(content + (pace_q - 0.5) * 1.2, 0.0, cfg.A_PACE_MAX)
        notes.append(f"语速 {wpm:.0f} wpm（目标 {target:.0f}）")
    else:
        pace_content = content
        notes.append("缺音频时长，语速维度不参与微调")

    total = _clamp(pronunciation + pace_content, 0.0, cfg.PART_A_MAX)
    # 注意：计算层保留完整精度，不做 round —— 展示层再格式化。
    # 否则与 Kotlin 版（不做 round）会产生 0.0x 级的双端差异。
    return PartAResult(
        recognized=asr.text, pronunciation=pronunciation,
        pace_content=pace_content, total=total,
        band=_band(total, cfg.PART_A_MAX), word_accuracy=round(al.accuracy, 4),
        omitted_words=omitted, wpm=round(wpm, 1) if wpm else None,
        source=asr.source, notes=notes,
    )


# ────────────────────────────── Part B ──────────────────────────────
@dataclass
class PartBItemResult:
    index: int = 0
    kind: str = "question"            # question | answer
    recognized: str = ""
    language: float = 0.0
    information: float = 0.0
    total: float = 0.0
    max_score: float = 2.0
    structure_ok: bool = False
    content_hit: float = 0.0
    spurious: float = 0.0
    source: str = "offline"
    notes: List[str] = field(default_factory=list)


def _info_hit(reference: str, recognized: str) -> tuple:
    """内容词召回 / 精确率 / 无关信息占比。"""
    r = [w for w in content_words(reference)]
    h = [w for w in content_words(recognized)]
    if not r:
        return 0.0, 0.0, 0.0
    rs, hs = set(r), set(h)
    recall = len(rs & hs) / len(rs)
    precision = len(rs & hs) / len(hs) if hs else 0.0
    spurious = 1.0 - precision
    return recall, precision, spurious


def score_part_b_item(reference: str, asr: ASRResult, index: int = 0,
                      kind: str = "question", cfg: ScoringConfig | None = None,
                      cn_prompt: str = "") -> PartBItemResult:
    """角色扮演单题评分（三问或五答），严格按官方「语言 + 信息」双维度。

    三问：语言 1.5（语法结构/选词/疑问句式）、信息 0.5（是否按中文提示提问）
    五答：语言 0.5（是否影响理解）、信息 1.5（是否按要求传递信息）
    """
    cfg = cfg or ScoringConfig()
    if _empty(asr):
        return PartBItemResult(index=index, kind=kind, recognized="", max_score=cfg.B_ITEM_MAX,
                               notes=["未作答或识别为空，记 0 分"])
    is_q = (kind == "question")
    lang_max = cfg.B_Q_LANG if is_q else cfg.B_A_LANG
    info_max = cfg.B_Q_INFO if is_q else cfg.B_A_INFO
    notes: List[str] = []

    # ── 语言维度（官方表格是离散档，不用连续比例乘满分）──
    struct_ok, struct_score = (looks_like_question(asr.text) if is_q else (True, 1.0))
    well = sentence_wellformedness(asr.text)
    al = align_words(reference, asr.text)
    if asr.grammar is not None:
        lang_q = _clamp(asr.grammar)
        notes.append("语言分来自在线语法评测")
    elif is_q:
        # 官方扣分点：疑问词错误、结构不完整、助动词/时态/语序
        lang_q = _clamp(0.50 * struct_score + 0.30 * al.accuracy + 0.20 * well)
        if not struct_ok:
            notes.append("疑问句结构有误（疑问词/助动词语序）")
    else:
        lang_q = _clamp(0.55 * al.accuracy + 0.45 * well)
    if lang_q < cfg.LANG_FLOOR:
        language = 0.0
        notes.append("语言/选词错误导致不能理解，语言维度记 0")
    elif is_q:
        # 三问语言：1.5 全对 / 1.0 基本正确（时态·语态·及物性·主谓一致有误）/ 0
        language = 1.5 if lang_q >= 0.85 else (1.0 if lang_q >= 0.55 else 0.0)
    else:
        # 五答语言：0.5 不影响理解 / 0 严重语法选词错误
        language = 0.5 if lang_q >= 0.50 else 0.0

    # ── 信息维度（官方表格同样是离散档）──
    recall, precision, spurious = _info_hit(reference, asr.text)
    if recall >= 0.80 and spurious <= 0.55:
        info_q = 1.0                       # 按要求传递信息
    elif recall >= 0.45:
        info_q = 0.67                      # 基本传递（漏一两点次要信息/加无关信息）
        notes.append("基本传递信息：漏次要信息或含无关内容")
    else:
        info_q = 0.0                      # 不能按要求传递信息
        if recall < cfg.INFO_HIT_FLOOR:
            notes.append("关键信息缺失")
    if is_q:
        # 三问信息：0.5 基本按要求传递 / 0
        information = info_max if info_q >= 0.67 else 0.0
    else:
        # 五答信息：1.5 完整 / 1.0 基本 / 0
        information = info_max if info_q == 1.0 else (1.0 if info_q >= 0.67 else 0.0)

    total = _clamp(language + information, 0.0, cfg.B_ITEM_MAX)
    return PartBItemResult(
        index=index, kind=kind, recognized=asr.text,
        language=language, information=information,
        total=total, max_score=cfg.B_ITEM_MAX,
        structure_ok=struct_ok, content_hit=round(recall, 3),
        spurious=round(spurious, 3), source=asr.source, notes=notes,
    )


@dataclass
class PartBResult:
    questions: List[PartBItemResult] = field(default_factory=list)
    answers: List[PartBItemResult] = field(default_factory=list)
    total: float = 0.0
    max_score: float = 16.0
    band: str = "C"


def _build_part_b(items: List[PartBItemResult], cfg: ScoringConfig) -> PartBResult:
    q = [i for i in items if i.kind == "question"]
    a = [i for i in items if i.kind == "answer"]
    total = sum(i.total for i in items)
    mx = len(q) * cfg.B_ITEM_MAX + len(a) * cfg.B_ITEM_MAX
    return PartBResult(questions=q, answers=a, total=total,
                       max_score=mx, band=_band(total, mx or cfg.PART_B_MAX))


# ────────────────────────────── Part C ──────────────────────────────
@dataclass
class PartCResult:
    recognized: str = ""
    content: float = 0.0              # 0~12
    language: float = 0.0             # 0~4
    fluency: float = 0.0              # 0~5
    pronunciation: float = 0.0        # 0~3
    total: float = 0.0                # 0~24
    band: str = "C"
    coverage: str = "0/0"
    point_scores: List[float] = field(default_factory=list)
    wpm: Optional[float] = None
    length_ratio: float = 0.0
    source: str = "offline"
    notes: List[str] = field(default_factory=list)


def score_part_c(key_points: str, asr: ASRResult, cfg: ScoringConfig | None = None,
                 source_text: str = "") -> PartCResult:
    """故事复述评分：内容12 + 语言4 + 流利5 + 语音3。"""
    cfg = cfg or ScoringConfig()
    if _empty(asr):
        return PartCResult(recognized="", source=asr.source,
                           notes=["未作答或识别为空，记 0 分"])
    notes: List[str] = []
    cov = keyphrase_coverage(key_points, asr.text)

    # ── 内容 0~12（官方 A:8-12 大多数信息点 / B:4-7 主要 / C:0-3 部分）──
    c_ratio = cov.ratio
    content = _official_band(c_ratio, 8.0, cfg.C_CONTENT_MAX, 4.0, 7.0, 3.0)
    # 长度惩罚：与原文长度挂钩、线性衰减，替换原来拍脑袋的 (词数/20)^2
    src_len = len(tokenize(source_text))
    hyp_len = len(tokenize(asr.text))
    length_ratio = hyp_len / src_len if src_len else 1.0
    if src_len and length_ratio < cfg.MIN_RETELL_RATIO:
        content *= max(0.0, length_ratio / cfg.MIN_RETELL_RATIO)
        notes.append(f"复述过短（原文 {src_len} 词 / 作答 {hyp_len} 词），内容分按比例衰减")
    content = _clamp(content, 0.0, cfg.C_CONTENT_MAX)

    # ── 语言 0~4（官方 A:3-4 规范 / B:2 基本合乎规范 / C:0-1 错误较多）──
    lang_q = _clamp(asr.grammar) if asr.grammar is not None else sentence_wellformedness(asr.text)
    language = _official_band(lang_q, 3.0, cfg.C_LANG_MAX, 2.0, 2.0, 1.0)

    # ── 流利 0~5 ──
    wpm = asr.wpm if asr.wpm is not None else speech_rate_wpm(asr.text, asr.duration_sec)
    pace_q = 0.5
    if wpm and wpm > 0:
        pace_q = _clamp(1.0 - abs(wpm - cfg.TARGET_WPM) / cfg.TARGET_WPM)
    pause = asr.pause_ratio
    pause_q = _clamp(1.0 - pause) if pause is not None else 0.6
    words = tokenize(asr.text)
    repeat_q = _clamp(len(set(words)) / len(words) * 1.4) if words else 0.0
    flu_q = _clamp(0.45 * pace_q + 0.30 * pause_q + 0.25 * repeat_q)
    if pause is None:
        notes.append("缺停顿特征，流利度按语速+重复率近似")
    # 官方 A:4-5 流利 / B:2-3 比较流利 / C:0-1 不够流利
    fluency = _official_band(flu_q, 4.0, cfg.C_FLUENCY_MAX, 2.0, 3.0, 1.0)

    # ── 语音 0~3（官方 A:3 不影响理解 / B:2 有些错误但基本不影响 / C:1 影响理解）──
    if asr.pronunciation is not None:
        pronunciation = _official_band(_clamp(asr.pronunciation), 3.0, cfg.C_PRON_MAX,
                                      2.0, 2.0, 1.0)
    else:
        # 离线：无音素级信号，保守封顶 B 档（2 分），绝不凭文本吻合度给 A 档
        pronunciation = 2.0 if c_ratio >= 0.50 else 1.0
        notes.append("语音分缺音素级评测，离线保守记 B/C 档（≤2 分）")

    total = _clamp(content + language + fluency + pronunciation, 0.0, cfg.PART_C_MAX)
    return PartCResult(
        recognized=asr.text, content=content, language=language,
        fluency=fluency, pronunciation=pronunciation,
        total=total, band=_band(total, cfg.PART_C_MAX),
        coverage=f"{cov.matched}/{cov.total}",
        point_scores=[round(s, 3) for s in cov.per_point],
        wpm=round(wpm, 1) if wpm else None,
        length_ratio=round(length_ratio, 3), source=asr.source, notes=notes,
    )


# ────────────────────────────── 汇总 ──────────────────────────────
@dataclass
class CELSTReport:
    partA: PartAResult
    partB: PartBResult
    partC: PartCResult
    paper_score: float            # 卷面 0~60
    paper_max: float
    final_score: int              # 折算后 0~20（官方四舍五入）
    final_max: int
    band: str
    online_used: bool
    config: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_report(a: PartAResult, b: PartBResult, c: PartCResult,
                 cfg: ScoringConfig | None = None) -> CELSTReport:
    cfg = cfg or ScoringConfig()
    paper = _clamp(a.total + b.total + c.total, 0.0, cfg.PAPER_MAX)
    final = min(cfg.FINAL_MAX, round_half_up(paper / cfg.CONVERT_DIVISOR))
    return CELSTReport(
        partA=a, partB=b, partC=c,
        paper_score=paper, paper_max=cfg.PAPER_MAX,
        final_score=final, final_max=cfg.FINAL_MAX,
        band=_band(paper, cfg.PAPER_MAX),
        online_used=any(x.source == "online" for x in
                        [a, c, *b.questions, *b.answers]),
        config={"convert": f"÷{cfg.CONVERT_DIVISOR:g} 四舍五入",
                "target_wpm": cfg.TARGET_WPM,
                "weights": {"A": "语音语调12 + 语速与内容8",
                            "B": "三问(语言1.5+信息0.5) / 五答(语言0.5+信息1.5)",
                            "C": "内容12 + 语言4 + 流利5 + 语音3"}},
    )


def grade_exam(spec: dict, recordings: dict, provider: ASRProvider,
               cfg: ScoringConfig | None = None) -> tuple:
    """统一批改入口。

    spec: 题目包解析后的字典（字段与 SoloPackage.to_dict() 一致）
        {
          "partA": {"hidden_text": "..."},
          "partB": {"three_questions": [{"cn_prompt","en_answer","hidden_answer"}],
                    "five_answers":  [{"en_question","hidden_answer"}]},
          "partC": {"key_points": "p1, p2, ...", "tts_text": "原文"}
        }
    recordings: {"partA": path, "partB": {"PartB_Q1": path, ..., "PartB_A1": path, ...},
                 "partC": path}
    provider: ASRProvider（AutoASRProvider 即「联网优先 + 离线兜底」）

    返回 (CELSTReport, legacy_eval)。legacy_eval 结构与原 evaluate_recordings()
    完全一致，可直接 return 给现有 UI，无需改动任何显示代码。
    """
    cfg = cfg or ScoringConfig()
    pa_spec = spec.get("partA") or {}
    pb_spec = spec.get("partB") or {}
    pc_spec = spec.get("partC") or {}

    # ── Part A ──
    a_asr = provider.recognize(recordings.get("partA") or "") if recordings.get("partA") else ASRResult(source="empty")
    a = score_part_a(pa_spec.get("hidden_text", ""), a_asr, cfg)

    # ── Part B ──
    pb_rec = recordings.get("partB") or {}
    if isinstance(pb_rec, list):                   # 兼容早期 list 存储
        pb_rec = {**{f"PartB_Q{i+1}": p for i, p in enumerate(pb_rec[:3])},
                  **{f"PartB_A{i+1}": p for i, p in enumerate(pb_rec[3:])}}
    qs = pb_spec.get("three_questions") or []
    answers = pb_spec.get("five_answers") or []
    b_items: List[PartBItemResult] = []
    for i, q in enumerate(qs):
        path = pb_rec.get(f"PartB_Q{i+1}")
        asr = provider.recognize(path) if path else ASRResult(source="empty")
        b_items.append(score_part_b_item(q.get("hidden_answer", ""), asr, i, "question",
                                         cfg, q.get("cn_prompt", "")))
    for i, ans in enumerate(answers):
        path = pb_rec.get(f"PartB_A{i+1}")
        asr = provider.recognize(path) if path else ASRResult(source="empty")
        b_items.append(score_part_b_item(ans.get("hidden_answer", ""), asr, i, "answer", cfg))
    b = _build_part_b(b_items, cfg)

    # ── Part C ──
    c_path = recordings.get("partC")
    c_asr = provider.recognize(c_path) if c_path else ASRResult(source="empty")
    c = score_part_c(pc_spec.get("key_points", ""), c_asr, cfg,
                     source_text=pc_spec.get("tts_text", "") or pc_spec.get("summary", ""))

    report = build_report(a, b, c, cfg)

    # ── 向后兼容输出（原 UI 读的字段）──
    legacy_eval = {
        "partA": {
            "recognized": a.recognized,
            "wer": round(1.0 - a.word_accuracy, 4),
            "accuracy": round(a.total / cfg.PART_A_MAX, 4),
        },
        "partB_three": [
            {"recognized": i.recognized, "similarity": round(i.total / cfg.B_ITEM_MAX, 4)}
            for i in b.questions
        ],
        "partB_five": [
            {"recognized": i.recognized, "similarity": round(i.total / cfg.B_ITEM_MAX, 4)}
            for i in b.answers
        ],
        "partC": {
            "recognized": c.recognized,
            "coverage": c.coverage,
            "semantic_sim": round(c.total / cfg.PART_C_MAX, 4),
            "points": c.point_scores,
        },
        # 新增字段：旧 UI 会忽略，新 UI 可展示逐维度明细
        "score_report": report.to_dict(),
    }
    return report, legacy_eval
