"""
Guarda en muestras.txt trozos reales de HTML de las webs que todavía no se leen
automáticamente, para poder escribir sus lectores en la siguiente ronda.
"""
import re

from comun import descargar

# (nombre, dirección, textos que buscamos para localizar eventos; None = primera fecha de 2026)
OBJETIVOS = [
    ("Roig Arena (listado de eventos)", "https://www.roigarena.com/es/eventos/",
     ["/es/event/", "m-card__title"]),
    ("Teatre Micalet (agenda técnica)",
     "https://companyiateatremicalet.com/wp-json/tribe/events/v1/events?per_page=5",
     ["\"events\""]),
    ("Teatre Micalet (web)", "https://companyiateatremicalet.com/agenda/", None),
]


def limpiar(html):
    html = re.sub(r"<svg.*?</svg>", "<svg/>", html, flags=re.S | re.I)
    html = re.sub(r"data:[^\"')\s]{80,}", "data:…", html)
    html = re.sub(r"<script[^>]*>.*?</script>", "<script/>", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", "<style/>", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html)


def main():
    with open("muestras.txt", "w", encoding="utf-8") as f:
        for nombre, url, claves in OBJETIVOS:
            f.write(f"\n{'=' * 70}\n{nombre}\n{url}\n")
            try:
                html = limpiar(descargar(url))
            except Exception as e:  # noqa: BLE001
                f.write(f"ERROR: {e}\n")
                continue
            f.write(f"tamaño de la página limpia: {len(html)} caracteres\n")
            for clave in (claves or ["2026"]):
                i = html.lower().find(clave.lower())
                if i < 0:
                    f.write(f"No se encontró: {clave}\n")
                    continue
                f.write(f"--- alrededor de: {clave} ---\n")
                f.write(html[max(0, i - 1500): i + 3000] + "\n")


if __name__ == "__main__":
    main()
