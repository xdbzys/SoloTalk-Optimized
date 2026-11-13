@file:JvmName("GdCelstScoring")
package com.solotalk.scoring

import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/**
 * 广东高考英语听说考试（CELST）评分引擎 v3.0 —— Android / Kotlin 版。
 *
 * 与 Python 版 `scoring/gd_celst.py` 算法等价，纯 Kotlin 标准库实现：
 *   * 零第三方依赖、零模型文件、零 JNI、零 assets 模型；
 *   * 不加载 ONNX Runtime / Vosk 模型，常驻内存为常数级（< 1 MB）；
 *   * 可直接放进任意 Android 工程（Kotlin 或 Java 通过 JvmName 调用）。
 *
 * 官方口径：
 *   Part A 20 = 语音语调 12 + 语速与内容 8
 *   Part B 16 = 三问(语言 1.5 + 信息 0.5)×3 + 五答(语言 0.5 + 信息 1.5)×5
 *   Part C 24 = 内容 12 + 语言 4 + 流利 5 + 语音 3
 *   卷面 60 ÷ 3，四舍五入取整 → 计入高考 20 分
 *
 * 相对原 APK 内评分逻辑修正：
 *   1. Part A 不再用单一 (1-WER)×20，且修复 WER 未钳制导致的负分；
 *   2. Part B 不再用 (cos+1)/2 的 BGE 相似度（无关文本稳定得 ≈0.5 分），
 *      改按官方「语言 + 信息」双维度离散档给分；
 *   3. Part C 不再把 24 分全压在要点相似度上，补齐语言/流利/语音三维；
 *   4. 新增折算、A/B/C 档次、逐维度可解释报告。
 */

// ───────────────────────────── 数据结构 ─────────────────────────────

data class AsrResult(
    val text: String = "",
    val source: String = "offline",            // online | offline | empty
    val pronunciation: Double? = null,         // 音素/词级平均置信度 0~1
    val durationSec: Double? = null,
    val wpm: Double? = null,
    val pauseRatio: Double? = null,
    val grammar: Double? = null,
)

data class ScoringConfig(
    val paperMax: Double = 60.0,
    val partAMax: Double = 20.0,
    val partBMax: Double = 16.0,
    val partCMax: Double = 24.0,
    val convertDivisor: Double = 3.0,
    val finalMax: Int = 20,
    val aPronMax: Double = 12.0,
    val aPaceMax: Double = 8.0,
    val targetWpm: Double = 130.0,
    val bQLang: Double = 1.5,
    val bQInfo: Double = 0.5,
    val bALang: Double = 0.5,
    val bAInfo: Double = 1.5,
    val bItemMax: Double = 2.0,
    val cContentMax: Double = 12.0,
    val cLangMax: Double = 4.0,
    val cFluencyMax: Double = 5.0,
    val cPronMax: Double = 3.0,
    val langFloor: Double = 0.28,
    val minRetellRatio: Double = 0.18,
)

data class PartAResult(
    val recognized: String = "",
    val pronunciation: Double = 0.0,
    val paceContent: Double = 0.0,
    val total: Double = 0.0,
    val band: String = "C",
    val wordAccuracy: Double = 0.0,
    val omittedWords: Int = 0,
    val wpm: Double? = null,
    val source: String = "offline",
    val notes: List<String> = emptyList(),
)

data class PartBItemResult(
    val index: Int = 0,
    val kind: String = "question",             // question | answer
    val recognized: String = "",
    val language: Double = 0.0,
    val information: Double = 0.0,
    val total: Double = 0.0,
    val maxScore: Double = 2.0,
    val structureOk: Boolean = false,
    val source: String = "offline",
    val notes: List<String> = emptyList(),
)

data class PartBResult(
    val questions: List<PartBItemResult> = emptyList(),
    val answers: List<PartBItemResult> = emptyList(),
    val total: Double = 0.0,
    val maxScore: Double = 16.0,
    val band: String = "C",
)

data class PartCResult(
    val recognized: String = "",
    val content: Double = 0.0,
    val language: Double = 0.0,
    val fluency: Double = 0.0,
    val pronunciation: Double = 0.0,
    val total: Double = 0.0,
    val band: String = "C",
    val coverage: String = "0/0",
    val pointScores: List<Double> = emptyList(),
    val wpm: Double? = null,
    val source: String = "offline",
    val notes: List<String> = emptyList(),
)

data class CelstReport(
    val partA: PartAResult,
    val partB: PartBResult,
    val partC: PartCResult,
    val paperScore: Double,
    val paperMax: Double,
    val finalScore: Int,
    val finalMax: Int,
    val band: String,
    val onlineUsed: Boolean,
)

// ───────────────────────────── 文本工具 ─────────────────────────────

private val PUNCT = Regex("[^a-z0-9'\\s]+")
private val WS = Regex("\\s+")

private val STOPWORDS: Set<String> = setOf(
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "so", "because",
    "although", "though", "while", "of", "in", "on", "at", "to", "for", "from",
    "with", "by", "as", "into", "onto", "over", "under", "about", "above",
    "below", "up", "down", "out", "off", "again", "once", "here", "there",
    "when", "where", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "too", "very", "can", "will", "just", "don", "should", "now", "i", "you",
    "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my",
    "your", "his", "its", "our", "their", "this", "that", "these", "those",
    "am", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "having", "do", "does", "did", "doing", "would", "could", "shall",
    "may", "might", "must", "um", "uh", "er", "ah", "like", "well", "okay",
    "ok", "yeah", "'s", "'t", "'re", "'ve", "'ll", "'d", "'m"
)

private val IRREGULAR: Map<String, String> = mapOf(
    "was" to "be", "were" to "be", "is" to "be", "are" to "be", "am" to "be",
    "been" to "be", "being" to "be", "had" to "have", "has" to "have",
    "having" to "have", "did" to "do", "does" to "do", "doing" to "do",
    "went" to "go", "gone" to "go", "going" to "go", "got" to "get",
    "gotten" to "get", "getting" to "get", "made" to "make", "making" to "make",
    "took" to "take", "taken" to "take", "taking" to "take", "gave" to "give",
    "given" to "give", "giving" to "give", "found" to "find", "finding" to "find",
    "told" to "tell", "telling" to "tell", "saw" to "see", "seen" to "see",
    "seeing" to "see", "said" to "say", "saying" to "say", "bought" to "buy",
    "brought" to "bring", "thought" to "think", "felt" to "feel", "left" to "leave",
    "kept" to "keep", "slept" to "sleep", "men" to "man", "women" to "woman",
    "children" to "child", "people" to "person", "mice" to "mouse", "feet" to "foot",
    "teeth" to "tooth", "better" to "good", "best" to "good", "worse" to "bad",
    "worst" to "bad"
)

// ⚠️ 显式写死 canon，必须与 scoring/text_utils.py 的 _SYNONYM_MAP 逐条一致；
// 不要用 minByOrNull 从 Set 里挑（迭代顺序与 Python 不同会造成双端评分不一致）。
private val SYNONYM_MAP: Map<String, String> = mapOf(
    "present" to "gift", "gift" to "gift",
    "buy" to "buy", "purchase" to "buy", "bought" to "buy", "purchased" to "buy",
    "poor" to "poor", "broke" to "poor",
    "rich" to "rich", "wealthy" to "rich", "well-off" to "rich",
    "shop" to "shop", "store" to "shop", "market" to "shop",
    "manager" to "boss", "owner" to "boss", "shopkeeper" to "boss", "boss" to "boss",
    "vase" to "vase", "jar" to "vase", "pot" to "vase",
    "break" to "break", "broken" to "break", "smash" to "break",
    "smashed" to "break", "shatter" to "break", "pieces" to "break",
    "birthday" to "birthday",
    "girlfriend" to "girlfriend", "girl" to "girlfriend",
    "surprise" to "surprise", "surprised" to "surprise",
    "amazed" to "surprise", "shocked" to "surprise",
    "help" to "help", "helped" to "help", "assist" to "help", "assisted" to "help",
    "plan" to "plan", "planned" to "plan", "idea" to "plan", "scheme" to "plan",
    "worker" to "worker", "employee" to "worker",
    "pack" to "pack", "packed" to "pack", "wrap" to "pack",
    "wrapped" to "pack", "package" to "pack",
    "drop" to "drop", "dropped" to "drop", "fall" to "drop", "fell" to "drop",
    "guest" to "guest", "guests" to "guest", "visitor" to "guest", "visitors" to "guest",
    "expensive" to "expensive", "costly" to "expensive", "dear" to "expensive",
    "decide" to "decide", "decided" to "decide", "decision" to "decide",
    "want" to "want", "wanted" to "want", "wish" to "want",
    "wished" to "want", "hope" to "want", "hoped" to "want",
)

private val Q_WORDS = setOf("what", "when", "where", "why", "who", "whom", "whose", "which", "how")
private val AUX = setOf(
    "am", "is", "are", "was", "were", "do", "does", "did", "have", "has", "had",
    "can", "could", "will", "would", "shall", "should", "may", "might", "must"
)

fun normalize(text: String): String {
    if (text.isEmpty()) return ""
    val s = text.lowercase().replace('’', '\'').replace('‘', '\'')
    return WS.replace(PUNCT.replace(s, " "), " ").trim()
}

fun tokenize(text: String): List<String> =
    normalize(text).split(' ').filter { it.isNotEmpty() }

fun stem(word: String): String {
    var w = word.lowercase().trim('\'')
    if (w.isEmpty()) return ""
    w = IRREGULAR[w] ?: w
    SYNONYM_MAP[w]?.let { return it }
    if (w.length > 4 && w.endsWith("ies")) return w.dropLast(3) + "y"
    if (w.length > 5 && w.endsWith("ing")) {
        var b = w.dropLast(3)
        if (b.length > 2 && b.last() == b[b.length - 2] && b.last() !in "aeiou") b = b.dropLast(1)
        return b
    }
    if (w.length > 4 && w.endsWith("ed")) {
        var b = w.dropLast(2)
        if (b.length > 2 && b.last() == b[b.length - 2] && b.last() !in "aeiou") b = b.dropLast(1)
        return b
    }
    if (w.length > 4 && w.endsWith("es") &&
        !w.endsWith("ses") && !w.endsWith("xes") && !w.endsWith("ches") && !w.endsWith("shes")) {
        val c = w[w.length - 3]
        return w.dropLast(2) + (if (c == 's') "s" else "")
    }
    if (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") && !w.endsWith("us") && !w.endsWith("is"))
        return w.dropLast(1)
    return w
}

fun contentWords(text: String): List<String> =
    tokenize(text).filter { it !in STOPWORDS }.map { stem(it) }

private fun clamp(x: Double, lo: Double = 0.0, hi: Double = 1.0): Double =
    max(lo, min(hi, x))

private fun officialBand(q: Double, aLo: Double, aHi: Double,
                         bLo: Double, bHi: Double, cHi: Double): Double {
    val v = clamp(q)
    return when {
        v >= 0.80 -> aLo + (v - 0.80) / 0.20 * (aHi - aLo)
        v >= 0.50 -> bLo + (v - 0.50) / 0.30 * (bHi - bLo)
        else -> v / 0.50 * cHi
    }
}

private fun band(score: Double, maxScore: Double): String {
    val r = score / maxOf(1e-9, maxScore)
    return if (r >= 0.70) "A" else if (r >= 0.35) "B" else "C"
}

/** 官方「四舍五入」，不能用 kotlin.math.round（1.5 的行为依赖实现）。 */
fun roundHalfUp(x: Double): Int = floor(x + 0.5).toInt()

data class Alignment(
    val refLen: Int, val hypLen: Int, val hits: Int,
    val substitutions: Int, val deletions: Int, val insertions: Int,
    val accuracy: Double, val omitted: Int,
)

/** 词级编辑对齐；accuracy 钳制在 [0,1]，修复原实现负分。 */
fun alignWords(ref: String, hyp: String): Alignment {
    val r = tokenize(ref); val h = tokenize(hyp)
    val n = r.size; val m = h.size
    if (n == 0) return Alignment(0, m, 0, 0, 0, m, 0.0, 0)
    var prev = IntArray(m + 1) { it }
    val ops = IntArray((n + 1) * (m + 1))
    val W = m + 1
    for (i in 1..n) {
        val cur = IntArray(m + 1); cur[0] = i
        for (j in 1..m) {
            val cost = if (r[i - 1] == h[j - 1]) 0 else 1
            val diag = prev[j - 1] + cost
            val dele = prev[j] + 1
            val ins = cur[j - 1] + 1
            val best = minOf(diag, dele, ins)
            cur[j] = best
            ops[i * W + j] = if (best == diag) 0 else if (best == dele) 1 else 2
        }
        prev = cur
    }
    var hits = 0; var subs = 0; var dele = 0; var ins = 0
    var i = n; var j = m
    while (i > 0 || j > 0) {
        when {
            i == 0 -> { ins++; j-- }
            j == 0 -> { dele++; i-- }
            else -> when (ops[i * W + j]) {
                0 -> { if (r[i - 1] == h[j - 1]) hits++ else subs++; i--; j-- }
                1 -> { dele++; i-- }
                else -> { ins++; j-- }
            }
        }
    }
    val acc = max(0.0, 1.0 - (subs + dele + ins).toDouble() / maxOf(1, n))
    return Alignment(n, m, hits, subs, dele, ins, acc, dele + subs)
}

data class Coverage(val matched: Int, val total: Int, val ratio: Double,
                    val perPoint: List<Double>)

private fun phraseHit(point: String, hypContent: List<String>): Double {
    val pw = tokenize(point).filter { it !in STOPWORDS }.map { stem(it) }
    if (pw.isEmpty()) return 0.0
    val joined = pw.joinToString(" ")
    val hypJoined = hypContent.joinToString(" ")
    if (joined.isNotEmpty() && hypJoined.contains(joined)) return 1.0
    val hs = hypContent.toSet()
    val distinct = pw.toSet()
    val hit = distinct.count { it in hs }
    val ratio = hit.toDouble() / maxOf(1, distinct.size)
    // 硬门槛：命中不足一半记 0，杜绝随机文本刷分（原 BGE 映射的病根）
    return if (ratio < 0.5) 0.0 else min(1.0, (ratio - 0.5) * 2.0)
}

fun keyphraseCoverage(keyPoints: String, recognized: String): Coverage {
    val points = keyPoints.split(',').map { it.trim() }.filter { it.isNotEmpty() }
    if (points.isEmpty()) return Coverage(0, 0, 0.0, emptyList())
    val hc = contentWords(recognized)
    val per = points.map { phraseHit(it, hc) }
    val matched = per.count { it >= 0.80 }
    return Coverage(matched, points.size,
        if (per.isEmpty()) 0.0 else per.sum() / per.size, per)
}

fun looksLikeQuestion(text: String): Pair<Boolean, Double> {
    val w = tokenize(text)
    if (w.isEmpty()) return false to 0.0
    val checks = mutableListOf<Double>()
    val first = w[0]
    checks.add(if (first in Q_WORDS || first in AUX) 1.0 else 0.0)
    val hasQ = w.any { it in Q_WORDS }
    checks.add(if (hasQ || first in AUX) 1.0 else 0.0)
    checks.add(if (first in Q_WORDS) (if (w.size > 1 && w[1] in AUX) 1.0 else 0.35) else 1.0)
    checks.add(if (w.size in 3..25) 1.0 else 0.4)
    val s = checks.sum() / checks.size
    return (s >= 0.6) to s
}

fun sentenceWellformedness(text: String): Double {
    val w = tokenize(text)
    if (w.size < 3) return if (w.isEmpty()) 0.0 else 0.1
    var s = 1.0
    val func = w.count { it in STOPWORDS }
    if (func.toDouble() / w.size < 0.12) s -= 0.30
    if (w.toSet().size.toDouble() / w.size < 0.45) s -= 0.25
    if (w.size > 160) s -= 0.15
    return clamp(s)
}

fun speechRateWpm(text: String, durationSec: Double?): Double? {
    if (durationSec == null || durationSec <= 0) return null
    return tokenize(text).size * 60.0 / durationSec
}

// ───────────────────────────── 评分 ─────────────────────────────

fun scorePartA(reference: String, asr: AsrResult, cfg: ScoringConfig = ScoringConfig()): PartAResult {
    if (asr.text.isBlank()) return PartAResult(source = asr.source,
        notes = listOf("未作答或识别为空，记 0 分"))
    val al = alignWords(reference, asr.text)
    val notes = mutableListOf<String>()
    var pronQ = if (asr.pronunciation != null) {
        notes.add("发音分来自在线音素级评测"); clamp(asr.pronunciation)
    } else {
        notes.add("离线近似：以词级对齐准确率代理发音分")
        clamp(0.6 * al.accuracy + 0.4 * al.hits.toDouble() / maxOf(1, al.refLen))
    }
    // 交叉校验：念了完全无关的内容时，在线发音分也要降级
    if (al.accuracy < 0.35) {
        pronQ = min(pronQ, al.accuracy / 0.35 * 0.40)
        notes.add("识别文本与原文不匹配，发音分随内容对齐一并降级")
    }
    val pron = officialBand(pronQ, 8.0, cfg.aPronMax, 4.0, 7.0, 3.0)

    val omitted = al.omitted
    var content = when {
        omitted <= 3 -> 6.0 + (1.0 - omitted / 4.0) * 2.0
        omitted <= 10 -> 3.0 + (10 - omitted) / 7.0 * 2.0
        else -> max(0.0, 2.0 - (omitted - 10) * 0.15)
    }
    if (al.accuracy < 0.35) {
        content = min(content, 2.0 * max(0.0, al.accuracy / 0.35))
        notes.add("识别文本与原文整体不匹配，内容完整度按 C 档封顶")
    }
    val wpm = asr.wpm ?: speechRateWpm(asr.text, asr.durationSec)
    val paceContent: Double
    if (wpm != null && wpm > 0) {
        val paceQ = clamp(1.0 - kotlin.math.abs(wpm - cfg.targetWpm) / cfg.targetWpm)
        paceContent = clamp(content + (paceQ - 0.5) * 1.2, 0.0, cfg.aPaceMax)
        notes.add("语速 ${wpm.toInt()} wpm（目标 ${cfg.targetWpm.toInt()}）")
    } else {
        paceContent = content
        notes.add("缺音频时长，语速维度不参与微调")
    }
    val total = clamp(pron + paceContent, 0.0, cfg.partAMax)
    return PartAResult(asr.text, pron, paceContent, total, band(total, cfg.partAMax),
        al.accuracy, omitted, wpm, asr.source, notes)
}

private fun infoHit(reference: String, recognized: String): Pair<Double, Double> {
    val r = contentWords(reference); val h = contentWords(recognized)
    if (r.isEmpty()) return 0.0 to 0.0
    val rs = r.toSet(); val hs = h.toSet()
    val recall = rs.intersect(hs).size.toDouble() / rs.size
    val precision = if (hs.isEmpty()) 0.0 else rs.intersect(hs).size.toDouble() / hs.size
    return recall to (1.0 - precision)
}

fun scorePartBItem(reference: String, asr: AsrResult, index: Int = 0,
                   kind: String = "question",
                   cfg: ScoringConfig = ScoringConfig()): PartBItemResult {
    if (asr.text.isBlank()) return PartBItemResult(index, kind, "",
        notes = listOf("未作答或识别为空，记 0 分"), maxScore = cfg.bItemMax)
    val isQ = kind == "question"
    val notes = mutableListOf<String>()
    val (structOk, structScore) = if (isQ) looksLikeQuestion(asr.text) else true to 1.0
    val well = sentenceWellformedness(asr.text)
    val al = alignWords(reference, asr.text)
    val langQ = when {
        asr.grammar != null -> { notes.add("语言分来自在线语法评测"); clamp(asr.grammar) }
        isQ -> {
            if (!structOk) notes.add("疑问句结构有误（疑问词/助动词语序）")
            clamp(0.50 * structScore + 0.30 * al.accuracy + 0.20 * well)
        }
        else -> clamp(0.55 * al.accuracy + 0.45 * well)
    }
    val language = when {
        langQ < cfg.langFloor -> { notes.add("语言/选词错误导致不能理解，记 0"); 0.0 }
        isQ -> if (langQ >= 0.85) 1.5 else if (langQ >= 0.55) 1.0 else 0.0
        else -> if (langQ >= 0.50) 0.5 else 0.0
    }
    val (recall, spurious) = infoHit(reference, asr.text)
    val infoQ = when {
        recall >= 0.80 && spurious <= 0.55 -> 1.0
        recall >= 0.45 -> { notes.add("基本传递信息：漏次要信息或含无关内容"); 0.67 }
        else -> 0.0
    }
    val information = if (isQ)
        (if (infoQ >= 0.67) cfg.bQInfo else 0.0)
    else
        when { infoQ == 1.0 -> cfg.bAInfo; infoQ >= 0.67 -> 1.0; else -> 0.0 }
    val total = clamp(language + information, 0.0, cfg.bItemMax)
    return PartBItemResult(index, kind, asr.text, language, information, total,
        cfg.bItemMax, structOk, asr.source, notes)
}

fun scorePartC(keyPoints: String, asr: AsrResult,
               sourceText: String = "",
               cfg: ScoringConfig = ScoringConfig()): PartCResult {
    if (asr.text.isBlank()) return PartCResult(source = asr.source,
        notes = listOf("未作答或识别为空，记 0 分"))
    val notes = mutableListOf<String>()
    val cov = keyphraseCoverage(keyPoints, asr.text)
    var content = officialBand(cov.ratio, 8.0, cfg.cContentMax, 4.0, 7.0, 3.0)
    val srcLen = tokenize(sourceText).size
    val hypLen = tokenize(asr.text).size
    if (srcLen > 0 && hypLen.toDouble() / srcLen < cfg.minRetellRatio) {
        content *= max(0.0, (hypLen.toDouble() / srcLen) / cfg.minRetellRatio)
        notes.add("复述过短，内容分按比例衰减")
    }
    content = clamp(content, 0.0, cfg.cContentMax)

    val langQ = if (asr.grammar != null) clamp(asr.grammar) else sentenceWellformedness(asr.text)
    val language = officialBand(langQ, 3.0, cfg.cLangMax, 2.0, 2.0, 1.0)

    val wpm = asr.wpm ?: speechRateWpm(asr.text, asr.durationSec)
    val paceQ = if (wpm != null && wpm > 0)
        clamp(1.0 - kotlin.math.abs(wpm - cfg.targetWpm) / cfg.targetWpm) else 0.5
    val pauseQ = if (asr.pauseRatio != null) clamp(1.0 - asr.pauseRatio) else 0.6
    val words = tokenize(asr.text)
    val repeatQ = if (words.isEmpty()) 0.0
    else clamp(words.toSet().size.toDouble() / words.size * 1.4)
    val fluQ = clamp(0.45 * paceQ + 0.30 * pauseQ + 0.25 * repeatQ)
    if (asr.pauseRatio == null) notes.add("缺停顿特征，流利度按语速+重复率近似")
    val fluency = officialBand(fluQ, 4.0, cfg.cFluencyMax, 2.0, 3.0, 1.0)

    val pronunciation = if (asr.pronunciation != null)
        officialBand(clamp(asr.pronunciation), 3.0, cfg.cPronMax, 2.0, 2.0, 1.0)
    else {
        notes.add("语音分缺音素级评测，离线保守记 B/C 档（≤2 分）")
        if (cov.ratio >= 0.50) 2.0 else 1.0
    }
    val total = clamp(content + language + fluency + pronunciation, 0.0, cfg.partCMax)
    return PartCResult(asr.text, content, language, fluency, pronunciation, total,
        band(total, cfg.partCMax), "${cov.matched}/${cov.total}", cov.perPoint,
        wpm, asr.source, notes)
}

// ───────────────────────────── 汇总入口 ─────────────────────────────

/** 题目规格（由 .solo 的 data.json 解析后填入）。 */
data class ExamSpec(
    val partAHiddenText: String = "",
    val partBThree: List<String> = emptyList(),        // 每题 hidden_answer
    val partBFive: List<String> = emptyList(),
    val partCKeyPoints: String = "",
    val partCSourceText: String = "",
)

/** 识别结果集（key 与录音槽位一致）。 */
data class Recognized(
    val partA: AsrResult = AsrResult(),
    val partBThree: List<AsrResult> = emptyList(),
    val partBFive: List<AsrResult> = emptyList(),
    val partC: AsrResult = AsrResult(),
)

fun gradeExam(spec: ExamSpec, rec: Recognized,
              cfg: ScoringConfig = ScoringConfig()): CelstReport {
    val a = scorePartA(spec.partAHiddenText, rec.partA, cfg)
    val qs = spec.partBThree.mapIndexed { i, ref ->
        scorePartBItem(ref, rec.partBThree.getOrElse(i) { AsrResult() }, i, "question", cfg)
    }
    val ans = spec.partBFive.mapIndexed { i, ref ->
        scorePartBItem(ref, rec.partBFive.getOrElse(i) { AsrResult() }, i, "answer", cfg)
    }
    val bTotal = qs.sumOf { it.total } + ans.sumOf { it.total }
    val bMax = (qs.size + ans.size) * cfg.bItemMax
    val b = PartBResult(qs, ans, bTotal, bMax, band(bTotal, if (bMax > 0) bMax else cfg.partBMax))
    val c = scorePartC(spec.partCKeyPoints, rec.partC, spec.partCSourceText, cfg)

    val paper = clamp(a.total + b.total + c.total, 0.0, cfg.paperMax)
    val final = minOf(cfg.finalMax, roundHalfUp(paper / cfg.convertDivisor))
    val online = a.source == "online" || c.source == "online" ||
        qs.any { it.source == "online" } || ans.any { it.source == "online" }
    return CelstReport(a, b, c, paper, cfg.paperMax, final, cfg.finalMax,
        band(paper, cfg.paperMax), online)
}

/**
 * 兼容原 UI 的简化输出：把 CelstReport 折算成旧字段名，
 * 便于在不动现有历史记录/结果页的前提下平滑替换。
 */
fun CelstReport.toLegacyMap(cfg: ScoringConfig = ScoringConfig()): Map<String, Any> = mapOf(
    "partA" to mapOf("accuracy" to partA.total / cfg.partAMax,
                     "wer" to 1.0 - partA.wordAccuracy, "recognized" to partA.recognized),
    "partB_three" to partB.questions.map {
        mapOf("similarity" to it.total / cfg.bItemMax, "recognized" to it.recognized) },
    "partB_five" to partB.answers.map {
        mapOf("similarity" to it.total / cfg.bItemMax, "recognized" to it.recognized) },
    "partC" to mapOf("semantic_sim" to partC.total / cfg.partCMax,
                     "coverage" to partC.coverage, "recognized" to partC.recognized,
                     "points" to partC.pointScores),
    "paper_score" to paperScore, "final_score" to finalScore, "band" to band,
)
