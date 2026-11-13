@file:JvmName("ScoringParitySmoke")
package com.solotalk.scoring

/**
 * 双端一致性冒烟测试（纯 JVM，不需要 Android SDK）。
 *
 * 编译运行（需要 kotlinc）：
 *   kotlinc GdCelstScoring.kt ScoringParitySmoke.kt -include-runtime -d parity.jar
 *   java -jar parity.jar
 *
 * 输出每行格式： case | paper | final | band | A.pron | A.pace | A.total |
 *               B.total | C.content | C.lang | C.flu | C.pron | C.total
 * 与 tools/verify_parity.py 的 Python 侧输出逐字段比对，用于证明
 * 电脑版与安卓版评分结果一致。
 */
import java.util.Locale

private fun f(x: Double): String = String.format(Locale.US, "%.6f", x)

private fun emit(tag: String, r: CelstReport) {
    println(listOf(
        tag, f(r.paperScore), r.finalScore.toString(), r.band,
        f(r.partA.pronunciation), f(r.partA.paceContent), f(r.partA.total),
        f(r.partB.total),
        f(r.partC.content), f(r.partC.language), f(r.partC.fluency),
        f(r.partC.pronunciation), f(r.partC.total),
    ).joinToString("|"))
}

private fun online(text: String) = AsrResult(
    text = text, source = "online", pronunciation = 0.90,
    wpm = 130.0, pauseRatio = 0.10, grammar = 0.90,
)

private fun offline(text: String) = AsrResult(text = text, source = "offline")

fun main() {
    val refA = "A young man who lived in London was in love with a beautiful girl."
    val q1 = "Do you have to do a part-time job?"
    val a1 = "She was born in 1990."
    val kp = "young man, lived in London, beautiful girl, poor, rich"
    val story = ("A young man who lived in London was very poor while the girl was rich. "
                 + "He wanted to give her a beautiful present but he had very little money.")
    val spec = ExamSpec(
        partAHiddenText = refA,
        partBThree = listOf(q1),
        partBFive = listOf(a1),
        partCKeyPoints = kp,
        partCSourceText = story,
    )

    // ① 全优（在线评测信号）
    emit("full", gradeExam(spec, Recognized(
        online(refA), listOf(online(q1)), listOf(online(a1)), online(story))))

    // ② 全程未作答
    emit("empty", gradeExam(spec, Recognized()))

    // ③ Part A 全是无关噪声
    emit("noiseA", gradeExam(spec, Recognized(
        offline("blah ".repeat(60).trim()), listOf(AsrResult()), listOf(AsrResult()), AsrResult())))

    // ④ Part B 答非所问（离线）
    emit("offtopicB", gradeExam(spec, Recognized(
        AsrResult(), listOf(offline("apple banana totally unrelated")),
        listOf(offline("the weather is nice today")), AsrResult())))

    // ⑤ 离线完整作答（无发音/语法信号）
    emit("offlineFull", gradeExam(spec, Recognized(
        offline(refA), listOf(offline(q1)), listOf(offline(a1)), offline(story))))

    // ⑥ 折算边界：直接验证 roundHalfUp
    println("roundHalfUp|${roundHalfUp(1.5)}|${roundHalfUp(2.5)}|${roundHalfUp(58.5 / 3.0)}")
}
