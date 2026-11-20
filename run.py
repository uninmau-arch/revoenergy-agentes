"""Un ciclo de trabajo de los agentes RevoEnergy.

Flujo de estados en la pestaña Posts:
  pendiente → (investigador) → redactando → (redactor) → imagenes → (ilustrador) → en_revision
  en_revision → (supervisor: Claude) → aprobado | rechazado
  rechazado → (redactor + ilustrador otra vez, usando la nota de revisión) → en_revision
  aprobado → (publicador, solo si PUBLICAR=si) → publicado
  en_espera → no se toca (temas guardados para lotes futuros)
"""
import os
import time
import traceback

from agentes import vista_previa
from agentes.hoja import Hoja
from agentes.ilustrador import ilustrar
from agentes.investigador import investigar
from agentes.publicador import publicar
from agentes.redactor import redactar

MAX_POR_CICLO = int(os.environ.get("MAX_POR_CICLO") or 2)
PUBLICAR = (os.environ.get("PUBLICAR") or "no").strip().lower() == "si"
LIMITE_SEGUNDOS = 50 * 60


def procesar(hoja, n, post, sitio, lineamientos):
    pid = post["ID"]
    if post["ESTADO"] == "pendiente":
        hoja.actualizar(n, ESTADO="investigando")
        analisis, fuentes = investigar(post["TEMA"], sitio)
        hoja.actualizar(n, INVESTIGACION=analisis, FUENTES=fuentes, ESTADO="redactando")
        post.update(INVESTIGACION=analisis, FUENTES=fuentes, ESTADO="redactando")
        hoja.log("investigador", pid, "Investigación lista")

    if post["ESTADO"] in ("redactando", "rechazado"):
        nota = post["REVISION"] if post["ESTADO"] == "rechazado" else ""
        art = redactar(post["TEMA"], post["INVESTIGACION"], post["FUENTES"], sitio, lineamientos, nota)
        hoja.actualizar(n, TITULO=art["titulo"], SLUG=art["slug"], META=art["meta"],
                        CATEGORIA=art["categoria"], HTML=art["html"], ESTADO="imagenes")
        post.update(TITULO=art["titulo"], SLUG=art["slug"], META=art["meta"],
                    CATEGORIA=art["categoria"], HTML=art["html"], ESTADO="imagenes")
        hoja.log("redactor", pid, f"Artículo escrito ({len(art['html'])} caracteres)" + (" tras revisión" if nota else ""))

    if post["ESTADO"] == "imagenes":
        datos = {"html": post["HTML"], "titulo": post["TITULO"], "slug": post["SLUG"]}
        html, escenas, alts, archivos = ilustrar(datos, sitio)
        hoja.actualizar(n, HTML=html, PROMPTS=escenas, ALTS=alts, ARCHIVOS=archivos, ESTADO="en_revision")
        post.update(HTML=html, PROMPTS=escenas, ALTS=alts, ARCHIVOS=archivos, ESTADO="en_revision")
        hoja.log("ilustrador", pid, f"Imágenes creadas: {archivos}")


def revisar_claves():
    faltan = [k for k in ("GOOGLE_SA_JSON", "OPENROUTER_API_KEY", "SERPER_API_KEY") if not (os.environ.get(k) or "").strip()]
    if PUBLICAR:
        faltan += [k for k in ("WP_USER", "WP_APP_PASSWORD") if not (os.environ.get(k) or "").strip()]
    if faltan:
        raise SystemExit(
            "FALTAN CLAVES en GitHub (Settings → Secrets and variables → Actions → New repository secret): "
            + ", ".join(faltan)
        )


def main():
    revisar_claves()
    inicio = time.time()
    hoja = Hoja()
    sitios = hoja.sitios()
    lineamientos = hoja.lineamientos()
    filas = hoja.leer_posts()

    trabajados = 0
    for n, post in filas:
        if post["ESTADO"] not in ("pendiente", "redactando", "rechazado", "imagenes", "investigando"):
            continue
        if post["ESTADO"] == "investigando":  # se quedó a medias en un ciclo anterior
            post["ESTADO"] = "pendiente"
        if trabajados >= MAX_POR_CICLO or time.time() - inicio > LIMITE_SEGUNDOS:
            break
        sitio = sitios.get(post["SITIO"])
        if not sitio:
            hoja.log("sistema", post["ID"], f"Sitio {post['SITIO']} no existe en la pestaña Sitios")
            continue
        try:
            procesar(hoja, n, post, sitio, lineamientos)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            hoja.log("error", post["ID"], f"{type(e).__name__}: {e}")
        trabajados += 1

    filas = hoja.leer_posts()
    listos = [p for _, p in filas if p["ESTADO"] in ("en_revision", "aprobado")]
    vista_previa.generar(listos)

    if PUBLICAR:
        for n, post in filas:
            if post["ESTADO"] != "aprobado":
                continue
            sitio = sitios.get(post["SITIO"], {})
            if not sitio.get("wp_url", "").startswith("http"):
                hoja.log("publicador", post["ID"], "Falta la URL de WordPress en la pestaña Sitios")
                break
            try:
                url, fecha = publicar(post, sitio["wp_url"].split(" ")[0])
                hoja.actualizar(n, URL=url, FECHA=fecha, ESTADO="publicado")
                hoja.log("publicador", post["ID"], f"Publicado: {url}")
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                hoja.log("error", post["ID"], f"Publicación: {e}")


if __name__ == "__main__":
    main()
