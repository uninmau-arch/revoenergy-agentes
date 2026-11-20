"""Agente investigador: revisa los mejores resultados de Google y detecta qué mejorar."""
import os
import re

import requests
from bs4 import BeautifulSoup

from .llm import chat

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def buscar_en_google(consulta, pais="es", idioma="es"):
    r = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"},
        json={"q": consulta, "gl": pais, "hl": idioma, "num": 10},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def texto_de_pagina(url, maximo=7000):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": UA})
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type", ""):
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            t.decompose()
        cuerpo = soup.find("article") or soup.find("main") or soup.body
        if not cuerpo:
            return ""
        texto = cuerpo.get_text("\n", strip=True)
        return re.sub(r"\n{2,}", "\n", texto)[:maximo]
    except Exception:  # noqa: BLE001
        return ""


def investigar(tema, sitio):
    datos = buscar_en_google(tema)
    organicos = datos.get("organic", [])[:8]
    preguntas = [q.get("question", "") for q in datos.get("peopleAlsoAsk", [])]
    relacionadas = [q.get("query", "") for q in datos.get("relatedSearches", [])]

    paginas = []
    for o in organicos[:6]:
        texto = texto_de_pagina(o.get("link", ""))
        if len(texto) > 600:
            paginas.append(f"### Posición {o.get('position')}: {o.get('title')}\nURL: {o.get('link')}\n{texto}")
        if len(paginas) == 5:
            break

    listado = "\n".join(f"{o.get('position')}. {o.get('title')} — {o.get('link')}\n   {o.get('snippet', '')}" for o in organicos)
    prompt = f"""Analiza los mejores resultados de Google (España) para la búsqueda: "{tema}".
El objetivo es escribir después un artículo ORIGINAL y MEJOR que todos ellos para el sitio "{sitio['nombre']}".
Temática del sitio: {sitio['descripcion']}

Resultados de Google:
{listado}

Otras preguntas que hace la gente: {"; ".join(p for p in preguntas if p) or "(ninguna)"}
Búsquedas relacionadas: {"; ".join(r for r in relacionadas if r) or "(ninguna)"}

Contenido de las páginas mejor posicionadas:
{chr(10).join(paginas) or "(no se pudo descargar ninguna)"}

Responde en español, sin introducciones, exactamente con estas secciones:
INTENCIÓN DE BÚSQUEDA: qué quiere resolver la persona (1-2 frases).
RESPUESTA DIRECTA: la respuesta concreta que debe aparecer en los dos primeros párrafos.
LO QUE CUBREN LOS MEJORES: lista breve.
HUECOS Y MEJORAS: lista de lo que falta, está desactualizado o mal explicado.
PREGUNTAS A RESPONDER: lista (de "otras preguntas" y búsquedas relacionadas).
DATOS CLAVE CON FUENTE: cifras y hechos verificables, cada uno con la URL de donde sale. No inventes ningún dato.
ESTRUCTURA PROPUESTA: lista de subtítulos H2 (y H3 si hace falta).
LONGITUD RECOMENDADA: número aproximado de palabras, parecido a los mejores resultados.
No copies frases de las páginas: resume con tus palabras."""
    analisis = chat(
        [
            {"role": "system", "content": "Eres un analista SEO meticuloso. Respondes solo con lo que se pide."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
        temperatura=0.3,
    )
    fuentes = "\n".join(o.get("link", "") for o in organicos[:6])
    return analisis, fuentes
