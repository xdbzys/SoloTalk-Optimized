# SoloTalk 优化版 · 广东英语听说练习与智能评分

针对 `FallingLighty/SoloTalk` 的完整优化交付：
**评分更准、内存更小、18 套带出处试题、可直接使用的听说练习应用、固定下载链接**。

> 🔐 你在对话里明文提供的 GitHub PAT 请**立即撤销并重新生成**；本次仅用于只读 API 访问，交付物中不含令牌。
>
> 📖 建议先读 [`docs/04_现状核查与结论.md`](docs/04_现状核查与结论.md)（仓库现状）与
> [`docs/06_听说练习应用与固定下载链接.md`](docs/06_听说练习应用与固定下载链接.md)（本轮新增）。
>
> ⚠️ 原仓库**没有安卓源码**（只有 Python 电脑版源码 + 235 MB APK 二进制），GitHub 上也**没有试题**。
> 本轮交付据此采用可落地方案，未反编译/重打包原 APK。

---

## 一、最新一轮新增（重点）

| 你的诉求 | 结果 |
|---|---|
| 结合网络制作十几套试题、最好广东真题和模拟题、要有出处 | ✅ **18 套**：10 套官方真题公开整理版（2021–2025 广东高考听说 + 2022/2025 深圳中考听说）、2 套考生回忆版、1 套广东省全真模拟、1 套**用户上传原题（含真实听力 mp3）**、4 套原创改编。每套 `meta.source` 记录年份/卷别/地区/**公开链接**/完整度/免责声明，逐套清单见 [`docs/05_试题出处清单.md`](docs/05_试题出处清单.md) |
| 试题放进软件内 | ✅ 全部 `.solo` 置于 `assets/question_bank/`，**双格式兼容**（同时含电脑版 CELST 字段与手机版听说综合字段），电脑版、手机版、评分引擎、Web 应用均可直接读取；按需加载，合计约 518 KB |
| 提供软件下载链接、后续优化同一个链接 | ✅ 发布为在线应用，**重复发布同一目录保持同一链接**；链接内提供在线练习 + 6 类实时打包下载（题库/完整工程/评分引擎/Kotlin/电脑版源码/文档）+ 单套 `.solo` 下载。下载包按磁盘现状实时生成，永远与最新版一致 |
| 增加听说功能 | ✅ 新增 **Web 听说练习应用**：TTS 示范朗读（语速可调）＋ 真实听力音频播放 ＋ 浏览器语音识别（说）＋ 文本兜底 ＋ 计时 ＋ 分步练习 ＋ 逐维度评分报告与改进建议 ＋ 练习记录趋势。真实浏览器全流程验证通过 |

### 关于「安卓安装包」的诚实说明

原仓库无安卓工程源码，**无法重新编译出新 APK**。因此「软件」以两种可立即使用的形态交付：

1. **在线听说练习应用**（本轮新增）：手机/电脑浏览器直接打开，听、说、评分、看出处、下载全部可用；
2. **完整工程包下载**：Kotlin 评分内核 + 电脑版优化源码 + 题库 + 文档，交给有安卓工程的一方可直接集成产出新 APK。

原作者未改动的 APK 仍在其 [GitHub Releases](https://github.com/FallingLighty/SoloTalk/releases)。

---

## 二、上一轮基础：评分与内存优化

| 诉求 | 结果 |
|---|---|
| 结合网络 + 广东高考评分系统优化评分 | ✅ 重构为**多维 CELST 评分引擎 v3.0**（Python + Kotlin 双实现），在线评测优先 / 离线兜底，含 60→20 折算与 A/B/C 档次；10 个场景对照全部通过 |
| 优化内存使其减小 | ✅ 精确解析 APK 794 个条目：BGE/ONNX + Vosk 模型占 200+ MiB、4 份 ABI 重复打包。已落地零模型评分内核与按需加载，给出 **223.89 MiB → 约 40.79 MiB（−82%）** 的可执行方案 |
| 优化「安卓软件」 | ✅ Kotlin 评分内核已用 Kotlin 2.0.21 编译通过、与 Python 版 6 组输入逐字段一致；同时给出**已改造完成的电脑版可运行源码**（保留原 7626 行 UI，仅替换 4 处） |

**原评分算法的三处系统性缺陷**（与作者 README 自述「A 偏低、B 偏高」吻合）：

1. **Part A**：`score = (1 − WER) × 20`，WER 未钳制 → 识别文本过长时**出现负分**；且只测文本吻合，不评语音语调/语速。
2. **Part B / C**：用 BGE 语义相似度并做 `(cos+1)/2` 归一化 → **两句完全无关的英文也稳定得 ≈0.5 分**。实测**全程未作答原算法仍得 8.00 分**。
3. **Part C**：24 分全压在「要点覆盖率」一维，官方的语言 / 流利 / 语音三维完全不计分。

**优化后**（详见 `report/verification_report.md`）：

| 场景 | 原算法卷面 | 优化版卷面 |
|---|---:|---:|
| 全优作答 | 53.03 | **57.06 / 60 → 19 / 20（A 档）** |
| 全程未作答 | **8.00** | **0.00** |
| 语义无关文本 | 13.15 | 7.52（信息/内容维度归零） |
| 识别文本远长于原文 | **−13.38** | **0.60** |
| 无意义单词堆砌 | 9.08 | **2.83** |

---

## 三、快速开始

### 在线使用（推荐）

打开交付时给出的**固定分享链接**即可，无需安装。后续优化复用同一链接。

### 本地运行 Web 应用

```bash
cd SoloTalk-Optimized
pip3 install -r webapp/requirements.txt
PORT=3000 python3 webapp/app.py
# 浏览器打开 http://127.0.0.1:3000/
```

### 可复现脚本（纯标准库，无需模型/音频）

```bash
python3 tools/build_question_bank.py   # 重新生成 18 套带出处试题 + 索引 + 出处清单
python3 tools/verify_scoring.py        # 评分准确度对照 → report/verification_report.md
python3 tools/verify_integration.py    # 优化版源码集成验证 → report/integration_report.md
python3 tools/verify_parity.py         # Python/Kotlin 双端一致性 → report/parity_report.md
python3 scoring/question_bank.py       # 题库按需加载自检
python3 tools/apply_optimizations.py   # 从基线源码重新生成 app/SoloTalk_optimized.py
python3 tools/analyze_apk.py --tail <apk末尾片段> --total 235045570
```

运行改造后的电脑版（保持 `app/` 与 `scoring/` 同级）：

```bash
cd app && python3 SoloTalk_optimized.py
```

启用在线评测（可选，不配则走离线兜底）：

```bash
export SOLOTALK_ASR_ENDPOINT="https://your-asr.example.com/v1/evaluate"
```

---

## 四、目录

```
├── webapp/                   听说练习 Web 应用 ★ 本轮新增
│   ├── app.py                Flask 后端：题库/音频/评分/下载 API
│   ├── requirements.txt      flask
│   └── static/               index.html + app.js + style.css（响应式）
├── assets/question_bank/     18 套 .solo + bank_index.json（约 518 KB）★
├── scoring/                  Python 评分引擎（零依赖）★
│   ├── gd_celst.py            CELST 多维评分核心
│   ├── asr_provider.py        在线优先 / 离线兜底识别层
│   ├── text_utils.py          归一化、对齐、要点覆盖、语法启发式
│   ├── question_bank.py       题库按需加载器
│   └── legacy.py              原算法复现（对照用）
├── android/                  Android 侧 ★
│   ├── GdCelstScoring.kt      Kotlin 评分内核（已编译验证）
│   ├── SoloTalkScoringBridge.kt  题库读取 + 在线 ASR
│   ├── ScoringParitySmoke.kt  双端一致性冒烟测试
│   └── README.md              Gradle / ABI / R8 配置
├── app/
│   ├── SoloTalk_original.py   原始 7626 行源码（基线）
│   ├── SoloTalk_optimized.py  已接入新引擎的可运行源码
│   └── solotalk_patch.diff    仅 4 处改动的完整差异
├── tools/                    可复现脚本（含 bank_data.py 试题与出处数据）
├── docs/
│   ├── 05_试题出处清单.md     ← 18 套逐套出处 ★
│   ├── 06_听说练习应用与固定下载链接.md  ← 本轮说明 ★
│   ├── 04_现状核查与结论.md
│   ├── 01_评分标准与算法对照.md
│   ├── 02_集成指南.md
│   └── 03_内存与体积优化报告.md
├── report/                   验证报告 + APK 真实数据快照 + 题库报告
└── index.html                交付总览页
```

---

## 五、诚实说明的边界

1. **没有重编译 APK**：无安卓源码、无签名私钥。交付的是可直接集成的 Kotlin 内核与精确诊断，不是「装得上但没验证过」的 APK。
2. **「真题」非官方原卷**：广东省教育考试院不公开听说考试原卷与官方题库。题库中的真题为公开网络整理版，回忆版/模拟题/原创改编已分别标注，绝不冒充官方真题；仅供个人备考练习，请勿商用。
3. **在线评测服务需自备**：未配置端点时发音/语法维度走离线近似（引擎已封顶并标注）；浏览器语音识别只提供文本，同样走近似路径。要完全对齐官方机考需接入音素级发音评测。
4. **40.79 MiB 是估算值**，需重新打包后用 `tools/analyze_apk.py` 实测确认。
5. 评分结果用于练习自评与档次参考，最终成绩以广东省教育考试院公布为准。
