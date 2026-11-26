"""Regenera PDF, DOCX y XLSX de la cafetería con reportlab, python-docx y openpyxl (herramientas de autoría opcionales)."""

from pathlib import Path
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4

DIRECTORIO = Path(__file__).resolve().parents[1] / "data/demo/cafeteria"
EMPRESAS = [
    ("aurora", "Servicios Campus Aurora (demo)", "00900000001", 4200, 7, 320, True),
    ("horizonte", "Operaciones Horizonte (demo)", "00900000002", 4950, 3, 230, False),
    ("nova", "Gestión Nova Campus (demo)", "00900000003", 4400, 5, 270, True),
]


def pdf(ruta, titulo, empresa, bloques):
    c = canvas.Canvas(str(ruta), pagesize=A4, invariant=1)
    c.setTitle(titulo + " · " + empresa)
    c.setAuthor("TrazaUNT · Simulación")
    c.setFillColor(HexColor("#12377b"))
    c.rect(0, 742, 596, 100, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica", 10)
    c.drawString(46, 799, "TRAZAUNT      /      CAF-DEMO-001")
    c.setFont("Helvetica-Bold", 22)
    c.drawString(46, 761, titulo)
    c.setFillColor(HexColor("#233450"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(46, 692, empresa)
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
    c.drawString(
        46,
        55,
        "Documento ficticio de simulación académica.   ·   18 de noviembre de 2026",
    )
    c.drawRightString(550, 55, "1 / 1")
    c.save()


def generar():
    DIRECTORIO.mkdir(parents=True, exist_ok=True)
    pdf(
        DIRECTORIO / "bases-cafeteria.pdf",
        "Bases de la concesión",
        "Servicio de cafetería universitaria",
        [
            (
                "Objeto y condiciones",
                [
                    "Operación de la cafetería del Pabellón Norte por doce meses.",
                    "Contraprestación mensual: S/ 4000.00",
                    "Plazo: 12 meses",
                ],
            ),
            (
                "Admisibilidad documental",
                [
                    "Requisito: RUC",
                    "Requisito: Experiencia",
                    "Requisito: Plan operativo",
                    "Requisito: Garantía",
                ],
            ),
            (
                "Evaluación del comité",
                [
                    "Operación 30 %, experiencia 20 %, mantenimiento y calidad 15 %.",
                    "Sostenibilidad y atención 10 %, contraprestación 25 %.",
                ],
            ),
            (
                "Seguimiento",
                [
                    "Obligación: registrar el pago mensual de la contraprestación.",
                    "Obligación: entregar un registro mensual de mantenimiento.",
                ],
            ),
        ],
    )
    for slug, nombre, ruc, monto, exp, cap, garantia in EMPRESAS:
        pdf(
            DIRECTORIO / f"{slug}-oferta.pdf",
            "Propuesta económica",
            nombre,
            [
                (
                    "Identificación del postulante",
                    [f"RUC: {ruc}", f"Razón social: {nombre}"],
                ),
                (
                    "Oferta del servicio",
                    [
                        f"Contraprestación mensual: S/ {monto:.2f}",
                        "Plazo: 12 meses",
                        "Unidad: soles por mes de operación.",
                    ],
                ),
                (
                    "Alcance",
                    [
                        "El importe corresponde al uso del espacio de cafetería.",
                        "Las partidas de operación constan en el anexo económico.",
                    ],
                ),
            ],
        )
        doc = Document()
        doc.core_properties.author = "TrazaUNT (demo)"
        doc.core_properties.created = doc.core_properties.modified = datetime(
            2026, 11, 18
        )
        normal = doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)
        doc.sections[0].top_margin = Inches(0.9)
        doc.add_paragraph("CAF-DEMO-001    /    DOCUMENTO DE SIMULACIÓN")
        p = doc.add_paragraph(style="Title")
        r = p.add_run("Plan de operación de cafetería")
        r.font.color.rgb = RGBColor(21, 32, 45)
        doc.add_paragraph(
            f"{nombre} presenta su capacidad de atención y sus compromisos operativos para la concesión de doce meses."
        )
        doc.add_heading("Identificación y experiencia", level=1)
        doc.add_paragraph(f"RUC: {ruc}")
        doc.add_paragraph(f"Experiencia: {exp} años")
        doc.add_heading("Organización del servicio", level=1)
        doc.add_paragraph(f"Capacidad operativa: {cap} raciones diarias")
        doc.add_paragraph(
            "Plan operativo: atención de lunes a viernes con supervisión de higiene y control de inventario al cierre."
        )
        if garantia:
            doc.add_paragraph(
                "Garantía: compromiso documental de respaldo por dos mensualidades."
            )
        doc.add_paragraph(
            "Obligación: presentar el parte de mantenimiento y el registro mensual de atención."
        )
        doc.save(DIRECTORIO / f"{slug}-plan.docx")
        presupuesto = Workbook()
        hoja = presupuesto.active
        hoja.title = "Presupuesto"
        ingresos, costos, anexo = {
            "aurora": (22000, 16200, 4200),
            "horizonte": (17500, 12700, 5250),
            "nova": (20000, 14100, 4400),
        }[slug]
        for fila in [
            ["Anexo económico mensual"],
            [nombre],
            [],
            ["Convocatoria", "CAF-DEMO-001"],
            ["RUC", ruc],
            ["Ingresos mensuales", ingresos],
            ["Costos mensuales", costos],
            ["Contraprestación mensual", anexo],
            ["Saldo operativo", "=B6-B7-B8"],
            [],
            ["Datos simulados · Presupuesto de un mes de operación."],
        ]:
            hoja.append(fila)
        hoja.column_dimensions["A"].width = 52
        hoja.column_dimensions["B"].width = 24
        hoja["A1"].font = Font(bold=True, color="FFFFFF", size=15)
        hoja["A1"].fill = PatternFill("solid", fgColor="12377B")
        for indice in range(6, 10):
            hoja[f"B{indice}"].number_format = '"S/" #,##0.00'
        presupuesto.save(DIRECTORIO / f"{slug}-anexo.xlsx")


if __name__ == "__main__":
    generar()
