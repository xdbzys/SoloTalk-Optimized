# -*- coding: utf-8 -*-
"""原 SoloTalk v2.6 评分逻辑的最小复现，仅用于 verify_scoring.py 做对照实验。

原实现（SoloTalk.py L840-937, L988-1111, L6085-6122）：
  * Part A: score = (1 - WER) × 20            —— WER 未钳制，可为负
  * Part B: 每题 score = sim × 2              —— sim 为 BGE (cos+1)/2 或 Jaccard
  * Part C: score = mean(max(词袋命中, BGE语义)) × 24，再乘 (词数/20)^2
  * 无 60→20 折算、无 A/B/C 档次、无双维度拆分
"""
from __future__ import annotations

from typing import List


def levenshtein_wer(ref: str, hyp: str):
    r, h = ref.lower().split(), hyp.lower().split()
    n = len(r)
    if n == 0:
        return 0.0, 1.0
    prev = list(range(len(h) + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * len(h)
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    wer = prev[len(h)] / n          # ← 无上界：识别文本过长时 wer > 1
    return wer, 1.0 - wer          # ← accuracy 可为负


def jaccard(a: str, b: str) -> float:
    s1, s2 = set(a.lower().split()), set(b.lower().split())
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)


def bge_like_similarity(a: str, b: str) -> float:
    """原 BGE 归一化 (cos+1)/2 的行为近似：

    真实 BGE 对语义无关的两句英文，cos 通常落在 0.0~0.3 区间，
    经 (cos+1)/2 映射后得到 0.50~0.65 —— 即「胡说八道也拿一半分」。
    这里用 Jaccard 生成一个相似量级的伪 cos，再套用同一映射，
    以便在无 ONNX 模型的环境下复现该系统性偏差。
    """
    raw = jaccard(a, b) * 0.6          # 伪 cos ≈ 0~0.6
    return max(0.0, min(1.0, (raw + 1.0) / 2.0))


def partC_point_scores(recognized: str, key_points: str) -> List[float]:
    points = [p.strip() for p in key_points.split(",") if p.strip()]
    if not points or not recognized.strip():
        return [0.0] * len(points)
    hw = recognized.lower().split()
    scores = []
    for p in points:
        pw = [w for w in p.lower().split() if w]
        distinct = set(pw)
        wb = sum(1 for w in distinct if w in hw) / len(distinct) if distinct else 0.0
        sem = bge_like_similarity(p, recognized)
        scores.append(max(wb, sem))
    n = max(1, len(hw))
    penalty = min(1.0, (n / 20.0) ** 2)      # ← 原实现的长度惩罚
    return [s * penalty for s in scores]


def grade_legacy(spec: dict, recognized: dict) -> dict:
    """recognized: {'partA': str, 'partB_three': [str], 'partB_five': [str], 'partC': str}

    返回与原 _eval_total_score 一致的卷面分（0~60，可能为负）。
    """
    pa = spec.get("partA", {})
    pb = spec.get("partB", {})
    pc = spec.get("partC", {})

    wer, acc = levenshtein_wer(pa.get("hidden_text", ""), recognized.get("partA", ""))
    a_score = acc * 20                                   # ← 可能为负

    b_score = 0.0
    for i, q in enumerate(pb.get("three_questions", [])):
        hyp = (recognized.get("partB_three") or [""] * 99)[i] if i < len(recognized.get("partB_three") or []) else ""
        b_score += bge_like_similarity(q.get("hidden_answer", ""), hyp) * 2
    for i, a in enumerate(pb.get("five_answers", [])):
        hyp = (recognized.get("partB_five") or [""] * 99)[i] if i < len(recognized.get("partB_five") or []) else ""
        b_score += bge_like_similarity(a.get("hidden_answer", ""), hyp) * 2

    scores = partC_point_scores(recognized.get("partC", ""), pc.get("key_points", ""))
    sem = sum(scores) / len(scores) if scores else 0.0
    c_score = sem * 24

    return {
        "partA": round(a_score, 2),
        "partB": round(b_score, 2),
        "partC": round(c_score, 2),
        "paper": round(a_score + b_score + c_score, 2),
        "final_20": None,        # 原实现没有折算
        "band": None,            # 原实现没有档次
    }
