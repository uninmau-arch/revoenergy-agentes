# Agentes RevoEnergy · Método Vuela automatizado

Máquina de contenidos que lee órdenes de la **hoja de control de Google Sheets**, investiga los mejores resultados de Google, escribe un post mejorado con **Muse Spark** (OpenRouter), dibuja las ilustraciones con código (SVG → WebP) y, cuando un post está aprobado, lo publica en **WordPress**.

## Flujo

```
pendiente → investigador → redactor → ilustrador → en_revision
en_revision → supervisor (Claude) → aprobado | rechazado (con nota)
rechazado → redactor + ilustrador otra vez → en_revision
aprobado → publicador (solo al ejecutar con publicar = si) → publicado
en_espera → temas guardados para lotes futuros
```

Corre solo cada hora en GitHub Actions, o a mano desde **Actions → Agentes RevoEnergy → Run workflow**.
Las imágenes y la vista previa (`salida/vista_previa/index.html`) se guardan en este repositorio.

## Configuración (una sola vez)

En el repositorio: **Settings → Secrets and variables → Actions**.

**Secrets** (pestaña *Secrets* → *New repository secret*):

| Nombre | Valor |
|---|---|
| `OPENROUTER_API_KEY` | Clave de OpenRouter (`sk-or-...`) |
| `SERPER_API_KEY` | Clave de Serper |
| `GOOGLE_SA_JSON` | Contenido completo del archivo `.json` de la cuenta de servicio |
| `WP_USER` | Usuario de WordPress (cuando exista el sitio) |
| `WP_APP_PASSWORD` | Contraseña de aplicación de WordPress (cuando exista el sitio) |

**Variables** (pestaña *Variables*, opcionales):

| Nombre | Valor por defecto |
|---|---|
| `MODELO` | `meta/muse-spark-1.3` |
| `SHEET_ID` | ID de la hoja de control |

La hoja debe estar compartida como **Editor** con el correo de la cuenta de servicio.

## Lanzar un lote nuevo

1. En la pestaña **Posts**, cambia de `en_espera` a `pendiente` los temas del lote.
2. Ejecuta el workflow (o espera al ciclo de cada hora). `max_por_ciclo` controla cuántos posts trabaja por ejecución.
3. Cuando todos estén aprobados, ejecuta el workflow con **publicar = si**: se suben todos juntos con fechas pasadas aleatorias.
