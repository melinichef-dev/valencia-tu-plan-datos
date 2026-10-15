"""
Guarda en muestras.txt trozos reales de HTML de las webs que todavía no se leen
automáticamente, para poder escribir sus lectores en la siguiente ronda.
"""
import re

from comun import descargar

# (nombre, dirección, texto que buscamos en la página para localizar un evento)
OBJETIVOS = [
    ("Palau de la Música", "https://palauvalencia.com/", "orquesta-sinfonica-de-dusseldorf"),
    ("Radio City", "https://radiocityvalencia.es/agenda/", "cenk-essen"),
    ("Peter Rock Club", "https://www.peterrockclub.es/", "los-routers"),
    ("La Rambleta", "https://larambleta.com/", "joe-jackson"),
    ("Teatre Talia", "https://www.teatretalia.es/", "apocalipsi-fatxa"),
    ("Les Arts", "https://www.lesarts.com/es/programacion.html", "riccardo-primo"),
    ("Palau Alameda", "https://palaualameda.com/agenda-de-conciertos", "elyella"),
    ("Teatre Principal", "https://ivc.gva.es/es/escena/programacion-escena/teatro-principal-de-valencia-escena", "los-duelistas"),
    ("Teatre Rialto", "https://ivc.gva.es/es/escena/programacion-escena/teatro-rialto-de-valencia-escena", "karma-letal"),
]


def limpiar(html):
    html = re.sub(r"<svg.*?</svg>", "<svg/>", html, flags=re.S | re.I)
    html = re.sub(r"data:[^\"')\s]{80,}", "data:…", html)
    html = re.sub(r"<script[^>]*>.*?</script>", "<script/>", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", "<style/>", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html)


def main():
    with open("muestras.txt", "w", encoding="utf-8") as f:
        for nombre, url, clave in OBJETIVOS:
            f.write(f"\n{'=' * 70}\n{nombre}\n{url}\nbuscando: {clave}\n")
            try:
                html = limpiar(descargar(url))
            except Exception as e:  # noqa: BLE001
                f.write(f"ERROR: {e}\n")
                continue
            i = html.lower().find(clave.lower())
            if i < 0:
                f.write("No se encontró el texto buscado en la página.\n")
                continue
            f.write(html[max(0, i - 1800): i + 3200] + "\n")


if __name__ == "__main__":
    main()
