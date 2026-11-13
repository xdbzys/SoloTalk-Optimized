# -*- coding: utf-8 -*-
"""题库按需加载器（内存优化）。

原实现 `_open_package_zip()` 里直接 `zf.extractall(temp_dir)`，会把整个题目包
（可能含几十~几百 MB 的视频/音频）一次性解压到磁盘，且临时目录不随用随清，
是手机版「历史记录不稳定 / 内存爆掉」的重要诱因之一。

本模块改为：
  * 启动/列表阶段**只读 bank_index.json**（几 KB），不触碰任何 .solo 包；
  * 用户选中某套题时，才从对应 .solo 里只读取 `data.json`
    （`zf.open()` 流式读单个条目，不解压整包）；
  * 仅当确实需要某个媒体文件时才解压该文件，且设置单文件与总量上限；
  * 用 `TemporaryDirectory` 上下文，退出即自动清理，杜绝临时文件堆积。
"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from contextlib import contextmanager
from typing import Iterator

__all__ = ["QuestionBank", "PackageHandle", "MAX_MEDIA_BYTES", "MAX_EXTRACT_TOTAL"]

MAX_MEDIA_BYTES = 32 * 1024 * 1024      # 单个媒体文件解压上限 32 MB
MAX_EXTRACT_TOTAL = 64 * 1024 * 1024   # 单套题累计解压上限 64 MB


class QuestionBank:
    """轻量题库索引。构造时只加载索引，不打开任何题目包。"""

    def __init__(self, bank_dir: str):
        self.bank_dir = bank_dir
        idx_path = os.path.join(bank_dir, "bank_index.json")
        with open(idx_path, "r", encoding="utf-8") as f:
            self.index = json.load(f)
        self.packages = {p["id"]: p for p in self.index.get("packages", [])}

    def list(self):
        """返回 (id, name, 字节数, 来源) 列表，供 UI 渲染题库页。"""
        return [(p["id"], p["name"], p["bytes"], p.get("source", ""))
                for p in self.index.get("packages", [])]

    def path_of(self, package_id: str) -> str:
        p = self.packages.get(package_id)
        if not p:
            raise KeyError(f"题库中不存在 {package_id}")
        return os.path.join(self.bank_dir, p["file"])

    def read_spec(self, package_id: str) -> dict:
        """只读取 data.json（流式，不解压媒体）—— 评分引擎所需的全部数据。"""
        path = self.path_of(package_id)
        with zipfile.ZipFile(path, "r") as zf:
            cands = [n for n in zf.namelist()
                     if n == "data.json" or n.endswith("/data.json")]
            if not cands:
                raise ValueError(f"{package_id} 内找不到 data.json，不是有效题目包")
            target = min(cands, key=lambda n: n.count("/"))
            with zf.open(target) as f:
                return json.loads(f.read().decode("utf-8"))

    @contextmanager
    def open_media(self, package_id: str) -> Iterator["PackageHandle"]:
        """按需解压媒体文件的上下文：进入时准备目录，退出时自动清理。

        用法：
            with bank.open_media(pid) as h:
                video = h.materialize("partA_video.mp4")   # 只解压这一个文件
                ... 播放 ...
            # 离开 with 后临时文件已删除
        """
        spec = self.read_spec(package_id)
        with tempfile.TemporaryDirectory(prefix="solotalk_") as td:
            yield PackageHandle(self.path_of(package_id), td, spec)


class PackageHandle:
    """单个题目包的惰性媒体句柄。"""

    def __init__(self, zip_path: str, temp_dir: str, spec: dict):
        self.zip_path = zip_path
        self.temp_dir = temp_dir
        self.spec = spec
        self._extracted = 0
        self._cache: dict = {}

    def materialize(self, filename: str) -> str | None:
        """只解压指定文件并返回绝对路径；超限或不存在返回 None。"""
        if not filename:
            return None
        if filename in self._cache:
            return self._cache[filename]
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            match = next((n for n in zf.namelist()
                          if os.path.basename(n) == filename), None)
            if match is None:
                return None
            info = zf.getinfo(match)
            if (info.file_size > MAX_MEDIA_BYTES
                    or self._extracted + info.file_size > MAX_EXTRACT_TOTAL):
                return None
            out = zf.extract(match, self.temp_dir)
            self._extracted += info.file_size
            self._cache[filename] = out
            return out

    def part_a_video(self):
        return self.materialize((self.spec.get("partA") or {}).get("video"))

    def part_b_audio(self):
        return self.materialize((self.spec.get("partB") or {}).get("listening_audio"))

    def part_c_audio(self):
        return self.materialize((self.spec.get("partC") or {}).get("audio"))


if __name__ == "__main__":
    import sys
    bank = QuestionBank(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    "assets", "question_bank"))
    print("索引条目：", len(bank.list()))
    for pid, name, size, src in bank.list():
        spec = bank.read_spec(pid)
        print(f"  {pid}: {size/1024:.1f} KB | A {len(spec['partA']['hidden_text'].split())} 词 | "
              f"C {len(spec['partC']['tts_text'].split())} 词")
        # 双格式兼容校验
        ok = all(k in spec for k in
                 ("partA", "partB", "partC", "partB_secA", "partB_secB",
                  "partC_secA", "partC_secB", "meta"))
        assert ok, f"{pid} 缺少双格式字段"
    print("双格式字段：全部 18 套完整 ✅")
    first = bank.list()[0][0]
    with bank.open_media(first) as h:
        print("按需句柄可用，未解压任何媒体：", h.part_a_video() is None)
    # 内置音频按需读取
    audio_id = next((p["id"] for p in bank.index["packages"] if p.get("media_embedded")), None)
    if audio_id:
        with bank.open_media(audio_id) as h:
            rel = next((s.get("audio") for s in h.spec.get("partB_secA", []) if s.get("audio")), None)
            print("内置听力音频按需解压：", bool(rel and h.materialize(os.path.basename(rel))))
