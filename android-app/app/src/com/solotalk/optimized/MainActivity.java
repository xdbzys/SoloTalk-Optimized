package com.solotalk.optimized;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** SoloTalk 优化版 —— 原生 WebView 壳，承载前端 + CELST 评分引擎。
 *  体积控制：不内置 TTS 引擎（用系统 TextToSpeech）、不内置识别模型
 *  （用系统 SpeechRecognizer）、题库与音频均在 .solo 包内随 APK 轻量分发。 */
public class MainActivity extends Activity {

    public static final String PKG_DIR = "solo";
    private WebView webView;
    private SoloBridge bridge;
    private TtsManager tts;
    private Recognizer recognizer;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 首次运行：把 assets/solo/*.solo 解压到内部存储
        extractPackagesIfNeeded();

        webView = new WebView(this);
        tts = new TtsManager(this);
        recognizer = new Recognizer(this);
        bridge = new SoloBridge(this, tts, recognizer);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setMediaPlaybackRequiresUserGesture(false);
        webView.addJavascriptInterface(bridge, "SoloBridge");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest r) {
                return false;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> {
                    for (String p : request.getResources()) {
                        if (p.equals(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                                    == PackageManager.PERMISSION_GRANTED) {
                                request.grant(request.getResources());
                                return;
                            }
                        }
                    }
                    request.deny();
                });
            }
        });

        setContentView(webView);
        webView.loadUrl("file:///android_asset/www/index.html");
    }

    public WebView getWebView() {
        return webView;
    }


    /** 把 assets 里的 .solo 题库包解压到 getFilesDir()/solo/<id>/ */
    private void extractPackagesIfNeeded() {
        File flag = new File(getFilesDir(), PKG_DIR + "/.extracted");
        if (flag.exists()) return;
        try {
            String[] list = getAssets().list(PKG_DIR);
            if (list == null) return;
            File base = new File(getFilesDir(), PKG_DIR);
            base.mkdirs();
            for (String name : list) {
                if (!name.endsWith(".solo")) continue;
                String id = name.substring(0, name.length() - 5);
                try (InputStream in = getAssets().open(PKG_DIR + "/" + name);
                     ZipInputStream zis = new ZipInputStream(in)) {
                    File outDir = new File(base, id);
                    outDir.mkdirs();
                    ZipEntry e;
                    while ((e = zis.getNextEntry()) != null) {
                        File f = new File(outDir, e.getName());
                        if (e.isDirectory()) {
                            f.mkdirs();
                            continue;
                        }
                        f.getParentFile().mkdirs();
                        try (OutputStream os = new FileOutputStream(f)) {
                            byte[] buf = new byte[8192];
                            int n;
                            while ((n = zis.read(buf)) > 0) os.write(buf, 0, n);
                        }
                        zis.closeEntry();
                    }
                }
            }
            new FileOutputStream(flag).close();
        } catch (IOException ex) {
            Toast.makeText(this, "题库解压失败：" + ex.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        super.onRequestPermissionsResult(code, perms, res);
        recognizer.onRequestPermissionsResult(code, perms, res);
    }

    @Override
    protected void onDestroy() {
        if (tts != null) tts.shutdown();
        if (recognizer != null) recognizer.shutdown();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
