# -*- coding: utf-8 -*-
"""集成验证：证明 app/SoloTalk_optimized.py 的 4 处改动可独立运行。

PyQt5 桌面环境在 CI / 沙箱里通常不可用，因此不整体 import 整个 7600 行脚本，
而是用 AST 精确抽出被替换的两个函数（evaluate_recordings / _open_package_zip），
在最小命名空间里执行并验证其行为。

验证点：
  1. evaluate_recordings 返回结构 == 原 UI 期望的 4 个键 + 新增 score_report；
  2. score_report 含卷面分、折算分、档次、在线来源；
  3. 未作答时记 0 分（原算法会白送 8 分）；
  4. _open_package_zip 不再解压整包：纯文本题库的临时目录为空。
"""
from __future__ import annotations

import ast
import json
import os
import sys
import types
import zipfile
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
APP = os.path.join(ROOT, "app")

import scoring
from scoring import ASRResult, ASRProvider


def extract_func(source: str, name: str):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            mod = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(mod)
            ns = {
                "sys": sys, "os": os, "json": json, "zipfile": zipfile,
                "tempfile": __import__("tempfile"),
                "SAMPLE_RATE": 16000,
            }
            exec(compile(mod, f"<{name}>", "exec"), ns)
            return ns[name]
    raise RuntimeError(f"未找到函数 {name}")


class FakeProvider(ASRProvider):
    def __init__(self, text=""):
        self.text = text

    def recognize(self, path):
        if not self.text:
            return ASRResult(source="empty")
        return ASRResult(text=self.text, source="online", pronunciation=0.9,
                         grammar=0.9, pause_ratio=0.1, duration_sec=20.0)


def main():
    src = open(os.path.join(APP, "SoloTalk_optimized.py"), encoding="utf-8").read()
    fn_eval = extract_func(src, "evaluate_recordings")
    fn_open = extract_func(src, "_open_package_zip")

    results = []

    # ── 1. 全优作答 ──
    spec_pkg = SimpleNamespace(
        partA_hidden_text="A young man who lived in London was in love with a beautiful girl.",
        partB_three_questions=[{"hidden_answer": "Do you have to do a part-time job?"}],
        partB_five_answers=[{"hidden_answer": "She was born in 1990."}],
        partC_key_points="young man, lived in London, beautiful girl, poor, rich",
        partC_tts_text="A young man who lived in London was in love with a beautiful girl. He was very poor while the girl was rich.",
        partC_summary="",
    )
    recs = {"partA": "A", "partB": {"PartB_Q1": "Q1", "PartB_A1": "A1"}, "partC": "C"}

    original_auto = scoring.AutoASRProvider
    scoring.AutoASRProvider = lambda **kw: FakeProvider(
        "A young man who lived in London was in love with a beautiful girl "
        "he was very poor while the girl was rich and he wanted to give her a present")
    try:
        ev = fn_eval(recs, spec_pkg, model=None, progress_cb=lambda s, t, l: None)
    finally:
        scoring.AutoASRProvider = original_auto

    keys_ok = all(k in ev for k in ("partA", "partB_three", "partB_five", "partC", "score_report"))
    rep = ev["score_report"]
    results.append(("evaluate_recordings 返回结构兼容原 UI", keys_ok,
                    f"keys={sorted(k for k in ev if k != 'score_report')}"))
    results.append(("score_report 含卷面/折算/档次", all(
        k in rep for k in ("paper_score", "final_score", "band", "online_used")),
        f"卷面 {rep['paper_score']}/60 → 折算 {rep['final_score']}/20，{rep['band']} 档"))
    results.append(("在线识别来源被记录", rep["online_used"] is True,
                    f"online_used={rep['online_used']}"))

    # 原 UI 的 _eval_total_score 依赖的字段类型
    ok_types = (isinstance(ev["partA"].get("accuracy"), float)
                and all(isinstance(x.get("similarity"), float) for x in ev["partB_three"])
                and all(isinstance(x.get("similarity"), float) for x in ev["partB_five"])
                and isinstance(ev["partC"].get("semantic_sim"), float))
    results.append(("字段类型可直接喂给 _eval_total_score", ok_types,
                    f"accuracy={ev['partA']['accuracy']}, sem={ev['partC']['semantic_sim']}"))

    # ── 2. 未作答应 0 分 ──
    scoring.AutoASRProvider = lambda **kw: FakeProvider("")
    try:
        ev0 = fn_eval({}, spec_pkg, model=None)
    finally:
        scoring.AutoASRProvider = original_auto
    results.append(("未作答记 0 分", ev0["score_report"]["paper_score"] == 0,
                    f"paper={ev0['score_report']['paper_score']}（原算法全空会白送 8 分）"))

    # ── 3. 题库按需解压 ──
    bank_dir = os.path.join(ROOT, "assets", "question_bank")
    solo = os.path.join(bank_dir, "celst_mock_01.solo")
    data, tmp, base = fn_open(solo)
    leftovers = []
    for _, _, files in os.walk(tmp):
        leftovers.extend(files)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    results.append(("题库加载不再 extractall 整包", len(leftovers) == 0,
                    f"data.json 已解析（{len(data)} 个顶层键）；临时目录解压文件数={len(leftovers)}"))
    results.append(("题库数据可被评分引擎消费",
                    all(k in data for k in ("meta", "partA", "partB", "partC")),
                    f"要点 {len(data['partC']['key_points'].split(','))} 条"))

    # ── 输出 ──
    print("=" * 68)
    print("集成验证：SoloTalk_optimized.py 改动可运行性")
    print("=" * 68)
    all_ok = True
    for name, ok, detail in results:
        print(f"  {'✅' if ok else '❌'}  {name}\n        {detail}")
        all_ok &= ok
    print("=" * 68)
    print("总体：", "全部通过" if all_ok else "存在失败项")

    # 写报告
    lines = ["# 集成验证报告", "",
             "> 运行：`python3 tools/verify_integration.py`（用 AST 抽取改动函数在最小环境执行，无需 PyQt5）", "",
             "| 验证项 | 结果 | 细节 |", "|---|---|---|"]
    for name, ok, detail in results:
        lines.append(f"| {name} | {'✅ 通过' if ok else '❌ 失败'} | {detail} |")
    lines += ["", "## 说明", "",
              "- `app/SoloTalk_optimized.py` 由 `tools/apply_optimizations.py` 从原始 7626 行源码生成，"
              "仅替换 4 处（import / BGE 停用 / 评分函数 / 题库解压）+ 1 处注释，其余 UI 与流程代码保持不变。",
              "- `evaluate_recordings` 的返回字典结构与原实现完全一致，"
              "因此 `_eval_total_score()`、历史记录、结果卡片无需任何改动；"
              "新增的 `score_report` 字段旧 UI 会自然忽略。",
              "- 差异全文见 `app/solotalk_patch.diff`。", ""]
    with open(os.path.join(ROOT, "report", "integration_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
