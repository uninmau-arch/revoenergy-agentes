"""Genera una vista previa HTML de los posts listos para revisión (como se verían publicados)."""
import html as html_lib
import os

from .ilustrador import CARPETA, alts_como_dict

SALIDA = os.path.join(os.path.dirname(CARPETA), "vista_previa")

PLANTILLA = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Vista previa – RevoEnergy</title>
<style>
body{{font-family:Georgia,serif;max-width:760px;margin:40px auto;padding:0 20px;color:#222;line-height:1.7}}
article{{border-bottom:3px solid #6BAA4E;padding-bottom:40px;margin-bottom:60px}}
h1{{font-family:Arial,sans-serif;font-size:2em;line-height:1.2}} h2,h3{{font-family:Arial,sans-serif}}
img{{width:100%;height:auto;border-radius:8px}} table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:6px}} .meta{{font-family:Arial;font-size:.9em;color:#555;background:#f3f7f0;padding:10px;border-radius:6px}}
</style></head><body>{articulos}</body></html>"""


def generar(posts):
    os.makedirs(SALIDA, exist_ok=True)
    bloques = []
    for p in posts:
        alts = alts_como_dict(p["ALTS"])
        cuerpo = p["HTML"]
        for nombre, alt in alts.items():
            img = f'<figure><img src="../imagenes/{nombre}.webp" alt="{html_lib.escape(alt)}"></figure>'
            cuerpo = cuerpo.replace(f"<!--IMG:{nombre}-->", img)
        portada = next((n for n in alts if n.endswith("-portada")), "")
        bloques.append(
            f'<article><p class="meta"><b>{p["ID"]}</b> · Categoría: {html_lib.escape(p["CATEGORIA"])} · '
            f'Slug: /{p["SLUG"]}/<br>Meta: {html_lib.escape(p["META"])}</p>'
            f'<h1>{html_lib.escape(p["TITULO"])}</h1>'
            + (f'<img src="../imagenes/{portada}.webp" alt="{html_lib.escape(alts.get(portada, ""))}">' if portada else "")
            + cuerpo + "</article>"
        )
    with open(os.path.join(SALIDA, "index.html"), "w", encoding="utf-8") as f:
        f.write(PLANTILLA.format(articulos="\n".join(bloques)))
