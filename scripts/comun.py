"""Utilidades compartidas por los programas de actualización."""
import re
import time
import unicodedata
import urllib.robotparser
from urllib.parse import urlparse

import requests

UA = "ValenciaTuPlanBot/1.0 (agenda cultural gratuita sin ánimo de lucro)"
CABECERAS = {"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"}
PAUSA = 1.0  # segundos entre visitas a la misma web

NOTAS = []  # observaciones que se copian al informe
_robots = {}


def robots_permite(url):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers=CABECERAS, timeout=15)
            if r.status_code >= 400:
                rp = None  # sin robots.txt: se permite
            else:
                rp.parse(r.text.splitlines())
        except Exception:  # noqa: BLE001
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)


def descargar(url):
    """Descarga una página respetando robots.txt. Devuelve el HTML o lanza error."""
    if not robots_permite(url):
        raise RuntimeError(f"robots.txt no permite leer {url}")
    r = requests.get(url, headers=CABECERAS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    time.sleep(PAUSA)
    return r.text


def slug(texto, largo=40):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:largo]


MANTENER = {"DJ", "MT", "UK", "USA", "II", "III", "IV", "VI", "VII", "VIII",
            "IX", "XV", "XX", "TV", "EP", "LP", "IVC", "OST"}


def bonito(titulo):
    """Convierte TÍTULOS EN MAYÚSCULAS en Título Normal. Si ya está bien, no toca nada."""
    t = titulo.strip()
    letras = [c for c in t if c.isalpha()]
    if not letras or sum(c.isupper() for c in letras) < 0.8 * len(letras):
        return t

    pequenas = {"de", "del", "la", "las", "el", "los", "y", "e", "o", "u", "a", "al",
                "en", "por", "para", "un", "una", "the", "of", "and", "in", "on",
                "to", "for", "i", "amb", "els", "les"}

    def cambiar(m):
        w = m.group(0)
        if w in MANTENER:
            return w
        previo = t[m.start() - 1] if m.start() > 0 else ""
        if previo and len(w) == 1 and previo in "'’":
            return w.lower()
        if previo == "·":
            return w.lower()
        if previo == "-" and len(w) <= 3:
            return w.lower()
        if m.start() > 0 and w.lower() in pequenas and t[:m.start()].strip()[-1:] not in ":.-¡¿":
            return w.lower()
        return w.capitalize()

    return re.sub(r"[^\W\d_]+", cambiar, t)


def euros(valor):
    """'18.00' -> '18 €'; '16.5' -> '16,50 €'. Devuelve None si no hay precio."""
    if valor in (None, "", "0", "0.00"):
        return None
    try:
        n = float(str(valor).replace(",", "."))
    except ValueError:
        return None
    if n <= 0:
        return None
    return f"{int(n)} €" if n == int(n) else f"{n:.2f}".replace(".", ",") + " €"


def es_venta(url):
    """¿La dirección parece de una plataforma de venta de entradas?"""
    host = url.lower().split("/")[2] if url.count("/") >= 2 else url.lower()
    claves = ("ticket", "entrad", "fever", "universe", "passline", "dice.fm",
              "eventbrite", "woutick", "fourvenues", "vibess", "koobin",
              "taquilla", "sacatuentrada", "enterticket", "notikumi", "mutick")
    return any(c in host for c in claves)
