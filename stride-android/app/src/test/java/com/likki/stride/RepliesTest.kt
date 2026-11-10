package com.likki.stride

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RepliesTest {
    private val day = 24L * 60 * 60 * 1000

    @Test fun okAndSteps() {
        assertEquals("""{"ok":true}""", Replies.ok())
        assertEquals("""{"ok":true,"steps":11240}""", Replies.steps(11240))
        assertEquals("""{"ok":true,"steps":0}""", Replies.steps(-5))
    }

    @Test fun errorsWithAndWithoutMessage() {
        assertEquals("""{"ok":false,"error":"no_permission"}""", Replies.error(Replies.NO_PERMISSION))
        assertEquals("""{"ok":false,"error":"failed"}""", Replies.error(Replies.FAILED, " "))
        assertEquals("""{"ok":false,"error":"failed","message":"boom"}""", Replies.error(Replies.FAILED, "boom"))
    }

    @Test fun messagesCannotBreakOutOfTheJsonString() {
        val nasty = "a\"b\\c\nd</script> e\u0001"
        assertEquals("a\\\"b\\\\c\\nd\\u003c/script>\\u2028e\\u0001", Replies.escape(nasty))
    }

    @Test fun acceptsOneCalendarDayIncludingDstDays() {
        assertEquals(1_000L until 1_000L + day, Replies.parseRange("1000", (1_000L + day).toString()))
        assertEquals(0L until 25 * 60 * 60 * 1000L, Replies.parseRange("0", (25L * 60 * 60 * 1000).toString()))
    }

    @Test fun rejectsBadRanges() {
        assertNull(Replies.parseRange(null, "5"))
        assertNull(Replies.parseRange("abc", "5"))
        assertNull(Replies.parseRange("1.5", "5"))
        assertNull(Replies.parseRange("10", "10"))
        assertNull(Replies.parseRange("10", "5"))
        assertNull(Replies.parseRange("-1", "5"))
        assertNull(Replies.parseRange("0", (3 * day).toString()))
    }
}
