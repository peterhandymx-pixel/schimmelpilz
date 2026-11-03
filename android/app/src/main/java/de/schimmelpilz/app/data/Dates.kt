package de.schimmelpilz.app.data

import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.time.temporal.ChronoUnit
import java.util.Locale

/** Dates as in the web app: German TT.MM.JJJJ (English DD/MM/YYYY); the API always uses ISO. */
object Dates {
    private val de = DateTimeFormatter.ofPattern("dd.MM.yyyy")
    private val en = DateTimeFormatter.ofPattern("dd/MM/yyyy")
    private val deTime = DateTimeFormatter.ofPattern("dd.MM.yyyy, HH:mm")
    private val enTime = DateTimeFormatter.ofPattern("dd/MM/yyyy, HH:mm")
    private val zone: ZoneId = ZoneId.of("Europe/Berlin")

    fun label(iso: String?, lang: String = "de"): String {
        val date = toDate(iso) ?: return "—"
        return date.format(if (lang == "de") de else en)
    }

    fun labelWithTime(iso: String?, lang: String = "de"): String {
        if (iso.isNullOrBlank()) return "—"
        val moment = runCatching { OffsetDateTime.parse(iso).atZoneSameInstant(zone) }.getOrNull() ?: return label(iso, lang)
        return moment.format(if (lang == "de") deTime else enTime)
    }

    /** ISO date (YYYY-MM-DD) or timestamp -> local calendar date. */
    fun toDate(iso: String?): LocalDate? {
        if (iso.isNullOrBlank()) return null
        return runCatching { LocalDate.parse(iso) }.getOrNull()
            ?: runCatching { OffsetDateTime.parse(iso).atZoneSameInstant(zone).toLocalDate() }.getOrNull()
            ?: runCatching { Instant.parse(iso).atZone(zone).toLocalDate() }.getOrNull()
    }

    /** Accepts 05.11.2026, 5.11.26, 05/11/2026 and ISO; returns ISO, "" for empty input, null when invalid. */
    fun parseInput(text: String): String? {
        val value = text.trim()
        if (value.isEmpty()) return ""
        Regex("""^(\d{4})-(\d{1,2})-(\d{1,2})$""").matchEntire(value)?.let { m ->
            return build(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt())
        }
        Regex("""^(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})$""").matchEntire(value)?.let { m ->
            var year = m.groupValues[3].toInt()
            if (year < 100) year += 2000
            return build(year, m.groupValues[2].toInt(), m.groupValues[1].toInt())
        }
        return null
    }

    private fun build(year: Int, month: Int, day: Int): String? =
        runCatching { LocalDate.of(year, month, day).toString() }.getOrNull()

    fun today(): LocalDate = LocalDate.now(zone)

    fun daysUntil(iso: String?): Long? = toDate(iso)?.let { ChronoUnit.DAYS.between(today(), it) }

    fun relative(iso: String?, lang: String = "de"): String {
        val days = daysUntil(iso) ?: return ""
        return if (lang == "de") when {
            days < -1 -> "seit ${-days} Tagen überfällig"
            days == -1L -> "seit gestern überfällig"
            days == 0L -> "heute"
            days == 1L -> "morgen"
            else -> "in $days Tagen"
        } else when {
            days < -1 -> "${-days} days overdue"
            days == -1L -> "overdue since yesterday"
            days == 0L -> "today"
            days == 1L -> "tomorrow"
            else -> "in $days days"
        }
    }

    fun weekday(iso: String?, lang: String = "de"): String =
        toDate(iso)?.dayOfWeek?.getDisplayName(TextStyle.SHORT, if (lang == "de") Locale.GERMAN else Locale.ENGLISH)
            ?.removeSuffix(".")?.uppercase() ?: ""

    fun month(iso: String?, lang: String = "de"): String =
        toDate(iso)?.month?.getDisplayName(TextStyle.SHORT, if (lang == "de") Locale.GERMAN else Locale.ENGLISH)
            ?.removeSuffix(".")?.take(3)?.uppercase() ?: ""
}
