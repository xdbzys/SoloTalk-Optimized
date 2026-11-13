# -*- coding: utf-8 -*-
"""把 CELST 评分引擎 v3.0 接入原 SoloTalk.py，生成 app/SoloTalk_optimized.py。

原则：**只动 4 处**，其余 7600+ 行 UI / 流程代码原样保留，
保证优化版可直接替换原脚本运行，且不破坏编辑模式、练习模式、历史记录。

  1. import 区：把工程根目录加入 sys.path，使 scoring 包可导入；
  2. _get_bge_model()：停用 BGE/ONNX 模型（省 >130 MB 常驻内存、消除评分虚高）；
  3. evaluate_recordings()：替换为多维评分引擎适配层（签名与返回结构完全兼容 UI）；
  4. _open_package_zip()：extractall 全包 → 仅按需解压媒体 + 容量上限。

运行： python3 tools/apply_optimizations.py
输出： app/SoloTalk_optimized.py、app/solotalk_patch.diff
"""
from __future__ import annotations

import difflib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
SRC = os.path.join(APP, "SoloTalk_original.py")
DST = os.path.join(APP, "SoloTalk_optimized.py")
DIFF = os.path.join(APP, "solotalk_patch.diff")

NEW_IMPORT = '''_SCRIPT_DIR = _BASE_DIR
# ===== [SoloTalk 优化版 v3.0] 接入 CELST 多维评分引擎 =====
# 保持工程目录结构（app/ 与 scoring/ 同级）即可；也可通过 PYTHONPATH 指定。
# 评分引擎为纯标准库实现，不加载任何模型。
sys.path.insert(0, os.path.join(_BASE_DIR, ".."))
sys.path.insert(0, _BASE_DIR)
# ========================================================='''

NEW_BGE = '''def _get_bge_model():
    """[优化版 v3.0] 已停用 BGE / ONNX 嵌入模型。

    原实现加载 bge-small-en-v1.5（APK 内 32.44 MB 模型文件，运行时 >130 MB 常驻内存），
    且 `_embedding_cosine_similarity` 把余弦值用 `(cos+1)/2` 映射到 [0,1]：
    两句语义完全无关的英文也稳定得到 ≈0.5 分，正是原 README 自述「B 偏高」的根因。
    新评分引擎改用零模型、可解释的多维算法，故此处直接返回 None ——
    既消除系统性虚高，也直接省掉整块运行时内存与 APK 体积。
    """
    return None
'''

NEW_EVAL = '''def evaluate_recordings(recs, pkg, model, existing_eval=None, selection=None,
                        progress_cb=None):
    """[SoloTalk 优化版 v3.0] 广东高考英语听说（CELST）评分引擎适配层。

    ★ 函数签名与返回字典结构 == 原 evaluate_recordings()，
      因此编辑模式 / 练习模式 / 模考模式 / 历史记录 / 结果卡片 **无需任何改动**。
      返回里额外附带 `score_report`（逐维度明细），旧 UI 会自然忽略。

    ★ 「结合网络」：AutoASRProvider 在配置了 SOLOTALK_ASR_ENDPOINT 时走在线
      识别 + 发音/语法评测（拿到音素置信度、语速、停顿等韵律信号），
      断网或超时自动回退本地 Vosk，考场弱网环境同样能完整出分。

    评分口径（官方）：
      Part A 20 = 语音语调 12 + 语速与内容 8
      Part B 16 = 三问(语言1.5+信息0.5)×3 + 五答(语言0.5+信息1.5)×5
      Part C 24 = 内容 12 + 语言 4 + 流利 5 + 语音 3
      卷面 60 ÷ 3，四舍五入取整 → 计入高考 20 分
    """
    import os as _os
    from scoring import (grade_exam, ScoringConfig, AutoASRProvider,
                         OfflineASRProvider, OnlineASRProvider)

    # ── 识别层：在线优先 + 离线兜底 ──
    _endpoint = _os.environ.get("SOLOTALK_ASR_ENDPOINT", "").strip()
    _key = _os.environ.get("SOLOTALK_ASR_KEY", "")
    _offline = OfflineASRProvider(model=model, sample_rate=SAMPLE_RATE)
    _online = OnlineASRProvider(_endpoint, api_key=_key) if _endpoint else None
    provider = AutoASRProvider(online=_online, offline=_offline)

    # ── 题目 spec（字段与 SoloPackage.to_dict() 一致）──
    spec = {
        "partA": {"hidden_text": getattr(pkg, "partA_hidden_text", "") or ""},
        "partB": {
            "three_questions": getattr(pkg, "partB_three_questions", []) or [],
            "five_answers": getattr(pkg, "partB_five_answers", []) or [],
        },
        "partC": {
            "key_points": getattr(pkg, "partC_key_points", "") or "",
            "tts_text": (getattr(pkg, "partC_tts_text", "") or ""
                         or getattr(pkg, "partC_summary", "") or ""),
        },
    }

    # ── 进度回调（保持契约：step 从 1 起）──
    _pb = recs.get("partB", {}) or {}
    _n = 1 + (len(_pb) if isinstance(_pb, (dict, list)) else 0) + 1
    if progress_cb:
        try:
            progress_cb(1, _n, "多维评分批改中")
        except Exception:
            pass

    report, ev = grade_exam(spec, recs, provider, ScoringConfig())

    # ── selection：历史「重新批改选中记录」时，未选中槽位保留旧值 ──
    if selection and existing_eval:
        if not selection.get("partA"):
            ev["partA"] = existing_eval.get("partA", ev["partA"])
        if not selection.get("partC"):
            ev["partC"] = existing_eval.get("partC", ev["partC"])
        s3 = selection.get("partB_three") or {}
        s5 = selection.get("partB_five") or {}
        old3 = existing_eval.get("partB_three", []) or []
        old5 = existing_eval.get("partB_five", []) or []
        ev["partB_three"] = [
            ev["partB_three"][i] if s3.get(i)
            else (old3[i] if i < len(old3) else ev["partB_three"][i])
            for i in range(len(ev["partB_three"]))
        ]
        ev["partB_five"] = [
            ev["partB_five"][i] if s5.get(i)
            else (old5[i] if i < len(old5) else ev["partB_five"][i])
            for i in range(len(ev["partB_five"]))
        ]

    # 新增：逐维度报告（卷面分 / 折算分 / 档次 / 在线离线来源）
    ev["score_report"] = report.to_dict()
    if progress_cb:
        try:
            progress_cb(_n, _n, "批改完成")
        except Exception:
            pass
    return ev

'''

NEW_EXTRACT = '''        # [优化版 v3.0] 不再 extractall 全包。
        # 原实现把整个题目包（可能含几十~几百 MB 视频）一次性解压到磁盘，
        # 且临时目录不随用随清，是手机版内存/存储峰值与「历史记录不稳定」的诱因。
        # 现在只解压 data.json 实际引用到的媒体，并设单文件 / 总量上限。
        needed = set()
        _pa = data.get("partA") or {}
        _pb = data.get("partB") or {}
        _pc = data.get("partC") or {}
        for _v in (_pa.get("video"), _pb.get("listening_audio"), _pc.get("audio")):
            if _v:
                needed.add(os.path.basename(_v))
        for _q in (_pb.get("three_questions") or []):
            if _q.get("en_audio"):
                needed.add(os.path.basename(_q["en_audio"]))
        for _q in (_pb.get("five_answers") or []):
            if _q.get("q_audio"):
                needed.add(os.path.basename(_q["q_audio"]))
        _MAX_ONE = 32 * 1024 * 1024       # 单文件 32 MB
        _MAX_ALL = 64 * 1024 * 1024       # 单套题累计 64 MB
        _used = 0
        for _name in zf.namelist():
            if os.path.basename(_name) not in needed:
                continue
            _info = zf.getinfo(_name)
            if _info.file_size > _MAX_ONE or _used + _info.file_size > _MAX_ALL:
                print(f"[题库] 跳过超大媒体 {_name} ({_info.file_size} bytes)")
                continue
            zf.extract(_name, temp_dir)
            _used += _info.file_size
'''


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"[{label}] 期望匹配 1 处，实际 {text.count(old)} 处，已中止")
    return text.replace(old, new, 1)


def _replace_range(text: str, start_marker: str, end_marker: str, new: str, label: str) -> str:
    s = text.find(start_marker)
    if s < 0:
        raise RuntimeError(f"[{label}] 找不到起始标记")
    e = text.find(end_marker, s)
    if e < 0:
        raise RuntimeError(f"[{label}] 找不到结束标记")
    return text[:s] + new + text[e:]


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        src = f.read()
    out = src

    # 1) import 区
    out = _replace_once(out, "_SCRIPT_DIR = _BASE_DIR", NEW_IMPORT, "import")

    # 2) 停用 BGE
    out = _replace_range(out, "def _get_bge_model():", "\ndef _embedding_cosine_similarity",
                         NEW_BGE, "BGE")

    # 3) 替换评分函数（从 def 到「后台批改」注释之前）
    out = _replace_range(out, "def evaluate_recordings(recs, pkg, model, existing_eval=None",
                         "# ------------------ 后台批改", NEW_EVAL, "evaluate_recordings")

    # 4) 题库按需解压
    out = _replace_once(out, "        zf.extractall(temp_dir)\n", NEW_EXTRACT, "extractall")

    # 5) 修正过时的批改说明注释
    out = _replace_once(
        out,
        "# 批改 = Vosk 离线识别 + BGE 语义相似度，纯 CPU 且按槽位串行，单份录音常需数秒。",
        "# [优化版 v3.0] 批改 = 在线识别(优先)/本地 Vosk(兜底) + 零模型 CELST 多维评分；\n"
        "# 不再加载 BGE ONNX 模型，常驻内存从数百 MB 降到常数级，批改耗时也显著缩短。",
        "comment")

    with open(DST, "w", encoding="utf-8") as f:
        f.write(out)

    diff = difflib.unified_diff(
        src.splitlines(keepends=True), out.splitlines(keepends=True),
        fromfile="app/SoloTalk_original.py", tofile="app/SoloTalk_optimized.py", n=3)
    with open(DIFF, "w", encoding="utf-8") as f:
        f.writelines(diff)

    # 语法检查
    import py_compile
    py_compile.compile(DST, doraise=True)
    print(f"✅ 已生成 {DST}")
    print(f"   原 {len(src.splitlines())} 行 → 优化版 {len(out.splitlines())} 行")
    print(f"✅ 语法检查通过")
    print(f"✅ 差异已写入 {DIFF}")


if __name__ == "__main__":
    main()
