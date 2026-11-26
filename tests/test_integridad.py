import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from db.convocatorias import Convocatoria
from db.database import crear_motor, crear_tablas, obtener_sesion
from db.integridad import (
    Declaracion,
    EvidenciaIFP,
    Interviniente,
    Perfil,
    Vinculo,
    Concesion,
    Cuota,
    Abono,
)
from db.models import Proveedor
from services.concesiones import ficha_concesion, simular
from services.integridad import (
    AURORA,
    HORIZONTE,
    NOVA,
    CAFETERIA,
    CORTE,
    casos,
    evaluar_vinculo,
    iniciar_integridad,
    resultado_ifp,
)
from services.integridad_api import router
from services.padron import consultar_publico, importar, ruc_valido


class IntegridadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.motor = crear_motor(Path(self.tmp.name) / "test.sqlite3")
        crear_tablas(self.motor)
        with obtener_sesion(self.motor) as s:
            for r, n in [
                (AURORA, "Servicios Campus Aurora"),
                (HORIZONTE, "Operaciones Horizonte"),
                (NOVA, "Gestión Nova Campus"),
            ]:
                s.add(
                    Proveedor(
                        ruc=r,
                        razon_social=n + " (demo)",
                        fecha_constitucion=date(2018, 1, 1),
                        domicilio="(demo)",
                        representante="(demo)",
                    )
                )
        iniciar_integridad(self.motor)
        app = FastAPI()
        app.state.motor = self.motor

        @app.middleware("http")
        async def identidad(request: Request, siguiente):
            request.state.usuario = {
                "rol": request.headers.get("rol", "analista"),
                "usuario": "Unidad de pruebas",
            }
            return await siguiente(request)

        app.include_router(router)
        self.cliente = TestClient(app)

    def tearDown(self):
        self.cliente.close()
        self.motor.dispose()
        self.tmp.cleanup()

    def test_cobertura_renormalizada(self):
        with obtener_sesion(self.motor) as s:
            p = s.scalar(select(Proveedor).where(Proveedor.ruc == AURORA))
            sin_monto = resultado_ifp(s, p)
            con_monto = resultado_ifp(s, p, 1000)
            self.assertEqual((sin_monto["ifp"], sin_monto["cobertura"]), (100, 85))
            self.assertEqual(con_monto["cobertura"], 100)
            self.assertEqual(resultado_ifp(s, p, corte=date(2027, 2, 1))["ifp"], None)
            self.assertEqual(
                resultado_ifp(s, p, corte=date(2026, 10, 30))["cobertura"], 0
            )

    def test_naturales_y_semilla_idempotente(self):
        iniciar_integridad(self.motor)
        with obtener_sesion(self.motor) as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(Perfil)), 12)
            p = s.scalar(select(Proveedor).join(Perfil).where(Perfil.tipo == "natural"))
            r = resultado_ifp(s, p)
            self.assertIsNone(r["ifp"])
            self.assertLess(r["cobertura"], 50)
            self.assertNotEqual(r["confianza"], "Alta")
            self.assertNotIn("solvencia", [d["clave"] for d in r["dimensiones"]])

    def test_senales_declaracion_y_limites(self):
        with obtener_sesion(self.motor) as s:
            self.assertEqual(casos(s, CAFETERIA, AURORA), [])
            caso = casos(s, CAFETERIA, NOVA)[0]
            self.assertEqual(
                {x["regla"] for x in caso["senales"]}, {"R08", "R09", "R11"}
            )
            v = s.get(Vinculo, caso["id"])
            i = s.get(Interviniente, v.interviniente_id)
            i.registro_completo = False
            self.assertEqual(len(evaluar_vinculo(i, v, [])), 2)
            i.registro_completo = True
            self.assertEqual(
                len(
                    evaluar_vinculo(i, v, [Declaracion(accion="abstención registrada")])
                ),
                2,
            )
            v.grado = 3
            self.assertFalse(evaluar_vinculo(i, v, []))
            v.grado = 2
            v.verificado = False
            self.assertFalse(evaluar_vinculo(i, v, []))
            v.verificado = True
            v.desde = CORTE + timedelta(days=1)
            self.assertFalse(evaluar_vinculo(i, v, []))

    def test_historial_persistido_y_permisos(self):
        datos = dict(ruc=AURORA, monto=4000, categoria="concesiones")
        self.assertEqual(
            self.cliente.post(
                "/api/proveedores/verificar", json=datos, headers={"rol": "consulta"}
            ).status_code,
            403,
        )
        res = self.cliente.post("/api/proveedores/verificar", json=datos)
        self.assertEqual(res.status_code, 200, res.text)
        r = res.json()
        historial = self.cliente.get(f"/api/proveedores/{r['id']}/evaluaciones").json()[
            "items"
        ]
        self.assertEqual(historial[0]["resultado"]["modelo"], r["modelo"])
        self.assertEqual(historial[0]["resultado"]["ifp"], 100)
        self.assertEqual(
            self.cliente.get("/api/conflictos", headers={"rol": "auditor"}).status_code,
            403,
        )

    def test_manual_y_datos_reales_separados(self):
        proveedor = self.cliente.get("/api/proveedores", params={"q": AURORA}).json()[
            "items"
        ][0]
        datos = dict(
            dimension="sanciones",
            resultado=True,
            referencia="ACTA-SIM-123",
            corte=str(CORTE),
            vigente_hasta="2026-12-31",
        )
        url = f"/api/proveedores/{proveedor['id']}/verificaciones-manuales"
        self.assertEqual(self.cliente.post(url, json=datos).status_code, 201)
        self.assertEqual(self.cliente.post(url, json=datos).status_code, 409)
        r = self.cliente.get("/api/proveedores/" + str(proveedor["id"])).json()
        self.assertEqual(r["impedimentos"][0]["referencia"], datos["referencia"])
        for ruc in ["10000000006", "00000000001"]:
            self.assertEqual(
                self.cliente.post(
                    "/api/proveedores/verificar", json={"ruc": ruc, "modo": "publico"}
                ).status_code,
                422,
            )

    def test_concesion_y_abono_parcial(self):
        con = self.cliente.get("/api/concesiones").json()["items"]
        vig = next(x for x in con if x["codigo"] == "HIST-DEMO-02")
        url = "/api/concesiones/" + str(vig["id"])
        inicial = self.cliente.get(url).json()
        self.assertEqual(inicial["saldo_vencido"], 2400)
        self.assertEqual(
            {a["codigo"] for a in inicial["alertas"]}, {"C02", "C03", "C11"}
        )
        cuota = next(x for x in inicial["pagos"] if x["estado"] == "Vencida")
        abono = dict(
            cuota_id=cuota["id"], fecha=str(CORTE), referencia="REC-TRIAL", monto=600
        )
        self.assertEqual(self.cliente.post(url + "/pagos", json=abono).status_code, 201)
        self.assertEqual(self.cliente.post(url + "/pagos", json=abono).status_code, 409)
        self.assertEqual(self.cliente.get(url).json()["saldo_vencido"], 1800)
        with obtener_sesion(self.motor) as s:
            c = s.get(Concesion, vig["id"])
            previo = ficha_concesion(s, c, c.inicio - timedelta(days=1))
            self.assertIsNone(previo["cumplimiento"])
            self.assertEqual(previo["registrado"], 0)

    def test_escenario_no_muta_fuentes(self):
        con = self.cliente.get("/api/concesiones").json()["items"][0]
        url = "/api/concesiones/" + str(con["id"])
        inicial = self.cliente.get(url).json()
        sim = self.cliente.post(
            url + "/simular",
            json=dict(ingresos=7000, costos=5900, contraprestacion=800),
        )
        self.assertEqual(sim.status_code, 200, sim.text)
        self.assertEqual(sim.json()["escenarios"][1]["flujo"], 300)
        self.assertTrue(sim.json()["escenarios"][0]["revision"])
        self.assertEqual(self.cliente.get(url).json(), inicial)

    def test_fuente_offline_selectiva(self):
        ruc = next(
            "2000000000" + str(i)
            for i in range(10)
            if ruc_valido("2000000000" + str(i))
        )
        ruta = Path(self.tmp.name) / "padron.csv"
        destino = Path(self.tmp.name) / "padron.sqlite3"
        ruta.write_bytes(
            (
                "RUC|NOMBRE O RAZÓN SOCIAL|ESTADO DEL CONTRIBUYENTE|CONDICIÓN DE DOMICILIO|\n"
                + f"{ruc}|Empresa de fixture|ACTIVO|HABIDO|\n"
            ).encode("latin1")
        )
        self.assertEqual(importar(ruta, destino, {ruc}, CORTE), 1)
        r = consultar_publico(ruc, destino)
        self.assertEqual(r["registro"]["corte"], str(CORTE))
        self.assertIsNone(r["ifp"])
        self.assertNotIn("impedimentos", r)
        with self.assertRaises(ValueError):
            importar(ruta, destino, {NOVA}, CORTE)


if __name__ == "__main__":
    unittest.main()
