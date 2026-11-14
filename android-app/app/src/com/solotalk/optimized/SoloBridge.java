package com.solotalk.optimized;

import android.webkit.JavascriptInterface;

import org.json.JSONObject;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/** 暴露给前端 JS 的原生能力桥：题库读取、系统 TTS、音频播放、语音识别。 */
public class SoloBridge {

    private final MainActivity activity;
    private final TtsManager tts;
    private final Recognizer recognizer;

    public SoloBridge(MainActivity activity, TtsManager tts, Recognizer recognizer) {
        this.activity = activity;
        this.tts = tts;
        this.recognizer = recognizer;
    }

    private File soloDir() {
        return new File(activity.getFilesDir(), MainActivity.PKG_DIR);
    }

    /** 读取题库索引（assets/www/bank_index.json） */
    @JavascriptInterface
    public String getBankMeta() {
        try {
            return readAsset("www/bank_index.json");
        } catch (IOException e) {
            return "{\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    /** 读取某个 .solo 包解压后的 data.json */
    @JavascriptInterface
    public String getPackage(String id) {
        File f = new File(new File(soloDir(), id), "data.json");
        if (!f.exists()) return "{\"error\":\"package not found: " + id + "\"}";
        try {
            return new String(java.nio.file.Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
        } catch (IOException e) {
            return "{\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    private String readAsset(String path) throws IOException {
        try (java.io.InputStream in = activity.getAssets().open(path)) {
            byte[] buf = new byte[in.available()];
            int n = in.read(buf);
            return new String(buf, 0, n, StandardCharsets.UTF_8);
        }
    }

    /** 系统 TTS 朗读。lang: en-US / zh-CN；rate: 0.5~2.0 */
    @JavascriptInterface
    public void speak(String text, String lang, float rate) {
        if (text == null || text.isEmpty()) return;
        tts.speak(text, lang == null ? "en-US" : lang, rate > 0 ? rate : 1.0f);
    }

    @JavascriptInterface
    public void stopSpeak() {
        tts.stop();
    }

    /** 播放包内音频文件。relPath 形如 audio/partB_secA_1/2_1.mp3 */
    @JavascriptInterface
    public String playAudio(String id, String relPath) {
        File f = new File(new File(soloDir(), id), relPath);
        if (!f.exists()) return "{\"ok\":false,\"error\":\"audio not found\"}";
        boolean ok = tts.playFile(f.getAbsolutePath());
        return "{\"ok\":" + ok + "}";
    }

    /** 启动语音识别。结果通过 window.onSoloRecognize(key, asrJson) 回调。 */
    @JavascriptInterface
    public void recognize(final String partKey, final int maxMs) {
        activity.runOnUiThread(() -> recognizer.start(partKey, maxMs,
            new Recognizer.Callback() {
                @Override
                public void onResult(String key, String text, long durationMs, boolean ok) {
                    double dur = durationMs / 1000.0;
                    int words = text.trim().isEmpty() ? 0
                        : text.trim().split("\\s+").length;
                    Double wpm = (dur > 0 && words > 0) ? (words * 60.0 / dur) : null;
                    try {
                        JSONObject o = new JSONObject();
                        o.put("text", text == null ? "" : text);
                        o.put("duration_sec", dur);
                        o.put("wpm", wpm == null ? JSONObject.NULL : wpm);
                        o.put("pause_ratio", JSONObject.NULL);
                        o.put("pronunciation", JSONObject.NULL);
                        o.put("grammar", JSONObject.NULL);
                        o.put("source", ok ? "asr" : "empty");
                        String js = "window.onSoloRecognize('" + escapeJs(key) + "', " + o.toString() + ");";
                        activity.runOnUiThread(() -> activity.getWebView().evaluateJavascript(js, null));
                    } catch (Exception e) {
                        deliverError(key, e.getMessage());
                    }
                }

                @Override
                public void onError(String key, String msg) {
                    deliverError(key, msg);
                }
            }));
    }

    @JavascriptInterface
    public String appVersion() {
        try {
            return activity.getPackageManager()
                .getPackageInfo(activity.getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "1.0";
        }
    }

    private void deliverError(String key, String msg) {
        try {
            JSONObject o = new JSONObject();
            o.put("text", "");
            o.put("duration_sec", 0);
            o.put("wpm", JSONObject.NULL);
            o.put("pause_ratio", JSONObject.NULL);
            o.put("pronunciation", JSONObject.NULL);
            o.put("grammar", JSONObject.NULL);
            o.put("source", "empty");
            o.put("error", msg == null ? "unknown" : msg);
            String js = "window.onSoloRecognize('" + escapeJs(key) + "', " + o.toString() + ");";
            activity.runOnUiThread(() -> activity.getWebView().evaluateJavascript(js, null));
        } catch (Exception ignore) {
        }
    }

    private static String escapeJs(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ");
    }
}
