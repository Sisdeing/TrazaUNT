from datetime import date, timedelta
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import crear_app
from db.database import crear_motor
from services.predicciones import entrenar, variables
from services.seguridad import guardar_cuenta

H = {"X-Traza-Client": "react"}


class IntegracionPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with patch.dict("os.environ", {"FUNCIONES_EXPERIMENTALES": "1"}):
            cls.app = crear_app(Path(cls.tmp.name) / "panel.sqlite3", acceso_local="A" * 40)
        cls.context = TestClient(cls.app)
        cls.c = cls.context.__enter__()
        cls.c.post(
            "/api/sesion/local", headers=H, json={"codigo": "A" * 40}
        ).raise_for_status()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)
        cls.tmp.cleanup()

    def test_panel_filtros_y_sumas(self):
        completo = self.c.get("/api/dashboard").json()
        self.assertEqual(completo["contrataciones"], 600)
        self.assertAlmostEqual(
            sum(float(x["monto"]) for x in completo["serie"]),
            completo["monto"],
            places=2,
        )
        partes = [
            self.c.get("/api/dashboard", params={"periodo": p}).json()
            for p in completo["opciones"]["periodos"]
        ]
        self.assertAlmostEqual(
            sum(p["monto"] for p in partes), completo["monto"], places=2
        )
        alto = self.c.get("/api/dashboard?severidad=alta").json()
        self.assertEqual(alto["alertas"], alto["severidades"]["alta"])
        self.assertTrue(completo["escenario"]["id"])

    def test_busqueda_y_bandeja(self):
        items = self.c.get("/api/buscar?q=CAF-DEMO").json()["items"]
        self.assertEqual(items[0]["tipo"], "Convocatoria")
        avisos = self.c.get("/api/notificaciones").json()["items"]
        self.assertEqual(len(avisos), len({x["clave"] for x in avisos}))
        d = next(x for x in avisos if x["codigo"] == "D03")
        self.c.post(
            "/api/notificaciones/" + d["clave"] + "/leer", headers=H
        ).raise_for_status()
        self.assertTrue(
            next(
                x
                for x in self.c.get("/api/notificaciones").json()["items"]
                if x["clave"] == d["clave"]
            )["leida"]
        )
        self.assertTrue(
            self.c.get("/api/asistente?tema=Prevenci%C3%B3n").json()["items"]
        )

    def test_identidad_y_auditor_agregado(self):
        with closing(TestClient(self.app)) as nop:
            self.assertEqual(nop.get("/api/dashboard").status_code, 401)
            guardar_cuenta(
                self.app.state.motor,
                "auditor.prueba",
                "Auditor de pruebas",
                "auditor",
                "clave-de-prueba-segura",
            )
            r = nop.post(
                "/api/sesion/entrar",
                headers=H,
                json={"usuario": "auditor.prueba", "clave": "clave-de-prueba-segura"},
            )
            self.assertIn("httponly", r.headers["set-cookie"].lower())
            d = nop.get("/api/dashboard").json()
            self.assertFalse(d["prioritarias"])
            self.assertFalse(d["concentracion"]["ranking"])
            self.assertIsNone(d["escenario"])
            for ruta in (
                "documentos/1",
                "buscar?q=demo",
                "auditoria",
                "expedientes/1",
                "predicciones",
            ):
                self.assertEqual(nop.get("/api/" + ruta).status_code, 403)
            self.assertEqual(nop.post("/api/analisis", headers=H).status_code, 403)
            nop.post("/api/sesion/salir", headers=H).raise_for_status()
            self.assertEqual(nop.get("/api/dashboard").status_code, 401)

    def test_mora_y_baseline(self):
        r = self.c.get("/api/predicciones").json()
        self.assertEqual(len(r["items"]), 3)
        self.assertTrue(
            any(c["nivel"] == "Predicción no disponible" for c in r["items"])
        )
        self.assertTrue(any(c["horizonte"] is not None for c in r["items"]))
        modelo = entrenar()[1]
        self.assertEqual(
            sum(sum(f) for f in modelo["resultados"]["Baseline"]["prueba"]["matriz"]),
            modelo["muestras"][2],
        )

    def test_variables_sin_informacion_posterior(self):
        corte = date(2026, 11, 23)
        fechas = [date(2026, m, 15) for m in [8, 9, 10]]
        self.assertEqual(
            variables([(d, None) for d in fechas], corte),
            variables([(d, corte + timedelta(days=5)) for d in fechas], corte),
        )
        self.assertIsNone(variables([(fechas[0], None)], corte))

    def test_rechaza_destinos_ajenos(self):
        original = Path(self.tmp.name) / "ajeno.sqlite3"
        with closing(sqlite3.connect(original)) as con, con:
            con.execute("CREATE TABLE registros(id INTEGER)")
        antes = original.read_bytes()
        with self.assertRaises(ValueError):
            crear_motor(original)
        self.assertEqual(original.read_bytes(), antes)

class EntornosProducto(unittest.TestCase):
    def test_publico_y_produccion_sin_acceso_automatico(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {
                "TRAZA_ENTORNO": "produccion",
                "FUNCIONES_EXPERIMENTALES": "0",
            }):
                app = crear_app(Path(tmp) / "producto.sqlite3", acceso_local="A" * 40)
            with TestClient(app) as cliente:
                r = cliente.get("/api/publico/contrataciones")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["origen"], "sintetico")
                self.assertEqual(sum(x["contrataciones"] for x in r.json()["periodos"]), 600)
                self.assertEqual(cliente.get("/api/dashboard").status_code, 401)
                self.assertGreaterEqual(cliente.post(
                    "/api/sesion/local", headers=H, json={"codigo": "A" * 40}
                ).status_code, 400)
                self.assertFalse(any(
                    getattr(ruta, "path", "") == "/api/predicciones" for ruta in app.routes
                ))
