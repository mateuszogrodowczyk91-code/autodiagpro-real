package pl.autodiag.real

import android.annotation.SuppressLint
import android.hardware.usb.UsbManager
import com.hoho.android.usbserial.driver.UsbSerialDriver
import com.hoho.android.usbserial.driver.UsbSerialPort
import java.io.ByteArrayOutputStream

/** K-line przez kabel K+DCAN (FTDI) na USB-OTG. 9600 8E1, jak w wersji na laptopa (me72.SerialLink). Bez roota. */
class UsbKLink(manager: UsbManager, driver: UsbSerialDriver) {
    private val port: UsbSerialPort = driver.ports[0]
    private val name = "USB ${driver.device.deviceName} (VID %04X PID %04X)".format(driver.device.vendorId, driver.device.productId)
    private var timeoutMs = 1000
    private val pending = ByteArrayOutputStream()

    init {
        val conn = manager.openDevice(driver.device) ?: throw IllegalStateException("Brak zgody na USB")
        port.open(conn)
        port.setParameters(9600, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_EVEN)
        try { port.dtr = false; port.rts = false } catch (_: Exception) {}
        try { (port as? com.hoho.android.usbserial.driver.FtdiSerialDriver.FtdiSerialPort)?.setLatencyTimer(1) } catch (_: Exception) {}
        clear()
    }

    fun getName(): String = name
    fun setTimeout(s: Double) { timeoutMs = (s * 1000).toInt().coerceAtLeast(10) }
    @Synchronized fun clear() {
        pending.reset()
        try { port.purgeHwBuffers(true, false) } catch (_: Exception) {}
        val b = ByteArray(256)
        while (port.read(b, 20) > 0) {}
    }
    @Synchronized fun write(b: ByteArray) { port.write(b, 2000) }
    @Synchronized fun read(n: Int): ByteArray {
        val deadline = System.currentTimeMillis() + timeoutMs
        val buf = ByteArray(256)
        while (pending.size() < n) {
            val left = deadline - System.currentTimeMillis()
            if (left <= 0) break
            val got = port.read(buf, left.toInt().coerceAtLeast(1))
            if (got > 0) pending.write(buf, 0, got)
        }
        val all = pending.toByteArray()
        val take = minOf(n, all.size)
        pending.reset(); if (all.size > take) pending.write(all, take, all.size - take)
        return all.copyOfRange(0, take)
    }
    fun close() { try { port.close() } catch (_: Exception) {} }
}

