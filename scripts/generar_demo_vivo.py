"""Genera los archivos de la demo en vivo (convocatoria FOT-DEMO-002).

* data/demo/vivo/bases-fotocopiado.pdf: bases que la universidad publica (se cargan solas).
* demo-en-vivo/: kit que sube la empresa Operaciones Horizonte (demo) durante la demo.

Todo es ficticio. Las diferencias son intencionales para que el sistema las detecte:
  - el anexo económico declara S/ 2150.00 y la oferta registrada es S/ 1950.00 (D03);
  - la garantía vence el 05/12/2026, antes del cierre de recepción del 11/12/2026 (D09);
  - ingresos - costos - contraprestación da un saldo mensual negativo (indicador preventivo).
"""

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

RAIZ = Path(__file__).resolve().parents[1]
BASES = RAIZ / "data/demo/vivo"
KIT = RAIZ / "demo-en-vivo"
CODIGO = "FOT-DEMO-002"
EMPRESA = "Operaciones Horizonte (demo)"
RUC = "00900000002"


def pdf(ruta, titulo, subtitulo, bloques, fecha):
    c = canvas.Canvas(str(ruta), pagesize=A4, invariant=1)
    c.setTitle(f"{titulo} · {subtitulo}")
    c.setAuthor("TrazaUNT · Simulación")
    c.setFillColor(HexColor("#000c4b"))
    c.rect(0, 742, 596, 100, fill=1, stroke=0)
    c.setFillColor(HexColor("#fdf107"))
    c.rect(0, 738, 596, 4, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica", 10)
    c.drawString(46, 799, f"TRAZAUNT      /      {CODIGO}")
    c.setFont("Helvetica-Bold", 22)
    c.drawString(46, 761, titulo)
    c.setFillColor(HexColor("#1b1811"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(46, 692, subtitulo)
    y = 642
    for cabecera, lineas in bloques:
        c.setFillColor(HexColor("#12377b"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(46, y, cabecera)
        y -= 27
        c.setFillColor(HexColor("#303a4b"))
        c.setFont("Helvetica", 11)
        for linea in lineas:
            c.drawString(46, y, linea)
            y -= 21
        y -= 25
    c.setStrokeColor(HexColor("#d6deea"))
    c.line(46, 75, 549, 75)
    c.setFont("Helvetica", 9)
    c.drawString(46, 55, f"Documento ficticio de simulación académica.   ·   {fecha}")
    c.drawRightString(550, 55, "1 / 1")
    c.save()


def bases():
    BASES.mkdir(parents=True, exist_ok=True)
    pdf(
        BASES / "bases-fotocopiado.pdf",
        "Bases de la concesión",
        "Servicio de fotocopiado e impresiones",
        [
            ("Objeto y condiciones", [
                "Operación del módulo de fotocopiado de la Biblioteca Central por doce meses.",
                "Contraprestación mensual: S/ 1800.00",
                "Plazo: 12 meses",
            ]),
            ("Admisibilidad documental", [
                "Requisito: RUC",
                "Requisito: Experiencia",
                "Requisito: Plan operativo",
                "Requisito: Garantía",
            ]),
            ("Evaluación del comité", [
                "Propuesta operativa 35 %, experiencia 20 %, atención al estudiante 15 %.",
                "Contraprestación ofrecida 30 %.",
            ]),
            ("Seguimiento", [
                "Obligación: registrar el pago mensual de la contraprestación.",
                "Obligación: mantener la garantía vigente durante toda la recepción.",
            ]),
        ],
        "26 de noviembre de 2026",
    )


def kit():
    KIT.mkdir(parents=True, exist_ok=True)
    pdf(
        KIT / "1-horizonte-propuesta-economica.pdf",
        "Propuesta económica",
        EMPRESA,
        [
            ("Identificación del postulante", [
                f"RUC: {RUC}",
                f"Razón social: {EMPRESA}",
                "Representante: Rosa Lumen Castillo (demo)",
            ]),
            ("Oferta del servicio", [
                "Contraprestación mensual: S/ 1950.00",
                "Plazo: 12 meses",
                "Unidad: soles por mes de operación.",
            ]),
            ("Alcance", [
                "El importe corresponde al uso del módulo de fotocopiado.",
                "Las partidas de operación constan en el anexo económico.",
            ]),
        ],
        "27 de noviembre de 2026",
    )

    doc = Document()
    doc.core_properties.author = "TrazaUNT (demo)"
    doc.core_properties.created = doc.core_properties.modified = datetime(2026, 11, 27)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    doc.sections[0].top_margin = Inches(0.9)
    doc.add_paragraph(f"{CODIGO}    /    DOCUMENTO DE SIMULACIÓN")
    r = doc.add_paragraph(style="Title").add_run("Plan operativo del servicio de fotocopiado")
    r.font.color.rgb = RGBColor(0, 12, 75)
    doc.add_paragraph(f"{EMPRESA} presenta su capacidad de atención y sus compromisos para la concesión de doce meses.")
    doc.add_heading("Identificación y experiencia", level=1)
    doc.add_paragraph(f"RUC: {RUC}")
    doc.add_paragraph("Experiencia: 3 años")
    doc.add_heading("Organización del servicio", level=1)
    doc.add_paragraph("Capacidad operativa: 4500 copias diarias")
    doc.add_paragraph("Plan operativo: atención de lunes a sábado de 7:30 a 20:00 con dos equipos de impresión y uno de respaldo.")
    doc.add_heading("Garantía", level=1)
    doc.add_paragraph("Garantía: carta fianza por dos mensualidades.")
    doc.add_paragraph("Vigencia de garantía: 2026-12-05")
    doc.add_paragraph("Obligación: presentar el reporte mensual de atención y mantenimiento de equipos.")
    doc.save(KIT / "2-horizonte-plan-operativo.docx")

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Presupuesto"
    for fila in [
        ["Anexo económico mensual"],
        [EMPRESA],
        [],
        ["Convocatoria", CODIGO],
        ["RUC", RUC],
        ["Ingresos mensuales", 7800],
        ["Costos mensuales", 6200],
        ["Contraprestación mensual", 2150],
        ["Saldo operativo", "=B6-B7-B8"],
        [],
        ["Datos simulados · Presupuesto de un mes de operación."],
    ]:
        hoja.append(fila)
    hoja.column_dimensions["A"].width = 44
    hoja.column_dimensions["B"].width = 22
    hoja["A1"].font = Font(bold=True, color="FFFFFF", size=15)
    hoja["A1"].fill = PatternFill("solid", fgColor="000C4B")
    for i in range(6, 10):
        hoja[f"B{i}"].number_format = '"S/" #,##0.00'
    libro.save(KIT / "3-horizonte-anexo-economico.xlsx")


if __name__ == "__main__":
    bases()
    kit()
