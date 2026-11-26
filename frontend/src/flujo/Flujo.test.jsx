import React from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Convocatorias, Concesiones } from "./Flujo";
import { Asistente, subir } from "./Asistente";
import { request } from "../api";
vi.mock("../api", () => ({ request: vi.fn() }));

const usuario = { nombre: "Revisor (demo)", rol: "analista" };
const ficha = {
  id: 12,
  codigo: "CON-DEMO",
  nombre: "Cafetería de prueba",
  estado: "abierta",
  version: 2,
  requisitos: ["Garantía"],
  criterios: [{ nombre: "Calidad", peso: 100 }],
  intervinientes: [],
  postulantes: [],
  historial: [],
  documentos: [],
  objeto: "Servicio de cafetería",
  presupuesto: 5000,
  duracion_meses: 12,
};
beforeEach(() => request.mockReset());
afterEach(cleanup);

test("la lista filtra por nombre y estado en el servidor", async () => {
  request.mockResolvedValue({
    items: [ficha],
    pagina: 1,
    tamano: 25,
    total: 1,
  });
  const u = userEvent.setup();
  render(<Convocatorias usuario={usuario} />);
  expect(
    (await screen.findByText("Cafetería de prueba")).getAttribute("href"),
  ).toBe("#convocatorias/12");
  await u.type(screen.getByLabelText("Buscar convocatoria"), "Cafetería");
  await u.selectOptions(screen.getByLabelText("Estado"), "abierta");
  await u.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  await waitFor(() =>
    expect(
      request.mock.calls.some(
        ([url]) =>
          url.includes("q=Cafeter%C3%ADa") && url.includes("estado=abierta"),
      ),
    ).toBe(true),
  );
});
test("la revisión conserva el texto cuando el servidor rechaza la operación", async () => {
  request.mockImplementation((p, o) =>
    o?.method === "POST"
      ? Promise.reject(new Error("Revisión rechazada"))
      : String(p).includes("/comparar")
        ? new Promise(() => {})
        : Promise.resolve(ficha),
  );
  const u = userEvent.setup();
  render(<Convocatorias id="12" usuario={usuario} />);
  await u.click(await screen.findByRole("button", { name: "Evaluación" }));
  await u.type(
    screen.getByLabelText("Justificación y referencia a la evidencia"),
    "Se contrastó el anexo con las bases.",
  );
  await u.click(screen.getByRole("button", { name: "Guardar revisión" }));
  expect((await screen.findByRole("alert")).textContent).toMatch(/rechazada/);
  expect(
    screen.getByLabelText("Justificación y referencia a la evidencia").value,
  ).toMatch(/anexo/);
});
test("cada empresa abre su ficha con sus documentos y la decisión de admisión", async () => {
  const conPostulante = {
    ...ficha,
    postulantes: [
      { id: 7, ruc: "00900000001", razon_social: "Aurora (demo)", representante: "Diego", oferta: 4200, experiencia: 7, admision_texto: "Pendiente de revisión", admisiones: [] },
      { id: 8, ruc: "00900000002", razon_social: "Horizonte (demo)", representante: "Rosa", oferta: 4950, experiencia: 3, admision_texto: "Pendiente de revisión", admisiones: [] },
    ],
    documentos: [
      { id: 1, postulante_id: 7, nombre: "aurora-oferta.pdf", tipo: "propuesta", version: 1, tamano: 3000, estado: "analizado" },
      { id: 2, postulante_id: 8, nombre: "horizonte-oferta.pdf", tipo: "propuesta", version: 1, tamano: 3000, estado: "analizado" },
      { id: 3, postulante_id: null, nombre: "bases.pdf", tipo: "bases", version: 1, tamano: 3000, estado: "analizado" },
    ],
    coincidencias: [],
  };
  request.mockImplementation((p) =>
    Promise.resolve(String(p).startsWith("/proveedores") ? { items: [] } : conPostulante),
  );
  const u = userEvent.setup();
  render(<Convocatorias id="12" usuario={usuario} />);
  expect(await screen.findByText("bases.pdf")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Documentos" })).toBeNull();
  await u.click(screen.getByRole("button", { name: /^Postulantes/ }));
  await u.click(await screen.findByText("Aurora (demo)"));
  expect(await screen.findByText("aurora-oferta.pdf")).toBeTruthy();
  expect(screen.queryByText("horizonte-oferta.pdf")).toBeNull();
  for (const b of ["Admitir", "Observar", "No admitir"])
    expect(screen.getByRole("button", { name: b })).toBeTruthy();
});
test("el perfil de consulta carece de acceso al expediente de evaluación", async () => {
  request.mockResolvedValue(ficha);
  render(<Convocatorias id="12" usuario={{ rol: "consulta" }} />);
  expect(await screen.findByText(/requiere un perfil/)).toBeTruthy();
  expect(request).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Documentos" })).toBeNull();
  expect(screen.queryByText("Cerrar recepción")).toBeNull();
});
test("la carga de un archivo vincula el documento al postulante y mantiene su contenido", async () => {
  request.mockResolvedValue({ id: 1 });
  await subir(
    12,
    new File(["Importe: 750"], "oferta.txt", { type: "text/plain" }),
    "anexo",
    9,
  );
  const [path, options] = request.mock.calls[0];
  expect(path).toBe("/convocatorias/12/documentos");
  expect(options.body.get("archivo").name).toBe("oferta.txt");
  expect(options.body.get("postulante_id")).toBe("9");
});
test("el asistente bloquea criterios que no suman 100 y conserva la etapa", async () => {
  const u = userEvent.setup();
  render(
    <Asistente
      original={{
        ...ficha,
        codigo: "DEMO",
        modalidad: "Servicios",
        area: "Gestión",
        responsable: "Ana Demo",
        apertura: "2026-11-01",
        cierre: "2026-12-01",
        intervinientes: [{ nombre: "Ana Demo", rol: "Comité" }],
      }}
    />,
  );
  for (let i = 0; i < 3; i++)
    await u.click(screen.getByRole("button", { name: "Continuar" }));
  fireEvent.change(screen.getByLabelText("Peso (%)"), {
    target: { value: "95" },
  });
  await u.click(screen.getByRole("button", { name: "Continuar" }));
  expect((await screen.findByRole("alert")).textContent).toContain("100");
  expect(request).not.toHaveBeenCalled();
});
test("la simulación usa importes de la ficha y escenarios devueltos por la API", async () => {
  const c = {
    id: 3,
    codigo: "C-3",
    espacio: "Cafetería",
    proveedor: "Aurora (demo)",
    cumplimiento: 95,
    ingresos: 700,
    costos: 250,
    contraprestacion: 310,
    pagos: [],
    obligaciones: [],
    alertas: [],
  };
  request.mockImplementation((p, o) =>
    Promise.resolve(
      o?.method === "POST"
        ? {
            perspectiva: "Operador",
            escenarios: [
              {
                nombre: "Central",
                ingresos: 700,
                costos: 250,
                contraprestacion: 310,
                flujo: 140,
              },
            ],
          }
        : c,
    ),
  );
  const u = userEvent.setup();
  render(<Concesiones id="3" usuario={usuario} />);
  await u.click(
    await screen.findByRole("button", { name: "Calcular escenarios" }),
  );
  expect(await screen.findByText("Central")).toBeTruthy();
  const [, options] = request.mock.calls.find(([p]) => p.endsWith("/simular"));
  expect(JSON.parse(options.body)).toEqual({
    ingresos: 700,
    costos: 250,
    contraprestacion: 310,
  });
});
