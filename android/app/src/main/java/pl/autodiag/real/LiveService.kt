package pl.autodiag.real

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

/** Usługa pierwszoplanowa (connectedDevice) – utrzymuje połączenie przy długiej sesji danych na żywo przy zgaszonym ekranie. */
class LiveService : Service() {
    override fun onBind(i: Intent?): IBinder? = null
    override fun onStartCommand(i: Intent?, f: Int, id: Int): Int {
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(NotificationChannel("live", "Sesja diagnostyczna", NotificationManager.IMPORTANCE_LOW))
        val pi = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val n = (if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, "live") else @Suppress("DEPRECATION") Notification.Builder(this))
            .setContentTitle("AutoDiagPro E39").setContentText(i?.getStringExtra("text") ?: "Połączenie z autem aktywne")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth).setContentIntent(pi).setOngoing(true).build()
        if (Build.VERSION.SDK_INT >= 29) startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE) else startForeground(1, n)
        return START_NOT_STICKY
    }
}
