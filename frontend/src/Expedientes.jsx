import React, { useState, useEffect } from "react";
import { request, download } from "./api";
const money = (v) =>
  new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(
    v,
  );
const percent = (v) =>
  v == null ? "No definida" : (v * 100).toFixed(1) + " %";
const date = (v) =>
  v ? new Date(v).toLocaleString("es-PE", { timeZone: "America/Lima" }) : "";
function useData(path, version = 0) {
  const [state, setState] = useState({ data: null, loading: true, error: "" });
  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, loading: true, error: "" });
    request(path, { signal: controller.signal })
      .then((data) => setState({ data, loading: false, error: "" }))
      .catch((e) => {
        if (e.name !== "AbortError")
          setState({ data: null, loading: false, error: e.message });
      });
    return () => controller.abort();
  }, [path, version]);
  return state;
}
export function Badge({ value, color = "" }) {
  return <span className={"badge " + color}>{value}</span>;
}
function Load({ state, children }) {
  if (state.loading)
    return (
      <div className="loading" role="status">
        Cargando información…
      </div>
    );
  if (state.error)
    return (
      <div className="error" role="alert">
        {state.error}
      </div>
    );
  return children(state.data);
}
function Metrics({ items }) {
  return (
    <div className="metrics">
      {items.map(([label, value, detail]) => (
        <div className="metric" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
          <small>{detail}</small>
        </div>
      ))}
    </div>
  );
}
function Pagination({ data, page, setPage }) {
  return (
    <div className="pagination">
      <span>
        {data.total ? (page - 1) * data.tamano + 1 : 0}–
        {Math.min(page * data.tamano, data.total)} de {data.total}
      </span>
      <button disabled={page === 1} onClick={() => setPage(page - 1)}>
        Anterior
      </button>
      <button
        disabled={page * data.tamano >= data.total}
        onClick={() => setPage(page + 1)}
      >
        Siguiente
      </button>
    </div>
  );
}
function AlertTable({ items }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Expediente</th>
            <th>Señal de revisión</th>
            <th>Prioridad</th>
            <th>Estado</th>
            <th>Acción</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id}>
              <td>
                <strong>{a.codigo}</strong>
              </td>
              <td>
                {a.regla_id
                  .replace(/^R\d+_/, "")
                  .replaceAll("_", " ")
                  .toLowerCase()}
              </td>
              <td>
                <Badge value={a.score.toFixed(2)} color={a.semaforo} />
              </td>
              <td>
                <Badge value={a.estado} />
              </td>
              <td>
                <a
                  className="button"
                  href={"#expedientes/" + a.contratacion_id}
                >
                  Revisar
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!items.length && (
        <p className="empty">No hay alertas con estos filtros.</p>
      )}
    </div>
  );
}
function Filters({ alerts, config, onApply }) {
  return (
    <form
      className="filters"
      onSubmit={(e) => {
        e.preventDefault();
        onApply(Object.fromEntries(new FormData(e.currentTarget)));
      }}
    >
      <label>
        Buscar
        <input
          name="q"
          placeholder="Expediente, proveedor u objeto"
          maxLength={200}
        />
      </label>
      <label>
        Entidad
        <select name="entidad">
          <option value="">Todas las entidades</option>
          {config.entidades.map((e) => (
            <option key={e.id} value={e.id}>
              {e.nombre}
            </option>
          ))}
        </select>
      </label>
      {alerts && (
        <>
          <label>
            Estado
            <select name="estado">
              <option value="todos">Todos</option>
              {["pendiente", "confirmada", "descartada"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Severidad
            <select name="severidad">
              <option value="todas">Todas</option>
              {["alta", "media", "baja"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Regla
            <select name="regla">
              <option value="">Todas las reglas</option>
              {config.reglas.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nombre}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      <button className="primary" type="submit">
        Aplicar filtros
      </button>
    </form>
  );
}
function Listing({ alerts, config, version }) {
  const [filters, setFilters] = useState({}),
    [page, setPage] = useState(1);
  const query = new URLSearchParams({
    ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "")),
    pagina: page,
  });
  const state = useData(
    (alerts ? "/alertas" : "/expedientes") + "?" + query,
    version,
  );
  return (
    <>
      <Filters
        alerts={alerts}
        config={config}
        onApply={(f) => {
          setFilters(f);
          setPage(1);
        }}
      />
      <section className="panel">
        <Load state={state}>
          {(d) => (
            <>
              {alerts ? (
                <AlertTable items={d.items} />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Expediente</th>
                        <th>Objeto / proveedor</th>
                        <th>Monto</th>
                        <th>Prioridad</th>
                        <th>Acción</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.items.map((c) => (
                        <tr key={c.id}>
                          <td>
                            <strong>{c.codigo}</strong>
                            <small>{c.entidad}</small>
                          </td>
                          <td>
                            {c.objeto}
                            <small>{c.proveedor}</small>
                          </td>
                          <td className="nowrap">{money(c.monto)}</td>
                          <td>
                            <Badge
                              value={c.priorizacion.semaforo}
                              color={c.priorizacion.semaforo}
                            />
                          </td>
                          <td>
                            <a className="button" href={"#expedientes/" + c.id}>
                              Ver expediente
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!d.items.length && (
                    <p className="empty">
                      No hay expedientes con estos filtros.
                    </p>
                  )}
                </div>
              )}
              <Pagination data={d} page={page} setPage={setPage} />
            </>
          )}
        </Load>
      </section>
    </>
  );
}
export function RevisionForm({ alerta, onSaved, usuario }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    const form = e.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError("");
    try {
      const r = await request("/alertas/" + alerta.id + "/revision", {
        method: "POST",
        body: JSON.stringify({ ...values, estado_esperado: alerta.estado }),
      });
      onSaved(r.mensaje);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="revision">
      <p>
        Confirmar valida la pertinencia de la alerta. El analista debe sustentar
        su decisión.
      </p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <div className="form-grid">
        <label>
          Analista
          <input
            name="analista"
            defaultValue={usuario?.nombre}
            readOnly={!!usuario}
            required
            maxLength={150}
            placeholder="Nombre del revisor"
          />
        </label>
        <label>
          Decisión
          <select
            name="estado"
            required
            defaultValue={
              alerta.estado === "confirmada" ? "descartada" : "confirmada"
            }
          >
            <option
              value="confirmada"
              disabled={alerta.estado === "confirmada"}
            >
              Confirmar alerta
            </option>
            <option
              value="descartada"
              disabled={alerta.estado === "descartada"}
            >
              Descartar alerta
            </option>
          </select>
        </label>
      </div>
      <label>
        Comentario de revisión
        <textarea
          name="comentario"
          required
          maxLength={4000}
          placeholder="Indica qué verificaste y sustenta tu decisión"
        />
      </label>
      <button type="submit" className="primary" disabled={busy}>
        {busy ? "Guardando…" : "Guardar decisión"}
      </button>
    </form>
  );
}
const NOMBRE_REGLA = {
  R01: "Posible fraccionamiento",
  R02: "Concentración de contratos en un proveedor",
  R03: "Pago con sustento incompleto",
  R04: "Monto justo por debajo del umbral",
  R05: "Fechas incoherentes",
  R06: "Proveedor reciente con monto alto",
};
// Muestra la explicación de la regla en lenguaje claro, sin datos técnicos.
function ExplicacionRegla({ texto }) {
  const partes = {};
  for (const linea of String(texto || "").split("\n\n").at(-1).split("\n"))
    for (const [k, p] of [["observado", "Qué se observó:"], ["criterio", "Criterio aplicado:"], ["revisar", "Qué revisar:"]])
      if (linea.startsWith(p))
        partes[k] = linea
          .slice(p.length)
          .trim()
          .replace(/ \[(ID|contratación) \d+\]/g, "")
          .replace(/(y )?la agrupación por tokens canónicos «[^»]*»/, "con objeto similar")
          .replace("días inclusivos", "días");
  return (
    <dl className="fl-datos explicacion-regla">
      {[["Qué se observó", partes.observado], ["Criterio aplicado", partes.criterio], ["Qué revisar", partes.revisar]]
        .filter(([, v]) => v)
        .map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
    </dl>
  );
}
function HistoryItems({ items }) {
  return items.length ? (
    <div className="timeline">
      {items.map((b) => (
        <details key={b.id}>
          <summary>
            <Badge value={b.accion} /> <strong>{b.analista}</strong>
            <small>
              {date(b.fecha)} · Alerta {b.alerta_id}
            </small>
          </summary>
          <p className="hist-texto">
            {String(b.comentario).trim().startsWith("{")
              ? "El sistema volvió a evaluar la alerta con los datos actualizados."
              : b.comentario}
          </p>
        </details>
      ))}
    </div>
  ) : (
    <p className="empty">Sin movimientos registrados.</p>
  );
}
function Detail({ id, version, onSaved, usuario }) {
  const state = useData("/expedientes/" + id, version);
  return (
    <Load state={state}>
      {(d) => (
        <>
          <a className="back" href="#expedientes">
            ← Volver a expedientes
          </a>
          <Metrics
            items={[
              ["Expediente", d.contrato.codigo, d.contrato.entidad],
              ["Monto", money(d.contrato.monto), d.contrato.objeto],
              [
                "Prioridad",
                d.contrato.priorizacion.score.toFixed(2),
                "Semáforo " + d.contrato.priorizacion.semaforo,
              ],
              ["Proveedor", d.contrato.ruc, d.contrato.proveedor],
            ]}
          />
          <section className="panel">
            <h2>Recorrido del expediente</h2>
            <div className="journey">
              <div>
                <small>Constitución del proveedor</small>
                <strong>{d.contrato.fecha_constitucion}</strong>
              </div>
              <div>
                <small>Contratación</small>
                <strong>{d.contrato.fecha}</strong>
              </div>
              <div>
                <small>Participación</small>
                <strong>{d.contrato.n_postores} postores</strong>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Pago</th>
                    <th>Fecha</th>
                    <th>Monto</th>
                    <th>Conformidad</th>
                    <th>Comprobante</th>
                  </tr>
                </thead>
                <tbody>
                  {d.pagos.map((p) => (
                    <tr key={p.id}>
                      <td>{p.id}</td>
                      <td>{p.fecha_pago}</td>
                      <td>{money(p.monto)}</td>
                      <td>
                        {p.tiene_conformidad ? "Registrada" : "No registrada"}
                      </td>
                      <td>
                        {p.tiene_comprobante ? "Registrado" : "No registrado"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="panel">
            <h2>Explicación y prioridad</h2>
            <p className="explanation">{String(d.explicacion).split("\n\n")[0].replace(/ \[contratación \d+\]/g, "")}</p>
            <div className="score-breakdown">
              <span>
                Reglas <b>{d.contrato.priorizacion.aportes.reglas}</b>
              </span>
              <span>
                Rareza IA <b>{d.contrato.priorizacion.aportes.ia}</b>
              </span>
              <span>
                Total <b>{d.contrato.priorizacion.score}</b>
              </span>
            </div>
            <p className="fl-help">
              La señal estadística compara este contrato con el resto (monto, frecuencia del proveedor, concentración
              de la entidad, antigüedad del proveedor y número de postores). Solo ordena la revisión: no crea alertas
              ni demuestra irregularidades.
            </p>
          </section>
          {d.alertas.map((a) => (
            <section className="panel" key={a.id}>
              <div className="panel-head">
                <h2>{NOMBRE_REGLA[a.regla_id.slice(0, 3)] || a.regla_id.replaceAll("_", " ")}</h2>
                <Badge value={a.vigente ? a.estado : "No vigente"} />
              </div>
              <ExplicacionRegla texto={a.explicacion} />
              <p>
                <a href={"#alertas/R-" + a.id}>Ver esta alerta en el centro de alertas →</a>
              </p>
              {a.vigente &&
                ["administrador", "analista"].includes(usuario.rol) && (
                  <RevisionForm
                    key={a.estado}
                    alerta={a}
                    usuario={usuario}
                    onSaved={onSaved}
                  />
                )}
            </section>
          ))}
          <section className="panel">
            <h2>Historial de este expediente</h2>
            <HistoryItems items={d.historial} />
          </section>
        </>
      )}
    </Load>
  );
}
function History({ version }) {
  const [page, setPage] = useState(1);
  const state = useData("/historial?pagina=" + page, version);
  return (
    <>
      <div className="notice">
        Cada revisión conserva el nombre de la cuenta, su justificación y la
        hora de Lima.
      </div>
      <section className="panel">
        <Load state={state}>
          {(d) => (
            <>
              <HistoryItems items={d.items} />
              <Pagination data={d} page={page} setPage={setPage} />
            </>
          )}
        </Load>
      </section>
    </>
  );
}
function Reports({ onSaved }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function action(tipo) {
    setBusy(true);
    setError("");
    try {
      if (tipo === "actualizar") {
        const r = await request("/analisis", { method: "POST", body: "{}" });
        onSaved(r.mensaje);
      } else await download(tipo);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <section className="panel report">
        <small>RESULTADOS REPRODUCIBLES</small>
        <h2>El sustento de cada revisión</h2>
        <p>
          Exporta todas las alertas, incluidas las no vigentes, o el historial
          completo. Los CSV no contienen etiquetas individuales de evaluación.
        </p>
        <div className="actions">
          <button disabled={busy} onClick={() => action("alertas")}>
            Descargar alertas CSV
          </button>
          <button disabled={busy} onClick={() => action("historial")}>
            Descargar bitácora CSV
          </button>
        </div>
      </section>
      <section className="panel">
        <h2>Reevaluación del conjunto</h2>
        <p>
          Vuelve a ejecutar las reglas y la IA con la configuración actual. Las
          decisiones e historial se conservan y las alertas que dejan de
          activarse pasan a no vigentes.
        </p>
        <button
          className="primary"
          disabled={busy}
          onClick={() => action("actualizar")}
        >
          {busy ? "Procesando…" : "Actualizar análisis"}
        </button>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </section>
    </>
  );
}
function Evaluation({ version }) {
  const state = useData("/metricas", version);
  return (
    <Load state={state}>
      {(m) => (
        <>
          <Metrics
            items={[
              ["Precisión", percent(m.precision), "TP / (TP + FP)"],
              ["Recall", percent(m.recall), "TP / (TP + FN)"],
              ["Falsos positivos", m.fp, "Casos normales marcados"],
              ["Tasa de FP", percent(m.tasa_fp), "FP / (FP + TN)"],
            ]}
          />
          <section className="panel">
            <h2>Matriz de confusión</h2>
            <p>
              Unidad de evaluación: contratación con al menos una regla activada
            </p>
            <div className="matrix">
              <table>
                <caption>
                  Filas: escenario sintético. Columnas: resultado de reglas.
                </caption>
                <thead>
                  <tr>
                    <th>Escenario</th>
                    <th>Sin alerta</th>
                    <th>Con alerta</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th>Normal sintético</th>
                    <td className="good">
                      {m.tn}
                      <small>Verdaderos negativos</small>
                    </td>
                    <td className="bad">
                      {m.fp}
                      <small>Falsos positivos</small>
                    </td>
                  </tr>
                  <tr>
                    <th>Anomalía inyectada</th>
                    <td className="bad">
                      {m.fn}
                      <small>Falsos negativos</small>
                    </td>
                    <td className="good">
                      {m.tp}
                      <small>Verdaderos positivos</small>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <div className="notice">
            Los escenarios se construyeron para estas reglas. Un resultado alto
            no demuestra eficacia en casos reales. Isolation Forest se ajusta y
            evalúa sobre la misma muestra. Confirmar o descartar alertas no
            modifica estas métricas.
          </div>
        </>
      )}
    </Load>
  );
}
function Ethics() {
  return (
    <section className="panel prose">
      <h2>Señales para revisar</h2>
      <p>
        Todos los expedientes, proveedores y pagos son sintéticos. No
        representan contrataciones reales ni acreditan incumplimientos.
      </p>
      <h3>La decisión requiere revisión humana</h3>
      <p>
        El analista contrasta la evidencia y documenta su decisión. El score
        prioriza revisión y no mide una probabilidad de corrupción. El semáforo
        verde tampoco garantiza integridad.
      </p>
      <h3>Falsos positivos y transparencia</h3>
      <p>
        La concentración, la reciente constitución y la rareza pueden tener
        explicaciones legítimas. Los umbrales monetarios son didácticos y la
        base legal está marcada como verificar. La IA no crea alertas por sí
        sola.
      </p>
      <h3>Alcance de esta versión</h3>
      <p>
        React consulta una API Python local con paginación de servidor. El
        análisis sigue usando el conjunto completo en memoria y SQLite conserva
        un solo escritor. El acceso utiliza sesiones locales con permisos por
        rol. Quien administra el archivo SQLite puede modificar su contenido.
      </p>
      <div className="notice">
        Los registros de demostración son sintéticos. La decisión y su justificación corresponden al equipo responsable.
      </div>
    </section>
  );
}

export {
  useData,
  Load,
  Listing,
  Detail,
  History,
  Reports,
  Evaluation,
  Ethics,
  Pagination,
};
