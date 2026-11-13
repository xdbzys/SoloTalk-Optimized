# -*- coding: utf-8 -*-
"""生成 SoloTalk 内置题库 v4（.solo = ZIP + data.json），共 18 套带出处试题。

与 v3 的区别：
  * 题量 4 → 18 套，覆盖 2021–2025 广东高考英语听说真题、深圳/广州中考听说真题、
    广东省专用全真模拟、用户上传的江门八下听说综合原题、以及明确标注的原创改编题；
  * 每套 meta.source 记录来源类型 / 年份 / 卷别 / 地区 / 公开链接 / 采集日期 /
    完整度 / 免责声明，可在 App 与 docs/05_试题出处清单.md 中核查；
  * 每套题**同时写入两套字段**：
      - 电脑版 CELST：partA.hidden_text / partB.three_questions+five_answers / partC.tts_text+key_points
      - 手机版听说综合：partB_secA / partB_secB / partC_secA / partC_secB
    因此任一版本的 SoloTalk 都能直接打开，且评分引擎可直接批改；
  * 用户上传原题的 3 段听力 mp3 **原样内置**（约 577 KB），并修正 audio 路径引用；
    其余 17 套不含任何音视频，由 App / 浏览器 TTS 合成，单套仅数 KB。

运行： python3 tools/build_question_bank.py
数据源：tools/bank_data.py
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bank_data import PAPERS, GENERAL_DISCLAIMER  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "question_bank")
DOCS = os.path.join(ROOT, "docs")
REPORT = os.path.join(ROOT, "report")

# 用户上传原题的音频素材（解压后）
UPLOADED_EXTRACTED = ("/root/.codebuddy/artifact/2f8a7d30-9c21-4f0b-1d6f-a624319b1000/"
                      "uploaded/extracted")
UPLOADED_AUDIO = [
    "audio/partB_secA_1/2_1.mp3",
    "audio/partB_secA_2/2_2.mp3",
    "audio/partB_secA_3/2_3.mp3",
]
UPLOADED_PAPER_ID = "jm_b8_listen_08"

CATEGORY_ORDER = ["official", "recall", "mock", "user", "original"]


def _build_one(paper: dict) -> dict:
    """写单个 .solo 包，返回索引条目。"""
    pid = paper["id"]
    data = json.loads(json.dumps(paper["data"], ensure_ascii=False))  # 深拷贝
    fname = f"{pid}.solo"
    path = os.path.join(OUT, fname)

    embedded_audio = []
    if pid == UPLOADED_PAPER_ID and os.path.isdir(UPLOADED_EXTRACTED):
        # 把用户上传原题的听力音频内置，并把 partB_secA 切到真实音频
        for i, rel in enumerate(UPLOADED_AUDIO):
            src = os.path.join(UPLOADED_EXTRACTED, rel)
            if not os.path.exists(src):
                continue
            sections = data.get("partB_secA") or []
            if i < len(sections):
                sections[i]["audio_source_type"] = "audio"
                sections[i]["audio"] = rel
                sections[i]["tts_text"] = ""
            embedded_audio.append((rel, src))

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=2))
        for rel, src in embedded_audio:
            zf.write(src, rel)

    size = os.path.getsize(path)
    with zipfile.ZipFile(path) as zf:
        raw = sum(x.file_size for x in zf.infolist())
        names = zf.namelist()

    src = data["meta"]["source"]
    st = data.get("stats", {})
    return {
        "id": pid,
        "name": paper["title"],
        "file": fname,
        "bytes": size,
        "uncompressed_bytes": raw,
        "level": data["meta"]["level"],
        "paper_type": data["meta"]["paper_type"],
        "category": src["category"],
        "category_cn": src["category_cn"],
        "year": src.get("year"),
        "paper_code": src.get("paper_code"),
        "region": src.get("region"),
        "urls": src.get("urls", []),
        "fidelity": src.get("fidelity"),
        "source_note": src.get("note", ""),
        "partA_words": st.get("part_a_words", 0),
        "partB_three": st.get("n_three", 0),
        "partB_five": st.get("n_five", 0),
        "partC_words": st.get("part_c_words", 0),
        "key_points": st.get("n_points", 0),
        "media_embedded": bool(embedded_audio),
        "media_files": [r for r, _ in embedded_audio],
        "has_celst_fields": all(k in data for k in ("partA", "partB", "partC")),
        "has_listening_fields": all(k in data for k in
                                    ("partB_secA", "partB_secB", "partC_secA", "partC_secB")),
        "entries": names,
    }


def _write_sources_doc(index: dict):
    """生成可核查的出处清单文档。"""
    lines = [
        "# 内置题库试题出处清单",
        "",
        f"> 生成时间：{index['generated']}　|　共 **{len(index['packages'])} 套**　|　"
        f"题库总大小 **{index['total_bytes']/1024:.1f} KB**",
        "",
        "## 重要声明",
        "",
        f"> {GENERAL_DISCLAIMER}",
        "",
        "官方（广东省教育考试院）**不公开**听说考试原卷与官方题库。下表 `official` 指的是"
        "「真题原文的网络公开整理版」——即由高考直通车、微信公众号、教辅网站等依据考生"
        "回忆与考后整理转录的版本，已逐套列出可核查链接。**回忆版**（`recall`）仅为考后"
        "回忆梗概，内容不完整；**模拟题**（`mock`）、**原创改编**（`original`）均非真题，"
        "已单独标注。上传原题（`user`）原样保留音频，仅补充出处元数据。",
        "",
        "## 分级统计",
        "",
        "| 类型 | 套数 | 说明 |",
        "|---|---:|---|",
    ]
    label = {
        "official": "官方真题（网络公开整理版）",
        "recall": "考生回忆版（非官方原卷）",
        "mock": "公开模拟题 / 全真模拟",
        "user": "用户上传原始题目包",
        "original": "原创改编（依据公开题型样例）",
    }
    for c in CATEGORY_ORDER:
        n = sum(1 for p in index["packages"] if p["category"] == c)
        if n:
            lines.append(f"| {label[c]} | {n} | `{c}` |")
    lines += [
        "",
        "## 逐套出处",
        "",
        "| # | 试题 | 类型 | 年份/卷别 | 完整度 | A 词数 | 三问/五答 | C 词数 | 要点 |",
        "|---:|---|---|---|---|---:|---:|---:|---:|",
    ]
    for i, p in enumerate(index["packages"], 1):
        yr = f"{p['year'] or '—'} {p['paper_code'] or ''}".strip()
        fid = "完整" if p["fidelity"] == "full" else "部分"
        lines.append(
            f"| {i} | {p['name']} | {p['category_cn']} | {yr} | {fid} | "
            f"{p['partA_words']} | {p['partB_three']}/{p['partB_five']} | "
            f"{p['partC_words']} | {p['key_points']} |"
        )
    lines += ["", "---", "", "## 详细来源链接与备注", ""]
    for i, p in enumerate(index["packages"], 1):
        lines += [
            f"### {i}. {p['name']}",
            "",
            f"- **来源分级**：{p['category_cn']}（`{p['category']}`）",
            f"- **考试 / 年份 / 卷别 / 地区**：{p['paper_type']} · {p['year'] or '—'} · "
            f"{p['paper_code'] or '—'} · {p['region'] or '—'}",
            f"- **完整度**：{'三部分原文与参考答案完整' if p['fidelity']=='full' else '仅部分原文/梗概，缺项已标注'}",
            "- **来源链接**：",
        ]
        if p["urls"]:
            for u in p["urls"]:
                lines.append(f"  - <{u}>")
        else:
            lines.append("  - （用户本地上传，无公开链接）")
        lines += [
            f"- **备注**：{p['source_note']}",
            f"- **包文件**：`assets/question_bank/{p['file']}`（{p['bytes']/1024:.1f} KB"
            + ("，含内置音频）" if p["media_embedded"] else "，纯文本无音视频）"),
            "",
        ]
    lines += [
        "## 版权与引用",
        "",
        "真题原文与参考答案的版权归原命题机构及原整理者所有。本工程仅作个人备考练习用途，"
        "已在每套题 `meta.source.disclaimer` 中写入同样声明。若原作者或权利人认为不妥，"
        "请删除相应题目包；商业使用请先取得授权。",
        "",
    ]
    with open(os.path.join(DOCS, "05_试题出处清单.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(REPORT, exist_ok=True)

    # 清理旧的 v3 题库文件（保留 bank_index.json 会被覆盖）
    for f in os.listdir(OUT):
        if f.endswith(".solo"):
            os.remove(os.path.join(OUT, f))

    packages = []
    for p in PAPERS:
        entry = _build_one(p)
        packages.append(entry)
        flag = " [含音频]" if entry["media_embedded"] else ""
        print(f"  {entry['file']:<38} {entry['bytes']/1024:7.1f} KB  "
              f"{entry['category_cn']}{flag}")

    index = {
        "schema": "solotalk.bank/4",
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "count": len(packages),
        "note": GENERAL_DISCLAIMER,
        "scoring_scheme": "CELST-2021（卷面 60 分 ÷ 3，四舍五入折算 20 分）",
        "format_note": "双格式兼容：每套同时含电脑版 CELST 字段与手机版听说综合字段",
        "categories": {c: sum(1 for p in packages if p["category"] == c)
                       for c in CATEGORY_ORDER},
        "packages": packages,
        "total_bytes": sum(p["bytes"] for p in packages),
    }
    with open(os.path.join(OUT, "bank_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    _write_sources_doc(index)

    # 兼容旧验证脚本：保留 celst_mock_01.solo 作为第一套的别名副本
    shutil.copyfile(os.path.join(OUT, packages[0]["file"]),
                    os.path.join(OUT, "celst_mock_01.solo"))

    # 机器可读的题库报告
    rep = {
        "schema": "solotalk.bank_report/1",
        "generated": index["generated"],
        "count": len(packages),
        "total_bytes": index["total_bytes"],
        "categories": index["categories"],
        "with_audio": [p["id"] for p in packages if p["media_embedded"]],
        "dual_format_ok": all(p["has_celst_fields"] and p["has_listening_fields"]
                              for p in packages),
        "packages": [
            {k: p[k] for k in ("id", "name", "category", "year", "paper_code",
                               "fidelity", "partA_words", "partB_three", "partB_five",
                               "partC_words", "key_points", "bytes", "media_embedded")}
            for p in packages
        ],
    }
    with open(os.path.join(REPORT, "question_bank_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print(f"\n共 {len(packages)} 套，合计 {index['total_bytes']/1024:.1f} KB")
    print(f"分级：{index['categories']}")
    print("双格式字段完整：", rep["dual_format_ok"])
    print("出处清单：docs/05_试题出处清单.md")
    return index


if __name__ == "__main__":
    build()
