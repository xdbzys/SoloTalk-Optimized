# -*- coding: utf-8 -*-
"""APK 体积/内存构成分析器（ZIP 中央目录直读，无需下载完整 APK）。

背景：SoloTalk_v2.2.apk 达 235 MB，完整下载在受限网络下会超时。
APK 本质是 ZIP，中央目录位于文件末尾，只需取末尾几百 KB 即可枚举全部条目
及其压缩/未压缩大小 —— 这正是体积诊断所需的全部信息。

用法：
  # 有完整 APK 时
  python3 tools/analyze_apk.py --apk /path/SoloTalk_v2.2.apk

  # 只有末尾片段时（分段下载 Range: bytes=<total-262144>-<total-1>）
  python3 tools/analyze_apk.py --tail /tmp/apk_tail.bin --total 235045570

  # 输出 JSON 快照
  python3 tools/analyze_apk.py --tail ... --total ... --json report/apk_analysis.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import struct

EOCD_SIG = b"PK\x05\x06"
CD_SIG = b"PK\x01\x02"
CD_FMT = "<IHHHHHHIIIHHHHHII"      # 46 字节固定头
EOCD_FMT = "<IHHHHIIH"             # 22 字节


def read_tail(path: str, apk_size: int):
    """从本地片段文件读取；返回 (bytes, 该片段对应的 APK 绝对起始偏移)。"""
    with open(path, "rb") as f:
        data = f.read()
    return data, apk_size - len(data)


def read_from_apk(path: str):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(max(0, size - 1 << 20))
        data = f.read()
    return data, size - len(data), size


def parse(data: bytes, base_offset: int, apk_size: int):
    i = data.rfind(EOCD_SIG)
    if i < 0:
        raise ValueError("未找到 ZIP EOCD，片段可能不含文件末尾")
    sig, disk, cd_disk, n_here, n_total, cd_size, cd_offset, clen = struct.unpack(
        EOCD_FMT, data[i:i + 22])
    start = cd_offset - base_offset
    if start < 0:
        raise ValueError(f"中央目录起点 {cd_offset} 不在片段范围内，请增大末尾读取量（当前 {len(data)} 字节）")
    entries = []
    pos = start
    for _ in range(n_total):
        if data[pos:pos + 4] != CD_SIG:
            raise ValueError(f"中央目录条目签名异常 @ {pos}")
        f = struct.unpack(CD_FMT, data[pos:pos + 46])
        fnlen, exlen, cmlen = f[10], f[11], f[12]
        name = data[pos + 46:pos + 46 + fnlen].decode("utf-8", "replace")
        entries.append({
            "name": name,
            "compressed": f[8],
            "uncompressed": f[9],
            "method": f[4],          # 0=stored, 8=deflated
            "local_offset": f[16],
        })
        pos += 46 + fnlen + exlen + cmlen
    return entries, {"entries": n_total, "cd_size": cd_size, "cd_offset": cd_offset,
                     "apk_size": apk_size}


def summarize(entries):
    MB = 1048576.0
    comp = sum(e["compressed"] for e in entries)
    raw = sum(e["uncompressed"] for e in entries)

    by_top = collections.defaultdict(lambda: {"bytes": 0, "count": 0})
    by_ext = collections.defaultdict(lambda: {"bytes": 0, "count": 0})
    for e in entries:
        n = e["name"]
        top = n.split("/")[0] if "/" in n else "(root)"
        ext = os.path.splitext(n)[1].lower() or "(no ext)"
        by_top[top]["bytes"] += e["compressed"]; by_top[top]["count"] += 1
        by_ext[ext]["bytes"] += e["compressed"]; by_ext[ext]["count"] += 1

    def group(pred):
        s = sum(e["compressed"] for e in entries if pred(e["name"]))
        c = sum(1 for e in entries if pred(e["name"]))
        return {"bytes": s, "mb": round(s / MB, 2), "count": c}

    abi = collections.defaultdict(lambda: {"bytes": 0, "count": 0})
    for e in entries:
        if e["name"].startswith("lib/") and "/" in e["name"][4:]:
            a = e["name"].split("/")[1]
            abi[a]["bytes"] += e["compressed"]; abi[a]["count"] += 1

    groups = {
        "onnx_runtime_so": group(lambda n: "libonnxruntime" in n and n.endswith(".so")),
        "vosk_so": group(lambda n: "libvosk" in n and n.endswith(".so")),
        "bge_model": group(lambda n: n.startswith("assets/bge-model/")),
        "vosk_model": group(lambda n: n.startswith("assets/vosk-model/")),
        "all_native_so": group(lambda n: n.endswith(".so")),
        "all_dex": group(lambda n: n.endswith(".dex")),
        "png": group(lambda n: n.endswith(".png")),
        "audio": group(lambda n: n.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac"))),
        "fst": group(lambda n: n.endswith(".fst")),
    }
    return {
        "total_compressed_bytes": comp,
        "total_compressed_mb": round(comp / MB, 2),
        "total_uncompressed_mb": round(raw / MB, 2),
        "by_top": {k: {"mb": round(v["bytes"] / MB, 2), "count": v["count"]}
                   for k, v in sorted(by_top.items(), key=lambda x: -x[1]["bytes"])},
        "by_ext": {k: {"mb": round(v["bytes"] / MB, 2), "count": v["count"]}
                   for k, v in sorted(by_ext.items(), key=lambda x: -x[1]["bytes"])[:20]},
        "by_abi": {k: {"mb": round(v["bytes"] / MB, 2), "count": v["count"]}
                   for k, v in sorted(abi.items(), key=lambda x: -x[1]["bytes"])},
        "groups": groups,
        "top_files": [{"name": e["name"], "mb": round(e["compressed"] / MB, 2),
                       "raw_mb": round(e["uncompressed"] / MB, 2),
                       "method": e["method"]}
                      for e in sorted(entries, key=lambda x: -x["compressed"])[:30]],
    }


def estimate(summary):
    """按本次优化方案估算可释放的体积（保守值，单位 MB）。"""
    g = summary["groups"]
    abi = summary["by_abi"]
    saved = {}
    # 1) 新评分引擎零模型依赖 → 删 BGE ONNX + onnxruntime 全部 so
    saved["remove_bge_and_onnxruntime"] = round(
        g["bge_model"]["mb"] + g["onnx_runtime_so"]["mb"], 2)
    # 2) 在线 ASR 优先，Vosk 模型改为按需下载（不随包内置），并删 libvosk
    saved["vosk_ondemand"] = round(g["vosk_model"]["mb"] + g["vosk_so"]["mb"], 2)
    # 3) 只保留 arm64-v8a（去掉 x86/x86_64/mips/armeabi 等非主流 ABI）
    saved["abi_split_arm64_only"] = round(
        sum(v["mb"] for k, v in abi.items() if k != "arm64-v8a"), 2)
    # 4) R8 全量混淆 + 依赖精简（9 个 dex 合计近 20MB，按行业常见 35% 估算）
    saved["r8_dex_shrink"] = round(g["all_dex"]["mb"] * 0.35, 2)
    # 5) PNG → WebP
    saved["png_to_webp"] = round(g["png"]["mb"] * 0.65, 2)
    # 去掉第 1、2 项与第 3 项的重叠（so 不能重复计算）
    overlap = round(g["onnx_runtime_so"]["mb"] + g["vosk_so"]["mb"], 2)
    total = (saved["remove_bge_and_onnxruntime"] + saved["vosk_ondemand"]
             + saved["abi_split_arm64_only"] + saved["r8_dex_shrink"]
             + saved["png_to_webp"] - overlap)
    saved["estimated_total_saving"] = round(min(total, summary["total_compressed_mb"] * 0.9), 2)
    saved["estimated_final_apk_mb"] = round(
        summary["total_compressed_mb"] - saved["estimated_total_saving"], 2)
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", help="完整 APK 路径")
    ap.add_argument("--tail", help="APK 末尾片段路径")
    ap.add_argument("--total", type=int, help="APK 总字节数（配合 --tail）")
    ap.add_argument("--json", help="输出 JSON 快照路径")
    args = ap.parse_args()

    if args.apk:
        data, base, size = read_from_apk(args.apk)
    elif args.tail and args.total:
        data, base = read_tail(args.tail, args.total)
        size = args.total
    else:
        ap.error("需要 --apk 或 (--tail + --total)")

    entries, meta = parse(data, base, size)
    summary = summarize(entries)
    result = {"meta": meta, "summary": summary, "estimate": estimate(summary),
              "entries": entries}

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"JSON 快照已写入 {args.json}")

    s = summary
    print(f"APK {size/1048576:.2f} MB | 条目 {meta['entries']} | "
          f"压缩后合计 {s['total_compressed_mb']:.2f} MB / 解压后 {s['total_uncompressed_mb']:.2f} MB")
    print("\n顶层构成：")
    for k, v in list(s["by_top"].items())[:8]:
        print(f"  {v['mb']:8.2f} MB  {v['count']:5d} 个  {k}")
    print("\n关键大项：")
    for k, v in s["groups"].items():
        print(f"  {v['mb']:8.2f} MB  {v['count']:4d} 个  {k}")
    print("\n各 ABI：")
    for k, v in s["by_abi"].items():
        print(f"  {v['mb']:8.2f} MB  {v['count']:4d} 个  {k}")
    print("\n瘦身估算：")
    for k, v in result["estimate"].items():
        print(f"  {v:8.2f} MB  {k}")
    return result


if __name__ == "__main__":
    main()
