package pl.autodiag.kdcan

/**
 * ELM327 (Bluetooth SPP) – TYLKO ogólne OBD-II silnika (E39: ISO 9141-2 na DME). Bez modułów BMW.
 * Odczyt: Mode 01, 03, 07, 09/02 (VIN). Mode 04 (kasowanie) tylko przez clearDtcConfirmed() – UI pokazuje dialog potwierdzenia.
 */
class Elm327(private val link: TextLink?) {
    var protocol: String = DASH; private set

    fun init(): String {
        val l = link ?: throw NoResponse(NO_LINK)
        val id = clean(l.command("ATZ", 3000))
        for (c in listOf("ATE0", "ATL0", "ATS1", "ATH0", "ATAT1", "ATSP0")) l.command(c, 1500)
        val probe = l.command("0100", 10000)
        if (isError(probe)) throw NoResponse("Adapter ELM327 odpowiada ($id), ale silnik nie: ${clean(probe)}. Sprawdź zapłon w pozycji 2.")
        protocol = clean(l.command("ATDPN", 1500)).let { PROTOCOLS[it.removePrefix("A")] ?: it }
        return id
    }

    private fun clean(s: String) = s.replace(">", "").replace("SEARCHING...", "").trim()
    private fun isError(s: String) = listOf("NO DATA", "UNABLE TO CONNECT", "ERROR", "?", "STOPPED", "BUS INIT").any { s.uppercase().contains(it) }

    /** Zwraca bajty odpowiedzi (wszystkie linie złączone), albo rzuca. */
    fun query(cmd: String, timeoutMs: Int = 3000): ByteArray {
        val l = link ?: throw NoResponse(NO_LINK)
        val mode = cmd.take(2)
        require(mode in setOf("01", "03", "07", "09")) { "Zablokowane: tylko odczyt" }
        val r = clean(l.command(cmd, timeoutMs))
        if (isError(r)) throw NoResponse("Brak danych ($r)")
        return parseHex(r)
    }

    fun battery(): Row = try { Row("Napięcie (adapter, pin 16)", clean(link?.command("ATRV", 1500) ?: throw NoResponse(NO_LINK)), "", "OK") }
        catch (e: DmeError) { Row("Napięcie (adapter, pin 16)", DASH, "", e.message ?: "") }

    fun live(): List<Row> = PIDS.map { p ->
        if (link == null) Row(p.name, DASH, "", NO_LINK) else try {
            val d = query("01%02X".format(p.pid))
            val i = (0 until d.size - 1).firstOrNull { d.u8(it) == 0x41 && d.u8(it + 1) == p.pid } ?: throw ProtocolError("Zła odpowiedź: ${hexs(d)}")
            val v = d.copyOfRange(i + 2, d.size)
            if (v.size < p.bytes) throw ProtocolError("Za krótka odpowiedź")
            Row(p.name, "%.1f".format(java.util.Locale.ROOT, p.f(v)).replace('.', ','), p.unit, "OK")
        } catch (e: DmeError) { Row(p.name, DASH, p.unit, e.message ?: "") }
    }

    fun storedDtc() = dtcRows("03", 0x43, "Błędy zapisane (Mode 03)")
    fun pendingDtc() = dtcRows("07", 0x47, "Błędy oczekujące (Mode 07)")

    private fun dtcRows(cmd: String, head: Int, title: String): List<Row> {
        if (link == null) return listOf(Row(title, DASH, "", NO_LINK))
        return try {
            val codes = decodeDtcs(query(cmd, 5000), head)
            if (codes.isEmpty()) listOf(Row(title, "brak", "", "OK")) else codes.map { Row(title, it, "", "OK") }
        } catch (e: DmeError) {
            if (e.message?.contains("NO DATA") == true) listOf(Row(title, "brak", "", "OK")) else listOf(Row(title, DASH, "", e.message ?: ""))
        }
    }

    fun vin(): Row = if (link == null) Row("VIN", DASH, "", NO_LINK) else try {
        val d = query("0902", 5000)
        val s = String(d.filter { it in 0x30..0x5A }.map { it }.toByteArray(), Charsets.US_ASCII)
        val v = if (s.length >= 17) s.takeLast(17) else throw ProtocolError("niepełny VIN")
        Row("VIN", v, "", "OK")
    } catch (e: DmeError) { Row("VIN", DASH, "", "niedostępny w tym aucie (E39 zwykle nie podaje VIN przez OBD)") }

    /** Mode 04 – wywoływać WYŁĄCZNIE po potwierdzeniu użytkownika w dialogu. */
    fun clearDtcConfirmed(): String {
        val l = link ?: throw NoResponse(NO_LINK)
        val r = clean(l.command("04", 5000))
        if (!r.replace(" ", "").startsWith("44")) throw ProtocolError("Silnik nie potwierdził kasowania: $r")
        return "Pamięć błędów silnika skasowana."
    }

    data class Pid(val pid: Int, val name: String, val unit: String, val bytes: Int, val f: (ByteArray) -> Double)

    companion object {
        val PROTOCOLS = mapOf("3" to "ISO 9141-2", "4" to "ISO 14230-4 KWP (5 baud)", "5" to "ISO 14230-4 KWP (szybki)",
            "6" to "CAN 11/500", "7" to "CAN 29/500", "8" to "CAN 11/250", "9" to "CAN 29/250")
        val PIDS = listOf(
            Pid(0x0C, "Obroty", "obr/min", 2) { it.u16(0) / 4.0 },
            Pid(0x05, "Temp. płynu chłodzącego", "°C", 1) { it.u8(0) - 40.0 },
            Pid(0x0F, "Temp. powietrza dolotowego", "°C", 1) { it.u8(0) - 40.0 },
            Pid(0x0D, "Prędkość", "km/h", 1) { it.u8(0).toDouble() },
            Pid(0x04, "Obciążenie silnika", "%", 1) { it.u8(0) * 100.0 / 255 },
            Pid(0x11, "Przepustnica", "%", 1) { it.u8(0) * 100.0 / 255 },
            Pid(0x0E, "Kąt wyprzedzenia zapłonu", "°", 1) { it.u8(0) / 2.0 - 64 },
            Pid(0x10, "Masa powietrza (MAF)", "g/s", 2) { it.u16(0) / 100.0 },
            Pid(0x06, "Korekta krótka bank 1", "%", 1) { (it.u8(0) - 128) * 100.0 / 128 },
            Pid(0x07, "Korekta długa bank 1", "%", 1) { (it.u8(0) - 128) * 100.0 / 128 },
            Pid(0x08, "Korekta krótka bank 2", "%", 1) { (it.u8(0) - 128) * 100.0 / 128 },
            Pid(0x09, "Korekta długa bank 2", "%", 1) { (it.u8(0) - 128) * 100.0 / 128 })

        fun parseHex(s: String): ByteArray = s.lines().map { it.trim() }.filter { it.isNotEmpty() }
            .map { line -> line.substringAfter(':').replace(" ", "") }
            .filter { it.matches(Regex("[0-9A-Fa-f]+")) && it.length % 2 == 0 }
            .flatMap { h -> h.chunked(2).map { it.toInt(16).toByte() } }.toByteArray()

        /** Dekoduje odpowiedź 43/47: pary bajtów → P0xxx itd., pomija 0000. Obsługuje wiele linii (każda z nagłówkiem 43). */
        fun decodeDtcs(d: ByteArray, head: Int): List<String> {
            val out = mutableListOf<String>()
            val pairs = mutableListOf<Pair<Int, Int>>()
            if (d.isNotEmpty() && d.size % 7 == 0 && (d.indices step 7).all { d.u8(it) == head }) {
                // K-line / ISO 9141: każda linia = nagłówek + 3 kody
                for (l in d.indices step 7) for (k in 0 until 3) pairs += d.u8(l + 1 + 2 * k) to d.u8(l + 2 + 2 * k)
            } else if (d.isNotEmpty() && d.u8(0) == head) {
                // CAN: nagłówek + licznik + kody
                var i = 2; while (i + 1 < d.size) { pairs += d.u8(i) to d.u8(i + 1); i += 2 }
            } else throw ProtocolError("Nieoczekiwana odpowiedź DTC: ${hexs(d)}")
            for ((a, b) in pairs) if (a != 0 || b != 0) out += "%c%d%X%02X".format("PCBU"[a shr 6], (a shr 4) and 3, a and 0xF, b)
            return out.distinct()
        }
    }
}
