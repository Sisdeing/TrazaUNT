import React from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Trazabilidad from "./Trazabilidad";
import { request } from "../api";
vi.mock("../api", () => ({ request: vi.fn() }));

const fase = (orden, estado, extra = {}) => ({
  id: orden,
  orden,
  codigo: "F-" + orden,
  nombre: ["Requerimiento", "Actuaciones preparatorias", "Convocatoria y selección", "Adjudicación y contratación", "Ejecución contractual", "Conformidad", "Pago", "Cierre"][orden - 1],
  estado,
  responsable: "Ana (demo)",
  limite: "2099-01-01",
  revision: 0,
  requisitos: [{ id: orden * 10, nombre: "Requisito " + orden, estado: "pendiente", obligatorio: true }],
  documentos: [],
  observaciones: [],
  avance: 0,
  ...extra,
});
const expediente = (fases) => ({
  id: 5,
  codigo: "EXP-UNT-2026-000005",
  nombre: "Compra de proyectores",
  tipo: "bienes",
  area: "Ingeniería",
  monto: "30000",
  inicio: "2026-11-26",
  datos: {},
  fases,
  eventos: [],
  alertas: [],
});
const usuario = { nombre: "Analista (demo)", rol: "analista" };
beforeEach(() => request.mockReset());
afterEach(cleanup);

test("una fase pendiente solo ofrece iniciarla", async () => {
  request.mockResolvedValue(expediente([fase(1, "pendiente"), ...[2, 3, 4, 5, 6, 7, 8].map((n) => fase(n, "pendiente"))]));
  render(<Trazabilidad id="5" usuario={usuario} />);
  expect(await screen.findByRole("button", { name: "Iniciar fase" })).toBeTruthy();
  for (const no of ["Verificar", "Dar visto bueno", "Cerrar fase", "Registrar pago", "Subir"])
    expect(screen.queryByRole("button", { name: no })).toBeNull();
});

test("con un documento presentado se puede verificar, y sin requisitos pendientes se da visto bueno", async () => {
  const conDoc = fase(1, "en_ejecucion", {
    requisitos: [{ id: 10, nombre: "Términos de referencia", estado: "presentado", obligatorio: true }],
    documentos: [{ id: 99, requisito_id: 10, nombre: "tdr.pdf", version: 1, sha256: "abc123abc123abc", autor: "Ana", registrado_por: "ana", fecha: "2026-11-26T10:00:00Z", estado: "presentado" }],
  });
  request.mockResolvedValue(expediente([conDoc, ...[2, 3, 4, 5, 6, 7, 8].map((n) => fase(n, "pendiente"))]));
  render(<Trazabilidad id="5" usuario={usuario} />);
  expect(await screen.findByRole("button", { name: "Verificar" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Dar visto bueno" })).toBeNull();
  cleanup();
  const lista = fase(1, "en_revision", {
    requisitos: [{ id: 10, nombre: "Términos de referencia", estado: "validado", obligatorio: true }],
  });
  request.mockResolvedValue(expediente([lista, ...[2, 3, 4, 5, 6, 7, 8].map((n) => fase(n, "pendiente"))]));
  render(<Trazabilidad id="5" usuario={usuario} />);
  expect(await screen.findByRole("button", { name: "Dar visto bueno" })).toBeTruthy();
});

test("el pago espera a que se cierre la conformidad", async () => {
  const fases = [1, 2, 3, 4, 5].map((n) => fase(n, "cerrada"));
  fases.push(fase(6, "en_revision"), fase(7, "validada"), fase(8, "pendiente"));
  request.mockResolvedValue(expediente(fases));
  const u = userEvent.setup();
  render(<Trazabilidad id="5" usuario={usuario} />);
  await u.click(await screen.findByRole("button", { name: /Pago/ }));
  expect(screen.getByRole("button", { name: "Registrar pago" }).disabled).toBe(true);
  expect(screen.getByText(/primero debe cerrarse la fase de Conformidad/)).toBeTruthy();
});

test("la lista muestra primero los expedientes en trámite", async () => {
  request.mockResolvedValue({
    items: [
      { id: 1, codigo: "EXP-1", nombre: "Caso en trámite", tipo: "servicios", inicio: "2026-01-01", datos: { sintetico: true }, avance: 50, alertas: 2 },
      { id: 2, codigo: "EXP-2", nombre: "Registro histórico", tipo: "bienes", inicio: "2020-01-01", datos: { origen: "publico" }, avance: 0, alertas: 0 },
    ],
  });
  render(<Trazabilidad usuario={{ rol: "consulta" }} />);
  expect(await screen.findByText("Caso en trámite")).toBeTruthy();
  expect(screen.queryByText("Registro histórico")).toBeNull();
  expect(screen.queryByRole("button", { name: /Nuevo expediente/ })).toBeNull();
});
