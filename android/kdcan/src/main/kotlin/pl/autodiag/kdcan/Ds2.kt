package pl.autodiag.kdcan

/** Port z autodiag_real/ds2.py: inne moduły E39 przez DS2 (9600 8E1). Tylko identyfikacja (00) i pamięć błędów (04), surowy hex. */
object Ds2 {
    val MODULES = listOf("EGS – skrzynia automatyczna" to 0x32, "ABS/ASC/DSC" to 0x56, "Airbag (MRS)" to 0xA4, "IKE – zegary" to 0x80,
        "LCM – światła" to 0xD0, "EHC – zawieszenie pneumatyczne" to 0xAC, "IHKA – klimatyzacja" to 0x5B, "GM – moduł ogólny" to 0x00)
    private val ALLOWED = setOf(0x00, 0x04)
    fun build(addr: Int, data: ByteArray): ByteArray { val b = bytesOf(addr, data.size + 3) + data; return b + byteArrayOf(xor(b).toByte()) }

    class Client(private val link: ByteLink?) {
        private fun frame(rx: java.io.ByteArrayOutputStream): ByteArray {
            val h = link!!.read(2, 1000); rx.write(h); if (h.size < 2) throw java.util.concurrent.TimeoutException()
            if (h.u8(1) < 3) throw ProtocolError("Zła długość ramki DS2: ${hexs(rx.toByteArray())}")
            val t = link.read(h.u8(1) - 2, 1000); rx.write(t); if (t.size < h.u8(1) - 2) throw java.util.concurrent.TimeoutException()
            val raw = h + t; if (xor(raw, raw.size - 1) != raw.u8(raw.size - 1)) throw ProtocolError("Zła suma DS2: ${hexs(raw)}")
            return raw
        }
        @Synchronized fun request(addr: Int, data: ByteArray): ByteArray {
            if (link == null) throw NoResponse(NO_LINK)
            require(data.isNotEmpty() && data.u8(0) in ALLOWED) { "Zablokowane: tylko odczyt" }
            val tx = build(addr, data); val rx = java.io.ByteArrayOutputStream(); link.clear(); link.write(tx)
            val r = try { frame(rx).let { if (it.contentEquals(tx)) frame(rx) else it } } catch (e: java.util.concurrent.TimeoutException) {
                throw NoResponse("Moduł 0x%02X nie odpowiada. Odebrane: %s".format(addr, hexs(rx.toByteArray())), tx, rx.toByteArray()) }
            if (r.u8(0) != addr) throw ProtocolError("Odpowiedź od innego adresu: ${hexs(r)}")
            if (r.size < 4 || r.u8(2) != 0xA0) throw ProtocolError("Moduł odmówił (status ${if (r.size > 2) "%02X".format(r.u8(2)) else "?"})")
            return r.copyOfRange(3, r.size - 1)
        }
        fun scan(): List<Row> = MODULES.flatMap { (name, a) ->
            listOf(0x00 to "identyfikacja", 0x04 to "błędy").map { (cmd, what) ->
                if (link == null) Row("$name – $what", DASH, "", NO_LINK)
                else try { Row("$name – $what", hexs(request(a, bytesOf(cmd))), "hex", "OK") }
                catch (e: DmeError) { Row("$name – $what", DASH, "", e.message?.substringBefore(".") ?: "błąd") }
            }
        }
    }
}
