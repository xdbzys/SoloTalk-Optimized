# Android 侧交付说明

> **重要**：原仓库 `FallingLighty/SoloTalk` **没有安卓源码**，只有编译后的
> `SoloTalk_v2.2.apk`（235 MB）。本目录不是「改好的 APK」，而是
> **可直接放进你安卓工程的两个 Kotlin 源文件** + 瘦身配置。

## 文件

| 文件 | 作用 | 依赖 |
|---|---|---|
| `GdCelstScoring.kt` | CELST 多维评分内核（与 Python 版算法等价） | **仅 Kotlin 标准库** |
| `SoloTalkScoringBridge.kt` | 从 assets 内的 `.solo` 题库流式读取 `data.json`；在线 ASR / 发音评测客户端；批改调用示例 | Android `Context`、平台 `org.json`、`HttpURLConnection`（均内置） |

Java 工程也可调用：`GdCelstScoringKt.gradeExam(...)`（已用 `@file:JvmName` 指定）。

## 三步集成

### 1. 拷贝源码与题库

```
app/src/main/java/com/solotalk/scoring/GdCelstScoring.kt
app/src/main/java/com/solotalk/scoring/SoloTalkScoringBridge.kt
app/src/main/assets/question_bank/*        ← 从 ../assets/question_bank/ 拷贝，18 套约 518 KB
                                             （其中 1 套含用户上传原题的 3 段听力 mp3）
```

### 2. 替换原评分调用

原 APK 的评分链路是 `Vosk 识别 → BGE ONNX 语义相似度 → 相似度 × 满分`。
改为：

```kotlin
val report = gradeOnce(spec, asrA, asrThree, asrFive, asrC)
```

`spec` 用 `SoloQuestionBank.readSpec(context, item)` 从题库读取；
`AsrResult` 由你的录音模块填充（在线评测字段见 `../docs/02_集成指南.md`）。
若要沿用旧的历史记录数据结构，用 `report.toLegacyMap()`。

### 3. 瘦身（关键）

在 `app/build.gradle.kts`：

```kotlin
android {
    defaultConfig {
        ndk { abiFilters += listOf("arm64-v8a") }   // 去掉 x86 / x86_64 / mips / armeabi
    }
    bundle { abi { enableSplit = true } }           // 首选：AAB 按 ABI 下发
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"),
                          "proguard-rules.pro")
        }
    }
}
```

并从工程里**删除**：

- `implementation("...onnxruntime-android...")` 及 `libonnxruntime*.so`
- `assets/bge-model/`（32.66 MiB）
- `assets/vosk-model/`（67.61 MiB，改为首次使用按需下载小模型）
- 非目标 ABI 的 `libvosk.so`

> 为什么可以删 BGE：新评分引擎完全不依赖嵌入模型，
> 而且原 `(cos+1)/2` 归一化本身就会让无关文本稳定得 ≈0.5 分（评分虚高根因）。
> 详见 `../docs/01_评分标准与算法对照.md` 与 `../docs/03_内存与体积优化报告.md`。

## 预期效果（实测基准）

| 指标 | 现状 | 优化后（估算） |
|---|---:|---:|
| APK 体积 | 223.89 MiB | **约 40.79 MiB**（−82%） |
| 评分相关常驻内存 | 250–350 MB | **< 5 MB** |
| 内置题库 | 无（QQ 群分发） | 18 套 / 约 518 KB，按需加载（出处见 `../docs/05_试题出处清单.md`） |

数字来自 `../report/apk_analysis.json`（对 794 个 ZIP 条目的真实解析）。

## 在线评测端点

`OnlineAsrClient` 只上传作答音频（`multipart/form-data`，字段 `audio`），
响应字段：`text`（必需）、`pronunciation`、`duration`、`wpm`、`pause_ratio`、`grammar`（可选）。
未配置或网络失败时，传 `AsrResult(text = ..., source = "offline")` 即可，
引擎自动走保守近似并在 `CelstReport.onlineUsed` 标注来源。

## 验证状态

| 项 | 状态 |
|---|---|
| `GdCelstScoring.kt` 编译 | ✅ 用 JetBrains Kotlin 2.0.21 JVM 编译器编译通过，12 个 class，无错误无警告 |
| 双端数值一致性 | ✅ `ScoringParitySmoke.kt` + `../tools/verify_parity.py` 在 6 组输入上逐字段一致（容差 1e-6），见 `../report/parity_report.md` |
| Python 版准确度 | ✅ 10 个场景对照 + 源码集成验证全部通过（`../report/`） |
| `SoloTalkScoringBridge.kt` 编译 | ⚠️ 依赖 `android.content.Context` 与平台 `org.json`，**沙箱内无 Android SDK，未编译**；已人工核对语法。集成进工程后由 Gradle 编译 |
| 真机运行 | ⚠️ 未做（无安卓源码工程、无签名私钥） |

复现双端一致性（纯 JVM，不需要 Android SDK）：

```bash
kotlinc GdCelstScoring.kt ScoringParitySmoke.kt -include-runtime -d parity.jar
java -jar parity.jar > /tmp/parity_kt.txt
cd .. && python3 tools/verify_parity.py
```

> 一致性前提：`../scoring/text_utils.py` 的 `_SYNONYM_MAP` 与 `GdCelstScoring.kt` 的
> `SYNONYM_MAP` 必须**显式逐条对齐**；不要用 `min(set, key=len)` 挑 canon
> （集合迭代顺序跨平台不确定，会让同一份作答在两个平台得到不同分数）。

## 合规提示

- 内置题库为**自建模拟题**，非官方真题；每套 `meta.disclaimer` 已标注。
- 在线评测涉及考生录音上传，请在应用内明确告知并取得同意，配置 HTTPS 与最小化上传。
