package pl.autodiag.android

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.PendingIntent
import android.bluetooth.BluetoothManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.*
import com.hoho.android.usbserial.driver.UsbSerialProber
import pl.autodiag.kdcan.*
import java.util.concurrent.Executors

/** Powłoka aplikacji. Cała komunikacja jest w module :kdcan (Me72, Ds2, Elm327) + Links.kt – inna powłoka może je wołać tak samo. */
class MainActivity : Activity() {
    private val io = Executors.newSingleThreadExecutor()
    private var kdcan: Me72Transport? = null
    private var ds2Link: ByteLink? = null
    private var elm: Elm327? = null
    private var elmLink: TextLink? = null
    private lateinit var status: TextView; private lateinit var out: TextView; private lateinit var info: TextView
    private lateinit var rbUsb: RadioButton; private lateinit var btnModules: Button; private lateinit var btnClear: Button
    private val ACTION_USB = "pl.autodiag.android.USB_PERMISSION"

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 24, 24, 24) }
        fun btn(t: String, f: () -> Unit) = Button(this).apply { text = t; setOnClickListener { f() } }.also { col.addView(it) }
        col.addView(TextView(this).apply { text = "AutoDiag Pro – BMW E39 (tylko odczyt)"; textSize = 20f; setTypeface(null, Typeface.BOLD) })
        val rg = RadioGroup(this)
        rbUsb = RadioButton(this).apply { text = "Kabel K+DCAN (USB-OTG)"; id = View.generateViewId() }
        val rbBt = RadioButton(this).apply { text = "Bluetooth ELM327"; id = View.generateViewId() }
        rg.addView(rbUsb); rg.addView(rbBt); rbUsb.isChecked = true; col.addView(rg)
        info = TextView(this).also { col.addView(it) }
        status = TextView(this).apply { text = "Status: $NO_LINK"; setTypeface(null, Typeface.BOLD) }.also { col.addView(it) }
        btn("Połącz") { connect() }
        btn("Rozłącz") { disconnect() }
        btn("Identyfikacja") { run { if (usb()) Me72(kdcan).ident() else listOf(elm?.vin() ?: Row("VIN", DASH, "", NO_LINK), Row("Protokół", elm?.protocol ?: DASH, "", "")) } }
        btn("Pamięć błędów") { run { if (usb()) Me72(kdcan).faults() else { val e = elm ?: Elm327(null); e.storedDtc() + e.pendingDtc() } } }
        btn("Dane na żywo") { run { if (usb()) Me72(kdcan).engine() + Me72(kdcan).roughness() else { val e = elm ?: Elm327(null); e.live() + e.battery() } } }
        btnModules = btn("Moduły E39 (DS2)") { run { Ds2.Client(ds2Link).scan() } }
        btnClear = btn("Kasuj błędy silnika (OBD Mode 04)") { confirmClear() }
        out = TextView(this).apply { typeface = Typeface.MONOSPACE; text = "—" }.also { col.addView(it) }
        setContentView(ScrollView(this).apply { addView(col) })
        rg.setOnCheckedChangeListener { _, _ -> disconnect(); updateMode() }
        updateMode()
        val f = IntentFilter(ACTION_USB)
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(usbRx, f, Context.RECEIVER_NOT_EXPORTED) else registerReceiver(usbRx, f)
    }

    private fun usb() = rbUsb.isChecked

    private fun updateMode() {
        info.text = if (usb()) "Kabel K+DCAN: przełącznik w trybie K-line (piny 7+8), zapłon w pozycji 2. DME ME7.2 + odczyt innych modułów. Programowanie, kodowanie i EWS są wyłączone."
        else "UWAGA: Bluetooth ELM327 to TYLKO ogólne OBD-II silnika (DME). Brak modułów BMW (ABS, airbag, skrzynia, zegary…), brak danych specyficznych dla BMW. Sparuj adapter w ustawieniach Bluetooth telefonu (PIN zwykle 1234)."
        btnModules.visibility = if (usb()) View.VISIBLE else View.GONE
        btnClear.visibility = if (usb()) View.GONE else View.VISIBLE
    }

    private fun setStatus(t: String) = runOnUiThread { status.text = "Status: $t" }

    private fun run(block: () -> List<Row>) {
        out.text = "Czytam…"
        io.execute {
            val rows = try { block() } catch (e: Exception) { listOf(Row("Błąd", DASH, "", e.message ?: e.toString())) }
            val txt = rows.joinToString("\n") { r -> "${r.name}: ${r.value} ${r.unit}".trimEnd() + if (r.status != "OK" && r.status.isNotEmpty()) "  [${r.status}]" else "" }
            runOnUiThread { out.text = txt }
        }
    }

    private fun connect() { disconnect(); if (usb()) connectUsb() else connectBt() }

    private fun disconnect() {
        val k = kdcan; val l = elmLink; kdcan = null; ds2Link = null; elm = null; elmLink = null
        io.execute { k?.close(); l?.close() }
        setStatus(NO_LINK); if (::out.isInitialized) out.text = "—"
    }

    // ---------------- USB
    private fun connectUsb() {
        val um = getSystemService(Context.USB_SERVICE) as UsbManager
        val drv = UsbSerialProber.getDefaultProber().findAllDrivers(um).firstOrNull()
            ?: return setStatus("$NO_LINK – nie wykryto kabla FTDI (sprawdź przejściówkę OTG)")
        if (!um.hasPermission(drv.device)) {
            val i = Intent(ACTION_USB).setPackage(packageName)
            val flags = if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
            um.requestPermission(drv.device, PendingIntent.getBroadcast(this, 0, i, flags))
            return setStatus("czekam na zgodę USB…")
        }
        io.execute {
            try {
                val link = UsbKdcanLink(um, drv); ds2Link = link; kdcan = Me72Transport(link)
                setStatus("kabel otwarty (9600 8E1) – naciśnij Identyfikacja, by sprawdzić DME")
            } catch (e: Exception) { setStatus("$NO_LINK – ${e.message}") }
        }
    }

    private val usbRx = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            if (i.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) connectUsb() else setStatus("$NO_LINK – brak zgody na USB")
        }
    }

    // ---------------- Bluetooth
    private fun btPerms() = if (Build.VERSION.SDK_INT >= 31) arrayOf(Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.BLUETOOTH_SCAN) else emptyArray()

    private fun connectBt() {
        val missing = btPerms().filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) { requestPermissions(missing.toTypedArray(), 1); return setStatus("czekam na zgodę Bluetooth…") }
        val ad = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
            ?: return setStatus("$NO_LINK – telefon nie ma Bluetooth")
        if (!ad.isEnabled) return setStatus("$NO_LINK – włącz Bluetooth")
        val devs = try { ad.bondedDevices.toList() } catch (e: SecurityException) { return setStatus("$NO_LINK – brak zgody Bluetooth") }
        if (devs.isEmpty()) return setStatus("$NO_LINK – brak sparowanych urządzeń; sparuj ELM327 w ustawieniach")
        val names = devs.map { (try { it.name } catch (_: SecurityException) { null } ?: "?") + "\n" + it.address }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Wybierz adapter ELM327").setItems(names) { _, w ->
            setStatus("łączę z ${devs[w].address}…")
            io.execute {
                try {
                    try { ad.cancelDiscovery() } catch (_: SecurityException) {}
                    val sock = devs[w].createRfcommSocketToServiceRecord(BtElmLink.SPP); sock.connect()
                    val l = BtElmLink(sock); val e = Elm327(l); elmLink = l
                    val id = e.init(); elm = e
                    setStatus("połączono: $id, protokół ${e.protocol} (ogólne OBD-II silnika)")
                } catch (e: Exception) { elmLink?.close(); elmLink = null; elm = null; setStatus("$NO_LINK – ${e.message}") }
            }
        }.show()
    }

    override fun onRequestPermissionsResult(rc: Int, p: Array<out String>, g: IntArray) {
        if (rc == 1) { if (g.isNotEmpty() && g.all { it == PackageManager.PERMISSION_GRANTED }) connectBt() else setStatus("$NO_LINK – odmówiono zgody Bluetooth") }
    }

    private fun confirmClear() {
        val e = elm ?: return setStatus(NO_LINK)
        AlertDialog.Builder(this).setTitle("Skasować błędy silnika?")
            .setMessage("To wyśle OBD Mode 04: skasuje zapisane błędy silnika, zamrożone ramki i zresetuje gotowość testów (readiness). Silnik wyłączony, zapłon w pozycji 2. Najpierw zapisz listę błędów. Kontynuować?")
            .setNegativeButton("Anuluj", null)
            .setPositiveButton("Tak, kasuj") { _, _ -> run { listOf(try { Row("Kasowanie", e.clearDtcConfirmed(), "", "OK") } catch (x: DmeError) { Row("Kasowanie", DASH, "", x.message ?: "") }) } }
            .show()
    }

    override fun onDestroy() { disconnect(); unregisterReceiver(usbRx); io.shutdown(); super.onDestroy() }
}
