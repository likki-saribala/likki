package com.likki.stride

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.addCallback
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.health.connect.client.PermissionController
import androidx.lifecycle.lifecycleScope
import androidx.webkit.WebViewAssetLoader
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

/**
 * Hosts the Stride web app (bundled in assets) and exposes a small bridge to it:
 * step totals from Health Connect, sharing text, and saving a backup file.
 */
class MainActivity : ComponentActivity() {

    private lateinit var web: WebView
    private lateinit var health: HealthBridge

    private var permissionRequestId: Int? = null
    private var saveRequest: Pair<Int, String>? = null
    private var fileChooser: ValueCallback<Array<Uri>>? = null

    private val requestHealthPermission =
        registerForActivityResult(PermissionController.createRequestPermissionResultContract()) { granted ->
            val id = permissionRequestId ?: return@registerForActivityResult
            permissionRequestId = null
            reply(id, if (granted.containsAll(HealthBridge.PERMISSIONS)) Replies.ok() else Replies.error(Replies.NO_PERMISSION))
        }

    private val createBackupFile =
        registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
            val (id, text) = saveRequest ?: return@registerForActivityResult
            saveRequest = null
            if (uri == null) return@registerForActivityResult reply(id, Replies.error(Replies.CANCELLED))
            try {
                val stream = contentResolver.openOutputStream(uri) ?: error("No output stream for the chosen file")
                stream.use { it.write(text.toByteArray(Charsets.UTF_8)) }
                reply(id, Replies.ok())
            } catch (e: Exception) {
                Log.e(TAG, "Saving the backup failed", e)
                reply(id, Replies.error(Replies.FAILED, e.message))
            }
        }

    private val pickBackupFile =
        registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            fileChooser?.onReceiveValue(if (uri != null) arrayOf(uri) else null)
            fileChooser = null
        }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        health = HealthBridge(applicationContext)

        val assets = WebViewAssetLoader.Builder()
            .addPathHandler("/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        web = WebView(this).apply {
            setBackgroundColor(getColor(R.color.bg))
            overScrollMode = WebView.OVER_SCROLL_NEVER
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true // the app keeps its data in localStorage
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            webViewClient = object : WebViewClient() {
                override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? =
                    assets.shouldInterceptRequest(request.url)

                // The bridge is only meant for the bundled app: anything else opens outside this WebView.
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    if (request.url.host == APP_HOST) return false
                    try {
                        startActivity(Intent(Intent.ACTION_VIEW, request.url))
                    } catch (e: ActivityNotFoundException) {
                        Log.w(TAG, "No app can open ${request.url}", e)
                    }
                    return true
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                    fileChooser?.onReceiveValue(null)
                    fileChooser = callback
                    return try {
                        pickBackupFile.launch("*/*")
                        true
                    } catch (e: ActivityNotFoundException) {
                        Log.w(TAG, "No file picker available", e)
                        fileChooser = null
                        false
                    }
                }
            }
            addJavascriptInterface(Bridge(), "StrideNative")
        }

        // Keep the page clear of the status bar, navigation bar, display cutout and keyboard.
        val root = FrameLayout(this).apply {
            setBackgroundColor(getColor(R.color.bg))
            addView(web, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val types = WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime()
            val bars = insets.getInsets(types)
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        setContentView(root)

        onBackPressedDispatcher.addCallback(this) {
            web.evaluateJavascript("window.__strideBack ? window.__strideBack() : false") { handled ->
                if (handled != "true") finish()
            }
        }

        if (savedInstanceState == null) web.loadUrl(START_URL) else web.restoreState(savedInstanceState)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onDestroy() {
        fileChooser?.onReceiveValue(null)
        fileChooser = null
        web.destroy()
        super.onDestroy()
    }

    /** Sends a reply to the web app. `json` must come from [Replies]. */
    private fun reply(id: Int, json: String) {
        runOnUiThread {
            if (!isDestroyed) web.evaluateJavascript("window.__strideNative && window.__strideNative.resolve($id, $json)", null)
        }
    }

    /** Methods called from JavaScript. They arrive on a WebView thread, so each hops to the main thread. */
    private inner class Bridge {

        @JavascriptInterface
        fun readSteps(id: Int, startMs: String?, endMs: String?) {
            val range = Replies.parseRange(startMs, endMs) ?: return reply(id, Replies.error(Replies.BAD_RANGE))
            lifecycleScope.launch {
                val result = try {
                    val reason = health.unavailableReason()
                    when {
                        reason != null -> Replies.error(reason)
                        !health.hasPermission() -> Replies.error(Replies.NO_PERMISSION)
                        else -> Replies.steps(health.steps(range))
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: SecurityException) {
                    Replies.error(Replies.NO_PERMISSION)
                } catch (e: Exception) {
                    Log.e(TAG, "Reading steps failed", e)
                    Replies.error(Replies.FAILED, e.message)
                }
                reply(id, result)
            }
        }

        @JavascriptInterface
        fun requestPermission(id: Int) = runOnUiThread {
            val reason = health.unavailableReason()
            if (reason != null) return@runOnUiThread reply(id, Replies.error(reason))
            permissionRequestId?.let { reply(it, Replies.error(Replies.CANCELLED)) }
            permissionRequestId = id
            try {
                requestHealthPermission.launch(HealthBridge.PERMISSIONS)
            } catch (e: Exception) {
                Log.e(TAG, "Could not open the Health Connect permission screen", e)
                permissionRequestId = null
                reply(id, Replies.error(Replies.FAILED, e.message))
            }
        }

        @JavascriptInterface
        fun openHealthConnect(id: Int) = runOnUiThread {
            try {
                startActivity(health.settingsIntent())
                reply(id, Replies.ok())
            } catch (e: Exception) {
                Log.e(TAG, "Could not open Health Connect", e)
                reply(id, Replies.error(Replies.FAILED, e.message))
            }
        }

        @JavascriptInterface
        fun shareText(id: Int, text: String?) = runOnUiThread {
            try {
                val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text.orEmpty())
                startActivity(Intent.createChooser(send, null))
                reply(id, Replies.ok())
            } catch (e: Exception) {
                Log.e(TAG, "Sharing failed", e)
                reply(id, Replies.error(Replies.FAILED, e.message))
            }
        }

        @JavascriptInterface
        fun saveFile(id: Int, name: String?, text: String?) = runOnUiThread {
            saveRequest?.let { reply(it.first, Replies.error(Replies.CANCELLED)) }
            saveRequest = id to text.orEmpty()
            try {
                createBackupFile.launch(name?.takeIf { it.isNotBlank() } ?: "stride-backup.json")
            } catch (e: Exception) {
                Log.e(TAG, "No app can save files", e)
                saveRequest = null
                reply(id, Replies.error(Replies.FAILED, e.message))
            }
        }
    }

    private companion object {
        const val TAG = "Stride"
        const val APP_HOST = WebViewAssetLoader.DEFAULT_DOMAIN
        const val START_URL = "https://$APP_HOST/index.html"
    }
}
