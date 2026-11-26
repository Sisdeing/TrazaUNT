import React, { useState } from "react";
import { request } from "../api";
import {
  Datos,
  ErrorAccion,
  Panel,
  fecha,
  money,
  post,
  useAccion,
} from "./Comun";

const pasos = [
  "Datos generales",
  "Bases",
  "Requisitos",
  "Criterios",
  "Intervinientes",
  "Revisión",
];
const formas = [
  "Servicios",
  "Bienes",
  "Obras",
  "Concesión",
  "Arrendamiento",
  "Explotación económica",
  "Otra",
];
const inicial = {
  nombre: "",
  codigo: "",
  modalidad: "Servicios",
  area: "",
  objeto: "",
  descripcion: "",
  ubicacion: "",
  presupuesto: "",
  duracion_meses: "",
  apertura: "",
  cierre: "",
  responsable: "",
  requisitos: [""],
  criterios: [{ nombre: "", peso: 100 }],
  intervinientes: [{ nombre: "", rol: "Responsable" }],
};

export async function subir(id, archivo, tipo, postulante) {
  const form = new FormData();
  form.set("archivo", archivo);
  form.set("tipo", tipo);
  if (postulante) form.set("postulante_id", String(postulante));
  return request("/convocatorias/" + id + "/documentos", {
    method: "POST",
    body: form,
  });
}
export function Asistente({ original, alSalir }) {
  const [form, setForm] = useState(() =>
    original
      ? Object.fromEntries(
          Object.keys(inicial).map((k) => [k, original[k] ?? inicial[k]]),
        )
      : inicial,
  );
  const [step, setStep] = useState(0);
  const [files, setFiles] = useState([]);
  const [saved, setSaved] = useState(null);
  const [warning, setWarning] = useState("");
  const action = useAccion();
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  function editRow(key, i, v) {
    set(
      key,
      form[key].map((r, idx) => (idx === i ? v : r)),
    );
  }
  function field(key, name, type = "text", required = true, attrs = {}) {
    return (
      <label>
        {name}
        <input
          type={type}
          required={required}
          value={form[key]}
          onChange={(e) => set(key, e.target.value)}
          {...attrs}
        />
      </label>
    );
  }
  function rows(key, title, blank, render) {
    return (
      <fieldset className="fl-rows">
        <legend>{title}</legend>
        {form[key].map((row, i) => (
          <div className="fl-row" key={i}>
            {render(row, i)}
            <button
              type="button"
              aria-label={"Quitar fila " + (i + 1)}
              disabled={form[key].length === 1}
              onClick={() =>
                set(
                  key,
                  form[key].filter((_, n) => n !== i),
                )
              }
            >
              Quitar
            </button>
          </div>
        ))}
        <button type="button" onClick={() => set(key, [...form[key], blank])}>
          Añadir fila
        </button>
      </fieldset>
    );
  }
  function next(event) {
    event.preventDefault();
    setWarning("");
    if (
      step === 3 &&
      Math.abs(form.criterios.reduce((s, c) => s + Number(c.peso), 0) - 100) >
        0.000001
    ) {
      setWarning("Los pesos deben sumar 100 %.");
      return;
    }
    if (step < 5) {
      setStep(step + 1);
      return;
    }
    action.run(async () => {
      let draft = saved;
      if (!draft) {
        const body = {
          ...form,
          presupuesto: Number(form.presupuesto),
          duracion_meses: Number(form.duracion_meses),
          criterios: form.criterios.map((c) => ({
            ...c,
            peso: Number(c.peso),
          })),
          intervinientes: form.intervinientes.map(({ documento, ...p }) =>
            documento ? { ...p, documento } : p,
          ),
        };
        if (original) body.version = original.version;
        draft = await post(
          "/convocatorias" + (original ? "/" + original.id : ""),
          body,
          original ? "PATCH" : "POST",
        );
        setSaved(draft);
      }
      for (const file of files) {
        await subir(draft.id, file, "bases");
        setFiles((f) => f.filter((v) => v !== file));
      }
      if (alSalir) alSalir(draft.id);
      else window.location.hash = "convocatorias/" + draft.id;
    });
  }
  return (
    <>
      <a
        href={original ? "#convocatorias/" + original.id : "#convocatorias"}
        onClick={
          alSalir
            ? (e) => {
                e.preventDefault();
                alSalir(original?.id);
              }
            : undefined
        }
      >
        ← {original ? "Volver a la ficha" : "Convocatorias"}
      </a>
      <Panel title={original ? "Editar borrador" : "Nueva convocatoria"}>
        <ol className="fl-steps" aria-label="Etapas de la convocatoria">
          {pasos.map((p, i) => (
            <li key={p} aria-current={i === step ? "step" : undefined}>
              <span>{i + 1}</span>
              {p}
            </li>
          ))}
        </ol>
        <form onSubmit={next}>
          <h3>{pasos[step]}</h3>
          {step === 0 && (
            <>
              <div className="fl-grid">
                {field("nombre", "Nombre de la convocatoria", "text", true, {
                  maxLength: 160,
                })}
                {field("codigo", "Código", "text", true, {
                  minLength: 2,
                  maxLength: 40,
                  pattern: "[\\p{L}\\p{N}_.\\-]{2,40}",
                  title: "De 2 a 40 letras, números, guiones o puntos",
                })}
                <label>
                  Modalidad
                  <select
                    value={form.modalidad}
                    onChange={(e) => set("modalidad", e.target.value)}
                  >
                    {[...new Set([...formas, form.modalidad])].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                {field("area", "Área responsable")}
                {field("responsable", "Responsable")}
                {field("ubicacion", "Ubicación (opcional)", "text", false)}
                {field(
                  "presupuesto",
                  "Importe referencial (S/)",
                  "number",
                  true,
                  { min: "0.01", step: "0.01" },
                )}
                {field("duracion_meses", "Duración (meses)", "number", true, {
                  min: 1,
                  max: 600,
                  step: 1,
                })}
                {field("apertura", "Fecha de apertura", "date")}
                {field("cierre", "Fecha de cierre", "date", true, {
                  min: form.apertura,
                })}
              </div>
              <label>
                Objeto
                <textarea
                  required
                  minLength={3}
                  maxLength={3000}
                  value={form.objeto}
                  onChange={(e) => set("objeto", e.target.value)}
                />
              </label>
              <label>
                Descripción (opcional)
                <textarea
                  value={form.descripcion}
                  onChange={(e) => set("descripcion", e.target.value)}
                />
              </label>
            </>
          )}
          {step === 1 && (
            <>
              <p className="fl-help">
                Selecciona las bases o anexos que se guardarán con el borrador.
                También puedes cargarlos desde su ficha.
              </p>
              <label>
                Adjuntar bases y anexos
                <input
                  type="file"
                  multiple
                  accept=".pdf,.docx,.xlsx,.txt,.csv"
                  onChange={(e) => setFiles(Array.from(e.target.files))}
                />
              </label>
              <ul>
                {files.map((f, i) => (
                  <li key={i}>{f.name}</li>
                ))}
              </ul>
            </>
          )}
          {step === 2 &&
            rows("requisitos", "Requisitos de admisibilidad", "", (r, i) => (
              <label>
                Requisito {i + 1}
                <input
                  required
                  value={r}
                  onChange={(e) => editRow("requisitos", i, e.target.value)}
                />
              </label>
            ))}
          {step === 3 &&
            rows(
              "criterios",
              "Criterios ponderados",
              { nombre: "", peso: "" },
              (r, i) => (
                <>
                  <label>
                    Criterio {i + 1}
                    <input
                      required
                      value={r.nombre}
                      onChange={(e) =>
                        editRow("criterios", i, {
                          ...r,
                          nombre: e.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    Peso (%)
                    <input
                      type="number"
                      required
                      step="0.01"
                      min="0.01"
                      max="100"
                      value={r.peso}
                      onChange={(e) =>
                        editRow("criterios", i, { ...r, peso: e.target.value })
                      }
                    />
                  </label>
                </>
              ),
            )}
          {step === 4 &&
            rows(
              "intervinientes",
              "Personas que intervienen",
              { nombre: "", rol: "" },
              (r, i) => (
                <>
                  <label>
                    Nombre {i + 1}
                    <input
                      required
                      value={r.nombre}
                      onChange={(e) =>
                        editRow("intervinientes", i, {
                          ...r,
                          nombre: e.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    Función
                    <input
                      required
                      value={r.rol}
                      onChange={(e) =>
                        editRow("intervinientes", i, {
                          ...r,
                          rol: e.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    DNI (opcional, para comparar identidades)
                    <input
                      inputMode="numeric"
                      pattern="[0-9]{8}"
                      maxLength="8"
                      value={r.documento || ""}
                      onChange={(e) =>
                        editRow("intervinientes", i, {
                          ...r,
                          documento: e.target.value.replace(/\D/g, ""),
                        })
                      }
                    />
                  </label>
                </>
              ),
            )}
          {step === 5 && (
            <>
              <Datos
                items={[
                  ["Convocatoria", form.nombre],
                  ["Código", form.codigo],
                  ["Modalidad", form.modalidad],
                  ["Área", form.area],
                  ["Importe", money(Number(form.presupuesto))],
                  ["Plazo", form.duracion_meses + " meses"],
                  ["Apertura", fecha(form.apertura)],
                  ["Cierre", fecha(form.cierre)],
                  ["Responsable", form.responsable],
                ]}
              />
              <p>{form.objeto}</p>
              <h4>Requisitos y criterios</h4>
              <ul>
                {form.requisitos.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
                {form.criterios.map((c, i) => (
                  <li key={"c" + i}>
                    {c.nombre} · {c.peso} %
                  </li>
                ))}
              </ul>
              <h4>Intervinientes</h4>
              <ul>
                {form.intervinientes.map((p, i) => (
                  <li key={i}>
                    {p.nombre} · {p.rol}
                  </li>
                ))}
              </ul>
              {!!files.length && (
                <p>
                  Archivos por adjuntar: {files.map((f) => f.name).join(", ")}
                </p>
              )}
              {saved && (
                <p role="status">
                  Borrador guardado. Puedes reintentar la carga pendiente o{" "}
                  <a href={"#convocatorias/" + saved.id}>abrir su ficha</a>.
                </p>
              )}
            </>
          )}
          <ErrorAccion error={warning || action.error} />
          <div className="fl-actions">
            {step > 0 && (
              <button
                type="button"
                disabled={action.busy || !!saved}
                onClick={() => {
                  setStep(step - 1);
                  setWarning("");
                }}
              >
                Anterior
              </button>
            )}
            <button className="fl-primary" disabled={action.busy}>
              {step < 5
                ? "Continuar"
                : action.busy
                  ? "Guardando…"
                  : saved
                    ? "Reintentar carga"
                    : "Guardar borrador"}
            </button>
          </div>
        </form>
      </Panel>
    </>
  );
}
