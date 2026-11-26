"""Prueba E2E opcional. Usa una base temporal propia y un navegador Chromium instalado."""

import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def comprobar(pagina, url, codigo, capturas):
    errores = []
    pagina.on("pageerror", lambda err: errores.append(str(err)))
    pagina.goto(url)
    expect(pagina.get_by_role("heading", name="Transparencia en contrataciones")).to_be_visible()
    if capturas:
        for nombre, ancho, alto in [("escritorio", 1440, 1000), ("movil", 360, 800)]:
            pagina.set_viewport_size({"width": ancho, "height": alto})
            expect(pagina.get_by_role("heading", name="Alertas atendidas")).to_be_visible()
            assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
            pagina.screenshot(path=str(capturas / f"portal-{nombre}.png"), full_page=True)
        pagina.set_viewport_size({"width": 1440, "height": 1000})
    tabla = pagina.locator("tbody tr")
    expect(tabla.first).to_be_visible()
    assert pagina.request.get(url + "/api/publico/contrataciones").json()["origen"] == "sintetico"
    pagina.get_by_label("Año", exact=True).select_option(index=1)
    expect(tabla).to_have_count(1)
    assert pagina.request.get(url + "/api/dashboard").status == 401
    pagina.get_by_role("link", name="Acceso institucional").click()
    expect(pagina.get_by_role("heading", name="Acceso al espacio de trabajo")).to_be_visible()
    pagina.goto(url + "/#acceso=" + codigo)
    expect(pagina.get_by_role("heading", name="Mi bandeja")).to_be_visible()
    for palabra in ("académico", "hackathon", "prototipo", "jurado", "DEMO"):
        assert pagina.get_by_text(palabra, exact=True).count() == 0
    if capturas:
        pagina.screenshot(path=str(capturas / "bandeja-escritorio.png"), full_page=True)
        pagina.set_viewport_size({"width": 360, "height": 800})
        pagina.get_by_role("button", name="Abrir menú").click()
        pagina.screenshot(path=str(capturas / "menu-movil.png"), full_page=True)
        pagina.set_viewport_size({"width": 1440, "height": 1000})
    pagina.get_by_role("link", name="Resumen ejecutivo", exact=True).click()
    expect(pagina.get_by_role("heading", name="Resumen ejecutivo")).to_be_visible()
    expect(pagina.locator(".kpi").nth(1)).to_contain_text("600")
    pagina.get_by_role("button", name="Filtros", exact=True).click()
    pagina.get_by_label("Periodo de expedientes").select_option("2025-S1")
    expect(pagina.locator(".kpi").nth(1)).not_to_contain_text("600")
    pagina.get_by_role("button", name="Limpiar filtros").click()
    pagina.get_by_role("button", name="Filtros", exact=True).click()
    pagina.get_by_role("button", name="Monto", exact=True).click()
    expect(
        pagina.get_by_role("heading", name="Evolución de contrataciones")
    ).to_be_visible()
    for nombre, ancho, alto in [
        ("escritorio", 1440, 1000),
        ("tablet", 820, 1080),
        ("movil", 390, 844),
    ]:
        pagina.set_viewport_size({"width": ancho, "height": alto})
        pagina.evaluate("document.fonts.ready")
        assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            nombre + ": desborde"
        )
        if capturas:
            pagina.screenshot(path=str(capturas / (nombre + ".png")), full_page=True)
    pagina.get_by_role("button", name="Abrir menú").click()
    expect(pagina.locator("aside.open")).to_be_visible()
    pagina.get_by_role("link", name="Convocatorias", exact=True).click()
    pagina.set_viewport_size({"width": 1440, "height": 1000})
    pagina.get_by_role(
        "link", name="Concesión de servicio de cafetería universitaria"
    ).click()
    pagina.get_by_role("button", name="Postulantes", exact=True).click()
    pagina.get_by_text("Registrar postulante", exact=True).click()
    registro = pagina.locator("details[open] form")
    registro.locator("select").select_option(index=1)
    registro.get_by_label("Oferta económica (S/)").fill("4500")
    registro.get_by_label("Experiencia declarada (años)").fill("4")
    registro.get_by_role("button", name="Guardar postulante").click()
    expect(pagina.locator(".flujo tbody tr")).to_have_count(4)
    pagina.get_by_role("button", name="Documentos", exact=True).click()
    pagina.get_by_text("Adjuntar documento", exact=True).click()
    pagina.get_by_label("Vincular a", exact=False).select_option(
        label="Operaciones Horizonte (demo)"
    )
    pagina.get_by_label("Archivo documental").set_input_files(
        str(ROOT / "data/demo/cafeteria/horizonte-aclaracion.txt")
    )
    pagina.get_by_role("button", name="Guardar archivo").click()
    pagina.get_by_role("button", name="Analizar documento").click()
    expect(pagina.locator(".fl-evidencias article").first).to_be_visible(timeout=20000)
    pagina.get_by_role("button", name="Comparación", exact=True).click()
    expect(pagina.get_by_text("D03", exact=False).first).to_be_visible()
    with pagina.expect_download() as descarga:
        pagina.get_by_role("button", name="Exportar CSV").click()
    assert descarga.value.suggested_filename.endswith(".csv")
    if capturas:
        pagina.screenshot(path=str(capturas / "comparacion.png"))
    pagina.get_by_role("button", name="Revisiones", exact=True).click()
    pagina.get_by_label("Justificación y referencia a la evidencia").fill(
        "Comité demo revisó el anexo y el origen de los montos."
    )
    pagina.get_by_role("button", name="Guardar revisión", exact=True).click()
    expect(
        pagina.get_by_role(
            "cell", name="Comité demo revisó el anexo y el origen de los montos."
        )
    ).to_be_visible()
    pagina.get_by_role("button", name="Bases", exact=True).click()
    for accion in [
        "Cerrar recepción",
        "Iniciar evaluación",
        "Registrar resultado ficticio",
    ]:
        pagina.get_by_text(accion, exact=True).click()
        if accion.startswith("Registrar"):
            pagina.get_by_label("Postulante seleccionado por el comité").select_option(
                label="Servicios Campus Aurora (demo)"
            )
        pagina.get_by_label("Motivo del cambio").fill(
            "Se documentó la decisión humana del comité ficticio."
        )
        pagina.get_by_role("button", name="Confirmar cambio de estado").click()
        expect(
            pagina.get_by_role("button", name="Confirmar cambio de estado")
        ).not_to_be_visible()
    pagina.get_by_role(
        "link", name="Abrir seguimiento de la concesión", exact=False
    ).click()
    expect(pagina.get_by_role("heading", name="Seguimiento económico")).to_be_visible()
    pagina.goto(url + "/#avisos")
    expect(pagina.locator(".notice-item").first).to_be_visible()
    pagina.get_by_role("button", name="Marcar leído").first.click()
    expect(pagina.get_by_text("Leído", exact=True).first).to_be_visible()
    for destino in [
        "expedientes",
        "alertas",
        "economia",
        "proveedores",
        "conflictos",
        "declaraciones",
        "reportes",
        "historial",
        "fuentes",
        "asistente",
        "predicciones",
        "metricas",
        "etica",
    ]:
        pagina.goto(url + "/#" + destino)
        pagina.wait_for_timeout(180)
        expect(pagina.locator("main h1").first).to_be_visible()
        assert not pagina.get_by_role("alert").count(), destino
    pagina.goto(url+"/#convocatorias/nueva")
    for campo,valor in [("Nombre de la convocatoria","Concesión de aula (demo)"),("Código","WEB-001"),
              ("Área responsable","Patrimonio (demo)"),("Responsable","Supervisión (demo)"),
              ("Importe referencial (S/)","1200"),("Duración (meses)","6"),("Fecha de apertura","2026-11-23"),
              ("Fecha de cierre","2026-11-30"),("Objeto","Uso temporal de aula demo")]:
        pagina.get_by_label(campo,exact=True).fill(valor)
    pagina.get_by_label("Modalidad").select_option(label="Concesión")
    continuar=pagina.get_by_role("button",name="Continuar",exact=True)
    continuar.click()
    pagina.locator('input[type=file]').set_input_files(str(ROOT/"data/demo/cafeteria/bases-cafeteria.pdf"))
    continuar.click()
    pagina.get_by_label("Requisito 1").fill("RUC")
    continuar.click()
    pagina.get_by_label("Criterio 1").fill("Operación")
    continuar.click()
    pagina.get_by_label("Nombre 1").fill("Evaluadora (demo)")
    continuar.click()
    pagina.get_by_role("button",name="Guardar borrador").click()
    expect(pagina.get_by_role("heading",name="Concesión de aula (demo)")).to_be_visible()
    pagina.get_by_text("Abrir registro interno",exact=True).click()
    pagina.get_by_label("Motivo del cambio").fill("Bases de demostración revisadas.")
    pagina.get_by_role("button",name="Confirmar cambio de estado").click()
    expect(pagina.get_by_text("Cerrar recepción",exact=True)).to_be_visible()
    assert not errores, errores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--chromium",
        help="Ruta a Edge o Chromium. Por defecto usa Chromium de Playwright.",
    )
    ap.add_argument("--capturas", type=Path)
    args = ap.parse_args()
    if args.capturas:
        args.capturas.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            puerto = sock.getsockname()[1]
        codigo = secrets.token_urlsafe(32)
        url = f"http://127.0.0.1:{puerto}"
        import threading
        import uvicorn

        sys.path.insert(0, str(ROOT))
        from app import crear_app

        servidor = uvicorn.Server(
            uvicorn.Config(
                crear_app(Path(tmp) / "e2e.sqlite3", acceso_local=codigo),
                host="127.0.0.1",
                port=puerto,
                access_log=False,
            )
        )
        hilo = threading.Thread(target=servidor.run, daemon=True)
        hilo.start()
        try:
            for _ in range(120):
                if servidor.started:
                    break
                if not hilo.is_alive():
                    raise RuntimeError("Fallo en el arranque de la API.")
                time.sleep(0.5)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=args.chromium)
                try:
                    page = browser.new_page(
                        locale="es-PE", viewport={"width": 1440, "height": 1000}
                    )
                    page.set_default_timeout(9000)
                    comprobar(page, url, codigo, args.capturas)
                finally:
                    browser.close()
        finally:
            servidor.should_exit = True
            hilo.join(timeout=20)
    print(
        "E2E correcto: tres anchos, registro, carga, extracción, comparación, revisión, resultado y concesión."
    )


if __name__ == "__main__":
    main()
