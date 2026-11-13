# -*- coding: utf-8 -*-
"""双端一致性验证：Python 引擎 vs Kotlin 引擎（ScoringParitySmoke.kt）。

运行： python3 tools/verify_parity.py
      优先读 /tmp/parity_kt.txt（本次实际编译 Kotlin 产物运行所得），
      若不存在则回退到随工程交付的 report/parity_kotlin_baseline.txt，
      逐字段比对并生成 report/parity_report.md —— 开箱即可复现。

Kotlin 侧输出约定见 android/ScoringParitySmoke.kt 文件头。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scoring import ScoringConfig, ASRProvider, ASRResult, grade_exam

REF_A = "A young man who lived in London was in love with a beautiful girl."
Q1 = "Do you have to do a part-time job?"
A1 = "She was born in 1990."
KP = "young man, lived in London, beautiful girl, poor, rich"
STORY = ("A young man who lived in London was very poor while the girl was rich. "
         "He wanted to give her a beautiful present but he had very little money.")

SPEC = {
    "partA": {"hidden_text": REF_A},
    "partB": {"three_questions": [{"hidden_answer": Q1}],
              "five_answers": [{"hidden_answer": A1}]},
    "partC": {"key_points": KP, "tts_text": STORY},
}


def online(t):
    return ASRResult(text=t, source="online", pronunciation=0.90,
                     wpm=130.0, pause_ratio=0.10, grammar=0.90)


def offline(t):
    return ASRResult(text=t, source="offline")


class MapProvider(ASRProvider):
    def __init__(self, mapping):
        self.mapping = mapping

    def recognize(self, path):
        return self.mapping.get(path) or ASRResult(source="empty")


def f(x):
    return f"{x:.6f}"


def emit(tag, rep):
    return "|".join([
        tag, f(rep.paper_score), str(rep.final_score), rep.band,
        f(rep.partA.pronunciation), f(rep.partA.pace_content), f(rep.partA.total),
        f(rep.partB.total),
        f(rep.partC.content), f(rep.partC.language), f(rep.partC.fluency),
        f(rep.partC.pronunciation), f(rep.partC.total),
    ])


def run():
    cfg = ScoringConfig()

    def grade(a, q, ans, c):
        m = {"A": a, "Q1": q, "A1": ans, "C": c}
        recs = {"partA": "A" if a.text else "",
                "partB": {"PartB_Q1": "Q1" if q.text else "",
                          "PartB_A1": "A1" if ans.text else ""},
                "partC": "C" if c.text else ""}
        rep, _ = grade_exam(SPEC, recs, MapProvider(m), cfg)
        return rep

    empty = ASRResult(source="empty")
    lines = [
        emit("full", grade(online(REF_A), online(Q1), online(A1), online(STORY))),
        emit("empty", grade(empty, empty, empty, empty)),
        emit("noiseA", grade(offline("blah " * 60), empty, empty, empty)),
        emit("offtopicB", grade(empty, offline("apple banana totally unrelated"),
                                offline("the weather is nice today"), empty)),
        emit("offlineFull", grade(offline(REF_A), offline(Q1), offline(A1), offline(STORY))),
    ]
    from scoring.gd_celst import round_half_up
    lines.append(f"roundHalfUp|{round_half_up(1.5)}|{round_half_up(2.5)}|"
                 f"{round_half_up(58.5 / 3.0)}")

    print("\n".join(lines))

    kt_path = "/tmp/parity_kt.txt"
    if not os.path.exists(kt_path):
        kt_path = os.path.join(ROOT, "report", "parity_kotlin_baseline.txt")
    if not os.path.exists(kt_path):
        print("\n[Kotlin 输出文件不存在，仅打印 Python 基准]", file=sys.stderr)
        return 0
    print(f"[对比基准] {kt_path}", file=sys.stderr)

    kt = [l.strip() for l in open(kt_path, encoding="utf-8") if l.strip()]
    rows = []
    all_ok = True
    for py_line, kt_line in zip(lines, kt):
        p, k = py_line.split("|"), kt_line.split("|")
        tag = p[0]
        diffs = []
        for i, (a, b) in enumerate(zip(p, k)):
            if i == 0:
                continue
            try:
                same = abs(float(a) - float(b)) < 1e-6
            except ValueError:
                same = (a == b)
            if not same:
                diffs.append(f"字段{i}: Python={a} Kotlin={b}")
        ok = not diffs and len(p) == len(k)
        all_ok &= ok
        rows.append((tag, ok, "; ".join(diffs) or "逐字段一致"))

    out = ["# 双端一致性验证报告（Python vs Kotlin）", "",
           "> 运行：`python3 tools/verify_parity.py`（Kotlin 侧由 "
           "`android/ScoringParitySmoke.kt` 编译运行；输出基准随工程交付于 "
           "`report/parity_kotlin_baseline.txt`，开箱即可复现）", "",
           "| 场景 | 结果 | 说明 |", "|---|---|---|"]
    for tag, ok, detail in rows:
        out.append(f"| {tag} | {'✅ 一致' if ok else '❌ 不一致'} | {detail} |")
    out += ["", "## 结论", "",
            ("- Python 与 Kotlin 评分内核在 6 组输入上**逐字段一致**（容差 1e-6），"
             "电脑版与安卓版可对同一份作答给出相同分数。" if all_ok
             else "- 存在不一致字段，需按上表排查双端实现差异。"),
            "- 一致性前提：`scoring/text_utils.py` 的 `_SYNONYM_MAP` 与 "
            "`android/GdCelstScoring.kt` 的 `SYNONYM_MAP` 显式逐条对齐"
            "（不能用 `min(set)` 挑 canon，集合迭代顺序跨平台不确定）。", ""]
    os.makedirs(os.path.join(ROOT, "report"), exist_ok=True)
    with open(os.path.join(ROOT, "report", "parity_report.md"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(out))
    print("\n总体：", "全部一致" if all_ok else "存在差异", file=sys.stderr)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(run())
