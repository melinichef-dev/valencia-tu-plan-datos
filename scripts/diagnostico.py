"""
Diagnóstico de las webs de salas y teatros.

Visita cada web UNA vez, respetando su archivo robots.txt, y escribe en
diagnostico.txt un resumen de qué datos se pueden leer automáticamente.
No modifica eventos.json.
"""
import json
import re
import urllib.robotparser
from urllib.parse import urlparse

import requests

UA = "ValenciaTuPlanBot/1.0 (agenda cultural gratuita sin ánimo de lucro)"
CABECERAS = {"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"}

SITIOS = {
    "16 Toneladas": "https://www.16toneladas.com/",
    "Loco Club": "https://lococlub.es/",
    "Rock City": "https://www.rockcity.es/",
    "Radio City": "https://radiocityvalencia.es/agenda/",
    "Peter Rock Club": "https://www.peterrockclub.es/",
    "Palau de la Música": "https://palauvalencia.com/",
    "La Rambleta": "https://larambleta.com/",
    "Teatre Talia": "https://www.teatretalia.es/",
    "Les Arts": "https://www.lesarts.com/es/programacion.html",
    "Palau Alameda": "https://palaualameda.com/agenda-de-conciertos",
    "Teatre Principal": "https://ivc.gva.es/es/escena/programacion-escena/teatro-principal-de-valencia-escena",
    "Teatre Rialto": "https://ivc.gva.es/es/escena/programacion-escena/teatro-rialto-de-valencia-escena",
    "Sala Moon": "https://www.salamoon.com/",
}

PATRONES_FECHA = {
    "dd/mm/aaaa": r"\b\d{1,2}/\d{1,2}/20\d\d\b",
    "aaaa-mm-dd": r"\b20\d\d-\d\d-\d\d\b",
    "mes escrito": r"\b\d{1,2}\s*(?:de\s+)?(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-záéíóú]*\.?(?:\s+(?:de\s+)?20\d\d)?",
}

DOMINIOS_ENTRADAS = [
    "movingtickets", "entradium", "feverup", "enterticket", "notikumi",
    "ticketmaster", "entradas.com", "vivaticket", "woutick", "mutick",
    "ticketere", "koobin", "fourvenues", "taquilla", "sacatuentrada",
    "universe.com", "passline", "ticketandroll", "teatroenvalencia",
    "tickets.palauvalencia",
]


def robots_permite(url):
    p = urlparse(url)
    try:
        r = requests.get(f"{p.scheme}://{p.netloc}/robots.txt",
                         headers=CABECERAS, timeout=15)
        if r.status_code >= 400:
            return True, "no tiene robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, url), "robots.txt leído"
    except Exception as e:  # noqa: BLE001
        return True, f"robots.txt no se pudo leer ({e})"


def eventos_json_ld(html):
    """Busca datos estructurados de tipo Event (los que usa Google)."""
    hallados = []
    bloques = re.findall(
        r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html, re.S | re.I)
    for b in bloques:
        try:
            datos = json.loads(b.strip())
        except Exception:  # noqa: BLE001
            continue
        pila = [datos]
        while pila:
            d = pila.pop()
            if isinstance(d, list):
                pila.extend(d)
            elif isinstance(d, dict):
                tipo = d.get("@type")
                tipos = tipo if isinstance(tipo, list) else [tipo]
                if any(isinstance(t, str) and "Event" in t for t in tipos):
                    hallados.append(d)
                pila.extend(v for v in d.values() if isinstance(v, (list, dict)))
    return hallados


def compactar(texto, limite):
    return re.sub(r"\s+", " ", texto)[:limite]


def resumir(nombre, url, f):
    f.write(f"\n{'=' * 70}\n{nombre}\n{url}\n")
    permitido, nota = robots_permite(url)
    f.write(f"robots.txt: {'PERMITIDO' if permitido else 'PROHIBIDO'} ({nota})\n")
    if not permitido:
        return
    try:
        r = requests.get(url, headers=CABECERAS, timeout=30)
    except Exception as e:  # noqa: BLE001
        f.write(f"ERROR de conexión: {e}\n")
        return
    html = r.text
    f.write(f"estado HTTP: {r.status_code} | tamaño: {len(html)} caracteres | URL final: {r.url}\n")
    if r.status_code != 200:
        return

    ld = eventos_json_ld(html)
    f.write(f"eventos en datos estructurados (JSON-LD): {len(ld)}\n")
    if ld:
        f.write("  ejemplo: " + compactar(json.dumps(ld[0], ensure_ascii=False), 600) + "\n")
    f.write(f"contiene __NEXT_DATA__ (web Next.js): {'__NEXT_DATA__' in html}\n")

    mejor = None
    for etiqueta, patron in PATRONES_FECHA.items():
        coincidencias = list(re.finditer(patron, html, re.I))
        f.write(f"fechas tipo '{etiqueta}': {len(coincidencias)}\n")
        if coincidencias and (mejor is None or len(coincidencias) > len(mejor)):
            mejor = coincidencias

    enlaces = re.findall(r'href=["\']([^"\']+)["\']', html)
    entradas = [e for e in enlaces if any(d in e.lower() for d in DOMINIOS_ENTRADAS)]
    f.write(f"enlaces de venta de entradas: {len(entradas)}\n")
    for e in entradas[:3]:
        f.write(f"  {e[:160]}\n")

    if mejor:
        for m in mejor[:2]:
            trozo = html[max(0, m.start() - 350): m.end() + 350]
            f.write("--- muestra de HTML alrededor de una fecha ---\n")
            f.write(compactar(trozo, 800) + "\n")


def main():
    with open("diagnostico.txt", "w", encoding="utf-8") as f:
        f.write("DIAGNÓSTICO DE WEBS\n")
        for nombre, url in SITIOS.items():
            try:
                resumir(nombre, url, f)
            except Exception as e:  # noqa: BLE001
                f.write(f"ERROR inesperado en {nombre}: {e}\n")
    print("Diagnóstico terminado: diagnostico.txt")


if __name__ == "__main__":
    main()
