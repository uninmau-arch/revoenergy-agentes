"""Agente publicador: sube imágenes y posts aprobados a WordPress por su API REST.

Usa una "Contraseña de aplicación" de WordPress (Usuarios → Perfil → Contraseñas de aplicación).
Publica con fechas pasadas aleatorias, como en el Método Vuela.
"""
import datetime
import os
import random

import requests

from .ilustrador import CARPETA, alts_como_dict


class WordPress:
    def __init__(self, url):
        self.base = url.rstrip("/") + "/wp-json/wp/v2"
        self.auth = (os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"].replace(" ", ""))
        self._categorias = {}

    def _pedir(self, metodo, ruta, **kw):
        r = requests.request(metodo, f"{self.base}/{ruta}", auth=self.auth, timeout=120, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"WordPress {metodo} {ruta} → {r.status_code}: {r.text[:300]}")
        return r.json()

    def subir_imagen(self, nombre, alt):
        ruta = os.path.join(CARPETA, f"{nombre}.webp")
        with open(ruta, "rb") as f:
            media = self._pedir(
                "POST", "media", data=f.read(),
                headers={"Content-Disposition": f'attachment; filename="{nombre}.webp"', "Content-Type": "image/webp"},
            )
        self._pedir("POST", f"media/{media['id']}", json={"alt_text": alt, "title": alt})
        return media["id"], media["source_url"]

    def categoria(self, nombre):
        if nombre in self._categorias:
            return self._categorias[nombre]
        for c in self._pedir("GET", "categories", params={"search": nombre, "per_page": 100}):
            if c["name"].strip().lower() == nombre.strip().lower():
                self._categorias[nombre] = c["id"]
                return c["id"]
        nueva = self._pedir("POST", "categories", json={"name": nombre})
        self._categorias[nombre] = nueva["id"]
        return nueva["id"]

    def crear_post(self, datos):
        return self._pedir("POST", "posts", json=datos)


def fecha_pasada_aleatoria(dias=120):
    ahora = datetime.datetime.now()
    return (ahora - datetime.timedelta(days=random.randint(1, dias), minutes=random.randint(0, 1439))).strftime("%Y-%m-%dT%H:%M:%S")


def publicar(post, wp_url):
    wp = WordPress(wp_url)
    alts = alts_como_dict(post["ALTS"])
    nombres = [n.strip() for n in post["ARCHIVOS"].split(",") if n.strip()]
    html = post["HTML"]
    portada_id = None
    for nombre in nombres:
        alt = alts.get(nombre, post["TITULO"])
        media_id, url = wp.subir_imagen(nombre, alt)
        if nombre.endswith("-portada"):
            portada_id = media_id
        else:
            figura = f'<figure class="wp-block-image size-large"><img src="{url}" alt="{alt}" loading="lazy" /></figure>'
            html = html.replace(f"<!--IMG:{nombre}-->", figura)
    creado = wp.crear_post({
        "title": post["TITULO"],
        "slug": post["SLUG"],
        "content": html,
        "excerpt": post["META"],
        "status": "publish",
        "date": fecha_pasada_aleatoria(),
        "categories": [wp.categoria(post["CATEGORIA"])],
        **({"featured_media": portada_id} if portada_id else {}),
    })
    return creado["link"], creado["date"]
