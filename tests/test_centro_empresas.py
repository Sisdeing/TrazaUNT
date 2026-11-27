"""Centro de alertas (categorías, agrupación, estados y decisiones) y fichas históricas por empresa."""
import pytest
from fastapi.testclient import TestClient

from app import crear_app

H = {"X-Traza-Client": "react"}
J = "Se revisó la evidencia con el área usuaria y se dejó constancia."


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    aplicacion = crear_app(tmp_path_factory.mktemp("centro") / "test.sqlite")
    with TestClient(aplicacion):
        yield aplicacion


def sesion(app, perfil):
    c = TestClient(app)
    c.post("/api/sesion/demo", headers=H, json={"perfil": perfil}).raise_for_status()
    return c


def todas(c, **f):
    return c.get("/api/centro-alertas", params={"tamano": 100, "estado": "", **f}).json()


def test_categorias_y_agrupacion(app):
    u = sesion(app, "universidad")
    d = todas(u)
    cats = {k: v["total"] for k, v in d["resumen"]["por_categoria"].items()}
    assert set(cats) == {"fraccionamiento", "colusion", "conflicto", "concentracion", "control"}
    assert cats["colusion"] >= 1 and cats["conflicto"] >= 3 and cats["fraccionamiento"] >= 1
    # R02 marca 30 contratos del mismo proveedor: en el centro es un solo caso.
    conc = [x for x in d["items"] if x["categoria"] == "concentracion"]
    assert len(conc) == 1 and len(conc[0]["ids"]) == 30
    # Ninguna alerta se presenta como conclusión.
    det = u.get(f"/api/centro-alertas/{conc[0]['uid']}").json()
    assert "No constituye una prueba" in det["aviso"]
    assert det["indicadores"] and det["registros"] and det["explicacion"]["revisar"]
    assert not any("{" in h["texto"] for h in det["historial"])


def test_textos_sin_jerga(app):
    u = sesion(app, "universidad")
    frac = todas(u, categoria="fraccionamiento")["items"]
    r01 = next(x for x in frac if x["codigo"] == "R01")
    assert "tokens" not in r01["descripcion"] and "[ID" not in r01["descripcion"]


def test_tomar_y_decidir_en_cada_origen(app):
    u = sesion(app, "universidad")
    items = todas(u)["items"]
    por_origen = {}
    for x in items:
        if x["estado"] == "pendiente":
            por_origen.setdefault(x["origen"], x)
    assert set(por_origen) == {"regla", "coincidencia", "trazabilidad"}
    r = por_origen["regla"]["uid"]
    assert u.post(f"/api/centro-alertas/{r}/tomar", headers=H).json()["estado"] == "en_revision"
    assert u.post(f"/api/centro-alertas/{r}/tomar", headers=H).status_code == 409
    corta = u.post(f"/api/centro-alertas/{r}/decision", headers=H, json={"decision": "revisada", "justificacion": "corta"})
    assert corta.status_code == 422
    for x in por_origen.values():
        res = u.post(f"/api/centro-alertas/{x['uid']}/decision", headers=H,
                     json={"decision": "descartada" if x["origen"] == "coincidencia" else "revisada", "justificacion": J})
        assert res.status_code == 200, res.text
        assert res.json()["estado"] in ("revisada", "descartada")
        assert any(J in (h["texto"] or "") for h in res.json()["historial"])
    again = u.post(f"/api/centro-alertas/{r}/decision", headers=H, json={"decision": "revisada", "justificacion": J})
    assert again.status_code == 409


def test_filtros(app):
    u = sesion(app, "universidad")
    altas = todas(u, prioridad="alta")["items"]
    assert altas and all(x["prioridad"] == "alta" for x in altas)
    rango = todas(u, desde="2025-03-01", hasta="2025-03-31")["items"]
    assert rango and all("2025-03-01" <= x["fecha_hecho"] <= "2025-03-31" for x in rango)
    assert todas(u, q="Horizonte")["total"] >= 1


def test_ficha_empresa(app):
    u = sesion(app, "universidad")
    lista = u.get("/api/fichas-empresa", params={"q": "00000000106"}).json()
    assert lista["total"] == 1
    f = u.get(f"/api/fichas-empresa/{lista['items'][0]['id']}").json()
    assert f["resumen"]["contratos"] == 30 and f["resumen"]["entidades"] == 1
    assert f["alertas_por_categoria"]["concentracion"] == 1
    assert sum(m["contratos"] for m in f["meses"]) == 30
    assert f["linea_tiempo"][0]["fecha"] >= f["linea_tiempo"][-1]["fecha"]
    assert f["limitaciones"]
    horizonte = u.get("/api/fichas-empresa", params={"q": "00900000002"}).json()["items"][0]
    h = u.get(f"/api/fichas-empresa/{horizonte['id']}").json()
    assert h["resumen"]["contratos"] == 7 and h["postulaciones"] and h["ifp"]["dimensiones"]
    # Historial de demostración: Horizonte tiene antecedentes detectados por las reglas; Aurora no.
    assert {"R01", "R03"} <= {a["codigo"] for a in h["alertas"]}
    aurora = u.get("/api/fichas-empresa", params={"q": "00900000001"}).json()["items"][0]
    assert not [a for a in u.get(f"/api/fichas-empresa/{aurora['id']}").json()["alertas"] if a["codigo"].startswith("R")]


def test_antecedentes_en_la_convocatoria(app):
    u = sesion(app, "universidad")
    conv = next(x for x in u.get("/api/convocatorias").json()["items"] if x["codigo"].startswith("CAF"))
    d = u.get(f"/api/convocatorias/{conv['id']}").json()
    ant = {p["razon_social"]: p["antecedentes"] for p in d["postulantes"]}
    assert ant["Operaciones Horizonte (demo)"]["total"] == 2
    assert ant["Servicios Campus Aurora (demo)"]["total"] == 0
    assert u.get("/api/fichas-empresa/999999").status_code == 404


def test_permisos(app):
    assert TestClient(app).get("/api/centro-alertas").status_code == 401
    e = sesion(app, "empresa-aurora")
    assert e.get("/api/centro-alertas").status_code == 403
    assert e.get("/api/fichas-empresa").status_code == 403
    assert e.get("/api/empresa/resumen").status_code == 200


def test_demo_en_vivo(app):
    """La convocatoria FOT-DEMO-002 arranca vacía y el kit de Horizonte dispara las señales previstas."""
    from pathlib import Path
    u = sesion(app, "universidad")
    conv = next(x for x in u.get("/api/convocatorias").json()["items"] if x["codigo"] == "FOT-DEMO-002")
    assert conv["estado"] == "abierta"
    assert u.get(f"/api/convocatorias/{conv['id']}").json()["postulantes"] == []
    e = sesion(app, "empresa-horizonte")
    e.post(f"/api/empresa/convocatorias/{conv['id']}/postulacion", headers=H,
           json={"oferta": "1950", "experiencia": 3}).raise_for_status()
    kit = Path(__file__).resolve().parents[1] / "demo-en-vivo"
    for nombre, tipo in [("1-horizonte-propuesta-economica.pdf", "propuesta"),
                         ("2-horizonte-plan-operativo.docx", "propuesta"),
                         ("3-horizonte-anexo-economico.xlsx", "anexo")]:
        e.post(f"/api/empresa/convocatorias/{conv['id']}/documentos", headers=H, data={"tipo": tipo},
               files={"archivo": (nombre, (kit / nombre).read_bytes())}).raise_for_status()
    d = u.get(f"/api/convocatorias/{conv['id']}").json()
    assert [c["tipo"] for c in d["coincidencias"]] == ["CI02"]
    assert d["postulantes"][0]["antecedentes"]["total"] >= 2
    for doc in [x for x in d["documentos"] if x.get("postulante_id")]:
        u.post(f"/api/documentos/{doc['id']}/analizar", headers=H).raise_for_status()
    k = u.get(f"/api/convocatorias/{conv['id']}/comparar").json()["items"][0]
    assert sorted(a["regla"] for a in k["alertas"]) == ["D03", "D09"]
    assert k["indicador_preventivo"]["valor"] < 0
    assert todas(u, q="FOT-DEMO-002")["total"] == 1
