package com.solotalk.optimized;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import java.util.ArrayList;

/** 系统级语音识别（基于设备自带的识别服务，无需内置模型，保持 APK 轻量）。
 *  识别文本作为 CELST 评分引擎的输入；若无可用识别服务则回调 error，由前端引导手动输入。 */
public class Recognizer {

    public interface Callback {
        void onResult(String key, String text, long durationMs, boolean ok);
        void onError(String key, String msg);
    }

    private final Activity activity;
    private SpeechRecognizer sr;
    private final Handler handler = new Handler(Looper.getMainLooper());

    // 单次识别的临时状态（同一时刻只有一次识别）
    private Callback cb;
    private String curKey;
    private long t0;
    private final String[] bestText = {""};
    private final boolean[] delivered = {false};

    public Recognizer(Activity activity) {
        this.activity = activity;
    }

    public void start(String key, int maxMs, Callback cb) {
        if (!SpeechRecognizer.isRecognitionAvailable(activity)) {
            cb.onError(key, "设备无可用语音识别服务（需联网的 Google 识别或厂商识别），请使用手动输入");
            return;
        }
        if (activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            cb.onError(key, "未授权麦克风权限，请在系统设置中授予后重试，或使用手动输入");
            return;
        }

        this.cb = cb;
        this.curKey = key;
        this.t0 = System.currentTimeMillis();
        bestText[0] = "";
        delivered[0] = false;

        if (sr != null) {
            try { sr.destroy(); } catch (Exception e) {}
        }
        sr = SpeechRecognizer.createSpeechRecognizer(activity);

        RecognitionListener listener = new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle b) {}
            @Override public void onBeginningOfSpeech() {}
            @Override public void onRmsChanged(float r) {}
            @Override public void onBufferReceived(byte[] b) {}
            @Override public void onEndOfSpeech() {}
            @Override public void onPartialResults(Bundle b) { collect(b); }
            @Override public void onEvent(int e, Bundle b) {}
            @Override public void onResults(Bundle b) { collect(b); complete(true); }
            @Override public void onError(int e) {
                if (delivered[0]) return;
                if (!bestText[0].trim().isEmpty()) { complete(true); return; }
                cb.onError(curKey, "识别失败（错误码 " + e + "），请联网后重试或使用手动输入");
            }
        };
        sr.setRecognitionListener(listener);

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        sr.startListening(intent);

        // 超时强制结束，交付已收集文本
        final long dur = Math.max(1500, maxMs);
        handler.postDelayed(new Runnable() {
            @Override public void run() {
                if (delivered[0]) return;
                try { if (sr != null) sr.stopListening(); } catch (Exception e) {}
                complete(true);
            }
        }, dur);
    }

    private void collect(Bundle b) {
        if (b == null) return;
        ArrayList<String> results = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (results != null && !results.isEmpty()) bestText[0] = results.get(0);
    }

    private void complete(boolean ok) {
        if (delivered[0]) return;
        delivered[0] = true;
        try { if (sr != null) sr.destroy(); } catch (Exception e) {}
        sr = null;
        cb.onResult(curKey, bestText[0], System.currentTimeMillis() - t0, ok);
    }

    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {}

    public void shutdown() {
        if (sr != null) {
            try { sr.destroy(); } catch (Exception e) {}
            sr = null;
        }
    }
}
