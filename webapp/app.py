# -*- coding: utf-8 -*-
"""SoloTalk 听说练习 Web 应用（Flask 后端）。

提供：
  GET  /                     单页应用
  GET  /api/bank             题库索引（18 套，含出处元数据）
  GET  /api/paper/<id>       单套题内容（双格式字段，供前端练习）
  GET  /api/audio/<id>/<n>   用户上传原题内置的第 n 段听力音频（按需流式读取）
  POST /api/score            提交作答 → 调用已验证的 CELST 评分引擎 → 逐维度报告
  GET  /api/scoring-info     评分标准说明
  GET  /download/<name>      打包下载（题库 / 源码 / 文档 / 完整工程）
  GET  /downloads/<file>     静态下载文件
  GET  /health               健康检查

启动： python3 webapp/app.py   （监听 $PORT，默认 3000，绑定 0.0.0.0）
"""
from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from typing import Dict

from flask import Flask, jsonify, request, send_file, send_from_directory, Response

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK_DIR = os.path.join(ROOT, "assets", "question_bank")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
DOWNLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
sys.path.insert(0, ROOT)

from scoring import (  # noqa: E402
    ScoringConfig, grade_exam, score_part_a, score_part_b_item, score_part_c,
    build_report,
)
from scoring.asr_provider import ASRResult, ASRProvider  # noqa: E402
from scoring.text_utils import align_words  # noqa: E402

app = Flask(__name__, static_folder=None)


# ───────────────────────────── 题库 ─────────────────────────────
def _index() -> dict:
    with open(os.path.join(BANK_DIR, "bank_index.json"), encoding="utf-8") as f:
        return json.load(f)


def _paper_spec(pid: str) -> dict:
    idx = _index()
    entry = next((p for p in idx["packages"] if p["id"] == pid), None)
    if not entry:
        raise KeyError(pid)
    with zipfile.ZipFile(os.path.join(BANK_DIR, entry["file"])) as zf:
        cands = [n for n in zf.namelist() if n == "data.json" or n.endswith("/data.json")]
        with zf.open(min(cands, key=lambda n: n.count("/"))) as f:
            return json.loads(f.read().decode("utf-8"))


@app.get("/api/bank")
def api_bank():
    idx = _index()
    return jsonify({
        "schema": idx["schema"], "count": idx["count"],
        "generated": idx["generated"], "categories": idx["categories"],
        "note": idx["note"],
        "packages": [{k: p[k] for k in (
            "id", "name", "level", "paper_type", "category", "category_cn",
            "year", "paper_code", "region", "urls", "fidelity", "source_note",
            "partA_words", "partB_three", "partB_five", "partC_words",
            "key_points", "bytes", "media_embedded", "media_files")}
            for p in idx["packages"]],
    })


@app.get("/api/paper/<pid>")
def api_paper(pid):
    try:
        spec = _paper_spec(pid)
    except KeyError:
        return jsonify({"error": "题目不存在"}), 404
    src = spec.get("meta", {}).get("source", {})
    a = spec.get("partA") or {}
    b = spec.get("partB") or {}
    c = spec.get("partC") or {}
    return jsonify({
        "id": pid,
        "name": spec.get("meta", {}).get("name", ""),
        "level": spec.get("meta", {}).get("level", ""),
        "source": src,
        "partA": {
            "hidden_text": a.get("hidden_text", ""),
            "tts_text": a.get("tts_text", "") or a.get("hidden_text", ""),
        },
        "partB": {
            "situation": b.get("situation", ""),
            "listening_text": b.get("listening_text", ""),
            "three_questions": b.get("three_questions", []),
            "five_answers": b.get("five_answers", []),
            "secA": spec.get("partB_secA", []),
            "secB": spec.get("partB_secB", {}),
        },
        "partC": {
            "summary": c.get("summary", ""), "keywords": c.get("keywords", ""),
            "tts_text": c.get("tts_text", ""), "key_points": c.get("key_points", ""),
            "secA": spec.get("partC_secA", {}), "secB": spec.get("partC_secB", {}),
        },
        "media_embedded": any((s.get("audio") for s in spec.get("partB_secA", []))),
    })


@app.get("/api/audio/<pid>/<int:n>")
def api_audio(pid, n):
    """按需从 .solo 里流式读取单个听力音频，不解压整包（内存优化）。"""
    try:
        idx = _index()
        entry = next(p for p in idx["packages"] if p["id"] == pid)
        if not entry.get("media_files") or not (0 <= n < len(entry["media_files"])):
            return jsonify({"error": "该套题无内置音频"}), 404
        rel = entry["media_files"][n]
        with zipfile.ZipFile(os.path.join(BANK_DIR, entry["file"])) as zf:
            if rel not in zf.namelist():
                return jsonify({"error": "音频不存在"}), 404
            data = zf.read(rel)
        return Response(data, mimetype="audio/mpeg",
                        headers={"Content-Length": str(len(data)),
                                 "Cache-Control": "public, max-age=86400"})
    except (KeyError, StopIteration):
        return jsonify({"error": "题目不存在"}), 404


# ───────────────────────────── 评分 ─────────────────────────────
class _TextASRProvider(ASRProvider):
    """把浏览器语音识别 / 手动输入的文本包装成识别结果。

    浏览器端 Web Speech API 只提供文本，没有音素级置信度，因此
    pronunciation / grammar / pause_ratio 留空 → 评分引擎自动走
    「离线近似」并在报告里标注；若在线评测端点已配置则由集成方补充。
    """

    def __init__(self, answers: Dict[str, dict]):
        self.answers = answers or {}

    @staticmethod
    def _asr(d: dict | None) -> ASRResult:
        if not d:
            return ASRResult(source="empty")
        text = str(d.get("text") or "").strip()
        if not text:
            return ASRResult(source="empty")
        r = ASRResult(
            text=text, source=str(d.get("source") or "offline"),
            duration_sec=_pos(d.get("duration_sec")),
            pause_ratio=_clamp01(d.get("pause_ratio")),
            wpm=_pos(d.get("wpm")),
        )
        pron = _clamp01(d.get("pronunciation"))
        gram = _clamp01(d.get("grammar"))
        if pron is not None:
            r.pronunciation = pron
        if gram is not None:
            r.grammar = gram
        return r

    def recognize(self, key: str) -> ASRResult:
        return self._asr(self.answers.get(key))


def _pos(v):
    try:
        x = float(v)
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def _clamp01(v):
    if v is None:
        return None
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


@app.post("/api/score")
def api_score():
    """提交作答，返回逐维度 CELST 评分报告。

    body: {
      "paper_id": "gd2023_celst_a",
      "answers": {
        "partA": {"text": "...", "duration_sec": 20},
        "PartB_Q1": {...}, "PartB_A1": {...},
        "partC": {"text": "...", "duration_sec": 45}
      }
    }
    """
    body = request.get_json(silent=True) or {}
    pid = str(body.get("paper_id") or "")
    answers = body.get("answers") or {}
    try:
        spec = _paper_spec(pid)
    except KeyError:
        return jsonify({"error": "题目不存在"}), 404

    # 构造 recordings 键（grade_exam 用键名向 provider 取识别结果）
    three = (spec.get("partB") or {}).get("three_questions") or []
    five = (spec.get("partB") or {}).get("five_answers") or []
    recs = {
        "partA": "partA",
        "partB": {**{f"PartB_Q{i+1}": f"PartB_Q{i+1}" for i in range(len(three))},
                  **{f"PartB_A{i+1}": f"PartB_A{i+1}" for i in range(len(five))}},
        "partC": "partC",
    }
    provider = _TextASRProvider(answers)
    cfg = ScoringConfig()
    report, _legacy = grade_exam(spec, recs, provider, cfg)

    out = report.to_dict()
    # 附加可读的改进建议与逐题对照
    out["advice"] = _advice(report, spec)
    out["paper_id"] = pid
    out["paper_name"] = spec.get("meta", {}).get("name", "")
    out["source"] = spec.get("meta", {}).get("source", {})
    return jsonify(out)


def _advice(rep, spec) -> list:
    tips = []
    a, b, c = rep.partA, rep.partB, rep.partC
    pa = (spec.get("partA") or {}).get("hidden_text", "")
    if pa and a.total < 14:
        if a.word_accuracy < 0.8:
            tips.append("模仿朗读：先听示范音频逐句跟读，重点补齐漏读的词；"
                        "录音时保持中等语速，不要抢拍或回读。")
        if a.wpm and (a.wpm < 90 or a.wpm > 170):
            tips.append(f"模仿朗读语速约 {a.wpm:.0f} 词/分，建议控制在 110–150 词/分，"
                        "并注意意群停顿与陈述句降调。")
        if not a.wpm:
            tips.append("模仿朗读：发音维度缺少音素级评测（当前为离线近似），"
                        "联网后可启用在线发音评测获得更准的语音语调分。")
    for it in b.questions:
        if it.total < 1.2:
            tips.append(f"角色扮演三问 第{it.index+1}题：注意疑问词、助动词与语序，"
                        "先完整复述中文提示的信息点再提问。")
    for it in b.answers:
        if it.total < 1.2:
            tips.append(f"角色扮演五答 第{it.index+1}题：听录音时抓数字、时间、地点、"
                        "人物与原因，回答用完整短句、避免只蹦单词。")
    if c.total < 15:
        if c.coverage and "/" in c.coverage:
            tips.append(f"故事复述：要点覆盖 {c.coverage}，按「人物→起因→经过→结果」"
                        "顺序复述，尽量覆盖全部关键词。")
        tips.append("故事复述：用自己的话转述而非逐字背诵，注意时态一致与连接词，"
                    "减少长时间停顿。")
    if not tips:
        tips.append("各部分表现均衡。继续保持每天一套完整限时练习，"
                    "重点打磨语调起伏与复述的信息完整度。")
    return tips


@app.get("/api/scoring-info")
def api_scoring_info():
    cfg = ScoringConfig()
    return jsonify({
        "scheme": "广东高考英语听说考试（CELST）卷面 60 分 ÷ 3 四舍五入折算 20 分",
        "parts": [
            {"name": "Part A 模仿朗读", "max": cfg.PART_A_MAX,
             "dims": ["语音语调 12", "语速与内容 8"]},
            {"name": "Part B 角色扮演", "max": cfg.PART_B_MAX,
             "dims": ["三问：语言 1.5 + 信息 0.5（每题2分）",
                      "五答：语言 0.5 + 信息 1.5（每题2分）"]},
            {"name": "Part C 故事复述", "max": cfg.PART_C_MAX,
             "dims": ["内容 12", "语言 4", "流利程度 5", "语音语调 3"]},
        ],
        "convert": f"卷面 {cfg.PAPER_MAX} 分 ÷ {cfg.CONVERT_DIVISOR:g} 四舍五入 → 满分 {cfg.FINAL_MAX} 分",
        "note": "浏览器语音识别仅提供文本，发音/语法维度走离线近似并已在报告中标注；"
                "配置在线音素级评测端点后自动切换为在线精细评分。",
    })


# ───────────────────────────── 下载 ─────────────────────────────
def _zip_bytes(paths, arcname_fn=None) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in paths:
            if not os.path.isfile(p):
                continue
            rel = arcname_fn(p) if arcname_fn else os.path.relpath(p, ROOT)
            zf.write(p, rel)
    buf.seek(0)
    return buf


@app.get("/download/<name>")
def download(name):
    """打包下载交付物。所有包在请求时按磁盘现状生成 → 后续优化自动同步。"""
    mapping = {}

    # 题库包
    bank_files = [os.path.join(BANK_DIR, f) for f in os.listdir(BANK_DIR)
                  if f.endswith(".solo") or f == "bank_index.json"]
    mapping["question_bank"] = ("SoloTalk_题库_18套.zip", bank_files,
                                lambda p: os.path.join("question_bank", os.path.basename(p)))

    # 评分引擎源码
    score_files = [os.path.join(ROOT, "scoring", f) for f in os.listdir(os.path.join(ROOT, "scoring"))
                   if f.endswith(".py")]
    mapping["scoring"] = ("SoloTalk_评分引擎_Python.zip", score_files,
                          lambda p: os.path.join("scoring", os.path.basename(p)))

    # Android Kotlin
    kt_dir = os.path.join(ROOT, "android")
    kt_files = [os.path.join(kt_dir, f) for f in os.listdir(kt_dir)]
    mapping["android"] = ("SoloTalk_Android_Kotlin.zip", kt_files,
                          lambda p: os.path.join("android", os.path.basename(p)))

    # 文档
    doc_files = [os.path.join(ROOT, "docs", f) for f in os.listdir(os.path.join(ROOT, "docs"))]
    mapping["docs"] = ("SoloTalk_文档.zip", doc_files,
                       lambda p: os.path.join("docs", os.path.basename(p)))

    # 优化版电脑版源码
    mapping["desktop"] = ("SoloTalk_电脑版优化源码.zip",
                          [os.path.join(ROOT, "app", f) for f in os.listdir(os.path.join(ROOT, "app"))],
                          lambda p: os.path.join("app", os.path.basename(p)))

    if name == "full":
        skip_dir = {"__pycache__", ".git", "downloads"}
        all_files = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in skip_dir]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                all_files.append(os.path.join(base, f))
        buf = _zip_bytes(all_files, lambda p: os.path.join("SoloTalk-Optimized", os.path.relpath(p, ROOT)))
        return send_file(buf, as_attachment=True, download_name="SoloTalk-Optimized_完整工程.zip",
                         mimetype="application/zip")

    if name not in mapping:
        return jsonify({"error": "未知下载项",
                        "available": list(mapping.keys()) + ["full"]}), 404
    fn, paths, arc = mapping[name]
    return send_file(_zip_bytes(paths, arc), as_attachment=True,
                     download_name=fn, mimetype="application/zip")


@app.get("/download/one/<pid>")
def download_one(pid):
    """下载单套 .solo 题目包。"""
    try:
        idx = _index()
        entry = next(p for p in idx["packages"] if p["id"] == pid)
        path = os.path.join(BANK_DIR, entry["file"])
        return send_file(path, as_attachment=True, download_name=entry["file"],
                         mimetype="application/octet-stream")
    except StopIteration:
        return jsonify({"error": "题目不存在"}), 404


@app.get("/downloads/<path:fn>")
def downloads(fn):
    return send_from_directory(DOWNLOADS, fn, as_attachment=True)


@app.get("/health")
def health():
    return jsonify({"ok": True, "papers": _index()["count"]})


# ───────────────────────────── 静态页面 ─────────────────────────────
@app.get("/")
def home():
    return send_from_directory(STATIC, "index.html")


@app.get("/static/<path:fn>")
def static_files(fn):
    return send_from_directory(STATIC, fn)


if __name__ == "__main__":
    # 端口优先级：命令行参数 > $PORT 环境变量 > 3000
    # 兼容发布脚本（python 分支会把命令串里的 $PORT 替换成实际端口）与本地运行。
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
