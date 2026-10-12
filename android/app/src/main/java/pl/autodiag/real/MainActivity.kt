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
    private var bt: ElmBtLink? = null
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
        root.addView(row("Błędy" to { run("faults") }, "Na żywo" to { run("live_data") }, "Rozłącz" to { disconnect() }))
        root.addView(row("Nie odpala na zimno" to { run("cold_start") }, "Moduły E39" to { run("modules") }, "Kasuj błędy" to { confirmClear() }))
        root.addView(row("Flash (zablokowane)" to { run("blocked", "Flashowanie (WinKFP)") },
            "NCS (zablokowane)" to { run("blocked", "Kodowanie NCS") }, "EWS (zablokowane)" to { run("blocked", "EWS") }).apply { alpha = 0.5f })
        out = tv("—\nbrak połączenia\n\n$dtcSrc", 12f).apply { typeface = Typeface.MONOSPACE; setTextIsSelectable(true) }
        root.addView(ScrollView(this).apply { addView(out) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)

        val f = IntentFilter(ACTION_USB)
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(usbReceiver, f, Context.RECEIVER_NOT_EXPORTED) else registerReceiver(usbReceiver, f)
    }

    override fun onDestroy() { unregisterReceiver(usbReceiver); disconnectNow(); super.onDestroy() }

    private fun setStatus(t: String) = runOnUiThread { status.text = "Status: $t" }

    private fun run(fn: String, vararg a: Any) {
        out.text = "…"
        io.execute {
            val r = try { bridge.callAttr(fn, *a).toString() } catch (e: Exception) { e.message ?: e.toString() }
            runOnUiThread { out.text = r }
        }
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

    @SuppressLint("MissingPermission")
    private fun pickBt() {
        if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT), 1); return
        }
        val ad = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
        if (ad == null || !ad.isEnabled) { setStatus("Bluetooth wyłączony – brak połączenia"); return }
        val devs = ad.bondedDevices.toList()
        if (devs.isEmpty()) { setStatus("brak sparowanych urządzeń – sparuj ELM327 w Ustawieniach (PIN 1234/0000)"); return }
        AlertDialog.Builder(this).setTitle("Wybierz ELM327")
            .setItems(devs.map { "${it.name ?: "?"} (${it.address})" }.toTypedArray()) { _, i ->
                setStatus("łączenie z ${devs[i].address}…")
                io.execute {
                    try { disconnectNow(); val l = ElmBtLink(devs[i]); bt = l; setStatus(bridge.callAttr("attach_elm", l).toString()) }
                    catch (e: Exception) { setStatus("błąd Bluetooth: ${e.message} – brak połączenia") }
                }
            }.show()
    }

    override fun onRequestPermissionsResult(rc: Int, p: Array<out String>, g: IntArray) {
        if (rc == 1 && g.firstOrNull() == PackageManager.PERMISSION_GRANTED) pickBt() else setStatus("brak zgody na Bluetooth – brak połączenia")
    }

    private fun disconnectNow() {
        bridge.callAttr("detach"); usb?.close(); usb = null; bt?.close(); bt = null
    }
    private fun disconnect() { io.execute { disconnectNow(); setStatus("— brak połączenia"); runOnUiThread { out.text = "—\nbrak połączenia" } } }
}
