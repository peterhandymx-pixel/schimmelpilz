package de.schimmelpilz.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import de.schimmelpilz.app.data.Api
import de.schimmelpilz.app.data.ApiException
import de.schimmelpilz.app.data.CaseFile
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.data.SessionCookieJar
import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.temporal.ChronoUnit

/**
 * Deadline reminders: once a day the phone asks the server for the cases and notifies about open deadlines and tasks
 * that are due in two days, tomorrow, today or are overdue. Each date is announced once per stage.
 */
object Reminders {
    private const val WORK = "deadline-reminders"
    private const val CHANNEL = "deadlines"
    const val OPEN_TAB = "open_tab"

    /** One date the user should hear about; [days] < 0 means overdue. */
    data class Due(val key: String, val caseId: String, val reference: String, val title: String, val date: String, val days: Long)

    /** Open dates due within two days or overdue (at most two weeks back), soonest first. */
    fun due(cases: List<CaseFile>, today: LocalDate): List<Due> = cases.flatMap { case ->
        val tasks = case.tasks.filter { !it.completed && it.dueOn != null }.map { Triple("task:${it.id}", it.title, it.dueOn!!) }
        val deadline = listOfNotNull(case.details.deadline?.let { Triple("case:${case.id}", case.details.deadlineNote.ifBlank { case.title }, it) })
        (deadline + tasks).mapNotNull { (key, title, date) ->
            val days = Dates.toDate(date)?.let { ChronoUnit.DAYS.between(today, it) } ?: return@mapNotNull null
            if (days in -14..2) Due(key, case.id, case.reference, title, date, days) else null
        }
    }.sortedBy { it.days }

    /** Stage of a date: announced again only when it moves to the next stage (2 days → tomorrow → today → overdue). */
    fun stage(days: Long): String = when { days < 0 -> "overdue"; else -> "d$days" }

    fun enabled(context: Context): Boolean = prefs(context).getBoolean("reminders", true)

    fun setEnabled(context: Context, on: Boolean) {
        prefs(context).edit { putBoolean("reminders", on) }
        schedule(context)
    }

    fun permissionNeeded(context: Context): Boolean = Build.VERSION.SDK_INT >= 33 &&
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED

    /** Daily check at about 08:00 while signed in and switched on; cancelled otherwise. */
    fun schedule(context: Context, signedIn: Boolean = true) {
        val work = WorkManager.getInstance(context)
        if (!signedIn || !enabled(context)) { work.cancelUniqueWork(WORK); return }
        val now = LocalDateTime.now()
        val next = now.toLocalDate().atTime(8, 0).let { if (it.isAfter(now)) it else it.plusDays(1) }
        val request = PeriodicWorkRequestBuilder<Worker>(Duration.ofDays(1))
            .setInitialDelay(Duration.between(now, next))
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        work.enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.UPDATE, request)
    }

    private fun prefs(context: Context) = context.getSharedPreferences("schimmelpilz", Context.MODE_PRIVATE)

    class Worker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
        override suspend fun doWork(): Result {
            val context = applicationContext
            if (!enabled(context) || permissionNeeded(context)) return Result.success()
            val api = Api(Server.url(context), SessionCookieJar(context.getSharedPreferences("session", Context.MODE_PRIVATE)))
            val cases = try { api.cases().filter { it.archivedAt == null } } catch (e: ApiException) {
                // Signed out (401) or the server is unreachable: nothing to announce, try again tomorrow.
                return if (e.status == 0) Result.retry() else Result.success()
            }
            val prefs = prefs(context)
            val sent = prefs.getStringSet("reminded", emptySet()).orEmpty()
            val due = due(cases, Dates.today()).filter { "${it.key}|${it.date}|${stage(it.days)}" !in sent }
            if (due.isNotEmpty()) notify(context, due)
            // Keep only markers of dates that can still come up, so the set stays small.
            val kept = (sent + due.map { "${it.key}|${it.date}|${stage(it.days)}" })
                .filter { marker -> Dates.daysUntil(marker.split('|').getOrNull(1))?.let { it >= -14 } == true }.toSet()
            prefs.edit { putStringSet("reminded", kept) }
            return Result.success()
        }
    }

    @SuppressLint("MissingPermission") // checked in doWork() before this is called
    private fun notify(context: Context, due: List<Due>) {
        val de = (prefs(context).getString("lang", "de") ?: "de") == "de"
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, if (de) "Fristen" else "Deadlines", NotificationManager.IMPORTANCE_DEFAULT))
        fun line(item: Due) = when {
            item.days < 0 -> if (de) "Überfällig" else "Overdue"
            item.days == 0L -> if (de) "Heute" else "Today"
            item.days == 1L -> if (de) "Morgen" else "Tomorrow"
            else -> if (de) "In ${item.days} Tagen" else "In ${item.days} days"
        } + " · ${Dates.label(item.date, if (de) "de" else "en")} · ${item.title} (${item.reference})"
        val open = PendingIntent.getActivity(context, 0,
            Intent(context, MainActivity::class.java).putExtra(OPEN_TAB, "deadlines").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val title = if (due.size == 1) line(due[0]).substringBefore(" · ") + ": " + due[0].title
            else if (de) "${due.size} Fristen stehen an" else "${due.size} deadlines coming up"
        val style = NotificationCompat.InboxStyle().also { s -> due.take(6).forEach { s.addLine(line(it)) } }
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(line(due[0]))
            .setStyle(style)
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(1, notification) }
    }
}
