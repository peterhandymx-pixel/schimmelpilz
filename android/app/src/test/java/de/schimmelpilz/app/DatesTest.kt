package de.schimmelpilz.app

import de.schimmelpilz.app.data.Dates
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DatesTest {
    @Test fun labelsUseGermanDayMonthYearWithLeadingZeros() {
        assertEquals("05.11.2026", Dates.label("2026-11-05"))
        assertEquals("05/11/2026", Dates.label("2026-11-05", "en"))
        assertEquals("—", Dates.label(null))
    }

    @Test fun timestampsUseBerlinCalendarDay() {
        // 22:30 UTC on 21 October is already 22 October in Berlin (UTC+2 in summer time).
        assertEquals("22.10.2026", Dates.label("2026-10-21T22:30:00+00:00"))
        assertEquals("22.10.2026, 00:30", Dates.labelWithTime("2026-10-21T22:30:00+00:00"))
    }

    @Test fun typedDatesAcceptGermanInputAndReturnIso() {
        listOf("05.11.2026", "5.11.2026", "5.11.26", "05/11/2026", "2026-11-05").forEach { assertEquals(it, "2026-11-05", Dates.parseInput(it)) }
        assertEquals("", Dates.parseInput("  "))
        listOf("31.02.2026", "11/31/2026", "morgen", "2026-13-01", "05.11").forEach { assertNull(it, Dates.parseInput(it)) }
    }

    @Test fun weekdayAndMonthAreShortCapitals() {
        assertEquals("DO", Dates.weekday("2026-10-29"))
        assertEquals("OKT", Dates.month("2026-10-29"))
        assertEquals("THU", Dates.weekday("2026-10-29", "en"))
    }
}
