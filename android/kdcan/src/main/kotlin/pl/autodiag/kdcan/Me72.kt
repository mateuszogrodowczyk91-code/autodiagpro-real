package pl.autodiag.kdcan

/**
 * Port 1:1 z autodiag_real/me72.py: DME Bosch ME7.2 (E39 540i M62TU), ramka BMW KWP: [B8][12][F1][len][dane][XOR], 9600 8E1.
 * TYLKO ODCZYT. Kasowanie błędów / flash / kodowanie / EWS celowo NIE istnieją w tym module.
 * Pozycje bajtów z tabeli SGBD ME72KWP1 – NIE ZWERYFIKOWANE na aucie.
 */
object Kwp {
    const val DME = 0x12; const val TESTER = 0xF1; const val HEADER = 0xB8
    fun build(payload: ByteArray, target: Int = DME, source: Int = TESTER): ByteArray {
        val body = bytesOf(HEADER, target, source, payload.size) + payload
        return body + byteArrayOf(xor(body).toByte())
    }
    /** Dozwolone usługi: A2 ident, 22 odczyt, 18 odczyt błędów, 12 freeze frame. Wszystko inne jest blokowane. */
    val READ_ONLY_SIDS = setOf(0xA2, 0x22, 0x18, 0x12)
}

class Me72Transport(private var link: ByteLink?, private val trace: (String, ByteArray) -> Unit = { _, _ -> }) {
    var replyTimeoutMs = 1000; var pendingTimeoutMs = 5000; private val maxPending = 20

    private fun readExact(n: Int, rx: java.io.ByteArrayOutputStream, t: Int): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        while (out.size() < n) {
            val c = link!!.read(n - out.size(), t)
            if (c.isEmpty()) throw java.util.concurrent.TimeoutException()
            out.write(c); rx.write(c)
        }
        return out.toByteArray()
    }

    private fun readFrame(rx: java.io.ByteArrayOutputStream, t: Int): ByteArray {
        val head = readExact(4, rx, t); val tail = readExact(head.u8(3) + 1, rx, t); val raw = head + tail
        if (xor(raw, raw.size - 1) != raw.u8(raw.size - 1))
            throw ProtocolError("Zła suma kontrolna ramki: ${hexs(raw)} (zły baud/parzystość albo zakłócenia)", ByteArray(0), rx.toByteArray())
        return raw
    }

    private fun frameOrRaise(rx: java.io.ByteArrayOutputStream, t: Int, tx: ByteArray, echo: Boolean, afterPending: Boolean = false): ByteArray {
        val before = rx.size()
        try { return readFrame(rx, t) } catch (e: java.util.concurrent.TimeoutException) {
            val r = rx.toByteArray()
            throw when {
                afterPending -> NoResponse("Brak odpowiedzi z DME (po 'odpowiedź w toku'). Odebrane: ${hexs(r)}", tx, r)
                r.isEmpty() -> NoResponse("Brak odpowiedzi z DME: nic nie przyszło – ani echo kabla, ani odpowiedź. Sprawdź kabel w OBD i przełącznik K-line (piny 7+8).", tx, r)
                echo && r.size == before -> NoResponse("Brak odpowiedzi z DME: kabel działa (wróciło echo), ale DME milczy. Sprawdź zapłon w pozycji 2.", tx, r)
                else -> NoResponse("Brak odpowiedzi z DME: przyszły tylko niepełne bajty ${hexs(r)} (zły baud/parzystość?).", tx, r)
            }
        }
    }

    @Synchronized fun request(payload: ByteArray): ByteArray {
        val l = link ?: throw NoResponse("Brak odpowiedzi z DME: port nie jest otwarty.")
        require(payload.isNotEmpty() && payload.u8(0) in Kwp.READ_ONLY_SIDS) { "Zablokowane: tylko odczyt" }
        val tx = Kwp.build(payload); var busy = 0
        while (true) {
            val rx = java.io.ByteArrayOutputStream(); var echo = false; var pending = 0
            l.clear(); trace("TX", tx); l.write(tx)
            val first = frameOrRaise(rx, replyTimeoutMs, tx, false)
            var resp = if (first.contentEquals(tx)) { echo = true; frameOrRaise(rx, replyTimeoutMs, tx, true) } else first
            checkAddr(resp, tx, rx.toByteArray())
            var data = resp.copyOfRange(4, resp.size - 1)
            while (data.size >= 3 && data.u8(0) == 0x7F && data.u8(2) == 0x78) {
                if (++pending > maxPending) throw ProtocolError("DME ciągle odpowiada 'w toku' – przerwano.", tx, rx.toByteArray())
                resp = frameOrRaise(rx, pendingTimeoutMs, tx, echo, true); checkAddr(resp, tx, rx.toByteArray())
                data = resp.copyOfRange(4, resp.size - 1)
            }
            if (data.size >= 3 && data.u8(0) == 0x7F && data.u8(2) == 0x21 && busy < 3) { busy++; Thread.sleep(200); continue }
            trace("RX", resp)
            if (data.size >= 3 && data.u8(0) == 0x7F) throw NegativeResponse(data.u8(1), data.u8(2), tx, rx.toByteArray())
            if (data.isEmpty()) throw ProtocolError("Pusta odpowiedź DME.", tx, rx.toByteArray())
            return data
        }
    }

    private fun checkAddr(r: ByteArray, tx: ByteArray, rx: ByteArray) {
        if (r.u8(0) != Kwp.HEADER || r.u8(1) != Kwp.TESTER || r.u8(2) != Kwp.DME)
            throw ProtocolError("Odpowiedź nie od DME (oczekiwano B8 F1 12 ..): ${hexs(r)}", tx, rx)
    }

    fun close() { link?.close(); link = null }
}

object Me72Decode {
    private fun expect(d: ByteArray, n: Int, head: IntArray, what: String) {
        if (d.size < n || head.indices.any { d.u8(it) != head[it] }) throw ProtocolError("Nieoczekiwana odpowiedź na $what: ${hexs(d)}")
    }
    private fun f(v: Double, dec: Int = 1) = "%.${dec}f".format(java.util.Locale.ROOT, v).replace('.', ',')

    fun ident(d: ByteArray): List<Row> {
        if (d.isEmpty() || d.u8(0) != 0xE2) throw ProtocolError("Nieoczekiwana odpowiedź identyfikacji: ${hexs(d)}")
        fun a(s: Int, e: Int) = if (d.size >= e) String(d.copyOfRange(s, e), Charsets.US_ASCII).trim(' ', '\u0000', '\u00ff') else DASH
        return listOf("Numer części BMW" to a(1, 8), "Hardware" to a(8, 10), "Indeks kodowania" to a(10, 12), "Indeks diagnozy" to a(12, 14),
            "Indeks magistrali" to a(14, 16), "Tydzień produkcji" to a(16, 18), "Rok produkcji" to a(18, 20), "Dostawca" to a(20, 26))
            .map { Row(it.first, it.second, "", "OK") }
    }

    val ENGINE_NAMES = listOf("Obroty", "Temp. płynu chłodzącego", "Temp. powietrza dolotowego", "Prędkość", "Czas wtrysku",
        "Kąt wyprzedzenia zapłonu", "Przepustnica", "Masa powietrza (MAF)", "Moment wskazany", "Napięcie akumulatora (DME)")

    fun engineValues(d: ByteArray): List<Double> {
        expect(d, 29, intArrayOf(0x62, 0x40, 0x00), "dane silnika (22 40 00)")
        return listOf(d.u16(10) * 0.25, d.u8(18) * 0.75 - 48, d.u8(17) * 0.75 - 48, d.u8(9) * 1.25, d.u16(3) * 0.016,
            d[19].toInt() * 0.75, d.u8(20) * 0.39216, d.u16(21) * 0.1, d.u16(23) * 0.0015259, d.u8(25) * 0.095)
    }
    private val ENGINE_UNITS = listOf("obr/min", "°C", "°C", "km/h", "ms", "°", "%", "kg/h", "%", "V")
    fun engine(d: ByteArray) = engineValues(d).mapIndexed { i, v -> Row(ENGINE_NAMES[i], f(v, if (i == 0) 0 else 1), ENGINE_UNITS[i], "OK") }

    /** 22 40 03: nierówność biegu cyl. 1–8 [1/s]. Kolejność cylindrów NIEPOTWIERDZONA. */
    fun roughness(d: ByteArray): List<Double> {
        expect(d, 19, intArrayOf(0x62, 0x40, 0x03), "nierówność biegu (22 40 03)")
        return (0 until 8).map { d.s16(3 + it * 2) * 0.0027756 }
    }

    data class Dtc(val code: Int, val status: Int)
    /** 18 02 FF FF → 58 [n] ([hi lo status])* — NIEPOTWIERDZONE dla ME7.2 */
    fun dtc(d: ByteArray): Pair<List<Dtc>, List<String>> {
        if (d.isEmpty() || d.u8(0) != 0x58) throw ProtocolError("Nieoczekiwana odpowiedź pamięci błędów: ${hexs(d)}")
        val count = if (d.size > 1) d.u8(1) else 0
        val recs = (2 until d.size - 2 step 3).map { Dtc(d.u16(it), d.u8(it + 2)) }
        val warn = if (recs.size == count) emptyList() else listOf("DME podało $count błędów, w odpowiedzi jest ${recs.size} pełnych rekordów.")
        return recs to warn
    }
}

/** Fasada dla powłoki aplikacji: każda metoda zwraca wiersze; bez połączenia – "—" i "brak połączenia". */
class Me72(private val t: Me72Transport?) {
    private fun guard(names: List<String>, block: () -> List<Row>): List<Row> =
        if (t == null) names.map { Row(it, DASH, "", NO_LINK) }
        else try { block() } catch (e: DmeError) { names.map { n -> Row(n, DASH, "", e.message ?: "błąd") } }

    fun ident() = guard(listOf("Identyfikacja DME")) { Me72Decode.ident(t!!.request(bytesOf(0xA2))) }
    fun engine() = guard(Me72Decode.ENGINE_NAMES) { Me72Decode.engine(t!!.request(bytesOf(0x22, 0x40, 0x00))) }
    fun roughness() = guard((1..8).map { "Nierówność poz. $it" }) {
        Me72Decode.roughness(t!!.request(bytesOf(0x22, 0x40, 0x03))).mapIndexed { i, v ->
            Row("Nierówność poz. ${i + 1}", "%.3f".format(java.util.Locale.ROOT, v).replace('.', ','), "1/s", "OK (kolejność cyl. niepotwierdzona)") }
    }
    fun faults() = guard(listOf("Pamięć błędów DME")) {
        val (recs, warn) = Me72Decode.dtc(t!!.request(bytesOf(0x18, 0x02, 0xFF, 0xFF)))
        if (recs.isEmpty()) listOf(Row("Pamięć błędów DME", "brak zapisanych błędów", "", "OK"))
        else recs.map { Row("Błąd %04X".format(it.code), "status %02X".format(it.status), "", "OK") } + warn.map { Row("Uwaga", it, "", "") }
    }
}
