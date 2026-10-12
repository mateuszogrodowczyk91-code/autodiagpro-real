package pl.autodiag.kdcan

import org.junit.Assert.*
import org.junit.Test

/** Bajtowy link do testów: odgrywa zadane odpowiedzi (z echem kabla). To NIE jest tryb aplikacji – aplikacja nie ma trybu demo. */
class ScriptLink(private val echo: Boolean, vararg replies: ByteArray) : ByteLink {
    private val q = ArrayDeque<ByteArray>(replies.toList()); private var buf = ByteArray(0); val sent = mutableListOf<ByteArray>()
    override fun clear() {}
    override fun write(b: ByteArray) { sent += b; buf += (if (echo) b else ByteArray(0)) + (q.removeFirstOrNull() ?: ByteArray(0)) }
    override fun read(n: Int, timeoutMs: Int): ByteArray { val k = minOf(n, buf.size); val r = buf.copyOf(k); buf = buf.copyOfRange(k, buf.size); return r }
    override fun close() {}
}
class ScriptText(private val m: Map<String, String>) : TextLink {
    val sent = mutableListOf<String>()
    override fun command(cmd: String, timeoutMs: Int): String { sent += cmd; return (m[cmd] ?: "?") + "\r>" }
    override fun close() {}
}
fun resp(vararg data: Int): ByteArray { val b = bytesOf(0xB8, 0xF1, 0x12, data.size, *data); return b + byteArrayOf(xor(b).toByte()) }

class ProtocolTest {
    @Test fun buildFrameMatchesPython() = assertEquals("B8 12 F1 03 22 40 00 3A", hexs(Kwp.build(bytesOf(0x22, 0x40, 0x00))))
    @Test fun ds2Frame() = assertEquals("32 04 00 36", hexs(Ds2.build(0x32, bytesOf(0x00))))

    @Test fun engineDecodeWithEcho() {
        val d = IntArray(29); d[0] = 0x62; d[1] = 0x40; d[2] = 0; d[10] = 0x0C; d[11] = 0x80; d[18] = 0x80; d[25] = 130
        val rows = Me72(Me72Transport(ScriptLink(true, resp(*d)))).engine()
        assertEquals("800", rows[0].value); assertEquals("48,0", rows[1].value); assertEquals("12,4", rows[9].value)
    }
    @Test fun noCableGivesDash() {
        Me72(null).engine().forEach { assertEquals(DASH, it.value); assertEquals(NO_LINK, it.status) }
        Elm327(null).live().forEach { assertEquals(DASH, it.value) }
        Ds2.Client(null).scan().forEach { assertEquals(DASH, it.value) }
    }
    @Test fun silentDmeGivesDashAndReason() {
        val r = Me72(Me72Transport(ScriptLink(true))).engine()
        assertEquals(DASH, r[0].value); assertTrue(r[0].status.contains("echo"))
    }
    @Test fun negativeResponse() {
        val r = Me72(Me72Transport(ScriptLink(false, resp(0x7F, 0x22, 0x11)))).engine()
        assertTrue(r[0].status.contains("nie zna"))
    }
    @Test(expected = IllegalArgumentException::class) fun writeServicesBlocked() { Me72Transport(ScriptLink(false)).request(bytesOf(0x14, 0xFF, 0x00)) }
    @Test(expected = IllegalArgumentException::class) fun ds2WriteBlocked() { Ds2.Client(ScriptLink(false)).request(0x12, bytesOf(0x0C)) }
    @Test(expected = IllegalArgumentException::class) fun elmMode04OnlyViaConfirmed() { Elm327(ScriptText(mapOf())).query("04") }
    @Test fun dtcDecode() {
        val (recs, warn) = Me72Decode.dtc(bytesOf(0x58, 2, 0x01, 0x33, 0x24, 0x00, 0x87, 0x20))
        assertEquals(listOf(0x0133, 0x0087), recs.map { it.code }); assertTrue(warn.isEmpty())
    }
    @Test fun elmDtcKline() = assertEquals(listOf("P0301", "P0171"), Elm327.decodeDtcs(Elm327.parseHex("43 03 01 01 71 00 00"), 0x43))
    @Test fun elmDtcHeaderLikeCode() = assertEquals(listOf("C0300"), Elm327.decodeDtcs(Elm327.parseHex("43 43 00 00 00 00 00"), 0x43))
    @Test fun elmLiveRpm() {
        val e = Elm327(ScriptText(mapOf("010C" to "41 0C 0C 80")))
        val rpm = e.live().first { it.name == "Obroty" }
        assertEquals("800,0", rpm.value)
        assertEquals(DASH, e.live().first { it.name == "Prędkość" }.value)
    }
    @Test fun elmNoData() = assertEquals("brak", Elm327(ScriptText(mapOf("03" to "NO DATA"))).storedDtc()[0].value)
}
