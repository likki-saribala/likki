package com.likki.stride

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant

/** Read-only access to step totals in Health Connect. */
class HealthBridge(private val context: Context) {

    private val client: HealthConnectClient by lazy { HealthConnectClient.getOrCreate(context) }

    /** null when Health Connect can be used, otherwise the error code for the web app. */
    fun unavailableReason(): String? = when (HealthConnectClient.getSdkStatus(context, PROVIDER)) {
        HealthConnectClient.SDK_AVAILABLE -> null
        HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> Replies.UPDATE_REQUIRED
        else -> Replies.UNAVAILABLE
    }

    suspend fun hasPermission(): Boolean =
        client.permissionController.getGrantedPermissions().containsAll(PERMISSIONS)

    /** Step total for the range. Health Connect de-duplicates overlapping sources when aggregating. */
    suspend fun steps(range: LongRange): Long {
        val result = client.aggregate(
            AggregateRequest(
                metrics = setOf(StepsRecord.COUNT_TOTAL),
                timeRangeFilter = TimeRangeFilter.between(
                    Instant.ofEpochMilli(range.first),
                    Instant.ofEpochMilli(range.last + 1),
                ),
            ),
        )
        return result[StepsRecord.COUNT_TOTAL] ?: 0L
    }

    /** Opens Health Connect, or its store page when it is missing or out of date. */
    fun settingsIntent(): Intent =
        if (unavailableReason() == Replies.UPDATE_REQUIRED) {
            Intent(Intent.ACTION_VIEW).apply {
                setPackage("com.android.vending")
                data = Uri.parse("market://details?id=$PROVIDER&url=healthconnect%3A%2F%2Fonboarding")
                putExtra("overlay", true)
                putExtra("callerId", context.packageName)
            }
        } else {
            Intent(HealthConnectClient.ACTION_HEALTH_CONNECT_SETTINGS)
        }

    companion object {
        const val PROVIDER = "com.google.android.apps.healthdata"
        val PERMISSIONS: Set<String> = setOf(HealthPermission.getReadPermission(StepsRecord::class))
    }
}
