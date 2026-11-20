"""Lectura y escritura de la hoja de control de Google Sheets."""
import datetime
import json
import os

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("SHEET_ID") or "1pInEETR2fGlAM8oO9G-sYVpBQPQwjeZpMYlnoGBIXdU"

# Columnas de la pestaña "Posts"
COL = {
    "ID": "A", "SITIO": "B", "TEMA": "C", "ESTADO": "D", "INVESTIGACION": "E",
    "FUENTES": "F", "TITULO": "G", "SLUG": "H", "META": "I", "CATEGORIA": "J",
    "HTML": "K", "PROMPTS": "L", "ALTS": "M", "ARCHIVOS": "N", "REVISION": "O",
    "FECHA": "P", "URL": "Q",
}
NOMBRES = list(COL)
LIMITE_CELDA = 49000  # Google Sheets admite 50.000 caracteres por celda


class Hoja:
    def __init__(self):
        info = json.loads(os.environ["GOOGLE_SA_JSON"])
        creds = Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        self.libro = gspread.authorize(creds).open_by_key(SHEET_ID)
        self.posts = self.libro.worksheet("Posts")
        self.hoja_log = self.libro.worksheet("Log")

    # ---------- Posts ----------
    def leer_posts(self):
        """Devuelve [(numero_de_fila, {columna: valor})] de la pestaña Posts."""
        valores = self.posts.get_all_values()
        filas = []
        for i, fila in enumerate(valores[1:], start=2):
            fila = fila + [""] * (len(NOMBRES) - len(fila))
            if not fila[0].strip():
                continue
            filas.append((i, dict(zip(NOMBRES, fila))))
        return filas

    def actualizar(self, n_fila, **cambios):
        datos = []
        for nombre, valor in cambios.items():
            valor = "" if valor is None else str(valor)
            if len(valor) > LIMITE_CELDA:
                valor = valor[:LIMITE_CELDA]
            datos.append({"range": f"{COL[nombre]}{n_fila}", "values": [[valor]]})
        if datos:
            self.posts.batch_update(datos, value_input_option="RAW")

    # ---------- Sitios ----------
    def sitios(self):
        valores = self.libro.worksheet("Sitios").get_all_values()
        cab = [c.strip() for c in valores[0]]
        res = {}
        for fila in valores[1:]:
            if fila and fila[0].strip():
                d = dict(zip(cab, fila + [""] * (len(cab) - len(fila))))
                res[fila[0].strip()] = {
                    "id": fila[0].strip(),
                    "nombre": d.get("Nicho", ""),
                    "dominio": d.get("Dominio", ""),
                    "wp_url": d.get("URL de WordPress", ""),
                    "categorias": [c.strip() for c in d.get("Categorías (5)", "").replace("Propuesta:", "").split("|") if c.strip()],
                    "descripcion": d.get("Descripción de la temática", ""),
                    "notas": d.get("Notas", ""),
                }
        return res

    # ---------- Lineamientos ----------
    def lineamientos(self):
        valores = self.libro.worksheet("Lineamientos").get_all_values()
        return "\n".join(f"- {f[0]}: {f[1]}" for f in valores[1:] if len(f) > 1 and f[0].strip())

    # ---------- Log ----------
    def log(self, agente, id_post, mensaje):
        ahora = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        print(f"[{agente}] {id_post}: {mensaje}")
        try:
            self.hoja_log.append_row([ahora, agente, id_post, str(mensaje)[:2000]], value_input_option="RAW")
        except Exception as e:  # noqa: BLE001
            print("No se pudo escribir en Log:", e)
