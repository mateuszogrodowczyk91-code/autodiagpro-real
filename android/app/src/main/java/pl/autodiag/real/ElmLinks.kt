package pl.autodiag.real

import android.annotation.SuppressLint
import android.bluetooth.*
import android.content.Context
import android.os.Build
import java.util.UUID
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/** Wspólny interfejs ELM327 widziany z Pythona (elm327.py): write, readUntilPrompt, reconnect. */
abstract class ElmLink {
    @Volatile var rssi: Int? = null
    @Volatile var reconnects = 0
    abstract val label: String
    abstract fun write(b: ByteArray)
    abstract fun readUntilPrompt(timeoutS: Double): String
    protected abstract fun open()
    abstract fun close()

    /** Ponowne połączenie z wykładniczym backoffem: 0,5 / 1 / 2 / 4 / 8 s. */
    fun reconnect(): Boolean {
        var delay = 500L
        repeat(5) {
            close()
            try { Thread.sleep(delay) } catch (_: InterruptedException) { return false }
            try { open(); reconnects++; return true } catch (_: Exception) {}
            delay *= 2
        }
        return false
    }
}

/** Klasyczny Bluetooth SPP (większość ELM327 v1.5 / v2.1). */
@SuppressLint("MissingPermission")
class ElmSppLink(private val dev: BluetoothDevice, private val adapter: BluetoothAdapter) : ElmLink() {
    private var sock: BluetoothSocket? = null
    override val label = "SPP ${dev.name ?: "?"} (${dev.address})"
    private val SPP = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    init { open() }

    override fun open() {
        try { adapter.cancelDiscovery() } catch (_: Exception) {}   // discovery mocno spowalnia RFCOMM
        val s = try { dev.createRfcommSocketToServiceRecord(SPP).also { it.connect() } }
        catch (e: Exception) {   // część klonów: tylko niezabezpieczony / kanał 1
            try { dev.createInsecureRfcommSocketToServiceRecord(SPP).also { it.connect() } }
            catch (_: Exception) {
                @Suppress("DiscouragedPrivateApi")
                (dev.javaClass.getMethod("createRfcommSocket", Int::class.java).invoke(dev, 1) as BluetoothSocket).also { it.connect() }
            }
        }
        sock = s
    }
    override fun write(b: ByteArray) { val o = sock!!.outputStream; o.write(b); o.flush() }
    override fun readUntilPrompt(timeoutS: Double): String {
        val ins = sock!!.inputStream; val sb = StringBuilder()
        val deadline = System.currentTimeMillis() + (timeoutS * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            if (ins.available() > 0) { val c = ins.read(); if (c < 0) break; if (c == '>'.code) return sb.toString(); sb.append(c.toChar()) }
            else Thread.sleep(5)
        }
        return sb.toString()
    }
    override fun close() { try { sock?.close() } catch (_: Exception) {}; sock = null }
}

/** BLE ELM327 (Vgate iCar Pro BLE, OBDLink CX, Veepeak BLE…): serwis FFF0 (FFF1 notify / FFF2 write) albo FFE0 (FFE1), inaczej dowolna para notify+write. */
@SuppressLint("MissingPermission")
class ElmBleLink(private val ctx: Context, private val dev: BluetoothDevice) : ElmLink() {
    private var gatt: BluetoothGatt? = null
    private var tx: BluetoothGattCharacteristic? = null
    private val rx = LinkedBlockingQueue<Byte>()
    private var mtu = 23
    @Volatile private var ready: Boolean? = null
    private val writeDone = java.util.concurrent.Semaphore(0)
    override val label = "BLE ${dev.name ?: "?"} (${dev.address})"
    private val CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
    private fun u(s: String) = UUID.fromString("0000$s-0000-1000-8000-00805f9b34fb")

    private val cb = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, st: Int) {
            if (st == BluetoothProfile.STATE_CONNECTED) {
                g.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH)
                g.requestMtu(247)
            } else ready = false
        }
        override fun onMtuChanged(g: BluetoothGatt, m: Int, status: Int) { if (status == BluetoothGatt.GATT_SUCCESS) mtu = m; g.discoverServices() }
        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            val svcs = g.services
            val pref = listOf(u("fff0") to (u("fff1") to u("fff2")), u("ffe0") to (u("ffe1") to u("ffe1")), u("18f0") to (u("2af0") to u("2af1")))
            var n: BluetoothGattCharacteristic? = null; var w: BluetoothGattCharacteristic? = null
            for ((sv, cc) in pref) g.getService(sv)?.let { s -> if (n == null) { n = s.getCharacteristic(cc.first); w = s.getCharacteristic(cc.second) } }
            if (n == null || w == null) for (s in svcs) for (c in s.characteristics) {
                if (n == null && c.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) n = c
                if (w == null && c.properties and (BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0) w = c
            }
            if (n == null || w == null) { ready = false; return }
            g.setCharacteristicNotification(n, true)
            n!!.getDescriptor(CCCD)?.let { d ->
                if (Build.VERSION.SDK_INT >= 33) g.writeDescriptor(d, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                else { @Suppress("DEPRECATION") run { d.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE; g.writeDescriptor(d) } }
            }
            tx = w; ready = true
        }
        @Deprecated("API<33") override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) { @Suppress("DEPRECATION") c.value?.forEach { rx.offer(it) } }
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic, v: ByteArray) { v.forEach { rx.offer(it) } }
        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) { writeDone.release() }
        override fun onReadRemoteRssi(g: BluetoothGatt, r: Int, status: Int) { if (status == BluetoothGatt.GATT_SUCCESS) rssi = r }
    }

    init { open() }

    override fun open() {
        ready = null; rx.clear()
        gatt = dev.connectGatt(ctx, false, cb, BluetoothDevice.TRANSPORT_LE)
        val deadline = System.currentTimeMillis() + 10000
        while (ready == null && System.currentTimeMillis() < deadline) Thread.sleep(20)
        if (ready != true) { close(); throw IllegalStateException("BLE: nie znaleziono serwisu ELM327 (FFF0/FFE0)") }
        Thread.sleep(200)
    }
    fun pollRssi() { gatt?.readRemoteRssi() }

    override fun write(b: ByteArray) {
        if (ready != true) throw java.io.IOException("BLE rozłączone")
        val c = tx!!; val g = gatt!!
        val noResp = c.properties and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0
        val type = if (noResp) BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE else BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        b.toList().chunked(maxOf(20, mtu - 3)).forEach { ch ->
            val a = ch.toByteArray(); writeDone.drainPermits()
            if (Build.VERSION.SDK_INT >= 33) g.writeCharacteristic(c, a, type)
            else { @Suppress("DEPRECATION") run { c.writeType = type; c.value = a; g.writeCharacteristic(c) } }
            writeDone.tryAcquire(1, TimeUnit.SECONDS)
        }
    }
    override fun readUntilPrompt(timeoutS: Double): String {
        val sb = StringBuilder(); val deadline = System.currentTimeMillis() + (timeoutS * 1000).toLong()
        while (true) {
            val left = deadline - System.currentTimeMillis(); if (left <= 0 || ready == false) break
            val b = rx.poll(left, TimeUnit.MILLISECONDS) ?: break
            if (b.toInt().toChar() == '>') return sb.toString(); sb.append((b.toInt() and 0xFF).toChar())
        }
        return sb.toString()
    }
    override fun close() { try { gatt?.disconnect(); gatt?.close() } catch (_: Exception) {}; gatt = null; ready = false }
}
