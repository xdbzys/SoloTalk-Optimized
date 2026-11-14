package com.solotalk.optimized;

import android.content.Context;
import android.media.MediaPlayer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;

import java.util.Locale;

/** 系统级 TTS 朗读 + 包内音频播放（不内置任何 TTS 引擎，故 APK 体积极小）。 */
public class TtsManager {

    private final Context ctx;
    private TextToSpeech tts;
    private MediaPlayer player;
    private boolean ready = false;

    public TtsManager(Context ctx) {
        this.ctx = ctx;
        tts = new TextToSpeech(ctx, status -> {
            if (status == TextToSpeech.SUCCESS) {
                ready = true;
            }
        });
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String u) {}
            @Override public void onDone(String u) {}
            @Override public void onError(String u) {}
        });
    }

    public void speak(String text, String lang, float rate) {
        if (!ready) return;
        tts.setLanguage(Locale.forLanguageTag(lang.replace('_', '-')));
        tts.setSpeechRate(rate);
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "solotalk_utt");
    }

    public void stop() {
        if (ready) tts.stop();
        if (player != null) {
            try { player.stop(); player.release(); } catch (Exception e) {}
            player = null;
        }
    }

    /** 播放包内音频文件（如 mp3）。返回是否成功启动播放。 */
    public boolean playFile(String path) {
        stop();
        try {
            player = new MediaPlayer();
            player.setDataSource(path);
            player.setOnCompletionListener(mp -> {
                try { mp.release(); } catch (Exception e) {}
                if (player == mp) player = null;
            });
            player.prepare();
            player.start();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public void shutdown() {
        stop();
        if (tts != null) tts.shutdown();
    }
}
