"""Conexión con el modelo de lenguaje (Muse Spark vía OpenRouter, compatible con OpenAI)."""
import os
import re
import time

import requests

URL = "https://openrouter.ai/api/v1/chat/completions"
MODELO = os.environ.get("MODELO") or "meta/muse-spark-1.3"


def chat(mensajes, max_tokens=8000, temperatura=0.5):
    """Envía una conversación al modelo y devuelve el texto de la respuesta."""
    ultimo_error = None
    for intento in range(4):
        try:
            r = requests.post(
                URL,
                headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "Content-Type": "application/json",
                    "X-Title": "RevoEnergy agentes",
                },
                json={
                    "model": MODELO,
                    "messages": mensajes,
                    "max_tokens": max_tokens,
                    "temperature": temperatura,
                },
                timeout=600,
            )
            r.raise_for_status()
            texto = r.json()["choices"][0]["message"]["content"]
            if texto and texto.strip():
                return texto.strip()
            ultimo_error = "respuesta vacía"
        except Exception as e:  # noqa: BLE001
            ultimo_error = e
        print(f"[llm] intento {intento + 1} falló: {ultimo_error}")
        time.sleep(5 * (intento + 1))
    raise RuntimeError(f"El modelo no respondió tras 4 intentos: {ultimo_error}")


def secciones(texto, nombres):
    """Extrae bloques con el formato ===NOMBRE=== ... del texto del modelo.

    Es más robusto que pedir JSON cuando el contenido lleva HTML o SVG.
    """
    resultado = {}
    patron = "|".join(re.escape(n) for n in nombres)
    partes = re.split(rf"^\s*===\s*({patron})\s*===\s*$", texto, flags=re.M)
    # partes = [antes, NOMBRE1, contenido1, NOMBRE2, contenido2, ...]
    for i in range(1, len(partes) - 1, 2):
        contenido = partes[i + 1]
        contenido = re.sub(r"^\s*===\s*FIN\s*===.*$", "", contenido, flags=re.M | re.S)
        resultado[partes[i]] = limpiar_bloque(contenido)
    faltan = [n for n in nombres if not resultado.get(n)]
    if faltan:
        raise ValueError(f"La respuesta del modelo no trae: {', '.join(faltan)}")
    return resultado


def limpiar_bloque(texto):
    texto = texto.strip()
    texto = re.sub(r"^```[a-zA-Z]*\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()
