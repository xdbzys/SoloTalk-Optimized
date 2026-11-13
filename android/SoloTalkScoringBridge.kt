@file:JvmName("SoloTalkScoringBridge")
package com.solotalk.scoring

import android.content.Context
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream

/**
 * Android 集成桥接层：把内置 .solo 题库与 CELST 评分引擎接起来。
 *
 * 关键的内存/体积约定（对应 docs/03 优化报告）：
 *   * 题库只读索引 → 选中某套才从 assets 打开对应 .solo，
 *     且**只读取 data.json 这一个 ZIP 条目**，绝不整包解压；
 *   * 不内置任何音视频，Part A / B / C 的听力文本走系统 TTS；
 *   * 不加载 ONNX / Vosk 模型；联网时用在线评测拿到发音与语法特征，
 *     断网用本地识别兜底（AsrResult 的韵律字段传 null，引擎自动走保守近似）。
 */
object SoloQuestionBank {

    data class Item(val id: String, val name: String, val file: String,
                    val source: String, val bytes: Long)

    /** 只读索引，几 KB，不打开任何题目包。 */
    fun index(context: Context): List<Item> {
        val text = context.assets.open("question_bank/bank_index.json")
            .bufferedReader().use { it.readText() }
        val arr = JSONObject(text).getJSONArray("packages")
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            Item(o.getString("id"), o.getString("name"), o.getString("file"),
                o.optString("source", ""), o.optLong("bytes", 0))
        }
    }

    /** 流式读取 .solo 内的 data.json（不解压整包、不落临时文件）。 */
    fun readSpec(context: Context, item: Item): ExamSpec {
        val data = readDataJson(context, item)
        val pa = data.optJSONObject("partA")
        val pb = data.optJSONObject("partB")
        val pc = data.optJSONObject("partC")
        val three = mutableListOf<String>()
        pb?.optJSONArray("three_questions")?.let { a ->
            for (i in 0 until a.length())
                three.add(a.getJSONObject(i).optString("hidden_answer", ""))
        }
        val five = mutableListOf<String>()
        pb?.optJSONArray("five_answers")?.let { a ->
            for (i in 0 until a.length())
                five.add(a.getJSONObject(i).optString("hidden_answer", ""))
        }
        val pcSource = pc?.optString("tts_text", "")?.takeIf { it.isNotEmpty() }
            ?: pc?.optString("summary", "") ?: ""
        return ExamSpec(
            partAHiddenText = pa?.optString("hidden_text", "") ?: "",
            partBThree = three,
            partBFive = five,
            partCKeyPoints = pc?.optString("key_points", "") ?: "",
            partCSourceText = pcSource,
        )
    }

    private fun readDataJson(context: Context, item: Item): JSONObject {
        ZipInputStream(context.assets.open("question_bank/${item.file}").buffered()).use { zis ->
            while (true) {
                val entry = zis.nextEntry ?: break
                if (entry.name == "data.json" || entry.name.endsWith("/data.json")) {
                    val buf = ByteArrayOutputStream()
                    val tmp = ByteArray(4096)
                    while (true) {
                        val n = zis.read(tmp)
                        if (n <= 0) break
                        buf.write(tmp, 0, n)
                        if (buf.size() > (1 shl 20)) break   // 上限 1 MB，防异常包撑爆内存
                    }
                    return JSONObject(buf.toString("UTF-8"))
                }
                zis.closeEntry()
            }
        }
        throw IllegalArgumentException("${item.file} 内找不到 data.json")
    }
}

/**
 * 在线识别 + 发音评测（「结合网络」）。
 * 只上传作答音频，不上传题目原文；响应 JSON 约定见 Python 版 asr_provider.py。
 * 网络失败由调用方 catch 后改传离线 AsrResult 即可，评分引擎不感知来源。
 */
class OnlineAsrClient(
    private val endpoint: String,
    private val apiKey: String = "",
    private val timeoutMs: Int = 8000,
) {
    fun recognize(wavBytes: ByteArray): AsrResult {
        val boundary = "----SoloTalkBoundary7d4a1f"
        val body = ByteArrayOutputStream().apply {
            write("--$boundary\r\n".toByteArray())
            write("Content-Disposition: form-data; name=\"audio\"; filename=\"answer.wav\"\r\n".toByteArray())
            write("Content-Type: audio/wav\r\n\r\n".toByteArray())
            write(wavBytes)
            write("\r\n--$boundary--\r\n".toByteArray())
        }.toByteArray()

        val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            setRequestProperty("Accept", "application/json")
            if (apiKey.isNotEmpty()) setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Length", body.size.toString())
        }
        conn.outputStream.use { it.write(body) }
        val code = conn.responseCode
        if (code !in 200..299) throw IllegalStateException("ASR HTTP $code")
        val raw = conn.inputStream.bufferedReader().use { it.readText() }
        conn.disconnect()
        val d = JSONObject(raw)
        fun dbl(k: String): Double? = if (d.has(k) && !d.isNull(k)) d.optDouble(k) else null
        return AsrResult(
            text = d.optString("text", ""),
            source = "online",
            pronunciation = dbl("pronunciation"),
            durationSec = dbl("duration"),
            wpm = dbl("wpm"),
            pauseRatio = dbl("pause_ratio"),
            grammar = dbl("grammar"),
        )
    }
}

/** 一次完整批改的调用示例（供 Activity / ViewModel 参考）。 */
fun gradeOnce(
    spec: ExamSpec,
    asrA: AsrResult,
    asrThree: List<AsrResult>,
    asrFive: List<AsrResult>,
    asrC: AsrResult,
): CelstReport = gradeExam(
    spec,
    Recognized(asrA, asrThree, asrFive, asrC),
    ScoringConfig(),
)
