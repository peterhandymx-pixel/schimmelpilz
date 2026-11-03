package de.schimmelpilz.app.data

import android.content.SharedPreferences
import androidx.core.content.edit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException
import java.util.UUID
import java.util.concurrent.TimeUnit

/** An error the server reported (`detail`), or a network failure (status 0). */
class ApiException(val status: Int, val detail: String) : Exception(detail)

/** Keeps the server's session cookie across app restarts, in app-private storage only. */
class SessionCookieJar(private val prefs: SharedPreferences) : CookieJar {
    private val key = "cookies"

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val kept = load().filterNot { old -> cookies.any { it.name == old.name && it.domain == old.domain && it.path == old.path } }
        val all = (kept + cookies).filter { it.expiresAt > System.currentTimeMillis() }
        prefs.edit { putStringSet(key, all.map { "${url.scheme}://${it.domain}|${it}" }.toSet()) }
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> = load().filter { it.matches(url) && it.expiresAt > System.currentTimeMillis() }

    private fun load(): List<Cookie> = prefs.getStringSet(key, emptySet()).orEmpty().mapNotNull { entry ->
        val (origin, header) = entry.split('|', limit = 2).takeIf { it.size == 2 } ?: return@mapNotNull null
        Cookie.parse(origin.toHttpUrl(), header)
    }

    @Synchronized
    fun clear() = prefs.edit { remove(key) }
}

@Serializable private data class Login(val email: String, val password: String, val mfa_code: String? = null)
@Serializable private data class Ask(val request_id: String, val question: String, val language: String, val workflow: String = "research", val use_legal_catalogue: Boolean = true)
@Serializable private data class NewTask(val title: String, val due_on: String? = null, val priority: String = "normal", val note: String = "")
@Serializable private data class EditTask(val title: String, val due_on: String? = null, val priority: String = "normal", val note: String = "", val completed: Boolean)
@Serializable private data class Assign(val case_id: String, val expected_version: Int)
@Serializable private data class Archive(val archived: Boolean, val expected_version: Int)
@Serializable private data class Switch(val owner_id: String)
@Serializable private data class DeleteAccount(val password: String, val confirm: String, val mfa_code: String? = null)

class Api(baseUrl: String, private val cookies: SessionCookieJar) {
    private val base = baseUrl.toHttpUrl()
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true }
    private val jsonType = "application/json".toMediaType()

    private val client = OkHttpClient.Builder()
        .cookieJar(cookies)
        .connectTimeout(15, TimeUnit.SECONDS)
        // A local model answer can take minutes on a CPU-only server.
        .readTimeout(5, TimeUnit.MINUTES)
        .addInterceptor { chain ->
            // The server requires this header on every write (CSRF protection); harmless on reads.
            chain.proceed(chain.request().newBuilder().header("X-Schimmelpilz-Request", "1").header("Accept", "application/json").build())
        }
        .build()

    fun url(path: String): String = base.resolve(path.removePrefix("/"))!!.toString()

    private suspend fun call(method: String, path: String, body: RequestBody? = null): String = withContext(Dispatchers.IO) {
        val request = Request.Builder().url(url(path)).method(method, body ?: if (method == "GET" || method == "DELETE") null else ByteArray(0).toRequestBody()).build()
        try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (!response.isSuccessful) throw ApiException(response.code, detail(text))
                text
            }
        } catch (error: IOException) {
            throw ApiException(0, "network")
        }
    }

    private fun detail(text: String): String = runCatching {
        when (val value = json.parseToJsonElement(text).jsonObject["detail"]) {
            is JsonPrimitive -> value.contentOrNull ?: ""
            is JsonArray -> (value.firstOrNull() as? JsonObject)?.get("msg")?.jsonPrimitive?.contentOrNull ?: "invalid"
            else -> ""
        }
    }.getOrDefault("")

    private inline fun <reified T> body(value: T): RequestBody = json.encodeToString(value).toRequestBody(jsonType)

    suspend fun login(email: String, password: String, mfaCode: String?): User =
        json.decodeFromString(call("POST", "api/auth/login", body(Login(email.trim(), password, mfaCode?.takeIf { it.isNotBlank() }))))

    suspend fun me(): User = json.decodeFromString(call("GET", "api/auth/me"))

    suspend fun logout() {
        runCatching { call("POST", "api/auth/logout") }
        cookies.clear()
    }

    suspend fun cases(): List<CaseFile> = json.decodeFromString(call("GET", "api/cases"))

    suspend fun case(id: String): CaseFile = json.decodeFromString(call("GET", "api/cases/$id"))

    suspend fun researchStatus(): ResearchStatus = json.decodeFromString(call("GET", "api/research/status"))

    suspend fun research(caseId: String): List<ResearchRun> = json.decodeFromString(call("GET", "api/cases/$caseId/research"))

    suspend fun ask(caseId: String, question: String, language: String): ResearchRun =
        json.decodeFromString(call("POST", "api/cases/$caseId/research", body(Ask(UUID.randomUUID().toString(), question, language))))

    suspend fun inbox(): List<InboxItem> = json.decodeFromString(call("GET", "api/inbox"))

    suspend fun upload(fileName: String, mime: String, bytes: ByteArray, receivedOn: String, subject: String, sender: String) {
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", fileName, bytes.toRequestBody(mime.toMediaType()))
            .addFormDataPart("received_on", receivedOn)
            .addFormDataPart("subject", subject)
            .addFormDataPart("sender", sender)
            .build()
        call("POST", "api/inbox", form)
    }

    suspend fun uploadToCase(caseId: String, fileName: String, mime: String, bytes: ByteArray) {
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", fileName, bytes.toRequestBody(mime.toMediaType()))
            .build()
        call("POST", "api/cases/$caseId/documents", form)
    }

    suspend fun assign(item: InboxItem, caseId: String) {
        call("POST", "api/inbox/${item.id}/assign", body(Assign(caseId, item.version)))
    }

    suspend fun addTask(caseId: String, title: String, dueOn: String?, priority: String) {
        call("POST", "api/cases/$caseId/tasks", body(NewTask(title.trim(), dueOn?.ifBlank { null }, priority)))
    }

    suspend fun setTaskDone(task: Task, done: Boolean) {
        call("PUT", "api/cases/${task.caseId}/tasks/${task.id}", body(EditTask(task.title, task.dueOn, task.priority, task.note, done)))
    }

    /**
     * Changes title, facts and status. The server replaces the whole record, so this starts from the case as the
     * server holds it (all fields, also those the app does not know) and changes only these three.
     */
    suspend fun updateCase(id: String, title: String, description: String, status: String) {
        val current = json.parseToJsonElement(call("GET", "api/cases/$id")).jsonObject
        val details = JsonObject(current["details"]!!.jsonObject + ("status" to JsonPrimitive(status)))
        val update = JsonObject(mapOf("title" to JsonPrimitive(title.trim()), "description" to JsonPrimitive(description.trim()),
            "language" to (current["language"] ?: JsonPrimitive("de")), "details" to details))
        call("PUT", "api/cases/$id", json.encodeToString(JsonObject.serializer(), update).toRequestBody(jsonType))
    }

    suspend fun archive(case: CaseFile, archived: Boolean) {
        call("PUT", "api/cases/${case.id}/archive", body(Archive(archived, case.archiveVersion)))
    }

    suspend fun team(): Team = json.decodeFromString(call("GET", "api/team"))

    /** Selects the workspace for this session (the server keeps it in a cookie). */
    suspend fun switchWorkspace(ownerId: String) { call("POST", "api/team/switch", body(Switch(ownerId))) }

    suspend fun billing(): Billing = json.decodeFromString(call("GET", "api/billing"))

    /** Deletes the account and all its data on the server (Google Play requires deletion inside the app). */
    suspend fun deleteAccount(password: String, confirm: String, mfaCode: String?) {
        call("POST", "api/auth/account/delete", body(DeleteAccount(password, confirm, mfaCode?.takeIf { it.isNotBlank() })))
        cookies.clear()
    }

    /** Saves a server export (PDF, Word) to [target]. */
    suspend fun download(path: String, target: File): File = withContext(Dispatchers.IO) {
        val request = Request.Builder().url(url(path)).get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw ApiException(response.code, detail(response.body?.string().orEmpty()))
                target.parentFile?.mkdirs()
                target.outputStream().use { out -> response.body!!.byteStream().copyTo(out) }
                target
            }
        } catch (error: IOException) {
            throw ApiException(0, "network")
        }
    }
}
