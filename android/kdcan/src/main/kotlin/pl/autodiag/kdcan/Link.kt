package pl.autodiag.kdcan

/** Warstwa bajtowa (K+DCAN przez USB-OTG). Implementacja w aplikacji: UsbKdcanLink (usb-serial-for-android, 9600 8E1). */
interface ByteLink {
    fun clear()
    fun write(b: ByteArray)
    /** Czyta do n bajtów; zwraca mniej (albo pusto), gdy minie timeoutMs. */
    fun read(n: Int, timeoutMs: Int): ByteArray
    fun close()
}

/** Warstwa tekstowa ELM327 (Bluetooth SPP). Wysyła komendę + CR i zwraca tekst do znaku zachęty '>'. */
interface TextLink {
    fun command(cmd: String, timeoutMs: Int): String
    fun close()
}

open class DmeError(msg: String, val tx: ByteArray = ByteArray(0), val rx: ByteArray = ByteArray(0)) : java.io.IOException(msg)
class NoResponse(msg: String, tx: ByteArray = ByteArray(0), rx: ByteArray = ByteArray(0)) : DmeError(msg, tx, rx)
class ProtocolError(msg: String, tx: ByteArray = ByteArray(0), rx: ByteArray = ByteArray(0)) : DmeError(msg, tx, rx)
class NegativeResponse(val sid: Int, val code: Int, tx: ByteArray, rx: ByteArray) :
    DmeError("DME odrzuciło komendę 0x%02X: kod 0x%02X = %s".format(sid, code, NRC[code] ?: "nieznany kod"), tx, rx)

val NRC = mapOf(0x10 to "odmowa ogólna", 0x11 to "DME nie zna tej komendy", 0x12 to "zły format / podfunkcja nieobsługiwana",
    0x21 to "DME zajęte, spróbuj ponownie", 0x22 to "warunki niespełnione", 0x31 to "parametr poza zakresem",
    0x33 to "brak dostępu (zabezpieczenie)", 0x78 to "odpowiedź w toku", 0x80 to "usługa niedostępna w tej sesji")

const val DASH = "—"
const val NO_LINK = "brak połączenia"

fun xor(d: ByteArray, end: Int = d.size): Int { var c = 0; for (i in 0 until end) c = c xor (d[i].toInt() and 0xFF); return c }
fun hexs(d: ByteArray): String = if (d.isEmpty()) "(nic)" else d.joinToString(" ") { "%02X".format(it.toInt() and 0xFF) }
fun bytesOf(vararg v: Int) = ByteArray(v.size) { v[it].toByte() }
internal fun ByteArray.u8(i: Int) = this[i].toInt() and 0xFF
internal fun ByteArray.u16(i: Int) = (u8(i) shl 8) or u8(i + 1)
internal fun ByteArray.s16(i: Int) = u16(i).toShort().toInt()

/** Wiersz do pokazania w UI: wartość "—" gdy brak danych. */
data class Row(val name: String, val value: String, val unit: String, val status: String)
