package de.schimmelpilz.app

import de.schimmelpilz.app.data.CaseDetails
import de.schimmelpilz.app.data.CaseFile
import de.schimmelpilz.app.data.Task
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate

class RemindersTest {
    private val today = LocalDate.of(2026, 10, 24)

    private fun task(id: String, due: String?, done: Boolean = false) = Task(id, "c1", "Aufgabe $id", dueOn = due, completed = done)

    @Test
    fun announcesOnlyOpenDatesWithinTwoDaysOrOverdue() {
        val case = CaseFile("c1", "SCH-1", "Mietminderung", details = CaseDetails(deadline = "2026-10-26", deadlineNote = "Mängelbeseitigung"), tasks = listOf(
            task("today", "2026-10-24"), task("tomorrow", "2026-10-25"), task("later", "2026-10-30"),
            task("overdue", "2026-10-20"), task("ancient", "2026-09-01"), task("done", "2026-10-24", done = true), task("undated", null),
        ))
        val due = Reminders.due(listOf(case), today)
        assertEquals(listOf("task:overdue", "task:today", "task:tomorrow", "case:c1"), due.map { it.key })
        assertEquals("Mängelbeseitigung", due.last().title)
        assertEquals(listOf(-4L, 0L, 1L, 2L), due.map { it.days })
    }

    @Test
    fun eachStageIsAnnouncedOnce() {
        assertEquals(listOf("overdue", "d0", "d1", "d2"), listOf(-3L, 0L, 1L, 2L).map(Reminders::stage))
        assertEquals(Reminders.stage(-1), Reminders.stage(-9))
    }
}
