"""Agente redactor: escribe el post mejorado siguiendo los lineamientos del Método Vuela."""
import re
import unicodedata

from .llm import chat, secciones

ETIQUETAS_PERMITIDAS = "h2, h3, p, ul, ol, li, strong, em, table, thead, tbody, tr, th, td, a"


def crear_slug(texto):
    texto = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    texto = re.sub(r"[\s-]+", "-", texto).strip("-")
    return texto[:70].rstrip("-")


def limpiar_html(html):
    html = re.sub(r"</?h1[^>]*>", "", html)  # el título ya es el H1 de WordPress
    html = re.sub(r"\bEn (conclusión|resumen),\s*(\w)", lambda m: m.group(2).upper(), html)
    html = re.sub(r"<(script|style|iframe)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    return html.strip()


def redactar(tema, investigacion, fuentes, sitio, lineamientos, nota_revision=""):
    categorias = sitio["categorias"]
    revision = ""
    if nota_revision.strip():
        revision = f"\nEL SUPERVISOR RECHAZÓ LA VERSIÓN ANTERIOR. Corrige esto obligatoriamente:\n{nota_revision}\n"

    sistema = f"""Eres el redactor principal de "{sitio['nombre']}" ({sitio['dominio']}).
Temática: {sitio['descripcion']}
Público: España. Escribe en español de España (euros, "placas solares", "factura de la luz", "móvil", "coche").
Tono cercano, claro y experto. Nada de relleno ni frases genéricas de IA.

LINEAMIENTOS OBLIGATORIOS DEL SITIO:
{lineamientos}
"""
    usuario = f"""Escribe el mejor artículo de internet para la búsqueda: "{tema}".
{revision}
Investigación de los mejores resultados de Google (úsala para superar a la competencia, sin copiar frases):
{investigacion}

Fuentes que puedes citar (usa SOLO estas URL, nunca inventes enlaces):
{fuentes}

Requisitos del artículo:
- Los dos primeros párrafos responden directamente la búsqueda.
- Cubre todo lo que cubren los mejores y además los HUECOS Y MEJORAS de la investigación.
- Responde las PREGUNTAS A RESPONDER, idealmente como subtítulos H2/H3 en forma de pregunta.
- Longitud: la recomendada en la investigación (mínimo 1.200 palabras).
- Párrafos de 2 a 4 líneas, listas y al menos una tabla si ayuda a comparar.
- Pon en <strong> la palabra clave y los conceptos importantes, sin abusar.
- Cifras y precios: indica que son orientativos y la fecha (año actual) o la fuente.
- Termina con un último H2 de cierre útil (no lo llames "Conclusión" ni empieces con "En conclusión").
- Después, un H2 "Fuentes consultadas" con una lista de enlaces <a href="..." rel="nofollow noopener" target="_blank"> a las fuentes que realmente usaste.
- HTML limpio usando solo estas etiquetas: {ETIQUETAS_PERMITIDAS}. Sin H1, sin estilos, sin imágenes.

Responde EXACTAMENTE con este formato y nada más:
===TITULO===
(título de 50 a 60 caracteres que empiece por la palabra clave principal)
===META===
(meta descripción de 100 a 130 caracteres)
===CATEGORIA===
(una sola de estas: {" | ".join(categorias)})
===HTML===
(el artículo en HTML)
===FIN==="""
    respuesta = chat(
        [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        max_tokens=16000,
        temperatura=0.6,
    )
    datos = secciones(respuesta, ["TITULO", "META", "CATEGORIA", "HTML"])
    titulo = datos["TITULO"].strip().strip('"').splitlines()[0]
    categoria = datos["CATEGORIA"].strip().splitlines()[0]
    if categoria not in categorias:
        coincidencias = [c for c in categorias if c.lower() in categoria.lower() or categoria.lower() in c.lower()]
        categoria = coincidencias[0] if coincidencias else categorias[0]
    return {
        "titulo": titulo,
        "slug": crear_slug(tema),
        "meta": datos["META"].strip().strip('"').splitlines()[0],
        "categoria": categoria,
        "html": limpiar_html(datos["HTML"]),
    }
