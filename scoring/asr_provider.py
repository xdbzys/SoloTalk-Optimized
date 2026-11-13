# -*- coding: utf-8 -*-
"""可插拔语音识别 / 发音评测层：在线优先 + 离线兜底。

「结合网络」的落地点：
  * 联网时走 OnlineASRProvider，拿到更准的识别文本，并额外取得
    词级/音素级置信度、语速、停顿等韵律特征 —— 这些正是官方评分里
    「语音语调」「流利程度」维度所必需、而离线 Vosk 无法提供的信号；
  * 断网、超时、服务不可用时自动回退 OfflineASRProvider（本地 Vosk），
    保证考场/弱网环境下依然能完整出分（评分引擎会标注「离线近似」）；
  * 所有 provider 返回统一的 ASRResult，评分引擎不感知来源。

隐私与体积：不内置任何模型文件；不上传题目原文，只上传作答音频；
在线端点由集成方自行配置（可指向自建服务或合规的云 ASR）。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

__all__ = ["ASRResult", "ASRProvider", "OnlineASRProvider",
           "OfflineASRProvider", "AutoASRProvider"]


@dataclass
class ASRResult:
    """统一识别结果。置信度类字段为 None 时，评分引擎使用离线近似策略。"""
    text: str = ""
    source: str = "offline"                  # "online" | "offline" | "empty"
    # 词/音素级平均置信度 0~1（在线评测或带置信度的离线引擎提供）
    pronunciation: Optional[float] = None
    # 音频有效时长（秒），用于语速计算
    duration_sec: Optional[float] = None
    # 语速 词/分钟（引擎可直接给出则优先采用）
    wpm: Optional[float] = None
    # 停顿占比 0~1（越大越不流利）
    pause_ratio: Optional[float] = None
    # 在线语法/语言规范评测分 0~1（可选）
    grammar: Optional[float] = None
    # 识别到的词数
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.text.split())


class ASRProvider:
    def recognize(self, audio_path: str) -> ASRResult:  # pragma: no cover
        raise NotImplementedError


class OnlineASRProvider(ASRProvider):
    """在线识别 + 发音评测。

    约定请求：POST multipart/form-data，字段 `audio` 为录音文件；
    约定响应 JSON：
      {
        "text": "...",                 // 必需
        "pronunciation": 0.0~1.0,     // 可选，音素/词级平均置信度
        "duration": 12.3,             // 可选，秒
        "wpm": 128,                   // 可选
        "pause_ratio": 0.18,          // 可选
        "grammar": 0.0~1.0            // 可选
      }
    集成方可按自有服务调整 _build_request / _parse_response。
    """

    def __init__(self, endpoint: str, api_key: str = "", timeout: float = 8.0,
                 sample_rate: int = 16000):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout
        self.sample_rate = sample_rate

    def _build_request(self, audio_path: str):
        boundary = "----SoloTalkBoundary7d4a1f"
        with open(audio_path, "rb") as f:
            payload = f.read()
        # 流式读文件但一次性发送：录音通常 < 2MB，避免分片带来的内存/连接开销
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="sample_rate"\r\n\r\n',
            str(self.sample_rate).encode(), b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="audio"; filename="answer.wav"\r\n',
            b"Content-Type: audio/wav\r\n\r\n", payload, b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}",
                   "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST"), body

    @staticmethod
    def _parse_response(raw: bytes) -> ASRResult:
        d = json.loads(raw.decode("utf-8", "replace"))
        if not isinstance(d, dict) or "text" not in d:
            raise ValueError("在线识别响应缺少 text 字段")

        def _f(key):
            v = d.get(key)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        return ASRResult(
            text=str(d.get("text") or ""),
            source="online",
            pronunciation=_f("pronunciation"),
            duration_sec=_f("duration"),
            wpm=_f("wpm"),
            pause_ratio=_f("pause_ratio"),
            grammar=_f("grammar"),
        )

    def recognize(self, audio_path: str) -> ASRResult:
        if not audio_path or not os.path.isfile(audio_path):
            return ASRResult(source="empty")
        req, _ = self._build_request(audio_path)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read(1 << 20)          # 上限 1MB，防止异常响应撑爆内存
        return self._parse_response(raw)


class OfflineASRProvider(ASRProvider):
    """本地 Vosk 兜底。仅提供文本；韵律类信号为 None，由评分引擎走离线近似。

    内存优化：模型按需加载一次并复用（不要在每道题里 new Model）；
    音频按 4000 帧流式读取，不整段载入内存。
    """

    def __init__(self, model=None, sample_rate: int = 16000):
        self.model = model
        self.sample_rate = sample_rate

    def recognize(self, audio_path: str) -> ASRResult:
        if not audio_path or not os.path.isfile(audio_path) or self.model is None:
            return ASRResult(source="empty")
        try:
            import wave
            from vosk import KaldiRecognizer
        except Exception:
            return ASRResult(source="empty")
        try:
            wf = wave.open(audio_path, "rb")
        except Exception:
            return ASRResult(source="empty")
        try:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                return ASRResult(source="empty")
            rec = KaldiRecognizer(self.model, self.sample_rate)
            parts = []
            total_frames = 0
            frames_per_sec = wf.getframerate() or self.sample_rate
            while True:
                data = wf.readframes(4000)     # 流式，内存恒定
                if not data:
                    break
                total_frames += len(data) // 2
                if rec.AcceptWaveform(data):
                    parts.append(json.loads(rec.Result()).get("text", ""))
            parts.append(json.loads(rec.FinalResult()).get("text", ""))
            text = " ".join(p for p in parts if p).strip()
            duration = total_frames / float(frames_per_sec) if frames_per_sec else None
            return ASRResult(text=text, source="offline", duration_sec=duration)
        except Exception:
            return ASRResult(source="empty")
        finally:
            try:
                wf.close()
            except Exception:
                pass


class AutoASRProvider(ASRProvider):
    """联网优先、失败自动回退；记录最近一次来源，供 UI 提示「在线/离线评分」。"""

    def __init__(self, online: Optional[OnlineASRProvider] = None,
                 offline: Optional[OfflineASRProvider] = None,
                 network_check_url: Optional[str] = None):
        self.online = online
        self.offline = offline or OfflineASRProvider()
        self.network_check_url = network_check_url
        self.last_source = "offline"
        self.last_error = ""

    def _net_ok(self) -> bool:
        if not self.network_check_url:
            return True                       # 不配置则直接尝试，靠超时兜底
        try:
            with urllib.request.urlopen(self.network_check_url, timeout=2.0) as r:
                return r.status < 500
        except Exception:
            return False

    def recognize(self, audio_path: str) -> ASRResult:
        if self.online and self._net_ok():
            try:
                r = self.online.recognize(audio_path)
                if r.text.strip():
                    self.last_source = "online"
                    self.last_error = ""
                    return r
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                self.last_error = f"{type(e).__name__}: {e}"
        r = self.offline.recognize(audio_path)
        self.last_source = r.source if r.source != "empty" else "offline"
        return r
