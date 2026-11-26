"""Perfiles (Universidad, Empresa, Público), coincidencias automáticas, admisión, CID y reglas TZ06/TZ09."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import crear_app
from services.coincidencias import calcular, dni_de_ruc, distintivos, normalizar
from services.seguridad import guardar_cuenta

H = {"X-Traza-Client": "react"}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    aplicacion = crear_app(tmp_path_factory.mktemp("perfiles") / "test.sqlite")
    with TestClient(aplicacion):
        yield aplicacion


def sesion(app, perfil):
    c = TestClient(app)
    c.post("/api/sesion/demo", headers=H, json={"perfil": perfil}).raise_for_status()
    return c


def test_normalizacion_y_dni():
    assert normalizar("Diego  SALAZAR Ríos (demo)") == "diego salazar rios"
    assert distintivos("Representante Nova (demo)") == {"nova"}
    assert dni_de_ruc("10456789012") == "45678901" and dni_de_ruc("20456789012") is None


def test_coincidencias_automaticas_del_escenario(app):
    u = sesion(app, "universidad")
    datos = u.get("/api/coincidencias?estado=todas").json()
    tipos = {x["tipo"]: x for x in datos["items"]}
    assert set(tipos) == {"CI02", "CI03", "CI04", "CI06"}
    assert tipos["CI06"]["nivel"] == "alta" and tipos["CI03"]["nivel"] == "baja"
    assert all("No constituye un conflicto" in x["aviso"] for x in datos["items"])
    ficha = u.get("/api/convocatorias/1").json()
    assert len(ficha["coincidencias"]) == 4


def test_revision_exige_justificacion_y_conserva_historial(app):
    u = sesion(app, "universidad")
    x = u.get("/api/coincidencias").json()["items"][0]
    url = f"/api/coincidencias/{x['id']}/revision"
    assert u.post(url, headers=H, json={"decision": "aclarada", "justificacion": "."}).status_code == 422
    r = u.post(url, headers=H, json={"decision": "aclarada", "justificacion": "Homónimo verificado con el DNI del registro."})
    assert r.status_code == 200 and r.json()["estado"] == "aclarada"
    assert u.post(url, headers=H, json={"decision": "aclarada", "justificacion": "Homónimo verificado con el DNI del registro."}).status_code == 409
    r = u.post(url, headers=H, json={"decision": "derivada", "justificacion": "Nueva evidencia: se deriva a integridad."})
    assert [v["decision"] for v in r.json()["revisiones"]] == ["aclarada", "derivada"]
    historial = u.get("/api/convocatorias/1").json()["historial"]
    assert any(h["accion"] == "revision_coincidencia" for h in historial)


def test_registro_de_postulante_detecta_dni_de_persona_natural(app):
    from db.database import obtener_sesion
    from db.models import Proveedor
    from db.convocatorias import Convocatoria, Postulacion
    with obtener_sesion(app.state.motor) as s:
        v = Proveedor(ruc="10456789012", razon_social="Ana Torres Vega (demo)", fecha_constitucion=date(2020, 1, 1),
                      domicilio="Calle Única 1 (demo)", representante="Ana Torres Vega (demo)")
        c = s.get(Convocatoria, 1)
        s.add(v)
        s.flush()
        s.add(Postulacion(convocatoria_id=c.id, proveedor_id=v.id, oferta=1000, experiencia=1, version_bases=c.version_bases))
        c.intervinientes = [*c.intervinientes, dict(nombre="Ana T. Vega (demo)", rol="Comité", documento="45678901")]
        s.flush()
        tipos = {h["tipo"] for h in calcular(s, c).values()}
        s.rollback()
    assert "CI01" in tipos


def test_perfil_empresa_aislado(app):
    e = sesion(app, "empresa-horizonte")
    resumen = e.get("/api/empresa/resumen").json()
    assert resumen["empresa"]["ruc"] == "00900000002" and len(resumen["postulaciones"]) == 1
    for ruta in ("/api/convocatorias/1", "/api/coincidencias", "/api/trazabilidad", "/api/dashboard", "/api/proveedores"):
        assert e.get(ruta).status_code == 403, ruta
    ficha = e.get("/api/empresa/convocatorias/1").json()
    texto = str(ficha)
    assert "Servicios Campus Aurora" not in texto and "Evaluadora Lumen" not in texto and "campos" not in ficha
    assert {d["estado"] for d in ficha["documentos_propios"]} <= {"recibido", "en_revision", "revisado", "atencion"}


def test_admision_visible_para_la_empresa_y_bloquea_resultado(app):
    u = sesion(app, "universidad")
    ficha = u.get("/api/convocatorias/1").json()
    horizonte = next(p for p in ficha["postulantes"] if p["ruc"] == "00900000002")
    url = f"/api/convocatorias/1/postulantes/{horizonte['id']}/admision"
    assert u.post(url, headers=H, json={"estado": "no_admitida", "motivo": "No acredita la garantía exigida."}).status_code == 200
    e = sesion(app, "empresa-horizonte")
    vista = e.get("/api/empresa/convocatorias/1").json()
    assert vista["admision"] == "no_admitida" and vista["admisiones"][-1]["motivo"].startswith("No acredita")
    assert e.post(url, headers=H, json={"estado": "admitida", "motivo": "Intento de la empresa"}).status_code == 403


def test_empresa_postula_y_dispara_comparacion(app):
    from db.database import obtener_sesion
    from db.convocatorias import Convocatoria
    u = sesion(app, "universidad")
    with obtener_sesion(app.state.motor) as s:
        c = Convocatoria(codigo="PRUEBA-EMP", nombre="Servicio de prueba", modalidad="Servicio", area="Logística",
                         objeto="Servicio", presupuesto=1000, duracion_meses=1, apertura=date(2026, 11, 1),
                         cierre=date(2026, 12, 1), responsable="Martín Quispe Arana (demo)", requisitos=["RUC"],
                         criterios=[dict(nombre="Precio", peso=100)], intervinientes=[], estado="abierta")
        s.add(c)
        s.flush()
        cid = c.id
    e = sesion(app, "empresa-nova")
    assert any(x["id"] == cid for x in e.get("/api/empresa/resumen").json()["disponibles"])
    r = e.post(f"/api/empresa/convocatorias/{cid}/postulacion", headers=H, json={"oferta": "950.00", "experiencia": 2})
    assert r.status_code == 201 and r.json()["postulado"]
    assert e.post(f"/api/empresa/convocatorias/{cid}/postulacion", headers=H, json={"oferta": "950.00", "experiencia": 2}).status_code == 409
    archivo = {"archivo": ("propuesta.txt", "Propuesta de servicio de prueba".encode(), "text/plain")}
    r = e.post(f"/api/empresa/convocatorias/{cid}/documentos", headers=H, files=archivo, data={"tipo": "propuesta"})
    assert r.status_code == 201 and r.json()["documentos_propios"][0]["estado"] == "recibido"
    # El responsable del proceso tiene el mismo nombre que el representante de Nova.
    coincidencias = u.get(f"/api/convocatorias/{cid}").json()["coincidencias"]
    assert any(x["tipo"] == "CI02" for x in coincidencias)


def test_acceso_demo_solo_local_y_en_demo(app):
    c = TestClient(app, client=("203.0.113.5", 5000))
    assert c.post("/api/sesion/demo", headers=H, json={"perfil": "universidad"}).status_code == 403
    assert TestClient(app).post("/api/sesion/demo", headers=H, json={"perfil": "root"}).status_code == 422


def test_portal_publico_sin_datos_personales(app):
    p = TestClient(app)
    conv = p.get("/api/publico/convocatorias").json()["items"]
    assert conv and "intervinientes" not in conv[0]
    lista = p.get("/api/publico/expedientes").json()
    assert lista["total"] >= 1
    detalle = p.get(f"/api/publico/expedientes/{lista['items'][0]['id']}").json()
    texto = str(detalle)
    assert "responsable" not in detalle and "(demo)" not in texto.replace("(demostración)", "")
    assert p.get("/api/trazabilidad").status_code == 401 and p.get("/api/coincidencias").status_code == 401


def test_tz06_y_tz09_en_un_ciclo_de_una_sola_cuenta(app):
    u = sesion(app, "universidad")
    r = u.post("/api/trazabilidad", headers=H, json=dict(nombre="Ciclo", objeto="Compra", tipo="servicios", area="Logística",
                                                          responsable="Área usuaria", inicio=date.today().isoformat(), monto="30000.00"))
    eid = r.json()["id"]
    path = f"/api/trazabilidad/{eid}"

    def fases():
        return u.get(path).json()["fases"]

    def accion(fid, nombre, **extra):
        f = next(x for x in fases() if x["id"] == fid)
        res = u.post(f"{path}/fases/{fid}/accion", headers=H,
                     json=dict(accion=nombre, revision=f["revision"], justificacion="Evidencia revisada", **extra))
        assert res.status_code == 200, res.text
        return res.json()

    for f in fases():
        accion(f["id"], "iniciar")
        for q in f["requisitos"]:
            u.post(f"{path}/fases/{f['id']}/documentos", headers=H, data={"requisito_id": q["id"], "autor": "Jefatura"},
                   files={"archivo": ("evidencia.txt", f"Evidencia {q['id']}".encode(), "text/plain")}).raise_for_status()
            doc = [d for d in next(x for x in fases() if x["id"] == f["id"])["documentos"] if d["requisito_id"] == q["id"]][-1]
            accion(f["id"], "verificar", requisito_id=q["id"], documento_id=doc["id"])
        accion(f["id"], "visto_bueno")
        if f["orden"] == 7:
            accion(f["id"], "pago", monto_autorizado="90000.00", monto_pagado="90000.00")
        d = accion(f["id"], "cerrar", responsable="Otra persona")
    reglas = [a["regla"] for a in d["alertas"] if a["vigente"]]
    assert reglas.count("TZ06") == 3 and "TZ09" in reglas
    # El responsable registrado es la cuenta autenticada, no el texto enviado por el cliente.
    assert not any(v["responsable"] == "Otra persona" for v in d["eventos"])
    alerta = next(a for a in d["alertas"] if a["regla"] == "TZ06")
    assert u.post(f"{path}/alertas/{alerta['id']}/revision", headers=H,
                  json=dict(accion="descartada", revision=0, justificacion=".")).status_code == 422


def test_cid_se_integra_con_procedencia(app):
    from services.cid import cargar, integrar_cid
    from services.datos_publicos import importar
    datos = cargar()
    assert datos["asientos_unt"], "Falta data/publicos/cid_universidades.json.gz"
    codigo = next(iter(datos["asientos_unt"]))
    importar(app.state.motor, [dict(id_fuente="ocds-prueba-cid", nombre="OBRA-PRUEBA", objeto="Obra de prueba", tipo="obras",
                                      inicio="2022-05-01", monto="100.00", fuentes=[], hitos=[],
                                      contratos_publicados=[dict(id=codigo)])])
    assert integrar_cid(app.state.motor) == len(datos["asientos_unt"][codigo])
    assert integrar_cid(app.state.motor) == 0  # idempotente
    u = sesion(app, "universidad")
    item = next(x for x in u.get("/api/trazabilidad").json()["items"] if x["datos"].get("registro_publico", {}).get("id_fuente") == "ocds-prueba-cid")
    d = u.get(f"/api/trazabilidad/{item['id']}").json()
    asiento = next(v for v in d["eventos"] if v["accion"] == "asiento_cid")
    assert asiento["datos"]["archivo"].startswith("CID") and asiento["datos"]["fila"] > 1
    assert next(f for f in d["fases"] if f["id"] == asiento["fase_id"])["nombre"].startswith("Ejecución")
    publico = TestClient(app).get(f"/api/publico/expedientes/{item['id']}").json()
    assert publico["cuaderno_obra"]["contrato"] == codigo
    assert all("descripcion" not in str(x) for x in publico["cronologia"])
    catalogo = u.get("/api/fuentes/catalogo").json()
    assert any(c["nombre"].startswith("Cuaderno de Obra") for c in catalogo["conjuntos"])


def test_cuenta_empresa_con_ruc(app):
    guardar_cuenta(app.state.motor, "nova.local", "Gestión Nova", "empresa", "clave-segura-empresa", ruc="00900000003")
    c = TestClient(app)
    r = c.post("/api/sesion/entrar", headers=H, json={"usuario": "nova.local", "clave": "clave-segura-empresa"})
    assert r.status_code == 200 and r.json()["usuario"]["proveedor_id"]
    with pytest.raises(ValueError):
        guardar_cuenta(app.state.motor, "sin.ruc", "Empresa", "empresa", "clave-segura-empresa")
