# 双端一致性验证报告（Python vs Kotlin）

> 运行：`python3 tools/verify_parity.py`（Kotlin 侧由 `android/ScoringParitySmoke.kt` 编译运行；输出基准随工程交付于 `report/parity_kotlin_baseline.txt`，开箱即可复现）

| 场景 | 结果 | 说明 |
|---|---|---|
| full | ✅ 一致 | 逐字段一致 |
| empty | ✅ 一致 | 逐字段一致 |
| noiseA | ✅ 一致 | 逐字段一致 |
| offtopicB | ✅ 一致 | 逐字段一致 |
| offlineFull | ✅ 一致 | 逐字段一致 |
| roundHalfUp | ✅ 一致 | 逐字段一致 |

## 结论

- Python 与 Kotlin 评分内核在 6 组输入上**逐字段一致**（容差 1e-6），电脑版与安卓版可对同一份作答给出相同分数。
- 一致性前提：`scoring/text_utils.py` 的 `_SYNONYM_MAP` 与 `android/GdCelstScoring.kt` 的 `SYNONYM_MAP` 显式逐条对齐（不能用 `min(set)` 挑 canon，集合迭代顺序跨平台不确定）。
