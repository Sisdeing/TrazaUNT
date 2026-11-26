import React from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CentroAlertas from "./CentroAlertas";
import Empresas from "../empresas/Empresas";
import { request } from "../api";
vi.mock("../api", () => ({ request: vi.fn() }));

const alerta = {
  uid: "R-1",
  origen: "regla",
  ids: [1, 2],
  codigo: "R01",
  categoria: "fraccionamiento",
  categoria_texto: "Posible fraccionamiento",
  titulo: "Posible fraccionamiento de una misma necesidad",
  prioridad: "alta",
  estado: "pendiente",
  fecha_hecho: "2025-03-01",
  empresas: [{ id: 101, ruc: "00000000101", nombre: "Empresa Demo" }],
  proceso: { tipo: "Contratación", id: 501, codigo: "EXP-2025-00501 y 1 más", nombre: "2 contratos", entidad: "Entidad", enlace: "#expedientes/501" },
  descripcion: "Hay 2 contratos con objeto similar.",
};
const resumen = {
  total: 1,
  abiertas: 1,
  por_categoria: {
    fraccionamiento: { nombre: "Posible fraccionamiento", ayuda: "", abiertas: 1, total: 1 },
    colusion: { nombre: "Posible colusión", ayuda: "", abiertas: 0, total: 0 },
  },
  por_prioridad: { alta: 1 },
  por_estado: { pendiente: 1 },
};
const detalle = {
  ...alerta,
  aviso: "Indicio para revisión humana.",
  categoria_ayuda: "Contratos parecidos.",
  explicacion: { observado: "Hay 2 contratos con objeto similar.", criterio: "Al menos 2 contratos.", revisar: "Contrastar la necesidad." },
  indicadores: [{ nombre: "Contratos agrupados", valor: "2" }],
  registros: [{ tipo: "Contrato", codigo: "EXP-2025-00501", fecha: "2025-03-01", monto: "S/ 15,000.00", detalle: "Equipos", enlace: "#expedientes/501" }],
  historial: [{ fecha: "2026-11-24T10:00:00-05:00", accion: "Detectada", autor: "Sistema", texto: "La regla se activó." }],
};
beforeEach(() => request.mockReset());
afterEach(cleanup);

test("el centro filtra por categoría y la decisión pide confirmación antes de guardarse", async () => {
  request.mockImplementation((path, o) => {
    if (o?.method === "POST") return Promise.resolve({ ...detalle, estado: "revisada" });
    if (String(path).startsWith("/centro-alertas/R-1")) return Promise.resolve(detalle);
    return Promise.resolve({ items: [alerta], total: 1, tamano: 15, pagina: 1, resumen });
  });
  const u = userEvent.setup();
  render(<CentroAlertas usuario={{ rol: "analista", nombre: "Ana" }} />);
  expect(await screen.findByText("Posible fraccionamiento de una misma necesidad")).toBeTruthy();
  await u.click(screen.getByRole("button", { name: /Posible colusión/ }));
  await waitFor(() => expect(request.mock.calls.some(([p]) => p.includes("categoria=colusion"))).toBe(true));
  await u.click(screen.getAllByRole("button", { name: /Ver detalle/ })[0]);
  expect(await screen.findByText("Contrastar la necesidad.")).toBeTruthy();
  await u.click(screen.getByText(/Revisada: amerita seguimiento/));
  await u.type(screen.getByLabelText(/Justificación/), "Se revisó la planificación anual del área.");
  await u.click(screen.getByText("Continuar"));
  expect(request.mock.calls.some(([, o]) => o?.method === "POST")).toBe(false);
  expect(screen.getByText(/se aplica a los 2 registros del patrón/)).toBeTruthy();
  await u.click(screen.getByText("Sí, registrar"));
  await waitFor(() =>
    expect(request.mock.calls.some(([p, o]) => p === "/centro-alertas/R-1/decision" && o?.method === "POST")).toBe(true),
  );
});

test("la ficha de empresa muestra lo no disponible y filtra por fechas", async () => {
  request.mockResolvedValue({
    empresa: { id: 9, ruc: "00000000009", nombre: "Empresa Nueve", representante: "", domicilio: "Av. Demo", constitucion: "2020-01-01", origen: "Registro sintético de demostración" },
    resumen: { participaciones: 2, contratos: 2, postulaciones: 0, entidades: 1, monto_total: 30000, alertas: 0, alertas_abiertas: 0 },
    entidades: [{ nombre: "Entidad A", contratos: 2, monto: 30000 }],
    contratos: [
      { id: 1, codigo: "EXP-1", fecha: "2025-01-10", entidad: "Entidad A", objeto: "Papel", monto: 10000, tipo: "Proceso A", postores: 3, alertas: [], enlace: "#expedientes/1" },
      { id: 2, codigo: "EXP-2", fecha: "2025-06-10", entidad: "Entidad A", objeto: "Tóner", monto: 20000, tipo: "Proceso A", postores: 4, alertas: [], enlace: "#expedientes/2" },
    ],
    postulaciones: [],
    meses: [],
    alertas: [],
    categorias: { fraccionamiento: "Posible fraccionamiento" },
    linea_tiempo: [],
    ifp: null,
    limitaciones: [],
  });
  const u = userEvent.setup();
  render(<Empresas id="9" />);
  expect(await screen.findByText("Empresa Nueve")).toBeTruthy();
  expect(screen.getByText(/Representante: No disponible/)).toBeTruthy();
  expect(screen.getByText("No registra postulaciones a convocatorias.")).toBeTruthy();
  await u.click(screen.getByRole("tab", { name: /Contratos \(2\)/ }));
  await u.type(screen.getByLabelText("Desde"), "2025-03-01");
  expect(await screen.findByRole("tab", { name: /Contratos \(1\)/ })).toBeTruthy();
  expect(screen.queryByText("EXP-1")).toBeNull();
  expect(screen.getByRole("button", { name: /Quitar filtro Desde/ })).toBeTruthy();
});
