"""
Actualiza eventos.json leyendo directamente las webs de algunas salas.

- Solo sustituye los eventos de las salas que ha podido leer bien.
- Si una sala falla o devuelve muy pocos eventos, CONSERVA sus datos anteriores.
- Escribe informe.txt con lo ocurrido.
"""
import datetime
import html as html_lib
import json
import re
import shutil
import traceback

from comun import NOTAS, bonito, descargar, euros, slug

HOY = datetime.date.today()
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
         "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
         "jan": 1, "apr": 4, "aug": 8, "dec": 12}
MINIMO_EVENTOS = 5
FORZAR_SALAS = set()  # salas cuyo reemplazo se fuerza una vez (normalmente vacío)  # menos que esto se considera una lectura fallida


def agotado(d):
    """¿El evento está agotado? Se mira cualquier campo que lo indique."""
    for k, v in d.items():
        k = k.lower()
        if isinstance(v, bool) and v and ("sold" in k or "agot" in k):
            return True
        if isinstance(v, str) and k not in ("title", "slug", "ticketurl", "imageurl") \
                and re.search(r"sold[ _-]?out|agotad", v, re.I):
            return True
    return False


def evento(prefijo, sala, fecha, titulo, url, precio, descripcion, fuente):
    return {
        "id": f"{prefijo}-{fecha[:10]}-{fecha[11:13] + fecha[14:16] if len(fecha) > 10 else 'x'}-{slug(titulo)}",
        "titulo": titulo, "artista": "", "sala": sala, "fecha": fecha,
        "categoria": "musica", "precio": precio, "urlEntradas": url,
        "descripcion": descripcion, "fuente": fuente,
    }


def trozos_next(pagina):
    """Lee los datos que Next.js guarda dentro de la página (cadenas JavaScript)."""
    salida = []
    for m in re.finditer(r'self\.__next_f\.push\(\[\d+,("(?:[^"\\]|\\.)*")\]\)', pagina):
        try:
            salida.append(json.loads(m.group(1)))
        except ValueError:
            continue
    return "\n".join(salida)


# ---------------------------------------------------------------- 16 Toneladas
def leer_16_toneladas():
    sala = "16 Toneladas"
    meses = [(HOY.year * 12 + HOY.month - 1 + i) for i in range(0, 11)]
    paginas = ["https://www.16toneladas.com/"] + [
        f"https://www.16toneladas.com/?month={m // 12}-{m % 12 + 1:02d}" for m in meses]
    vistos, resultado = set(), []
    claves_vistas, agotados = set(), 0
    decodificador = json.JSONDecoder()
    for url in paginas:
        try:
            pagina = descargar(url)
        except Exception:  # noqa: BLE001
            continue
        texto = trozos_next(pagina) or pagina.replace('\\"', '"')
        for m in re.finditer(r'"title":"', texto):
            inicio = texto.rfind("{", 0, m.start())
            if inicio < 0:
                continue
            try:
                d, _ = decodificador.raw_decode(texto, inicio)
            except ValueError:
                continue
            if not isinstance(d, dict) or "title" not in d or "date" not in d:
                continue
            claves_vistas.update(d.keys())
            if d.get("isPublished") is False:
                continue
            if agotado(d):
                agotados += 1
                continue
            enlace = d.get("ticketUrl")
            if not enlace:
                continue
            hora = d.get("showTime") or d.get("doorsTime")
            if not hora or not re.match(r"\d{4}-\d\d-\d\d$", str(d["date"])):
                continue
            dia = datetime.date.fromisoformat(d["date"])
            if dia < HOY:
                continue
            clave = (d.get("slug"), d["date"])
            if clave in vistos:
                continue
            vistos.add(clave)
            puertas = (d.get("doorsTime") or "")[:5]
            nota = f" Apertura de puertas: {puertas}." if puertas and puertas != hora[:5] else ""
            if int(hora[:2]) < 6:  # sesión de madrugada: pertenece a la noche del día anterior
                nota += f" Sesión de madrugada de la noche del {dia:%d/%m}."
                dia = dia + datetime.timedelta(days=1)
            fecha = f"{dia:%Y-%m-%d}T{hora[:5]}:00"
            a, b = euros(d.get("priceAdvance")), euros(d.get("priceDoor"))
            precio = " / ".join(x for x in (a, b) if x) or None
            resultado.append(evento(
                "16t", sala, fecha, bonito(d["title"]), enlace, precio,
                "Concierto en 16 Toneladas." + nota + " Consulta los detalles en la web de la sala.",
                f"16toneladas.com (lectura automática {HOY:%d/%m/%Y})"))
    NOTAS.append(f"16 Toneladas: campos de cada evento = {sorted(claves_vistas)}; descartados por agotados: {agotados}")
    return sala, resultado


# -------------------------------------------------------------------- Loco Club
def leer_loco_club():
    sala = "Loco Club"
    pagina = descargar("https://lococlub.es/")
    excluir = re.compile(r"feria del disco|concurso|weekender|christmas|jam session", re.I)
    resultado, vistos = [], set()
    for bloque in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
                             pagina, re.S | re.I):
        try:
            datos = json.loads(bloque.strip())
        except ValueError:
            continue
        pila = [datos]
        while pila:
            d = pila.pop()
            if isinstance(d, list):
                pila.extend(d)
                continue
            if not isinstance(d, dict):
                continue
            tipo = d.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if any(isinstance(t, str) and "Event" in t for t in tipos):
                ev = _evento_loco(d, sala, excluir)
                if ev and (ev["id"] not in vistos):
                    vistos.add(ev["id"])
                    resultado.append(ev)
            pila.extend(v for v in d.values() if isinstance(v, (list, dict)))
    return sala, resultado


def _precio_loco(texto):
    """Deja solo las tarifas generales (anticipada y taquilla) y limpia el formato."""
    if not texto:
        return None
    partes = [p.strip() for p in str(texto).split("/") if p.strip()]
    elegidas, vistas = [], set()
    for p in partes:
        tipo = p.split(":")[0].strip().lower()
        if tipo.startswith(("anticipada", "taquilla")) and tipo not in vistas:
            vistas.add(tipo)
            elegidas.append(p)
    resultado = " / ".join(elegidas or partes[:2])
    return resultado.replace("€", " €").replace("  ", " ").strip() or None


def _evento_loco(d, sala, excluir):
    estado = str(d.get("eventStatus", ""))
    if "Cancelled" in estado or "Postponed" in estado:
        return None
    ofertas = d.get("offers")
    if isinstance(ofertas, list):
        ofertas = ofertas[0] if ofertas else {}
    ofertas = ofertas or {}
    if "SoldOut" in str(ofertas.get("availability", "")):
        return None
    url = ofertas.get("url")
    inicio = str(d.get("startDate", ""))
    if not url or not re.match(r"\d{4}-\d\d-\d\d", inicio):
        return None
    titulo = d.get("name") or ""
    if not titulo:
        titulo = url.rstrip("/").split("/")[-1].replace("-", " ")
    titulo = bonito(html_lib.unescape(titulo))
    if excluir.search(titulo) or re.search(r"agotad|sold[ -]?out", titulo, re.I):
        return None
    # La web publica la hora local MÁS su desfase horario (p. ej. 22:30+02:00 para
    # un concierto a las 20:30). La hora real es la publicada menos ese desfase.
    try:
        dt = datetime.datetime.fromisoformat(inicio.replace("Z", "+00:00"))
        local = dt.replace(tzinfo=None) - (dt.utcoffset() or datetime.timedelta(0))
    except ValueError:
        return None
    if local.date() < HOY:
        return None
    hora = f"{local:%H:%M}" if len(inicio) > 10 else "00:00"
    fecha = f"{local:%Y-%m-%d}" if hora == "00:00" else f"{local:%Y-%m-%dT%H:%M}:00"
    precio = _precio_loco(ofertas.get("price"))
    return evento("loco", sala, fecha, titulo, url, precio,
                  "Concierto en Loco Club. Consulta los detalles y las entradas en la página del evento.",
                  f"lococlub.es (lectura automática {HOY:%d/%m/%Y})")


# -------------------------------------------------------------------- Rock City
PATRON_ROCK = re.compile(
    r'class="titulo-evento">\s*<a href="([^"]+)"[^>]*>(.*?)</a>\s*</div>\s*'
    r'<div class="fecha-evento">\s*<p>\s*(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})\s*<br\s*/?>\s*'
    r'(\d{1,2}:\d{2})\s*H', re.S | re.I)


def limpiar_titulo_rock(t):
    t = html_lib.unescape(re.sub(r"<[^>]+>", "", t)).strip()
    m = re.search(r"\s+en\s+Val[eè]ncia\s*(?:@\s*Rock City)?\s*(?:\|\s*(.*))?$", t, re.I)
    if m:
        extra = (m.group(1) or "").strip()
        t = t[:m.start()] + (f" ({bonito(extra)})" if extra else "")
    return t.strip()


def leer_rock_city():
    sala = "Rock City"
    resultado, vistos = [], set()
    for desplazamiento in range(0, 200, 8):
        pagina = descargar(f"https://www.rockcity.es/?eme_offset={desplazamiento}")
        encontrados = PATRON_ROCK.findall(pagina)
        if not encontrados:
            break
        nuevos = 0
        for url, titulo, dia, mes, anio, hora in encontrados:
            if "agotad" in titulo.lower():
                continue
            numero_mes = MESES.get(mes.lower())
            if not numero_mes:
                continue
            fecha = f"{int(anio):04d}-{numero_mes:02d}-{int(dia):02d}T{int(hora[:2]):02d}:{hora[-2:]}:00"
            clave = (url, fecha)
            if clave in vistos:
                continue
            vistos.add(clave)
            nuevos += 1
            resultado.append(evento(
                "rock", sala, fecha, limpiar_titulo_rock(titulo), url, None,
                "Concierto en Rock City. Consulta los detalles y las entradas en la página del evento.",
                f"rockcity.es (lectura automática {HOY:%d/%m/%Y})"))
        if nuevos == 0:
            break
    return sala, resultado


from lectores2 import LECTORES_NUEVOS  # noqa: E402

LECTORES = [leer_16_toneladas, leer_loco_club, leer_rock_city] + LECTORES_NUEVOS


# ---------------------------------------------------------------------- Principal
VIGILADOS = {
    "Festival de les Arts": "https://festivaldelesarts.com/",
    "BIGSOUND Valencia": "https://www.bigsoundfestival.com/",
    "Love to Rock": "https://lovetorockfestival.es/",
    "Deleste Festival": "https://delestefestival.com/",
    "Festival de Jazz de València (IVC)": "https://ivc.gva.es/es/musica",
}


def vigilar_festivales(informe):
    """Avisa en el informe si la web de un festival anual ya menciona la edición de 2027."""
    for nombre, url in VIGILADOS.items():
        try:
            pagina = descargar(url)
        except Exception as error:  # noqa: BLE001
            informe.append(f"Vigilancia {nombre}: no se pudo leer ({str(error)[:80]})")
            continue
        texto = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", pagina, flags=re.S | re.I)
        texto = re.sub(r"\s+", " ", html_lib.unescape(texto))
        m = re.search(r"(?<!\d)2027(?!\d)", texto)
        if m:
            fragmento = texto[max(0, m.start() - 80): m.end() + 80]
            informe.append(f"Vigilancia {nombre}: POSIBLE NOVEDAD, la web menciona 2027: «{fragmento}»")
        else:
            informe.append(f"Vigilancia {nombre}: sin novedades (no menciona 2027)")


def _norm(t):
    return re.sub(r"\W+", "", str(t).lower())


def misma_funcion(a, b):
    """¿Dos eventos son el mismo? Misma sala, mismo día y un título contenido en el otro."""
    if a.get("sala") != b.get("sala") or str(a["fecha"])[:10] != str(b["fecha"])[:10]:
        return False
    x, y = _norm(a["titulo"]), _norm(b["titulo"])
    return min(len(x), len(y)) >= 5 and (x in y or y in x)


PODCAST = re.compile(r"p[oó]dcast|festivalpod|odio a la gente|el arte del fracaso", re.I)


def clasificar_podcasts(eventos):
    n = 0
    for e in eventos:
        texto = f"{e.get('titulo', '')} {e.get('artista', '')} {e.get('descripcion', '')}"
        if e.get("categoria") != "podcast" and PODCAST.search(texto):
            e["categoria"] = "podcast"
            n += 1
    return n


def futuro(e):
    limite = e.get("fechaFin") or e["fecha"]
    return limite[:10] >= HOY.isoformat()


def main():
    with open("eventos.json", encoding="utf-8") as f:
        actuales = json.load(f)
    shutil.copy("eventos.json", "eventos_anterior.json")

    informe = [f"ACTUALIZACIÓN {datetime.datetime.now():%d/%m/%Y %H:%M}"]
    resultado = list(actuales)

    for lector in LECTORES:
        nombre = lector.__name__
        try:
            sala, nuevos = lector()
        except Exception:  # noqa: BLE001
            informe.append(f"{nombre}: ERROR, se conservan los datos anteriores\n{traceback.format_exc(limit=3)}")
            continue
        antiguos_futuros = [e for e in actuales if e["sala"] == sala and futuro(e)]
        if len(nuevos) == 0 or (len(nuevos) < MINIMO_EVENTOS and antiguos_futuros):
            informe.append(f"{sala}: solo {len(nuevos)} eventos leídos, se conservan los {len(antiguos_futuros)} anteriores")
            continue
        if sala in FORZAR_SALAS:
            informe.append(f"{sala}: reemplazo forzado (datos anteriores con repetidos): {len(antiguos_futuros)} -> {len(nuevos)}")
        elif len(antiguos_futuros) >= 8 and len(nuevos) < 0.8 * len(antiguos_futuros):
            informe.append(f"{sala}: lectura sospechosa ({len(nuevos)} frente a {len(antiguos_futuros)} anteriores), se conservan los anteriores")
            continue
        resultado = [e for e in resultado if e["sala"] != sala] + nuevos
        informe.append(f"{sala}: {len(nuevos)} eventos actualizados (antes {len(antiguos_futuros)})")

    # Eventos escritos a mano (festivales de una edición, salas bloqueadas...)
    try:
        with open("eventos_manuales.json", encoding="utf-8") as f:
            manuales = json.load(f)
    except FileNotFoundError:
        manuales = []
    except ValueError as error:
        manuales = []
        informe.append(f"eventos_manuales.json no se pudo leer: {error}")
    vigentes = [m for m in manuales if isinstance(m, dict) and "id" in m and "fecha" in m and futuro(m)]
    ids = {m["id"] for m in vigentes}
    for m in vigentes:  # si el manual no trae enlace, hereda el del evento leído de la misma función
        if not m.get("urlEntradas"):
            for e in resultado:
                if misma_funcion(e, m) and e.get("urlEntradas"):
                    m["urlEntradas"] = e["urlEntradas"]
                    break
    resultado = [e for e in resultado
                 if e["id"] not in ids and not any(misma_funcion(e, m) for m in vigentes)] + vigentes
    informe.append(f"Eventos manuales incluidos: {len(vigentes)}")

    informe.append(f"Eventos reclasificados como podcast: {clasificar_podcasts(resultado)}")
    vigilar_festivales(informe)

    resultado.sort(key=lambda e: e["fecha"])
    with open("eventos.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    informe.extend(NOTAS)
    informe.append(f"Total en eventos.json: {len(resultado)}")
    with open("informe.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(informe) + "\n")
    print("\n".join(informe))


if __name__ == "__main__":
    main()
