package de.schimmelpilz.app

import android.content.SharedPreferences
import de.schimmelpilz.app.data.Api
import de.schimmelpilz.app.data.ApiException
import de.schimmelpilz.app.data.SessionCookieJar
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** In-memory SharedPreferences: enough for the cookie jar in JVM tests. */
class MemoryPrefs : SharedPreferences {
    val values = mutableMapOf<String, Any?>()
    override fun getAll() = values
    override fun getString(key: String, def: String?) = values[key] as? String ?: def
    @Suppress("UNCHECKED_CAST") override fun getStringSet(key: String, def: MutableSet<String>?) = values[key] as? MutableSet<String> ?: def
    override fun getInt(key: String, def: Int) = values[key] as? Int ?: def
    override fun getLong(key: String, def: Long) = values[key] as? Long ?: def
    override fun getFloat(key: String, def: Float) = values[key] as? Float ?: def
    override fun getBoolean(key: String, def: Boolean) = values[key] as? Boolean ?: def
    override fun contains(key: String) = key in values
    override fun registerOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) {}
    override fun unregisterOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) {}
    override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
        override fun putString(k: String, v: String?) = apply { values[k] = v }
        override fun putStringSet(k: String, v: MutableSet<String>?) = apply { values[k] = v?.toMutableSet() }
        override fun putInt(k: String, v: Int) = apply { values[k] = v }
        override fun putLong(k: String, v: Long) = apply { values[k] = v }
        override fun putFloat(k: String, v: Float) = apply { values[k] = v }
        override fun putBoolean(k: String, v: Boolean) = apply { values[k] = v }
        override fun remove(k: String) = apply { values.remove(k) }
        override fun clear() = apply { values.clear() }
        override fun commit() = true
        override fun apply() {}
    }
}

class ApiTest {
    private val server = MockWebServer()
    private val prefs = MemoryPrefs()
    private lateinit var api: Api

    @Before fun start() { server.start(); api = Api(server.url("/").toString(), SessionCookieJar(prefs)) }
    @After fun stop() = server.shutdown()

    @Test fun loginKeepsSessionCookieAndSendsWriteHeader() = runTest {
        server.enqueue(MockResponse().setBody("""{"id":"u1","email":"a@b.de","full_name":"Dr. Anna Berger","organisation":"Kanzlei","unknown_field":1}""")
            .addHeader("Set-Cookie", "schimmelpilz_session=abc; Path=/; HttpOnly; Max-Age=3600"))
        server.enqueue(MockResponse().setBody("[]"))
        val user = api.login("a@b.de", "secret", null)
        assertEquals("Anna", user.firstName)
        assertEquals("AB", user.initials)
        api.cases()
        val login = server.takeRequest()
        assertEquals("1", login.getHeader("X-Schimmelpilz-Request"))
        assertTrue(login.body.readUtf8().contains("\"email\":\"a@b.de\""))
        assertEquals("schimmelpilz_session=abc", server.takeRequest().getHeader("Cookie"))
        // A new client with the same storage (app restart) still sends the session.
        server.enqueue(MockResponse().setBody("""{"id":"u1","email":"a@b.de"}"""))
        Api(server.url("/").toString(), SessionCookieJar(prefs)).me()
        assertEquals("schimmelpilz_session=abc", server.takeRequest().getHeader("Cookie"))
    }

    @Test fun serverErrorDetailIsReported() = runTest {
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"mfa_required"}"""))
        try { api.login("a@b.de", "secret", null); fail() } catch (e: ApiException) {
            assertEquals(401, e.status); assertEquals("mfa_required", e.detail)
        }
    }

    @Test fun casesParseRealServerShape() = runTest {
        server.enqueue(MockResponse().setBody("""[{"id":"c1","reference":"SCH-2026-000001","title":"Mietminderung","description":"x","language":"de","created_at":"2026-10-22T04:28:38+00:00",
            "details":{"status":"active","client_name":"Maria Schulz","legal_area":"tenancy","deadline":"2026-10-29","deadline_note":"Frist","dispute_value":2400.0,"received_on":null},
            "user_id":"u","archived_at":null,"archive_version":0,"documents":[{"id":"d","original_name":"a.pdf","content_type":"application/pdf","size_bytes":1,"created_at":"2026-10-22T04:28:38+00:00","extraction_status":"ready","reviewed_units":1}],
            "drafts":[],"tasks":[{"id":"t","case_id":"c1","title":"Prüfen","note":"","due_on":"2026-10-25","priority":"high","completed":false}],"activities":[]}]""".trimIndent()))
        val case = api.cases().single()
        assertEquals("Maria Schulz", case.details.clientName)
        assertEquals("2026-10-25" to "Prüfen", case.nextDue)
        assertEquals(1, case.documents.single().reviewedUnits)
    }

    @Test fun networkFailureBecomesStatusZero() = runTest {
        server.shutdown()
        try { api.cases(); fail() } catch (e: ApiException) { assertEquals(0, e.status) }
    }

    @Test fun deleteAccountSendsConfirmationAndForgetsSession() = runTest {
        prefs.values["cookies"] = mutableSetOf("http://localhost|schimmelpilz_session=abc; path=/")
        server.enqueue(MockResponse().setResponseCode(403).setBody("""{"detail":"password_incorrect"}"""))
        server.enqueue(MockResponse().setResponseCode(204))
        try { api.deleteAccount("wrong", "LÖSCHEN", null); fail() } catch (e: ApiException) { assertEquals("password_incorrect", e.detail) }
        assertTrue(prefs.values.containsKey("cookies"))
        api.deleteAccount("right", "LÖSCHEN", "123456")
        server.takeRequest()
        val request = server.takeRequest()
        assertEquals("/api/auth/account/delete", request.path)
        assertEquals("1", request.getHeader("X-Schimmelpilz-Request"))
        assertEquals("""{"password":"right","confirm":"LÖSCHEN","mfa_code":"123456"}""", request.body.readUtf8())
        assertTrue(!prefs.values.containsKey("cookies"))
    }

    @Test fun downloadWritesFileAndReportsErrors() = runTest {
        server.enqueue(MockResponse().setBody("%PDF-1.4 synthetic"))
        server.enqueue(MockResponse().setResponseCode(404).setBody("""{"detail":"Answer not found"}"""))
        val target = java.io.File.createTempFile("answer", ".pdf").also { it.delete() }
        api.download("api/cases/c1/research/r1/answer.pdf?lang=de", target)
        assertEquals("%PDF-1.4 synthetic", target.readText())
        assertEquals("/api/cases/c1/research/r1/answer.pdf?lang=de", server.takeRequest().path)
        try { api.download("api/cases/c1/research/x/answer.pdf", target); fail() } catch (e: ApiException) { assertEquals(404, e.status) }
    }
}
