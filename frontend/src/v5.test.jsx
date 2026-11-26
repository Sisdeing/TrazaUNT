import React from "react";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, test, expect, afterEach, beforeEach } from "vitest";
vi.mock("./api", () => ({ request: vi.fn(), download: vi.fn() }));
import { request } from "./api";
import { TarjetaCoincidencia } from "./Coincidencias";
import EmpresaApp from "./Empresa";
import PortalPublico from "./PortalPublico";

beforeEach(() => {
  request.mockReset();
  window.scrollTo = vi.fn();
});
afterEach(() => {
  cleanup();
  window.location.hash = "";
});

const coincidencia = {
  id: 7, tipo: "CI02", nivel: "media", titulo: "Nombre completo coincidente", detalle: "Puede tratarse de homónimos.",
  sujeto_a: { nombre: "Diego Salazar Ríos (demo)", rol: "Comité", fuente: "Convocatoria" },
  sujeto_b: { nombre: "Diego Salazar Ríos (demo)", rol: "Representante", fuente: "Proveedor" },
  evidencia: { campo: "Nombre completo", criterio: "Igualdad" }, estado: "pendiente", estado_texto: "Pendiente de revisión",
  vigente: true, detectada: "2026-11-26T10:00:00-05:00", aviso: "Coincidencia para revisión. No constituye un conflicto de intereses confirmado.",
  revisiones: [],
};

test("la coincidencia exige una decisión justificada y la registra", async () => {
  request.mockImplementation((path, o) =>
    Promise.resolve(o?.method === "POST" ? { ...coincidencia, estado: "derivada", estado_texto: "Derivada a revisión de integridad" } : { ...coincidencia }),
  );
  const u = userEvent.setup();
  render(<TarjetaCoincidencia item={coincidencia} />);
  expect(screen.getByText("Media")).toBeTruthy();
  await u.click(screen.getByRole("button", { name: /Ver evidencia y revisar/ }));
  expect(screen.getByText(/No constituye un conflicto/)).toBeTruthy();
  await u.click(screen.getByLabelText("Derivar a revisión de integridad"));
  await u.type(screen.getByLabelText("Justificación con referencia a la evidencia"), "Mismo DNI en la declaración jurada.");
  await u.click(screen.getByRole("button", { name: "Registrar revisión" }));
  const envio = request.mock.calls.find(([, o]) => o?.method === "POST");
  expect(envio[0]).toBe("/coincidencias/7/revision");
  expect(JSON.parse(envio[1].body)).toEqual({ decision: "derivada", justificacion: "Mismo DNI en la declaración jurada." });
  expect(await screen.findByText("Derivada a revisión de integridad")).toBeTruthy();
});

test("la empresa ve solo su postulación, su admisión y el estado de sus documentos", async () => {
  window.location.hash = "empresa/1";
  request.mockResolvedValue({
    id: 1, codigo: "CAF", nombre: "Cafetería", modalidad: "Concesión", area: "Patrimonio", estado: "abierta", estado_texto: "Recepción abierta",
    apertura: "2026-11-15", cierre: "2026-11-30", postulado: true, admision: "observada", admision_texto: "Observada", resultado: null,
    puede_postular: false, objeto: "Operar la cafetería", descripcion: "", ubicacion: "", presupuesto: 4000, duracion_meses: 12,
    requisitos: ["RUC"], criterios: [{ nombre: "Precio", peso: 100 }], comite: "2 miembro(s) registrados",
    etapas: [{ clave: "abierta", nombre: "Recepción de propuestas", estado: "actual" }],
    postulacion: { oferta: 4950, experiencia: 3, fecha: "2026-11-18T10:00:00-05:00" },
    admisiones: [{ estado: "observada", estado_texto: "Observada", motivo: "Falta la garantía vigente.", fecha: "2026-11-26T10:00:00-05:00" }],
    documentos_propios: [{ id: 5, nombre: "oferta.pdf", tipo: "propuesta", version: 1, sha256: "abc123def4567890", fecha: "2026-11-18T10:00:00-05:00", estado: "revisado", estado_texto: "Revisado por la universidad" }],
    historial: [], aviso: "Solo se muestra información de tu propia postulación.",
  });
  render(<EmpresaApp usuario={{ nombre: "Operaciones Horizonte (demo)", rol: "empresa" }} onSalir={vi.fn()} />);
  expect(await screen.findByText("Falta la garantía vigente.")).toBeTruthy();
  expect(screen.getByText("Revisado por la universidad")).toBeTruthy();
  expect(screen.getByText("Presentar documento")).toBeTruthy();
  expect(request).toHaveBeenCalledWith("/empresa/convocatorias/1", expect.anything());
});

test("el portal público muestra la trazabilidad sin nombres de personas", async () => {
  window.location.hash = "publico/trazabilidad/9";
  request.mockResolvedValue({
    id: 9, codigo: "EXP-UNT-2022-000009", referencia: "AS-1", nombre: "Obra", objeto: "Obra", tipo: "obras", monto: "100.00", inicio: "2022-05-01",
    procedencia: "publica", procedencia_texto: "Fuente pública (OECE / SEACE)",
    fases: [{ orden: 5, codigo: "EJE", nombre: "Ejecución contractual", estado: "pendiente", desde: "2022-10-13", hasta: "2023-04-21", actuaciones: 2, documentos: 0 }],
    cronologia: [{ fecha: "2022-10-13", fase: "Ejecución contractual", actividad: "Asiento N° 1 del cuaderno de obra digital", fuente: "CID2022_0.xlsx · fila 811648" }],
    documentos: [], fuentes: [], alertas: { vigentes: 0, atendidas: 0 },
    cuaderno_obra: { contrato: "2143235", numero_contrato: "C-47", contratista: "Empresa SAC", asientos: 130, primer_asiento: "2022-10-13", ultimo_asiento: "2023-04-21", vigencia_final: "2023-01-27", archivo: "CID2022_0.xlsx", conjunto: "CID" },
    aviso: "Vista pública: se omiten nombres de personas.",
  });
  render(<PortalPublico />);
  expect(await screen.findByText(/130 asientos/)).toBeTruthy();
  expect(screen.getByText("CID2022_0.xlsx · fila 811648")).toBeTruthy();
  await waitFor(() => expect(request).toHaveBeenCalledWith("/publico/expedientes/9", expect.anything()));
});
