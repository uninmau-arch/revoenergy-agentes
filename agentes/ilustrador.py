"""Agente ilustrador: dibuja con código (SVG) la portada y las imágenes internas, y las convierte a WebP.

Reglas de colocación del Método Vuela:
- Portada siempre.
- Sin H2: ninguna imagen interna. Con 1-4 H2: una a la mitad. Con más: dos (al 33% y al 66%).
"""
import io
import math
import os
import re
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image

from .llm import chat, secciones

CARPETA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "salida", "imagenes")
ANCHO, ALTO = 1200, 675

ESTILO = """ESTILO DE MARCA REVOENERGY (obligatorio):
- Ilustración vectorial plana (flat design), amable y moderna, con profundidad por capas de formas superpuestas.
- Paleta: cielo #BFE3F5 o #E8F4FA, sol #F7C548, verde #6BAA4E y #8CC56A, azul energía #2C4A7A y #378ADD,
  teja/terracota #C8553D, crema #F4EDE1, gris claro #E9EEF2, acentos #1D9E75. Puedes usar tonos intermedios de estos.
- Fondo completo (nada transparente), composición centrada y equilibrada, sin bordes.
- PROHIBIDO cualquier texto, letra, número, logo o marca de agua: no uses <text>, <tspan> ni formas que imiten letras.
- Sin imágenes externas, sin <image>, sin <foreignObject>, sin scripts, sin filtros ni fuentes.
- Mínimo 30 formas (rect, circle, ellipse, polygon, path) para que tenga detalle.
- Personas (si aparecen): siluetas sencillas y genéricas, sin rasgos de personas reales."""


def posiciones_imagenes(html):
    """Devuelve los índices (1..n) de los H2 tras los que va una imagen."""
    h2 = [t for t in re.findall(r"<h2[^>]*>(.*?)</h2>", html, flags=re.S) if "fuentes consultadas" not in t.lower()]
    n = len(h2)
    if n == 0:
        return []
    if n <= 4:
        return [math.ceil(n / 2)]
    return sorted({max(1, round(n * 0.33)), max(1, round(n * 0.66))})


def subtitulos_h2(html):
    return [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<h2[^>]*>(.*?)</h2>", html, flags=re.S)]


def dibujar(motivo, titulo, sitio):
    """Pide al modelo un SVG y su texto alternativo; devuelve (svg, alt, escena)."""
    prompt = f"""Dibuja con código SVG una ilustración para el artículo "{titulo}" del sitio "{sitio['nombre']}".
La ilustración debe representar: {motivo}

{ESTILO}

Requisitos técnicos: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {ALTO}" width="{ANCHO}" height="{ALTO}">.
Representa el tema de forma reconocible (por ejemplo placas solares, inversor, batería, casa, coche eléctrico, aerogenerador, etc.).

Responde EXACTAMENTE con este formato:
===ESCENA===
(una frase en español describiendo la escena)
===ALT===
(texto alternativo en español, una sola frase corta que describa lo que se ve)
===SVG===
(solo el código SVG completo)
===FIN==="""
    respuesta = chat(
        [
            {"role": "system", "content": "Eres ilustrador vectorial experto en SVG limpio y válido."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=12000,
        temperatura=0.7,
    )
    datos = secciones(respuesta, ["ESCENA", "ALT", "SVG"])
    svg = sanear_svg(datos["SVG"])
    alt = datos["ALT"].replace('"', "").splitlines()[0].rstrip(".")
    return svg, alt, datos["ESCENA"].splitlines()[0]


def sanear_svg(svg):
    m = re.search(r"<svg\b.*?</svg>", svg, flags=re.S | re.I)
    if not m:
        raise ValueError("El modelo no devolvió un <svg> válido")
    svg = m.group(0)
    svg = re.sub(r"<(text|tspan|script|foreignObject|image)\b.*?(</\1>|/>)", "", svg, flags=re.S | re.I)
    if "xmlns=" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    ET.fromstring(svg)  # lanza error si el XML no es válido
    return svg


def a_webp(svg, ruta_webp):
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=ANCHO, output_height=ALTO)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.save(ruta_webp, "WEBP", quality=82, method=6)


def crear_imagen(nombre, motivo, titulo, sitio, intentos=3):
    os.makedirs(CARPETA, exist_ok=True)
    ultimo = None
    for _ in range(intentos):
        try:
            svg, alt, escena = dibujar(motivo, titulo, sitio)
            with open(os.path.join(CARPETA, f"{nombre}.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
            a_webp(svg, os.path.join(CARPETA, f"{nombre}.webp"))
            return alt, escena
        except Exception as e:  # noqa: BLE001
            ultimo = e
            print(f"[ilustrador] {nombre}: reintento por {e}")
    raise RuntimeError(f"No se pudo crear la imagen {nombre}: {ultimo}")


def ilustrar(post, sitio):
    """Crea portada e imágenes internas. Devuelve html con marcadores, escenas, alts y nombres."""
    html, titulo, slug = post["html"], post["titulo"], post["slug"]
    trabajos = [(f"{slug}-portada", f"la idea principal del artículo: {titulo}", None)]
    subtitulos = [s for s in subtitulos_h2(html) if "fuentes consultadas" not in s.lower()]
    for n, pos in enumerate(posiciones_imagenes(html), start=1):
        sub = subtitulos[pos - 1]
        trabajos.append((f"{slug}-{n}", f"{sub} (dentro del tema: {titulo})", sub))

    escenas, alts, nombres = [], [], []
    for nombre, motivo, subtitulo in trabajos:
        alt, escena = crear_imagen(nombre, motivo, titulo, sitio)
        escenas.append(f"{nombre}: {escena}")
        alts.append(f"{nombre} | {alt}")
        nombres.append(nombre)
        if subtitulo:
            html = insertar_despues_de_h2(html, subtitulo, nombre)
    return html, "\n".join(escenas), "\n".join(alts), ", ".join(nombres)


def insertar_despues_de_h2(html, subtitulo, nombre):
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, flags=re.S):
        if re.sub(r"<[^>]+>", "", m.group(1)).strip() == subtitulo:
            return html[: m.end()] + f"\n<!--IMG:{nombre}-->" + html[m.end():]
    return html


def alts_como_dict(texto_alts):
    res = {}
    for linea in texto_alts.splitlines():
        if "|" in linea:
            k, v = linea.split("|", 1)
            res[k.strip()] = v.strip()
    return res
