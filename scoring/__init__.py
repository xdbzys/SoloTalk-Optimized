# -*- coding: utf-8 -*-
"""SoloTalk 优化版评分核心包（广东高考英语听说 CELST 标准）。

零第三方依赖、零模型文件，可直接用于：
  * PyQt 电脑版（drop-in 替换 evaluate_recordings）
  * Android / Kotlin（见 android/ 目录等价实现）
  * Chaquopy / Termux 等嵌入式 Python 运行时
"""
from .gd_celst import (
    ScoringConfig, PartAResult, PartBItemResult, PartBResult, PartCResult,
    CELSTReport, score_part_a, score_part_b_item, score_part_c,
    build_report, grade_exam, round_half_up,
)
from .asr_provider import (
    ASRResult, ASRProvider, OnlineASRProvider, OfflineASRProvider, AutoASRProvider,
)

__version__ = "3.0.0"
__all__ = [
    "ScoringConfig", "PartAResult", "PartBItemResult", "PartBResult", "PartCResult",
    "CELSTReport", "score_part_a", "score_part_b_item", "score_part_c",
    "build_report", "grade_exam", "round_half_up",
    "ASRResult", "ASRProvider", "OnlineASRProvider", "OfflineASRProvider", "AutoASRProvider",
]
