package com.likki.stride

/**
 * Replies sent back to the web app. Kept free of Android classes so it can be unit-tested on the JVM.
 * Shape: {"ok":true,...} or {"ok":false,"error":"<code>","message":"..."}.
 */
object Replies {
    const val NO_PERMISSION = "no_permission"
    const val UNAVAILABLE = "unavailable"
    const val UPDATE_REQUIRED = "update_required"
    const val BAD_RANGE = "bad_range"
    const val CANCELLED = "cancelled"
    const val FAILED = "failed"

    private const val MAX_RANGE_MS = 26L * 60 * 60 * 1000 // one calendar day, allowing for a DST shift

    fun ok(): String = """{"ok":true}"""

    fun steps(count: Long): String = """{"ok":true,"steps":${count.coerceAtLeast(0)}}"""

    fun error(code: String, message: String? = null): String =
        if (message.isNullOrBlank()) """{"ok":false,"error":"${escape(code)}"}"""
        else """{"ok":false,"error":"${escape(code)}","message":"${escape(message)}"}"""

    /** Parses a day range sent as millisecond strings; null when it is not a sane single day. */
    fun parseRange(startMs: String?, endMs: String?): LongRange? {
        val start = startMs?.toLongOrNull() ?: return null
        val end = endMs?.toLongOrNull() ?: return null
        if (start < 0 || end <= start || end - start > MAX_RANGE_MS) return null
        return start until end
    }

    fun escape(text: String): String = buildString(text.length + 8) {
        for (ch in text) when {
            ch == '"' -> append("\\\"")
            ch == '\\' -> append("\\\\")
            ch == '\n' -> append("\\n")
            ch == '\r' -> append("\\r")
            ch == '\t' -> append("\\t")
            // control characters, plus the two separators that are legal JSON but break JavaScript source
            ch < ' ' || ch == ' ' || ch == ' ' -> append("\\u%04x".format(ch.code))
            ch == '<' -> append("\\u003c") // never let a reply close a script context
            else -> append(ch)
        }
    }
}
