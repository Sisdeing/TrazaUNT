import React from "react";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, test, expect, afterEach, beforeEach } from "vitest";
vi.mock("./api", () => ({ request: vi.fn(), download: vi.fn() }));
import { request } from "./api";
import { App as Shell, RevisionForm } from "./main";
const App = () => (
  <Shell
    usuario={{ usuario: "prueba", nombre: "Prueba API", rol: "analista" }}
    onSalir={vi.fn()}
  />
);

beforeEach(() => {
  request.mockReset();
  window.location.hash = "";
  window.scrollTo = vi.fn();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
});
afterEach(() => cleanup());
test("envía revisión con estado esperado y comentario", async () => {
  request.mockResolvedValue({ mensaje: "Guardado" });
  const saved = vi.fn();
  const user = userEvent.setup();
  render(
    <RevisionForm alerta={{ id: 10, estado: "pendiente" }} onSaved={saved} />,
  );
  await user.type(screen.getByLabelText("Analista"), "Roberto");
  await user.type(
    screen.getByLabelText("Comentario de revisión"),
    "Evidencia revisada",
  );
  await user.click(screen.getByRole("button", { name: "Guardar decisión" }));
  expect(JSON.parse(request.mock.calls[0][1].body)).toEqual({
    analista: "Roberto",
    comentario: "Evidencia revisada",
    estado: "confirmada",
    estado_esperado: "pendiente",
  });
  expect(saved).toHaveBeenCalledWith("Guardado");
});
test("muestra conflicto y conserva el comentario", async () => {
  request.mockRejectedValue(new Error("Otro cambio modificó esta alerta."));
  const user = userEvent.setup();
  render(
    <RevisionForm alerta={{ id: 10, estado: "pendiente" }} onSaved={vi.fn()} />,
  );
  await user.type(screen.getByLabelText("Analista"), "Roberto");
  await user.type(screen.getByLabelText("Comentario de revisión"), "Revisado");
  await user.click(screen.getByRole("button", { name: "Guardar decisión" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Otro cambio",
  );
  expect(screen.getByLabelText("Comentario de revisión").value).toBe(
    "Revisado",
  );
});
test("renderiza inicio, abre acerca y menú", async () => {
  window.location.hash = "inicio";
  request.mockImplementation((path) =>
    Promise.resolve(
      path === "/configuracion"
        ? { entidades: [], reglas: [] }
        : {
            contrataciones: 600,
            alertas: 100,
            monto: 5000,
            proveedores: 2,
            pendientes: 100,
            contratos_con_alerta: 100,
            opciones: { periodos: [], tipos: [], categorias: [] },
            cartera: {},
            serie: [],
            severidades: { alta: 100 },
            prioritarias: [],
          },
    ),
  );
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText("600");
  await user.click(
    screen.getByRole("button", { name: /Equipo de integridad/ }),
  );
  expect(screen.getByRole("dialog").hasAttribute("open")).toBe(true);
  await user.click(screen.getByRole("button", { name: "Abrir menú" }));
  expect(
    screen
      .getByRole("button", { name: "Abrir menú" })
      .getAttribute("aria-expanded"),
  ).toBe("true");
  await user.click(screen.getByRole("button", { name: "Cerrar menú" }));
  expect(
    screen
      .getByRole("button", { name: "Abrir menú" })
      .getAttribute("aria-expanded"),
  ).toBe("false");
});
test("consulta páginas y filtros por API", async () => {
  window.location.hash = "expedientes";
  request.mockImplementation((path) =>
    Promise.resolve(
      path === "/configuracion"
        ? { entidades: [], reglas: [] }
        : { items: [], total: 40, tamano: 25, pagina: 1 },
    ),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "Siguiente" }));
  await waitFor(() =>
    expect(request.mock.calls.some(([p]) => p.includes("pagina=2"))).toBe(true),
  );
  await user.type(screen.getByLabelText("Buscar"), "EXP-2025");
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  await waitFor(() =>
    expect(
      request.mock.calls.some(
        ([p]) => p.includes("q=EXP-2025") && p.includes("pagina=1"),
      ),
    ).toBe(true),
  );
});
test("comunica error de conexión", async () => {
  request.mockRejectedValue(new Error("Sin conexión al servidor."));
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Sin conexión",
  );
});

test("la navegación simplificada oculta las secciones retiradas", async () => {
  request.mockResolvedValue({ entidades: [], reglas: [], items: [], entorno: "demo", por_nivel: { alta: 0, media: 0, baja: 0 }, total: 0 });
  window.location.hash = "alertas";
  render(<App />);
  expect(await screen.findByRole("link", { name: "Alertas y coincidencias" })).toBeTruthy();
  for (const retirada of ["Conflictos de interés", "Proveedores", "Reportes", "Gobierno del modelo", "Inteligencia económica", "Declaraciones"])
    expect(screen.queryByRole("link", { name: retirada })).toBeNull();
  expect(screen.getByRole("link", { name: "¿De dónde salen los datos?" })).toBeTruthy();
  for (const oculta of ["Datos y fuentes", "Bitácora de auditoría"])
    expect(screen.queryByRole("link", { name: oculta })).toBeNull();
  cleanup();
  window.location.hash = "conflictos";
  render(<App />);
  expect((await screen.findByText(/Esta sección se retiró/)).textContent).toContain("Sus datos se conservan");
  cleanup();
  window.location.hash = "inicio";
  render(<Shell usuario={{ nombre: "Control", rol: "auditor" }} onSalir={vi.fn()} />);
  expect(await screen.findByRole("link", { name: "Resumen ejecutivo" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Convocatorias" })).toBeNull();
});
