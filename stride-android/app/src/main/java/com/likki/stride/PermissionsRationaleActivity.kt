package com.likki.stride

import android.os.Bundle
import android.util.TypedValue
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/** Plain explanation of what the app does with Health Connect data. */
class PermissionsRationaleActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val pad = (24 * resources.displayMetrics.density).toInt()
        val textColor = getColor(R.color.text)
        val title = TextView(this).apply {
            setText(R.string.rationale_title)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 24f)
            setTextColor(textColor)
        }
        val body = TextView(this).apply {
            setText(R.string.rationale_body)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            setTextColor(textColor)
            setPadding(0, pad / 2, 0, 0)
        }
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(title)
            addView(body)
        }
        val root = ScrollView(this).apply { addView(column) }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.setPadding(bars.left + pad, bars.top + pad, bars.right + pad, bars.bottom + pad)
            insets
        }
        setContentView(root)
    }
}
