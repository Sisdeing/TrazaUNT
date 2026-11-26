import React, { useState } from "react";
import {
  Carga,
  ErrorAccion,
  Estado,
  Panel,
  Tabla,
  label,
  money,
  post,
  useAccion,
  useConsulta,
} from "./Comun";

function Registro({ ficha, done }) {
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState("");
  const query = useConsulta(
    "/proveedores?limite=25&pagina=1&q=" + encodeURIComponent(q),
  );
  const action = useAccion();
  function enviar(e) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    action.run(async () => {
      await post("/convocatorias/" + ficha.id + "/postulantes", {
        proveedor_id: Number(selected),
        oferta: Number(data.get("oferta")),
        experiencia: Number(data.get("experiencia")),
      });
      done();
    });
  }
  return (
    <details className="fl-fold">
      <summary>Registrar postulante</summary>
      <form onSubmit={enviar}>
        <label>
          Buscar proveedor por razón social o RUC
          <input
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setSelected("");
            }}
          />
        </label>
        <Carga query={query}>
          {(d) => (
            <label>
              Proveedor
              <select
                required
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="">Selecciona un proveedor</option>
                {d.items
                  .filter(
                    (v) =>
                      !ficha.postulantes.some((p) => p.proveedor_id === v.id),
                  )
                  .map((v) => (
                    <option value={v.id} key={v.id}>
                      {v.razon_social} · {v.ruc}
                    </option>
                  ))}
              </select>
            </label>
          )}
        </Carga>
        <div className="fl-grid">
          <label>
            Oferta económica (S/)
            <input
              type="number"
              name="oferta"
              required
              min="0.01"
              step="0.01"
            />
          </label>
          <label>
            Experiencia declarada (años)
            <input type="number" name="experiencia" required min="0" step="1" />
          </label>
        </div>
        <ErrorAccion error={action.error} />
        <button className="fl-primary" disabled={action.busy || !selected}>
          Guardar postulante
        </button>
      </form>
    </details>
  );
}
function Admision({ ficha, p, done }) {
  const action = useAccion();
  function guardar(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    action.run(async () => {
      await post(
        "/convocatorias/" + ficha.id + "/postulantes/" + p.id + "/admision",
        values,
      );
      done();
    });
  }
  return (
    <details className="fl-fold fl-no-print">
      <summary>Decidir admisión</summary>
      <form onSubmit={guardar}>
        <div className="fl-grid">
          <label>
            Decisión
            <select name="estado" required defaultValue="admitida">
              <option value="admitida">Admitida</option>
              <option value="observada">Observada (requiere subsanar)</option>
              <option value="no_admitida">No admitida</option>
            </select>
          </label>
        </div>
        <label>
          Motivo (la empresa verá este texto)
          <textarea name="motivo" required minLength="8" maxLength="2000" />
        </label>
        <ErrorAccion error={action.error} />
        <button className="fl-primary" disabled={action.busy}>
          Registrar decisión
        </button>
      </form>
    </details>
  );
}

export function Postulantes({ ficha, write, refresh }) {
  const decide =
    write && ["abierta", "cerrada", "en_evaluacion"].includes(ficha.estado);
  return (
    <Panel title="Postulantes y admisión">
      {write && ficha.estado === "abierta" && (
        <Registro ficha={ficha} done={refresh} />
      )}
      <Tabla
        headers={["Empresa", "RUC", "Oferta económica", "Experiencia", "Admisión"]}
        rows={ficha.postulantes.map((p) => (
          <tr key={p.id}>
            <th scope="row">
              {p.razon_social}
              <small>Representante: {p.representante}</small>
            </th>
            <td>{p.ruc}</td>
            <td>{money(p.oferta)}</td>
            <td>
              {p.experiencia ?? "No evaluado"}
              {p.experiencia != null ? " años" : ""}
            </td>
            <td>
              <Estado value={p.admision_texto || "Pendiente de revisión"} />
              {p.admisiones?.length > 0 && (
                <small>{p.admisiones.at(-1).motivo}</small>
              )}
              {decide && <Admision ficha={ficha} p={p} done={refresh} />}
            </td>
          </tr>
        ))}
        empty="Aún no se han registrado postulantes."
      />
      <p className="fl-help">
        Al registrar una empresa o un interviniente, el sistema compara
        automáticamente personas y empresas. Revisa el resultado en la pestaña
        Coincidencias.
      </p>
    </Panel>
  );
}

function csv(ficha, items) {
  const safe = (v) => {
    let s = String(v ?? "No evaluado");
    if (/^\s*[=+@-]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  const cells = [
    [
      "Convocatoria",
      "Versión",
      "Origen",
      "Postulante",
      "Oferta (S/)",
      "IFP",
      "Cobertura (%)",
      "Confianza",
      "Señales documentales",
    ],
    ...items.map((r) => [
      ficha.codigo,
      ficha.version_bases ?? ficha.version,
      "simulado",
      r.razon_social,
      r.oferta,
      r.ifp,
      r.cobertura,
      r.confianza,
      r.alertas.length,
    ]),
  ];
  const blob = new Blob(
    ["\uFEFF" + cells.map((row) => row.map(safe).join(";")).join("\r\n")],
    { type: "text/csv;charset=utf-8" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = ficha.codigo + "-comparacion.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function Calificacion({ ficha, p, done }) {
  const action = useAccion();
  const documentos = ficha.documentos.filter((d) => d.postulante_id === p.id);
  if (!documentos.length) return null;
  function submit(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    action.run(async () => {
      await post("/convocatorias/" + ficha.id + "/evaluaciones", {
        ...values,
        postulante_id: p.id,
        puntaje: Number(values.puntaje),
        documento_id: Number(values.documento_id),
      });
      done();
    });
  }
  return (
    <details className="fl-fold fl-no-print">
      <summary>Calificar criterio con evidencia</summary>
      <form onSubmit={submit}>
        <div className="fl-grid">
          <label>
            Criterio
            <select required name="criterio">
              {ficha.criterios.map((c) => (
                <option key={c.nombre}>{c.nombre}</option>
              ))}
            </select>
          </label>
          <label>
            Puntaje (0 a 100)
            <input
              required
              name="puntaje"
              type="number"
              min="0"
              max="100"
              step="0.01"
            />
          </label>
          <label>
            Documento de respaldo
            <select required name="documento_id">
              {documentos.map((d) => (
                <option value={d.id} key={d.id}>
                  {d.nombre} · v{d.version}
                </option>
              ))}
            </select>
          </label>
          <label>
            Página, hoja o sección
            <input required maxLength={110} name="ubicacion" />
          </label>
        </div>
        <label>
          Justificación de la calificación
          <textarea required minLength={8} maxLength={1000} name="motivo" />
        </label>
        <ErrorAccion error={action.error} />
        <button disabled={action.busy}>Guardar calificación</button>
      </form>
    </details>
  );
}
function DetallePostor({ p, abrir, docs, ficha, done }) {
  const evidencia = (id, ubicacion) =>
    id && docs ? (
      <button className="fl-link" onClick={() => abrir(id)}>
        {ubicacion || "Ver evidencia"}
      </button>
    ) : (
      ubicacion || "Sin referencia"
    );
  return (
    <article className="fl-candidato">
      <h3>{p.razon_social}</h3>
      <small>
        IFP {p.ifp ?? "No evaluado"} · Cobertura{" "}
        {p.cobertura == null ? "No evaluada" : p.cobertura + " %"} · Confianza{" "}
        {label(p.confianza)}
      </small>
      <h4>Matriz de requisitos</h4>
      <Tabla
        headers={["Requisito", "Estado", "Evidencia"]}
        rows={p.requisitos.map((r, i) => (
          <tr key={i}>
            <th scope="row">{r.requisito}</th>
            <td>
              <Estado value={r.estado} />
            </td>
            <td>{evidencia(r.documento_id, r.ubicacion)}</td>
          </tr>
        ))}
      />
      {p.criterios?.length > 0 && (
        <>
          <h4>Criterios puntuables</h4>
          <Tabla
            headers={["Criterio", "Peso", "Puntaje", "Evidencia"]}
            rows={p.criterios.map((c) => (
              <tr key={c.nombre}>
                <th scope="row">{c.nombre}</th>
                <td>{c.peso} %</td>
                <td>{c.puntaje ?? "Sin calificar"}</td>
                <td>{evidencia(c.documento_id, c.ubicacion)}</td>
              </tr>
            ))}
          />
          <p>
            Puntaje ponderado preliminar ·{" "}
            {p.puntaje_preliminar ?? "Pendiente de calificación"}
          </p>
          {docs && ficha.estado === "en_evaluacion" && (
            <Calificacion ficha={ficha} p={p} done={done} />
          )}
        </>
      )}
      {p.indicador_preventivo && (
        <>
          <h4>Indicador preventivo</h4>
          <p>
            <strong>
              {p.indicador_preventivo.nombre} ·{" "}
              {money(p.indicador_preventivo.valor)}
            </strong>
          </p>
          <p className="fl-help">
            {p.indicador_preventivo.explicacion}{" "}
            {evidencia(p.indicador_preventivo.documento_id)}
          </p>
        </>
      )}
      {!!p.alertas.length && (
        <>
          <h4>Señales documentales</h4>
          <ul className="fl-list">
            {p.alertas.map((a, i) => (
              <li key={i}>
                <strong>{a.regla}</strong> · {a.explicacion}
                <small>
                  {label(a.severidad)} ·{" "}
                  {evidencia(a.documento_id, a.ubicacion)}
                </small>
              </li>
            ))}
          </ul>
        </>
      )}
      {!!p.vinculaciones?.length && (
        <>
          <h4>Vinculaciones para revisión</h4>
          <ul className="fl-list">
            {p.vinculaciones.map((v, i) => (
              <li key={i}>
                <strong>{v.regla}</strong> · {v.motivo}
                {v.vinculo_id && (
                  <small>Revísala en la pestaña Coincidencias.</small>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}
export function Comparacion({ ficha, usuario, abrir, version }) {
  const [ids, setIds] = useState([]);
  const [edits, setEdits] = useState(0);
  const [pending, setPending] = useState(
    ficha.postulantes.slice(0, 5).map((p) => p.id),
  );
  const query = useConsulta(
    "/convocatorias/" +
      ficha.id +
      "/comparar" +
      (ids.length ? "?ids=" + ids.join(",") : ""),
    version + edits,
  );
  const [focused, setFocused] = useState("");
  const [printDate, setPrintDate] = useState(null);
  const time =
    printDate?.toLocaleString("es-PE", { timeZone: "America/Lima" }) || "";
  return (
    <Carga query={query}>
      {(d) => (
        <section className="fl-comparacion">
          <div className="fl-print-only">
            <h1>Informe comparativo de propuestas</h1>
            <p>
              {ficha.codigo} · {ficha.nombre}
            </p>
            <p>
              Fecha y hora de Lima {time} · Responsable{" "}
              {usuario?.nombre || usuario?.usuario} · Datos simulados · Versión{" "}
              {d.version}
            </p>
          </div>
          {ficha.postulantes.length > 5 && (
            <details className="fl-fold fl-no-print">
              <summary>Seleccionar hasta cinco postulantes</summary>
              <div className="fl-checkboxes">
                {ficha.postulantes.map((p) => (
                  <label key={p.id}>
                    <input
                      type="checkbox"
                      checked={pending.includes(p.id)}
                      disabled={!pending.includes(p.id) && pending.length === 5}
                      onChange={(e) =>
                        setPending((old) =>
                          e.target.checked
                            ? [...old, p.id]
                            : old.filter((id) => id !== p.id),
                        )
                      }
                    />
                    {p.razon_social}
                  </label>
                ))}
              </div>
              <button
                disabled={!pending.length}
                onClick={() => {
                  setIds([...pending]);
                  setFocused("");
                }}
              >
                Comparar selección
              </button>
            </details>
          )}
          <Panel
            title="Comparación de propuestas"
            action={
              d.items.length > 0 && (
                <div className="fl-actions fl-no-print">
                  <button onClick={() => csv(ficha, d.items)}>
                    Exportar CSV
                  </button>
                  <button
                    onClick={() => {
                      setPrintDate(new Date());
                      requestAnimationFrame(() => window.print());
                    }}
                  >
                    Imprimir informe
                  </button>
                </div>
              )
            }
          >
            <Tabla
              headers={[
                "Postulante",
                "Oferta",
                "IFP / 100",
                "Cobertura",
                "Documentos",
                "Señales",
              ]}
              rows={d.items.map((p) => (
                <tr key={p.id}>
                  <th scope="row">{p.razon_social}</th>
                  <td>{money(p.oferta)}</td>
                  <td>{p.ifp ?? "No evaluado"}</td>
                  <td>
                    {p.cobertura == null ? "No evaluada" : p.cobertura + " %"}
                  </td>
                  <td>{p.documentos}</td>
                  <td>{p.alertas.length}</td>
                </tr>
              ))}
              empty="Registra postulantes para comparar propuestas."
            />
          </Panel>
          {!!d.items.length && (
            <Panel
              title="Evidencia por postulante"
              action={
                <label className="fl-no-print">
                  Postulante
                  <select
                    value={focused}
                    onChange={(e) => setFocused(e.target.value)}
                  >
                    <option value="">Todos</option>
                    {d.items.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.razon_social}
                      </option>
                    ))}
                  </select>
                </label>
              }
            >
              {d.items.map((p) => (
                <div
                  key={p.id}
                  className={
                    focused && String(p.id) !== focused
                      ? "fl-only-print-row"
                      : ""
                  }
                >
                  <DetallePostor
                    p={p}
                    abrir={abrir}
                    docs={usuario?.rol !== "consulta"}
                    ficha={ficha}
                    done={() => setEdits((v) => v + 1)}
                  />
                </div>
              ))}
            </Panel>
          )}
          <div className="fl-print-only">
            <h3>Revisión humana</h3>
            {ficha.historial
              .filter((h) => h.motivo)
              .map((h, i) => (
                <p key={i}>
                  {h.fecha} · {h.autor} · {h.motivo}
                </p>
              ))}
            <p>
              Los indicadores apoyan la revisión y no constituyen una
              determinación legal ni una acusación. Verifique la información en
              la fuente oficial.
            </p>
          </div>
        </section>
      )}
    </Carga>
  );
}
