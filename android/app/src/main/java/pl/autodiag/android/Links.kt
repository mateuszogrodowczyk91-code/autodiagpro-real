package pl.autodiag.android

import android.bluetooth.BluetoothSocket
import android.hardware.usb.UsbManager
import com.hoho.android.usbserial.driver.UsbSerialDriver
import com.hoho.android.usbserial.driver.UsbSerialPort
import pl.autodiag.kdcan.ByteLink
import pl.autodiag.kdcan.TextLink
import java.util.UUID

/** K+DCAN (FTDI FT232R) przez USB-OTG: 9600 baud 8E1, DTR/RTS wyłączone (tryb K-line). */
class UsbKdcanLink(usb: UsbManager, driver: UsbSerialDriver) : ByteLink {
    private val port: UsbSerialPort = driver.ports[0]
    init {
        val conn = usb.openDevice(driver.device) ?: throw java.io.IOException("Brak zgody na USB")
        port.open(conn)
        port.setParameters(9600, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_EVEN)
        try { port.dtr = false; port.rts = false } catch (_: Exception) {}
        clear()
    }
    override fun clear() { try { port.purgeHwBuffers(true, true) } catch (_: Exception) {} }
    override fun write(b: ByteArray) = port.write(b, 1000)
    override fun read(n: Int, timeoutMs: Int): ByteArray {
        val out = java.io.ByteArrayOutputStream(); val end = System.currentTimeMillis() + timeoutMs
        val buf = ByteArray(64)
        while (out.size() < n) {
            val left = (end - System.currentTimeMillis()).toInt(); if (left <= 0) break
            val k = port.read(buf, left)
            if (k > 0) out.write(buf, 0, k)
        }
        return out.toByteArray()   // nadmiar bajtów nie występuje przy pół-dupleksie; ramki czytane po kolei
    }
    override fun close() { try { port.close() } catch (_: Exception) {} }
}

/** ELM327 przez Bluetooth classic SPP. */
class BtElmLink(private val sock: BluetoothSocket) : TextLink {
    companion object { val SPP: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB") }
    private val inp = sock.inputStream; private val out = sock.outputStream
    override fun command(cmd: String, timeoutMs: Int): String {
        while (inp.available() > 0) inp.read()
        out.write((cmd + "\r").toByteArray()); out.flush()
        val sb = StringBuilder(); val end = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < end) {
            if (inp.available() > 0) { val c = inp.read().toChar(); if (c == '>') return sb.toString().replace('\r', '\n'); sb.append(c) }
            else Thread.sleep(10)
        }
        return sb.toString().replace('\r', '\n') + "\nSTOPPED"
    }
    override fun close() { try { sock.close() } catch (_: Exception) {} }
}
