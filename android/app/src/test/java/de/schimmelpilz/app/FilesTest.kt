package de.schimmelpilz.app

import de.schimmelpilz.app.ui.safeName
import org.junit.Assert.assertEquals
import org.junit.Test

class FilesTest {
    @Test
    fun serverNamesStayInsideTheExportFolder() {
        assertEquals("Mängelanzeige 2026.pdf", safeName("Mängelanzeige 2026.pdf"))
        assertEquals("_.._etc_passwd", safeName("../../etc/passwd"))
        assertEquals("a_b.docx", safeName("a\\b.docx"))
        assertEquals("Datei", safeName("..."))
    }
}
