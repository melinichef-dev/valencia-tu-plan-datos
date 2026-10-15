"""
Guarda en muestras.txt trozos reales de HTML de las webs que todavía no se leen
automáticamente, para poder escribir sus lectores en la siguiente ronda.
"""
import re

from comun import descargar

# (nombre, dirección, textos que buscamos para localizar eventos; None = primera fecha de 2026)
OBJETIVOS = []  # de momento sin objetivos: se rellena cuando haya webs nuevas que probar

# Primera fecha que parezca de un evento futuro: "21 de octubre", "21/10/2026", "21 oct"...
PATRON_FECHA = re.compile(
    r"(?<!\d)\d{1,2}\s*(?:de\s+)?(?:octubre|noviembre|diciembre|oct|nov|dic)\b"
    r"|(?<!\d)\d{1,2}[/.-](?:10|11|12)[/.-](?:2026|26)\b", re.I)


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
            if claves:
                for clave in claves:
                    i = html.lower().find(clave.lower())
                    if i < 0:
                        f.write(f"No se encontró: {clave}\n")
                        continue
                    f.write(f"--- alrededor de: {clave} ---\n")
                    f.write(html[max(0, i - 1500): i + 3000] + "\n")
            else:
                m = PATRON_FECHA.search(html)
                if not m:
                    f.write("No se encontró ninguna fecha de evento futuro en la página.\n")
                    continue
                f.write(f"--- alrededor de la primera fecha: {m.group(0)} ---\n")
                f.write(html[max(0, m.start() - 1200): m.start() + 2200] + "\n")


if __name__ == "__main__":
    main()
