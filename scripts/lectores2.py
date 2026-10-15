"""
Lectores de salas y teatros (segunda tanda), escritos a partir del HTML real
recogido en muestras.txt.
"""
import datetime
import html as html_lib
import json
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from comun import NOTAS, bonito, descargar, es_venta, euros, slug

HOY = datetime.date.today()
MESES_ES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
            "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
            "noviembre": 11, "diciembre": 12}
NOMBRES_MES = "|".join(MESES_ES)
MES_ABREV = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
             "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
DIAS_SEMANA = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3,
               "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}


# ------------------------------------------------------------------ utilidades
def limpio(t):
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", "", t))).strip()


def fuente(dominio):
    return f"{dominio} (lectura automática {HOY:%d/%m/%Y})"


def evento(prefijo, sala, fecha, titulo, url, descripcion, dominio,
           categoria="musica", artista="", precio=None, fin=None):
    e = {"id": f"{prefijo}-{fecha}-{slug(titulo)}", "titulo": titulo, "artista": artista,
         "sala": sala, "fecha": fecha, "categoria": categoria, "precio": precio,
         "urlEntradas": url, "descripcion": descripcion, "fuente": fuente(dominio)}
    if fin:
        e["fechaFin"] = fin
    return e


def vigente(inicio, fin):
    """Descarta lo ya pasado. Una temporada en curso empieza hoy."""
    ultimo = fin or inicio
    if ultimo < HOY:
        return None
    if inicio < HOY:
        inicio = HOY
    return inicio, (fin if fin and fin > inicio else None)


def inferir_anio(mes, dia):
    try:
        candidata = datetime.date(HOY.year, mes, dia)
    except ValueError:
        return HOY.year
    return HOY.year + 1 if candidata < HOY - datetime.timedelta(days=60) else HOY.year


def interpretar_fechas(texto):
    """'20 de octubre de 2026', 'Del 23 al 24 de octubre de 2026',
    '16 octubre 2026 - 15 noviembre 2026', 'del 31 de octubre al 01 noviembre de 2026'
    -> (inicio, fin o None) como objetos date, o None si no se entiende."""
    t = limpio(texto).lower()
    toks = re.findall(
        rf"(?<!\d)(\d{{1,2}})(?!\d)(?:\s+de)?(?:\s+({NOMBRES_MES}))?(?:\s+de)?(?:\s+(\d{{4}}))?", t)
    if not toks:
        return None
    primero, ultimo = toks[0], toks[-1]
    mes_fin = MESES_ES.get(ultimo[1])
    if not mes_fin:
        return None
    dia_fin = int(ultimo[0])
    anio_fin = int(ultimo[2]) if ultimo[2] else (int(primero[2]) if primero[2] else inferir_anio(mes_fin, dia_fin))
    try:
        fin = datetime.date(anio_fin, mes_fin, dia_fin)
        if len(toks) == 1:
            return fin, None
        mes_ini = MESES_ES.get(primero[1]) or mes_fin
        anio_ini = int(primero[2]) if primero[2] else (anio_fin if mes_ini <= mes_fin else anio_fin - 1)
        ini = datetime.date(anio_ini, mes_ini, int(primero[0]))
    except ValueError:
        return None
    return (ini, fin) if ini < fin else (fin, None)


def fecha_hora(dia, hora=None):
    return f"{dia:%Y-%m-%d}T{hora}:00" if hora else f"{dia:%Y-%m-%d}"


def trozos(pagina, patron):
    """Divide la página en bloques que empiezan en cada coincidencia de `patron`."""
    marcas = list(re.finditer(patron, pagina))
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else min(len(pagina), m.start() + 9000)
        yield m, pagina[m.start():fin]


# ------------------------------------------------------------ Palau de la Música
def leer_palau_musica():
    sala = "Palau de la Música"
    pagina = descargar("https://palauvalencia.com/")
    excluir = re.compile(r"cine culpable|visuals|mostra365|charla|conferencia|cancelad", re.I)
    res, vistos = [], set()
    n = {"tarjetas": 0, "pasadas": 0, "excluidas": 0, "venta_oculta": 0, "sin_enlace": 0, "repetidas": 0}
    for m, b in trozos(pagina, r'<div id="event-(\d+)"[^>]*data-date="\d{2}/\d{2}/\d{4}"'):
        n["tarjetas"] += 1
        d = re.search(r'data-date="(\d{2})/(\d{2})/(\d{4})"', b)
        dia = datetime.date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        if dia < HOY:
            n["pasadas"] += 1
            continue
        hora = re.search(r'<span class="notranslate">(\d{1,2}:\d{2})</span>', b)
        hora = hora.group(1).zfill(5) if hora else None
        t = re.search(r'<h5 class="card-title event-title">\s*<span class="notranslate es">(.*?)</span>', b, re.S)
        if not t:
            continue
        lineas = [limpio(x) for x in re.split(r"<br\s*/?>", t.group(1))]
        lineas = [x for x in lineas if x]
        fuerte = re.search(r"<strong>(.*?)</strong>", t.group(1), re.S)
        titulo = limpio(fuerte.group(1)) if fuerte else (lineas[0] if lineas else "")
        resto = [x for x in lineas if x != titulo and titulo not in x][:3]
        if not titulo or excluir.search(titulo + " " + " ".join(resto)):
            n["excluidas"] += 1
            continue
        vis = re.search(r'<div class="(visible|invisible)">\s*<p class="small text-muted', b)
        oculta = bool(vis and vis.group(1) == "invisible")
        enlace = re.search(r'href="(//tickets\.palauvalencia\.com/entradas/[^"]+)"', b)
        ficha = re.search(r'href="(https://palauvalencia\.com/event\?id=\d+[^"]*)"', b)
        if oculta and ficha:
            url = html_lib.unescape(ficha.group(1))  # la venta está oculta: se enlaza la ficha
            nota = " La venta online aparece oculta en la web: consulta la ficha del concierto."
            n["venta_oculta"] += 1
        elif enlace and not oculta:
            url = "https:" + html_lib.unescape(enlace.group(1))
            nota = " Consulta los detalles y las entradas en la web del Palau."
        else:
            n["sin_enlace"] += 1
            continue
        clave = (m.group(1), dia, hora)
        if clave in vistos:
            n["repetidas"] += 1
            continue
        vistos.add(clave)
        res.append(evento("palaumusica", sala, fecha_hora(dia, hora), bonito(titulo), url,
                          "Concierto en el Palau de la Música de València." + nota,
                          "palauvalencia.com", artista=" · ".join(bonito(x) for x in resto)))
    NOTAS.append("Palau de la Música: " + ", ".join(f"{k}={v}" for k, v in n.items()))
    return sala, res


# --------------------------------------------------------------- Peter Rock Club
def leer_peter_rock():
    sala = "Peter Rock Club"
    pagina = descargar("https://www.peterrockclub.es/")
    inicio = '<div class="bg-card rounded-lg overflow-hidden shadow-md border border-border">'
    res, vistos = [], set()
    for bloque in pagina.split(inicio)[1:]:
        href = re.search(r'href="(/eventos/[^"]+)"', bloque)
        t = re.search(r"<h3[^>]*>(.*?)</h3>", bloque, re.S)
        f = re.search(r"<span>\s*[^<,]+,\s*(\d{1,2}) de ([a-záéíóú]+) de (\d{4})\s*</span>", bloque, re.I)
        if not (href and t and f) or f.group(2).lower() not in MESES_ES:
            continue
        dia = datetime.date(int(f.group(3)), MESES_ES[f.group(2).lower()], int(f.group(1)))
        if dia < HOY:
            continue
        h = (re.search(r"Concierto:(?:<!-- -->)?\s*<div[^>]*>\s*(\d{1,2}:\d{2})", bloque)
             or re.search(r"Apertura:(?:<!-- -->)?\s*<div[^>]*>\s*(\d{1,2}:\d{2})", bloque))
        hora = h.group(1).zfill(5) if h else None
        p = re.search(r'<span class="text-xl font-bold">(?:<span class="text-sm font-normal">(Desde)\s*</span>)?\s*'
                      r'(\d+(?:[.,]\d+)?)(?:<!-- -->)?\s*€', bloque)
        precio = None
        if p and euros(p.group(2)):
            precio = ("desde " if p.group(1) else "") + euros(p.group(2))
        externos = [x for x in re.findall(r'href="(https?://[^"]+)"', bloque) if es_venta(x)]
        if not externos and not precio:
            continue  # sin enlace de compra ni precio (p. ej. sesiones gratuitas)
        url = html_lib.unescape(externos[0]) if externos else "https://www.peterrockclub.es" + href.group(1)
        titulo = bonito(limpio(t.group(1)))
        clave = (href.group(1), dia, hora)
        if clave in vistos:
            continue
        vistos.add(clave)
        res.append(evento("peter", sala, fecha_hora(dia, hora), titulo, url,
                          "Concierto en Peter Rock Club. Consulta los detalles en la web de la sala.",
                          "peterrockclub.es", precio=precio))
    return sala, res


# ------------------------------------------------------------------- La Rambleta
def leer_rambleta():
    sala = "La Rambleta"
    pagina = descargar("https://larambleta.com/")
    res, vistos = [], set()
    for m, b in trozos(pagina, r'class="content_entradas last ([^"]*)"'):
        clases = m.group(1).split()
        if any(c in clases for c in ("cine", "factoria", "blog")):
            continue
        if "musica" in clases:
            categoria = "musica"
        elif "humor" in clases or "escenicas" in clases:
            categoria = "teatro"
        else:
            categoria = "otros"
        t = re.search(r'<span class="subtitulolast">(.*?)</span>', b, re.S)
        u = re.search(r'<a class="botonlast" href="([^"]+)"', b)
        f = re.search(r'<div class="fechalast"[^>]*>(.*?)</div>', b, re.S)
        if not (t and u and f):
            continue
        fechas = interpretar_fechas(f.group(1))
        if not fechas:
            continue
        ini, fin = fechas
        if fin and (fin - ini).days > 150:
            continue  # ciclos larguísimos, no son un plan concreto
        v = vigente(ini, fin)
        if not v:
            continue
        titulo = limpio(t.group(1)).replace(" – ", ": ")
        titulo = bonito(re.sub(r"[‘’“”]", "", titulo))
        url = html_lib.unescape(u.group(1))
        clave = (url, v[0])
        if clave in vistos:
            continue
        vistos.add(clave)
        res.append(evento("rambleta", sala, fecha_hora(v[0]), titulo, url,
                          "Evento en La Rambleta. Consulta los detalles, la hora y las entradas en la web de la sala.",
                          "larambleta.com", categoria=categoria,
                          fin=fecha_hora(v[1]) if v[1] else None))
    return sala, res


# ------------------------------------------------------------------- Teatre Talia
def leer_talia():
    sala = "Teatre Talia"
    pagina = descargar("https://www.teatretalia.es/")
    excluir = re.compile(r"tarjeta regalo|educandos|abono|bono|tablao", re.I)
    res, vistos = [], set()
    for m, b in trozos(pagina, r'<div class="item post-grid col-md-4 col-xs-12 ([^"]*)"'):
        clases = m.group(1).lower().split()
        t = re.search(r'<h4 class="title"><a[^>]*>(.*?)</a></h4>', b, re.S)
        f = re.search(r'<div class="meta">\s*<label>(.*?)</label>', b, re.S)
        u = re.search(r'href="(https://entradas\.teatroenvalencia\.com/espectaculo/[^"]+)"', b)
        if not (t and f and u):
            continue
        titulo = bonito(limpio(t.group(1)))
        if excluir.search(titulo):
            continue
        fechas = interpretar_fechas(f.group(1))
        if not fechas:
            continue
        v = vigente(*fechas)
        if not v:
            continue
        sub = re.search(r'<div class="body" style="display:none;">(.*?)</div>', b, re.S)
        categoria = "musica" if any(c in clases for c in ("flamenco", "música", "musica")) else "teatro"
        hora, nota = None, ""
        if "lasnochesdeltalia" in clases and not v[1]:
            hora = {4: "23:00", 5: "23:30"}.get(v[0].weekday())  # viernes / sábado
            nota = " Hora según el horario general de Las noches del Talia."
        clave = (u.group(1), v[0])
        if clave in vistos:
            continue
        vistos.add(clave)
        e = evento("talia", sala, fecha_hora(v[0], hora), titulo, u.group(1),
                   "Espectáculo en el Teatre Talia. Consulta los detalles, el horario y las entradas en la web de venta." + nota,
                   "teatretalia.es", categoria=categoria,
                   artista=limpio(sub.group(1)) if sub else "",
                   fin=fecha_hora(v[1]) if v[1] else None)
        res.append(e)
    return sala, res


# ------------------------------------------------------------------------ Les Arts
CATEGORIAS_ARTS_ESCENA = ("ópera", "opera", "danza", "dansa", "sarsuela", "zarzuela")
CATEGORIAS_ARTS_FUERA = ("educ", "familiar", "visita", "taller", "conferencia", "charla", "escuela")


def leer_les_arts():
    sala = "Palau de les Arts"
    pagina = descargar("https://www.lesarts.com/es/programacion.html")
    res, vistos = [], set()
    for m, b in trozos(pagina, r'<div role="listitem" class="[^"]*box_product[^"]*"'):
        c = re.search(r'class="button comprar[^"]*"\s+href="([^"]+)"', b)
        t = re.search(r'class="titol h4 no-margin">(.*?)</a>', b, re.S)
        i = re.search(r'<span class="data-inici">(.*?)</span>', b, re.S)
        if not (c and t and i):
            continue
        d1 = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", i.group(1))
        if not d1:
            continue
        ini = datetime.date(2000 + int(d1.group(3)), int(d1.group(2)), int(d1.group(1)))
        fin = None
        f = re.search(r'<span class="data-fi">(.*?)</span>', b, re.S)
        if f:
            d2 = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", f.group(1))
            if d2:
                fin = datetime.date(2000 + int(d2.group(3)), int(d2.group(2)), int(d2.group(1)))
        h = re.search(r"class=.hora.>\s*(\d{1,2}:\d{2})\s*h", b)
        hora = h.group(1).zfill(5) if h and not fin else None
        v = vigente(ini, fin)
        if not v:
            continue
        cat = re.search(r'<span class="small categoria c\d+">(.*?)</span>', b, re.S)
        cat = limpio(cat.group(1)) if cat else ""
        cl = cat.lower()
        if any(x in cl for x in CATEGORIAS_ARTS_FUERA):
            continue
        categoria = "teatro" if any(x in cl for x in CATEGORIAS_ARTS_ESCENA) else "musica"
        sub = re.search(r'<div class="subtitol h5">(.*?)</div>', b, re.S)
        esp = re.search(r'<div class="espai[^"]*"[^>]*>(?:<i[^>]*></i>)?(.*?)</div>', b, re.S)
        url = html_lib.unescape(c.group(1))
        clave = (url, v[0])
        if clave in vistos:
            continue
        vistos.add(clave)
        desc = " · ".join(x for x in (cat, limpio(esp.group(1)) if esp else "") if x)
        res.append(evento("arts", sala, fecha_hora(v[0], hora), bonito(limpio(t.group(1))), url,
                          f"{desc}. Consulta los detalles y las entradas en la web de Les Arts.",
                          "lesarts.com", categoria=categoria,
                          artista=bonito(limpio(sub.group(1))) if sub else "",
                          fin=fecha_hora(v[1]) if v[1] else None))
    return sala, res


# ------------------------------------------------------------------ Palau Alameda
def limpiar_url(url):
    partes = urlsplit(url)
    consulta = [(k, v) for k, v in parse_qsl(partes.query) if k.lower() not in ("srsltid", "utm_source", "utm_medium", "utm_campaign")]
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(consulta), ""))


def leer_palau_alameda():
    sala = "Palau Alameda"
    pagina = descargar("https://palaualameda.com/agenda-de-conciertos")
    res, vistos = [], set()
    for m, b in trozos(pagina, r'<a class="gig" [^>]*href="[^"]+"'):
        u = re.search(r'href="([^"]+)"', m.group(0))
        t = re.search(r'<span class="gig__booking-title">(.*?)</span>', b, re.S)
        f = re.search(rf'aria-label="[^"]*?(\d{{1,2}}) ({NOMBRES_MES}) (\d{{4}})(?: De (\d{{1,2}}:\d{{2}}))?', b, re.I)
        if not (u and t and f):
            continue
        titulo = limpio(t.group(1)).replace("✨", "").strip()
        titulo = re.sub(r"\s+en\s+val[eè]ncia$", "", titulo, flags=re.I)
        if re.search(r"coffee party", titulo, re.I):
            continue
        dia = datetime.date(int(f.group(3)), MESES_ES[f.group(2).lower()], int(f.group(1)))
        if dia < HOY:
            continue
        hora = f.group(4).zfill(5) if f.group(4) else None
        p = re.search(r'<span class="gig__price">(.*?)</span>', b, re.S)
        ptxt = limpio(p.group(1)) if p else ""
        num = re.search(r"(\d+(?:[.,]\d+)?)", ptxt)
        precio = (("desde " if "desde" in ptxt.lower() else "") + euros(num.group(1))) if num and euros(num.group(1)) else None
        url = limpiar_url(html_lib.unescape(u.group(1)))
        clave = (url, dia)
        if clave in vistos:
            continue
        vistos.add(clave)
        res.append(evento("alameda", sala, fecha_hora(dia, hora), bonito(titulo), url,
                          "Concierto en Palau Alameda. Consulta los detalles en la web de la sala.",
                          "palaualameda.com", precio=precio))
    return sala, res


# ------------------------------------------------------------- Principal y Rialto
def _leer_ivc(url, sala, prefijo):
    pagina = descargar(url)
    excluir = re.compile(r"abono|laboratori|laboratorio|taller", re.I)
    res, vistos = [], set()
    for m, b in trozos(pagina, r'<div class="minificha'):
        t = re.search(r'<h2><a href="([^"]*)" title="([^"]*)">', b)
        f = re.search(r'<p class="fecha">(.*?)</p>', b, re.S)
        if not (t and f):
            continue
        titulo = limpio(t.group(2))
        if excluir.search(titulo):
            continue
        fechas = interpretar_fechas(limpio(f.group(1)).split("·")[0])
        if not fechas:
            continue
        v = vigente(*fechas)
        if not v:
            continue
        venta = re.search(r'<a class="boton-venta[^"]*" href="([^"]+)"', b)
        enlace = html_lib.unescape(venta.group(1)) if venta else html_lib.unescape(t.group(1))
        clave = (enlace, v[0])
        if clave in vistos:
            continue
        vistos.add(clave)
        res.append(evento(prefijo, sala, fecha_hora(v[0]), bonito(titulo), enlace,
                          f"Artes escénicas en {sala}. Consulta los detalles, el horario y las entradas en la web de venta.",
                          "ivc.gva.es", categoria="teatro",
                          fin=fecha_hora(v[1]) if v[1] else None))
    return sala, res


def leer_principal():
    return _leer_ivc("https://ivc.gva.es/es/escena/programacion-escena/teatro-principal-de-valencia-escena",
                     "Teatre Principal (Martín i Soler)", "principal")


def leer_rialto():
    return _leer_ivc("https://ivc.gva.es/es/escena/programacion-escena/teatro-rialto-de-valencia-escena",
                     "Teatre Rialto", "rialto")


# --------------------------------------------------------------------- Radio City
def _titulo_de_slug(url):
    m = re.search(r"/eventos/(.+?)(?:-\d{1,2}-\d{1,2}-\d{4})?/?$", url)
    texto = (m.group(1) if m else "").replace("-", " ").strip() or "evento"
    return bonito(" ".join(w.capitalize() for w in texto.split()))


def leer_radio_city():
    sala = "Radio City"
    pagina = descargar("https://radiocityvalencia.es/agenda/")
    res, vistos = [], set()
    for m, b in trozos(pagina, r'<div class="card-container'):
        info = re.search(r'href="(https://radiocityvalencia\.es/eventos/[^"]+)"[^>]*>\s*\+\s*Info', b)
        fecha = re.search(r'class="Fecha_Banner">\s*([^<]+?)\s*<', b)
        hora = re.search(r'class="Hora_Banner">\s*(\d{1,2}:\d{2})\s*<', b)
        if not (info and fecha and hora):
            continue
        hora = hora.group(1).zfill(5)
        venta = re.search(r'href="(https://entradium\.com/es/events/[^"]+)"', b)
        generico = re.search(r'href="(https://entradium\.com/es/(?:search|organizers)[^"]*)"', b)
        t = re.search(r'class="Titulo_Banner[^"]*">(.*?)</p>', b, re.S)
        detalles = [limpio(x) for x in re.findall(r'class="Detalle_Banner">(.*?)</p>', b, re.S)]
        titulo_base = limpio(t.group(1)) if t else ""
        if titulo_base and detalles:
            if titulo_base.endswith(":"):
                titulo = f"{titulo_base} {detalles[0]}"
            elif titulo_base[:1] in "¡¿" or titulo_base.endswith(("!", "?")):
                titulo = f"{detalles[0]}: {titulo_base}"
            else:
                titulo = f"{titulo_base}: {detalles[0]}"
            artista = " · ".join(detalles[1:])
        else:
            titulo, artista = (titulo_base or _titulo_de_slug(info.group(1))), ""
        titulo = bonito(titulo)
        txt = fecha.group(1).strip()
        dm = re.match(r"(\d{1,2})-([A-Za-z]{3})", txt)
        if dm and dm.group(2).lower() in MES_ABREV:
            dia = datetime.date(inferir_anio(MES_ABREV[dm.group(2).lower()], int(dm.group(1))),
                                MES_ABREV[dm.group(2).lower()], int(dm.group(1)))
            if dia < HOY:
                continue
            if venta:
                url, nota = venta.group(1), ""
            elif generico and hora != "23:59":
                url, nota = info.group(1), ""
            else:
                continue  # sesiones sin entrada (pinchadiscos, jams)
            fechas = [dia]
        elif txt.lower() in DIAS_SEMANA and venta:
            # noche semanal con entrada: se generan las próximas 4 semanas
            objetivo = DIAS_SEMANA[txt.lower()]
            primero = HOY + datetime.timedelta(days=(objetivo - HOY.weekday()) % 7)
            fechas = [primero + datetime.timedelta(weeks=i) for i in range(4)]
            url, nota = venta.group(1), " Noche semanal: confirma el cartel de cada fecha en la web de la sala."
        else:
            continue
        for dia in fechas:
            clave = (info.group(1), dia)
            if clave in vistos:
                continue
            vistos.add(clave)
            res.append(evento("radiocity", sala, fecha_hora(dia, hora), titulo, url,
                              "Concierto en Radio City. Consulta los detalles en la web de la sala." + nota,
                              "radiocityvalencia.es", artista=artista))
    return sala, res


# ------------------------------------------------------------------ Sala Jerusalem
def leer_jerusalem():
    sala = "Sala Jerusalem"
    pagina = descargar("https://www.jerusalemclub.es/web/conciertos/")
    res, vistos = [], set()
    for m, b in trozos(pagina, r"<div class='brick"):
        u = re.search(r"<a class='inner[^']*' href='([^']+)'", b)
        t = re.search(r"<h2 class='title'>(.*?)</h2>", b, re.S)
        f = re.search(r"fa-calendar'></i>\s*(\d{2})/(\d{2})/(\d{4})", b)
        if not (u and t and f):
            continue
        dia = datetime.date(int(f.group(3)), int(f.group(2)), int(f.group(1)))
        if dia < HOY:
            continue
        titulo = re.sub(r"\s*\d{2}/\d{2}/\d{4}\s*$", "", limpio(t.group(1)))
        url = html_lib.unescape(u.group(1))
        clave = (url, dia)
        if not titulo or clave in vistos:
            continue
        vistos.add(clave)
        res.append(evento("jerusalem", sala, fecha_hora(dia), bonito(titulo), url,
                          "Concierto en Sala Jerusalem. Consulta la hora, el precio y las entradas en la web de la sala.",
                          "jerusalemclub.es"))
    return sala, res


# ---------------------------------------------------------------------- Roig Arena
def leer_roig_arena():
    sala = "Roig Arena"
    excluir = re.compile(r"valencia basket|baloncesto|euroliga|eurocup|partido|\bacb\b|supercopa|boxeo|\bufc\b|\bwwe\b", re.I)
    res, vistos = [], set()
    n = {"tarjetas": 0, "sin_enlace_con_fecha": 0, "deporte": 0}
    for pagina_url in ("https://www.roigarena.com/", "https://www.roigarena.com/es/eventos/"):
        try:
            pagina = descargar(pagina_url)
            NOTAS.append(f"Roig Arena: {pagina_url} leída ({len(pagina)} caracteres)")
        except Exception as error:  # noqa: BLE001
            NOTAS.append(f"Roig Arena: {pagina_url} NO se pudo leer ({str(error)[:120]})")
            continue
        for m, b in trozos(pagina, r'<div class="m-card(?: [^"]*)?"'):
            n["tarjetas"] += 1
            t = re.search(r'itemprop="headline">(.*?)</', b, re.S)
            u = re.search(r'href="(https://www\.roigarena\.com/es/event/[a-z0-9-]+-(\d{8})/tickets/?)"', b)
            if not (t and u):
                n["sin_enlace_con_fecha"] += 1
                continue
            ds = u.group(2)
            try:
                dia = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:]))
            except ValueError:
                continue
            titulo = limpio(t.group(1))
            if excluir.search(titulo):
                n["deporte"] += 1
                continue
            if dia < HOY or not titulo:
                continue
            clave = (u.group(1), dia)
            if clave in vistos:
                continue
            vistos.add(clave)
            res.append(evento("roig", sala, fecha_hora(dia), bonito(titulo), html_lib.unescape(u.group(1)),
                              "Evento en el Roig Arena. Consulta la hora, el precio y las entradas en la web del recinto.",
                              "roigarena.com", categoria="musica"))
    NOTAS.append("Roig Arena: " + ", ".join(f"{k}={v}" for k, v in n.items()))
    return sala, res


# ------------------------------------------------------------------- Teatre Micalet
def leer_micalet():
    sala = "Teatre Micalet"
    url = ("https://companyiateatremicalet.com/wp-json/tribe/events/v1/events"
           f"?per_page=50&start_date={HOY:%Y-%m-%d}")
    res, vistos = [], set()
    n = {"recibidos": 0, "otra_ciudad": 0, "sin_fecha_o_enlace": 0, "pasados": 0, "taller": 0}
    ejemplo = None
    for _ in range(4):
        datos = json.loads(descargar(url))
        if ejemplo is None:
            ejemplo = (f"claves de la respuesta={sorted(datos.keys())}; total={datos.get('total')}; "
                       f"primer evento={json.dumps((datos.get('events') or [None])[0], ensure_ascii=False)[:350]}")
        for e in datos.get("events", []):
            n["recibidos"] += 1
            v = e.get("venue") or {}
            if isinstance(v, dict) and v:
                nombre, ciudad = str(v.get("venue", "")).lower(), str(v.get("city", "")).lower()
                if "micalet" not in nombre and "val" not in ciudad:
                    n["otra_ciudad"] += 1
                    continue  # gira fuera de Valencia
            inicio = str(e.get("start_date", ""))
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?", inicio)
            if not m or not e.get("url"):
                n["sin_fecha_o_enlace"] += 1
                continue
            dia = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if dia < HOY:
                n["pasados"] += 1
                continue
            hora = f"{m.group(4)}:{m.group(5)}" if m.group(4) and not e.get("all_day") else None
            titulo = bonito(limpio(str(e.get("title", ""))))
            if re.search(r"taller|curso|casting|audici|campus", titulo, re.I):
                n["taller"] += 1
                continue
            clave = (e["url"], dia, hora)
            if not titulo or clave in vistos:
                continue
            vistos.add(clave)
            coste = limpio(str(e.get("cost", ""))) or None
            res.append(evento("micalet", sala, fecha_hora(dia, hora), titulo, e["url"],
                              "Función en el Teatre Micalet. Consulta los detalles y las entradas en la web de la compañía.",
                              "companyiateatremicalet.com", categoria="teatro", precio=coste))
        url = datos.get("next_rest_url")
        if not url:
            break
    NOTAS.append("Teatre Micalet: " + ", ".join(f"{k}={v}" for k, v in n.items()) + f"; {ejemplo}")
    return sala, res


LECTORES_NUEVOS = [leer_palau_musica, leer_peter_rock, leer_rambleta, leer_talia,
                   leer_les_arts, leer_palau_alameda, leer_principal, leer_rialto,
                   leer_radio_city, leer_jerusalem, leer_roig_arena, leer_micalet]
