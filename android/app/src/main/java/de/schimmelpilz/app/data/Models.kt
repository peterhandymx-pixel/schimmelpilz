package de.schimmelpilz.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

// Field names follow the server's JSON exactly (snake_case); unknown fields are ignored.

@Serializable
data class User(
    val id: String,
    val email: String,
    val audience: String = "consumer",
    @SerialName("full_name") val fullName: String = "",
    val organisation: String = "",
    @SerialName("is_admin") val isAdmin: Boolean = false,
    @SerialName("mfa_enabled") val mfaEnabled: Boolean = false,
) {
    val firstName: String get() = fullName.split(' ').firstOrNull { it.isNotBlank() && !it.endsWith('.') } ?: fullName
    val initials: String get() = fullName.split(' ').filter { it.isNotBlank() && !it.endsWith('.') }.take(2).joinToString("") { it.take(1).uppercase() }
}

@Serializable
data class CaseDetails(
    val status: String = "active",
    val responsible: String = "",
    @SerialName("client_name") val clientName: String = "",
    @SerialName("client_role") val clientRole: String = "other",
    @SerialName("opponent_name") val opponentName: String = "",
    @SerialName("opponent_address") val opponentAddress: String = "",
    @SerialName("legal_area") val legalArea: String = "general",
    val stage: String = "initial",
    val court: String = "",
    val deadline: String? = null,
    @SerialName("deadline_note") val deadlineNote: String = "",
    @SerialName("dispute_value") val disputeValue: Double? = null,
    val currency: String = "EUR",
)

@Serializable
data class CaseDocument(
    val id: String,
    @SerialName("original_name") val name: String,
    @SerialName("content_type") val contentType: String = "",
    @SerialName("size_bytes") val sizeBytes: Long = 0,
    @SerialName("created_at") val createdAt: String,
    @SerialName("extraction_status") val extractionStatus: String? = null,
    @SerialName("reviewed_units") val reviewedUnits: Int = 0,
    @SerialName("inbox_reassigned_at") val historical: String? = null,
    /** Automatic reading after upload: queued, running, done, no_text, ocr_unavailable, failed, interrupted. */
    @SerialName("auto_text_status") val autoTextStatus: String? = null,
    @SerialName("auto_text_ocr_pages") val ocrPages: Int = 0,
) {
    val reading: Boolean get() = autoTextStatus == "queued" || autoTextStatus == "running"
}

@Serializable
data class Draft(
    val id: String,
    val language: String = "de",
    val recipient: String = "",
    val kind: String = "letter",
    val version: Int = 1,
    @SerialName("review_status") val reviewStatus: String = "draft",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class Task(
    val id: String,
    @SerialName("case_id") val caseId: String,
    val title: String,
    val note: String = "",
    @SerialName("due_on") val dueOn: String? = null,
    val priority: String = "normal",
    val completed: Boolean = false,
)

@Serializable
data class CaseFile(
    val id: String,
    val reference: String,
    val title: String,
    val description: String = "",
    val language: String = "de",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("archived_at") val archivedAt: String? = null,
    @SerialName("archive_version") val archiveVersion: Int = 0,
    val details: CaseDetails = CaseDetails(),
    val documents: List<CaseDocument> = emptyList(),
    val drafts: List<Draft> = emptyList(),
    val tasks: List<Task> = emptyList(),
    val activities: List<Activity> = emptyList(),
) {
    /** Next open date: the case's own deadline or an open task, whichever comes first. */
    val nextDue: Pair<String, String>?
        get() = (listOfNotNull(details.deadline?.let { it to details.deadlineNote.ifBlank { title } }) +
            tasks.filter { !it.completed && it.dueOn != null }.map { it.dueOn!! to it.title }).minByOrNull { it.first }
}

@Serializable
data class Activity(
    val id: String,
    val action: String,
    val detail: String = "",
    @SerialName("created_at") val createdAt: String = "",
)

/** A workspace the user may work in: their own, or one they were invited to (GET /api/team). */
@Serializable
data class Workspace(@SerialName("owner_id") val ownerId: String, val name: String? = null, val role: String = "owner")

@Serializable
data class Team(val selected: String = "", val role: String = "owner", val workspaces: List<Workspace> = emptyList())

@Serializable
data class LegalSource(
    @SerialName("citation_id") val citationId: String = "",
    val key: String = "",
    val title: String = "",
    val pinpoint: String = "",
    val url: String = "",
    @SerialName("fetched_at") val fetchedAt: String? = null,
    val text: String = "",
    @SerialName("excerpt_truncated") val truncated: Boolean = false,
)

@Serializable
data class ResearchRun(
    val id: String,
    val question: String,
    val answer: String? = null,
    val status: String = "completed",
    val language: String = "de",
    val model: String = "",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("legal_sources") val legalSources: List<LegalSource> = emptyList(),
    @SerialName("citation_audit") val citationAudit: JsonElement? = null,
)

@Serializable
data class ResearchStatus(val ready: Boolean = false, val model: String = "", val reason: String = "", val enabled: Boolean = true)

@Serializable
data class InboxItem(
    val id: String,
    @SerialName("original_name") val name: String,
    val subject: String = "",
    val sender: String = "",
    @SerialName("received_on") val receivedOn: String,
    val note: String = "",
    val version: Int = 1,
    @SerialName("case_id") val caseId: String? = null,
    @SerialName("case_reference") val caseReference: String? = null,
    @SerialName("case_title") val caseTitle: String? = null,
)

@Serializable
data class Billing(
    val plan: String = "personal",
    val status: String = "pilot",
    @SerialName("effective_status") val effectiveStatus: String = "pilot",
    @SerialName("trial_end") val trialEnd: String? = null,
    @SerialName("period_end") val periodEnd: String? = null,
    val plans: Map<String, Int> = emptyMap(),
)
