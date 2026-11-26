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
    assert h["resumen"]["contratos"] == 0 and h["postulaciones"] and h["ifp"]["dimensiones"]
    assert u.get("/api/fichas-empresa/999999").status_code == 404


def test_permisos(app):
    assert TestClient(app).get("/api/centro-alertas").status_code == 401
    e = sesion(app, "empresa-aurora")
    assert e.get("/api/centro-alertas").status_code == 403
    assert e.get("/api/fichas-empresa").status_code == 403
    assert e.get("/api/empresa/resumen").status_code == 200
