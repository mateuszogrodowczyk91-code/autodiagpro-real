package pl.autodiag.real

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.app.PendingIntent
import android.bluetooth.BluetoothManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.*
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.hoho.android.usbserial.driver.UsbSerialProber
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val io = Executors.newSingleThreadExecutor()
    private lateinit var bridge: PyObject
    private lateinit var status: TextView
    private lateinit var out: TextView
    private var usb: UsbKLink? = null
    private var bt: ElmLink? = null
    private lateinit var rssiView: TextView
    private lateinit var liveBtn: Button
    @Volatile private var busy = false
    @Volatile private var liveOn = false
    private var scanRssi: Int? = null
    private val ui = android.os.Handler(android.os.Looper.getMainLooper())
    private val ticker = object : Runnable {
        override fun run() {
            val l = bt
            if (l is ElmBleLink) l.pollRssi()
            rssiView.text = if (l == null) "RSSI: —" else "RSSI: " + ((l.rssi ?: scanRssi)?.let { "$it dBm" + (if (l.rssi == null) " (ze skanu)" else "") + quality(it) } ?: "—") +
                "   |   ponowne połączenia: ${l.reconnects}"
            if (l != null && !busy && !liveOn) io.execute { if (!busy) try { bridge.callAttr("keepalive") } catch (_: Exception) {} }
            ui.postDelayed(this, 4000)
        }
    }
    private fun quality(r: Int) = when { r >= -60 -> " – bardzo dobry"; r >= -75 -> " – dobry"; r >= -85 -> " – słaby (przybliż telefon)"; else -> " – bardzo słaby" }
    private val ACTION_USB = "pl.autodiag.real.USB_PERMISSION"

    private val usbReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            if (i.action == ACTION_USB) {
                if (i.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) connectUsb()
                else setStatus("Brak zgody na USB – " + "brak połączenia")
            }
        }
    }

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        bridge = Python.getInstance().getModule("android_bridge")
        val dtcSrc = bridge.callAttr("set_prg_dir", getExternalFilesDir(null)?.absolutePath ?: filesDir.absolutePath).toString()

        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 48, 24, 24); setBackgroundColor(Color.rgb(18, 20, 24)) }
        fun tv(t: String, size: Float = 14f) = TextView(this).apply { text = t; textSize = size; setTextColor(Color.WHITE) }
        root.addView(tv("AutoDiagPro – BMW E39 540i (M62, ME7.2)", 18f))
        root.addView(tv("Odczyt + kasowanie błędów (z potwierdzeniem). Flash, kodowanie NCS i EWS są zablokowane.", 12f).apply { setTextColor(Color.rgb(255, 180, 80)) })
        status = tv("Status: — brak połączenia", 14f).apply { setPadding(0, 16, 0, 16) }
        root.addView(status)

        fun row(vararg b: Pair<String, () -> Unit>) = LinearLayout(this).apply {
            b.forEach { (t, f) -> addView(Button(this@MainActivity).apply { text = t; isAllCaps = false; setOnClickListener { f() } },
                LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)) }
        }
        root.addView(row("Kabel K+DCAN (USB-OTG)" to { connectUsb() }, "Bluetooth ELM327" to { pickBt() }))
        root.addView(tv("ELM327 = tylko standardowe OBD-II, tylko silnik. Pełny odczyt modułów BMW tylko przez kabel K+DCAN.", 11f).apply { setTextColor(Color.LTGRAY) })
        rssiView = tv("RSSI: —", 12f).apply { setTextColor(Color.LTGRAY) }; root.addView(rssiView)
        root.addView(row("Błędy" to { run("faults") }, "Na żywo" to { run("live_data") }, "Rozłącz" to { disconnect() }))
        liveBtn = Button(this).apply { text = "Na żywo ciągle: WYŁ."; isAllCaps = false; setOnClickListener { toggleLive() } }
        root.addView(liveBtn)
        root.addView(row("Nie odpala na zimno" to { run("cold_start") }, "Moduły E39" to { run("modules") }, "Kasuj błędy" to { confirmClear() }))
        root.addView(row("Flash (zablokowane)" to { run("blocked", "Flashowanie (WinKFP)") },
            "NCS (zablokowane)" to { run("blocked", "Kodowanie NCS") }, "EWS (zablokowane)" to { run("blocked", "EWS") }).apply { alpha = 0.5f })
        out = tv("—\nbrak połączenia\n\n$dtcSrc", 12f).apply { typeface = Typeface.MONOSPACE; setTextIsSelectable(true) }
        root.addView(ScrollView(this).apply { addView(out) }, LinearLayout.LayoutParams(-1, 0, 1f))
        root.setOnApplyWindowInsetsListener { v, ins ->   // edge-to-edge (Android 15/16)
            if (Build.VERSION.SDK_INT >= 30) {
                val b = ins.getInsets(android.view.WindowInsets.Type.systemBars() or android.view.WindowInsets.Type.displayCutout())
                v.setPadding(b.left + 24, b.top + 16, b.right + 24, b.bottom + 16)
            } else @Suppress("DEPRECATION") v.setPadding(ins.systemWindowInsetLeft + 24, ins.systemWindowInsetTop + 16, ins.systemWindowInsetRight + 24, ins.systemWindowInsetBottom + 16)
            ins
        }
        setContentView(root)
        ui.post(ticker)

        val f = IntentFilter(ACTION_USB)
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(usbReceiver, f, Context.RECEIVER_NOT_EXPORTED) else registerReceiver(usbReceiver, f)
    }

    override fun onDestroy() { liveOn = false; ui.removeCallbacksAndMessages(null); stopService(Intent(this, LiveService::class.java)); unregisterReceiver(usbReceiver); disconnectNow(); super.onDestroy() }

    private fun setStatus(t: String) = runOnUiThread { status.text = "Status: $t" }

    private fun run(fn: String, vararg a: Any) {
        out.text = "…"
        io.execute {
            busy = true
            val r = try { bridge.callAttr(fn, *a).toString() } catch (e: Exception) { e.message ?: e.toString() }
            busy = false
            runOnUiThread { out.text = r }
        }
    }

    private fun toggleLive() {
        liveOn = !liveOn
        liveBtn.text = "Na żywo ciągle: " + if (liveOn) "WŁ." else "WYŁ."
        val svc = Intent(this, LiveService::class.java)
        if (liveOn) {
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 3)
            try { if (Build.VERSION.SDK_INT >= 26) startForegroundService(svc) else startService(svc) } catch (e: Exception) { setStatus("usługa w tle niedostępna: ${e.message}") }
            io.execute(object : Runnable { override fun run() {
                if (!liveOn) return
                busy = true
                val r = try { bridge.callAttr("live_data").toString() } catch (e: Exception) { e.message ?: e.toString() }
                busy = false
                runOnUiThread { if (liveOn) out.text = r }
                ui.postDelayed({ if (liveOn) io.execute(this) }, 1000)
            } })
        } else stopService(svc)
    }

    private fun confirmClear() {
        val warn = bridge.callAttr("clear_warning").toString()
        AlertDialog.Builder(this).setTitle("Kasować błędy?").setMessage(warn + "\n\nCzy zapłon jest włączony, a silnik zgaszony?")
            .setPositiveButton("Tak, kasuj") { _, _ -> run("clear_faults", true) }
            .setNegativeButton("Anuluj", null).show()
    }

    private fun connectUsb() {
        val m = getSystemService(Context.USB_SERVICE) as UsbManager
        val drv = UsbSerialProber.getDefaultProber().findAllDrivers(m).firstOrNull()
        if (drv == null) { setStatus("nie widzę kabla K+DCAN (FTDI) – podłącz przez OTG; brak połączenia"); return }
        if (!m.hasPermission(drv.device)) {
            val flags = if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
            m.requestPermission(drv.device, PendingIntent.getBroadcast(this, 0, Intent(ACTION_USB).setPackage(packageName), flags)); return
        }
        io.execute {
            try {
                disconnectNow(); val l = UsbKLink(m, drv); usb = l
                setStatus(bridge.callAttr("attach_kline", l).toString())
            } catch (e: Exception) { setStatus("błąd USB: ${e.message} – brak połączenia") }
        }
    }

    private fun btPerms(): Array<String> = if (Build.VERSION.SDK_INT >= 31)
        arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT) else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)

    @SuppressLint("MissingPermission")
    private fun pickBt() {
        val miss = btPerms().filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (miss.isNotEmpty()) { requestPermissions(miss.toTypedArray(), 1); return }
        val ad = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
        if (ad == null || !ad.isEnabled) { setStatus("Bluetooth wyłączony – brak połączenia"); return }
        // skan 6 s: BLE (Vgate/OBDLink CX…) + klasyczny (ELM327 SPP) + sparowane
        data class Found(val dev: android.bluetooth.BluetoothDevice, var rssi: Int?, var ble: Boolean)
        val found = LinkedHashMap<String, Found>()
        ad.bondedDevices.forEach { found[it.address] = Found(it, null, it.type == android.bluetooth.BluetoothDevice.DEVICE_TYPE_LE) }
        val bleCb = object : android.bluetooth.le.ScanCallback() {
            override fun onScanResult(t: Int, r: android.bluetooth.le.ScanResult) {
                val f = found.getOrPut(r.device.address) { Found(r.device, r.rssi, true) }; f.rssi = r.rssi
                if (r.device.type == android.bluetooth.BluetoothDevice.DEVICE_TYPE_LE) f.ble = true
            }
        }
        val clRx = object : BroadcastReceiver() {
            override fun onReceive(c: Context, i: Intent) {
                val d: android.bluetooth.BluetoothDevice = (if (Build.VERSION.SDK_INT >= 33) i.getParcelableExtra(android.bluetooth.BluetoothDevice.EXTRA_DEVICE, android.bluetooth.BluetoothDevice::class.java)
                    else @Suppress("DEPRECATION") i.getParcelableExtra(android.bluetooth.BluetoothDevice.EXTRA_DEVICE)) ?: return
                val r = i.getShortExtra(android.bluetooth.BluetoothDevice.EXTRA_RSSI, Short.MIN_VALUE).toInt()
                found.getOrPut(d.address) { Found(d, null, false) }.rssi = if (r == Short.MIN_VALUE.toInt()) null else r
            }
        }
        registerReceiver(clRx, IntentFilter(android.bluetooth.BluetoothDevice.ACTION_FOUND))
        val sc = ad.bluetoothLeScanner
        try { sc?.startScan(null, android.bluetooth.le.ScanSettings.Builder().setScanMode(android.bluetooth.le.ScanSettings.SCAN_MODE_LOW_LATENCY).build(), bleCb) } catch (_: Exception) {}
        try { ad.startDiscovery() } catch (_: Exception) {}
        setStatus("szukam adapterów ELM327 (6 s)…")
        ui.postDelayed({
            try { sc?.stopScan(bleCb) } catch (_: Exception) {}; try { ad.cancelDiscovery() } catch (_: Exception) {}
            try { unregisterReceiver(clRx) } catch (_: Exception) {}
            val list = found.values.filter { it.dev.name != null || it.dev.bondState == android.bluetooth.BluetoothDevice.BOND_BONDED }
                .sortedWith(compareByDescending<Found> { (it.dev.name ?: "").uppercase().let { n -> listOf("OBD", "ELM", "VLINK", "VGATE", "ICAR", "OBDLINK", "VEEPEAK").any { k -> n.contains(k) } } }.thenByDescending { it.rssi ?: -200 })
            if (list.isEmpty()) { setStatus("nie znaleziono adaptera – włącz zapłon, sparuj ELM327 (PIN 1234/0000); brak połączenia"); return@postDelayed }
            AlertDialog.Builder(this).setTitle("Wybierz ELM327")
                .setItems(list.map { "${it.dev.name ?: "?"} ${if (it.ble) "[BLE]" else "[SPP]"} ${it.rssi?.let { r -> "$r dBm" } ?: ""}\n${it.dev.address}" }.toTypedArray()) { _, i ->
                    val f = list[i]; setStatus("łączenie z ${f.dev.address}…"); scanRssi = f.rssi
                    io.execute {
                        try {
                            disconnectNow()
                            val l: ElmLink = if (f.ble) ElmBleLink(this, f.dev) else ElmSppLink(f.dev, ad)
                            bt = l; setStatus(l.label + ": " + bridge.callAttr("attach_elm", l).toString())
                        } catch (e: Exception) { setStatus("błąd Bluetooth: ${e.message} – brak połączenia") }
                    }
                }.show()
        }, 6000)
    }

    override fun onRequestPermissionsResult(rc: Int, p: Array<out String>, g: IntArray) {
        if (rc != 1) return
        if (g.isNotEmpty() && g.all { it == PackageManager.PERMISSION_GRANTED }) pickBt() else setStatus("brak zgody na Bluetooth – brak połączenia")
    }

    private fun disconnectNow() {
        bridge.callAttr("detach"); usb?.close(); usb = null; bt?.close(); bt = null
    }
    private fun disconnect() { if (liveOn) toggleLive(); io.execute { disconnectNow(); setStatus("— brak połączenia"); runOnUiThread { out.text = "—\nbrak połączenia" } } }
}
