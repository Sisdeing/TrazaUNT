"""Lectura local de documentos en un proceso acotado. Nunca interpreta fórmulas ni órdenes."""

import csv
import hashlib
import io
import json
import os
import posixpath
import re
import subprocess
import sys
import unicodedata
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from defusedxml import ElementTree as ET

MAX_BYTES = 4 * 1024 * 1024
MAX_EXPANDIDO = 12 * 1024 * 1024
MIMES = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def paquete(datos, ext):
    z = zipfile.ZipFile(io.BytesIO(datos))
    try:
        miembros = z.infolist()
        if len(miembros) > 350 or sum(m.file_size for m in miembros) > MAX_EXPANDIDO:
            raise ValueError("El paquete supera el límite de contenido expandido.")
        nombres = set()
        for m in miembros:
            nombre = m.filename
            normal = nombre.lower()
            if (
                nombre in nombres
                or normal.startswith("/")
                or "\\" in nombre
                or ".." in normal.split("/")
                or ":" in nombre
                or m.flag_bits & 1
                or m.file_size > 6 * 1024 * 1024
                or normal.endswith(
                    (".bin", ".exe", ".js", ".vbs", ".ps1", ".xlsm", ".docm")
                )
                or "/embeddings/" in normal
                or "/activex/" in normal
            ):
                raise ValueError("El paquete contiene elementos no admitidos.")
            nombres.add(nombre)
        requerido = "word/document.xml" if ext == ".docx" else "xl/workbook.xml"
        if requerido not in nombres or "[Content_Types].xml" not in nombres:
            raise ValueError("La estructura no corresponde a la extensión.")
        tipos = ET.fromstring(z.read("[Content_Types].xml"))
        if any("macroenabled" in e.get("ContentType", "").lower() for e in tipos):
            raise ValueError("No se admiten documentos con macros.")
        return z
    except Exception:
        z.close()
        raise


def validar_archivo(nombre, mime, datos):
    if (
        not nombre
        or not re.fullmatch(r"[\w .()áéíóúÁÉÍÓÚñÑ-]{1,150}", nombre)
        or nombre.startswith(".")
    ):
        raise ValueError("Use un nombre de archivo simple, sin rutas.")
    ext = Path(nombre).suffix.lower()
    if ext not in MIMES or not 0 < len(datos) <= MAX_BYTES:
        raise ValueError("Formato o tamaño no admitido. Máximo 4 MiB por archivo.")
    aceptados = {MIMES[ext], "application/octet-stream"}
    if ext == ".csv":
        aceptados.update({"text/plain", "application/vnd.ms-excel"})
    if mime and mime.lower().split(";")[0] not in aceptados:
        raise ValueError("El tipo MIME no coincide con la extensión.")
    if ext in (".docx", ".xlsx"):
        try:
            with paquete(datos, ext):
                pass
        except Exception as e:
            raise ValueError(
                "Documento Office inválido o con contenido no admitido."
            ) from e
    elif ext == ".pdf":
        if not datos.startswith(b"%PDF-") or b"%%EOF" not in datos[-1024:]:
            raise ValueError("La firma del PDF no es válida.")
    elif b"\x00" in datos:
        raise ValueError("El documento no contiene texto válido.")
    else:
        try:
            datos.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise ValueError("Guarde el texto como UTF-8.") from e
    return MIMES[ext], hashlib.sha256(datos).hexdigest()


def fragmentos(ext, datos):
    if ext == ".pdf":
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(datos), strict=True)
        if lector.is_encrypted or len(lector.pages) > 60:
            raise ValueError("PDF cifrado o de más de 60 páginas.")
        for i, pagina in enumerate(lector.pages, 1):
            for linea in (pagina.extract_text() or "").splitlines():
                yield f"Página {i}", linea
    elif ext == ".docx":
        with paquete(datos, ext) as z:
            raiz = ET.fromstring(z.read("word/document.xml"))
            for i, p in enumerate(raiz.iter(W + "p"), 1):
                yield f"Párrafo {i}", "".join(n.text or "" for n in p.iter(W + "t"))
    elif ext == ".xlsx":
        with paquete(datos, ext) as z:
            libro = ET.fromstring(z.read("xl/workbook.xml"))
            relaciones = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            destinos = {
                n.get("Id"): n.get("Target")
                for n in relaciones
                if n.get("TargetMode") != "External"
            }
            strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                strings = [
                    "".join(t.text or "" for t in si.iter(S + "t"))
                    for si in ET.fromstring(z.read("xl/sharedStrings.xml"))
                ]
            for hoja in libro.iter(S + "sheet"):
                destino = destinos[hoja.get(R + "id")]
                ruta = (
                    destino.lstrip("/")
                    if destino.startswith("/")
                    else posixpath.normpath("xl/" + destino)
                )
                if not ruta.startswith("xl/worksheets/"):
                    raise ValueError("Hoja no admitida.")
                raiz = ET.fromstring(z.read(ruta))
                for fila in raiz.iter(S + "row"):
                    partes, refs = [], []
                    for celda in fila.findall(S + "c"):
                        if celda.find(S + "f") is not None:
                            continue
                        v = celda.findtext(S + "v", "")
                        if celda.get("t") == "s" and v:
                            v = strings[int(v)]
                        elif celda.get("t") == "inlineStr":
                            v = "".join(t.text or "" for t in celda.iter(S + "t"))
                        if v:
                            partes.append(v)
                            refs.append(celda.get("r", "?"))
                    if refs:
                        yield (
                            f"{hoja.get('name')}!{refs[0]}:{refs[-1]}",
                            ": ".join(partes),
                        )
    else:
        lineas = datos.decode("utf-8-sig").splitlines()
        if ext == ".csv":
            try:
                delimitador = (
                    csv.Sniffer()
                    .sniff("\n".join(lineas[:8]), delimiters=",;\t")
                    .delimiter
                )
            except csv.Error:
                delimitador = ";"
            for i, fila in enumerate(csv.reader(lineas, delimiter=delimitador), 1):
                yield f"Fila {i}", ": ".join(fila)
        else:
            yield from ((f"Línea {i}", l) for i, l in enumerate(lineas, 1))


def normal(s):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", s.casefold())
        if not unicodedata.combining(c)
    )


def soles(s):
    cadena = re.sub(r"(?i)s/\.?|\s", "", str(s))
    if not re.fullmatch(r"\d{1,14}(?:[,.]\d{1,14})*", cadena):
        raise ValueError("Importe ilegible.")
    if "," in cadena or "." in cadena:
        marca = max(cadena.rfind(","), cadena.rfind("."))
        centimos = len(cadena) - marca - 1
        if centimos <= 2:
            cadena = re.sub("[,.]", "", cadena[:marca]) + "." + cadena[marca + 1 :]
        elif centimos == 3:
            cadena = re.sub("[,.]", "", cadena)
        else:
            raise ValueError("Importe ambiguo.")
    try:
        importe = Decimal(cadena)
        if importe <= 0 or importe >= 10**12:
            raise ValueError("Importe fuera del intervalo admitido.")
        return importe.quantize(Decimal("0.01"))
    except InvalidOperation as e:
        raise ValueError("Importe inválido.") from e


ETIQUETAS = {
    "ruc": "ruc",
    "razon social": "razon_social",
    "representante": "representante",
    "oferta": "oferta",
    "oferta economica": "oferta",
    "contraprestacion mensual": "oferta",
    "experiencia": "experiencia",
    "capacidad operativa": "capacidad",
    "garantia": "garantia",
    "vigencia de garantia": "vigencia_garantia",
    "plan operativo": "plan_operativo",
    "plazo": "plazo",
    "requisito": "requisito",
    "criterio": "criterio",
    "obligacion": "obligacion",
    "ingresos mensuales": "ingresos",
    "costos mensuales": "costos",
}


def extraer(ext, datos):
    campos = []
    total = 0
    observaciones = []
    for numero, (ubicacion, linea) in enumerate(fragmentos(ext, datos), 1):
        total += len(linea)
        if total > 450000 or numero > 10000:
            raise ValueError("El documento excede el límite de lectura.")
        etiqueta, sep, valor = linea.strip().partition(":")
        clave = ETIQUETAS.get(normal(etiqueta.strip()))
        valor = valor.strip()
        if not sep or not clave or not valor:
            continue
        if clave == "ruc" and not re.fullmatch(r"\d{11}", valor):
            observaciones.append(
                f"{ubicacion}: el identificador requiere lectura manual."
            )
            continue
        if clave in ("oferta", "ingresos", "costos"):
            try:
                valor = str(soles(valor))
            except ValueError:
                observaciones.append(f"{ubicacion}: el monto requiere lectura manual.")
                continue
        if len(campos) >= 300:
            raise ValueError("Más de 300 campos candidatos. Divida el documento.")
        campos.append(
            dict(
                campo=clave,
                valor=valor[:300],
                ubicacion=ubicacion[:110],
                fragmento=linea[:400],
                confianza="alta" if clave in ("ruc", "oferta") else "media",
                estado="pendiente",
            )
        )
    if not campos:
        observaciones.append(
            "No se localizaron campos etiquetados. Se requiere lectura manual. OCR no habilitado."
        )
    return dict(
        campos=campos,
        observaciones=observaciones,
        estado="analizado" if campos and not observaciones else "requiere_revision",
    )


def limitar_memoria():
    limite = 420 * 1024 * 1024
    if os.name == "nt":
        # Límite de memoria del proceso en Windows. El handle vive hasta la salida.
        import ctypes
        from ctypes import wintypes as wt

        class Basic(ctypes.Structure):
            _fields_ = [
                ("per_process", ctypes.c_int64),
                ("per_job", ctypes.c_int64),
                ("flags", wt.DWORD),
                ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t),
                ("count", wt.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wt.DWORD),
                ("scheduling", wt.DWORD),
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", ctypes.c_uint64 * 6),
                ("process_limit", ctypes.c_size_t),
                ("job_limit", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.restype = wt.HANDLE
        k.GetCurrentProcess.restype = wt.HANDLE
        job = wt.HANDLE(k.CreateJobObjectW(None, None))
        info = Extended()
        info.basic.flags = 0x100
        info.process_limit = limite
        if not (
            job
            and k.SetInformationJobObject(
                job, 9, ctypes.byref(info), ctypes.sizeof(info)
            )
            and k.AssignProcessToJobObject(job, wt.HANDLE(k.GetCurrentProcess()))
        ):
            raise RuntimeError("No se pudo acotar el lector.")
    else:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (limite, limite))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 11))


def analizar_aislado(nombre, datos):
    try:
        r = subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                Path(nombre).suffix.lower(),
            ],
            input=datos,
            capture_output=True,
            timeout=15,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return dict(
            estado="error_lectura",
            campos=[],
            observaciones=[
                "No se completó la lectura dentro de los límites. El original está disponible para revisión."
            ],
        )


if __name__ == "__main__":
    try:
        limitar_memoria()
        salida = extraer(sys.argv[1], sys.stdin.buffer.read(MAX_BYTES + 1))
    except Exception:
        salida = dict(
            estado="error_lectura",
            campos=[],
            observaciones=[
                "La estructura no pudo leerse con seguridad. El original se conserva para revisión manual."
            ],
        )
    sys.stdout.buffer.write(json.dumps(salida, ensure_ascii=True).encode("ascii"))
