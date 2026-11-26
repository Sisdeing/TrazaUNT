import React, { useEffect, useState } from "react";
import { request } from "./api";
import "./integridad.css";

function useConsulta(path, revision = 0) {
  const [state, setState] = useState({ busy: true });
  useEffect(() => {
    let active = true;
    setState({ busy: true });
    request(path)
      .then((data) => {
        if (active) setState({ data });
      })
      .catch((error) => {
        if (active) setState({ error: error.message });
      });
    return () => {
      active = false;
    };
  }, [path, revision]);
  return state;
}

function Carga({ state, children }) {
  if (state.busy)
    return (
      <p role="status" className="ig-muted">
        Consultando registros…
      </p>
    );
  if (state.error)
    return (
      <p role="alert" className="ig-error">
        {state.error}
      </p>
    );
  return children(state.data);
}

function Etiqueta({ children }) {
  return <span className="ig-tag">{children}</span>;
}

function PanelIFP({ data }) {
  return (
    <section className="ig-box">
      <div className="ig-heading">
        <div>
          <small>Ficha de proveedor</small>
          <h2>{data.razon_social}</h2>
        </div>
        <Etiqueta>{data.tipo}</Etiqueta>
      </div>
      <p className="ig-muted">
        RUC {data.ruc} · Corte {data.corte} · {data.modelo}
      </p>
      <div className="ig-kpis">
        <div>
          <span>Índice de fiabilidad</span>
          <strong>{data.ifp ?? "No evaluado"}</strong>
        </div>
        <div>
          <span>Cobertura</span>
          <strong>{data.cobertura} %</strong>
        </div>
        <div>
          <span>Confianza</span>
          <strong>{data.confianza}</strong>
        </div>
      </div>
      {data.tipo === "natural" && (
        <p className="ig-note">Evaluación con datos limitados.</p>
      )}
      {data.impedimentos.map((i) => (
        <p key={i.referencia} className="ig-note">
          <b>{i.estado}</b> · {i.accion} {i.referencia}
        </p>
      ))}
      <h3>Factores y evidencia</h3>
      {data.dimensiones.map((d) => (
        <details className="ig-factor" key={d.clave}>
          <summary>
            <span>{d.nombre}</span>
            <strong>
              {d.valor === null
                ? "No evaluado"
                : Math.round(100 * d.valor) + " / 100"}
            </strong>
          </summary>
          <p>
            {d.motivo} · Peso {d.peso}
          </p>
          {d.evidencia && (
            <>
              <p>
                {d.evidencia.referencia} · {d.evidencia.origen} · Vigente hasta{" "}
                {d.evidencia.vigente_hasta}
              </p>
              <dl className="ig-facts">
                {Object.entries(d.evidencia.datos).map(([k, v]) => (
                  <React.Fragment key={k}>
                    <dt>{k.replaceAll("_", " ")}</dt>
                    <dd>
                      {v === true ? "Sí" : v === false ? "No" : String(v)}
                    </dd>
                  </React.Fragment>
                ))}
              </dl>
            </>
          )}
        </details>
      ))}
      <p className="ig-foot">
        Las señales pendientes de revisión se consultan en{" "}
        <a href="#conflictos">Conflictos de interés</a>.
      </p>
    </section>
  );
}

function Ficha({ id, editable }) {
  const [revision, setRevision] = useState(0);
  const state = useConsulta("/proveedores/" + id, revision);
  const historial = useConsulta(
    "/proveedores/" + id + "/evaluaciones",
    revision,
  );
  const [actual, setActual] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function evaluar(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const r = await request("/proveedores/verificar", {
        method: "POST",
        body: JSON.stringify({
          ruc: state.data.ruc,
          categoria: f.get("categoria"),
          monto: f.get("monto") || null,
        }),
      });
      setActual(r);
      setRevision((x) => x + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function manual(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await request("/proveedores/" + id + "/verificaciones-manuales", {
        method: "POST",
        body: JSON.stringify({
          dimension: f.get("dimension"),
          resultado: f.get("resultado") === "si",
          referencia: f.get("referencia"),
          corte: f.get("corte"),
          vigente_hasta: f.get("vigente_hasta"),
        }),
      });
      setActual(null);
      setRevision((x) => x + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ig-stack">
      <a href="#proveedores">← Directorio de proveedores</a>
      <Carga state={state}>
        {(d) => (
          <>
            <PanelIFP data={actual || d} />
            {editable && (
              <section className="ig-box">
                <h3>Verificar proveedor</h3>
                <form onSubmit={evaluar} className="ig-form">
                  <label>
                    Perfil de evaluación
                    <select name="categoria">
                      {["servicios", "bienes", "obras", "concesiones"].map(
                        (x) => (
                          <option key={x} value={x}>
                            {x}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <label>
                    Monto referencial (S/)
                    <input
                      name="monto"
                      type="number"
                      min=".01"
                      step=".01"
                      placeholder="Opcional"
                    />
                  </label>
                  <button disabled={busy} className="ig-primary">
                    Guardar evaluación
                  </button>
                </form>
                {d.tipo !== "sin clasificar" && (
                  <details className="ig-factor">
                    <summary>Registrar verificación manual sintética</summary>
                    <form onSubmit={manual} className="ig-form">
                      <label>
                        Dato revisado
                        <select name="dimension">
                          <option value="sanciones">Sanción vigente</option>
                          <option value="obligaciones">
                            Obligaciones al día
                          </option>
                        </select>
                      </label>
                      <label>
                        Resultado
                        <select name="resultado">
                          <option value="si">Sí</option>
                          <option value="no">No</option>
                        </select>
                      </label>
                      <label>
                        Referencia de evidencia
                        <input
                          name="referencia"
                          minLength="5"
                          maxLength="120"
                          required
                        />
                      </label>
                      <label>
                        Fecha del dato
                        <input
                          name="corte"
                          type="date"
                          max={d.corte}
                          defaultValue={d.corte}
                          required
                        />
                      </label>
                      <label>
                        Vigente hasta
                        <input name="vigente_hasta" type="date" required />
                      </label>
                      <button disabled={busy}>Registrar evidencia</button>
                    </form>
                  </details>
                )}
              </section>
            )}
          </>
        )}
      </Carga>
      {error && (
        <p className="ig-error" role="alert">
          {error}
        </p>
      )}
      <section className="ig-box">
        <h3>Evaluaciones guardadas</h3>
        <Carga state={historial}>
          {(h) =>
            h.items.length ? (
              h.items.map((x) => (
                <details key={x.id} className="ig-factor">
                  <summary>
                    <span>
                      Evaluación {x.id} · {x.resultado.categoria}
                    </span>
                    <b>{x.resultado.ifp ?? "No evaluado"}</b>
                  </summary>
                  <p>
                    {new Date(x.fecha).toLocaleString("es-PE", {
                      timeZone: "America/Lima",
                    })}{" "}
                    · {x.responsable} · {x.resultado.modelo} · Cobertura{" "}
                    {x.resultado.cobertura} %
                  </p>
                  <p>
                    {x.resultado.dimensiones
                      .filter((d) => d.evidencia)
                      .map((d) => d.evidencia.referencia)
                      .join(" · ")}
                  </p>
                </details>
              ))
            ) : (
              <p className="ig-muted">Sin evaluaciones guardadas.</p>
            )
          }
        </Carga>
      </section>
    </div>
  );
}

function Publico() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const ruc = new FormData(e.currentTarget).get("ruc");
    setBusy(true);
    setData(null);
    setError("");
    try {
      setData(
        await request("/proveedores/verificar", {
          method: "POST",
          body: JSON.stringify({ ruc, modo: "publico" }),
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ig-box">
      <h3>Padrón público autorizado</h3>
      <p className="ig-muted">
        Consulta empresarial en el último padrón importado localmente.
      </p>
      <form className="ig-form" onSubmit={submit}>
        <label>
          RUC de persona jurídica
          <input
            name="ruc"
            inputMode="numeric"
            pattern="20[0-9]{9}"
            maxLength="11"
            required
          />
        </label>
        <button disabled={busy}>Consultar padrón</button>
      </form>
      {error && (
        <p role="alert" className="ig-error">
          {error}
        </p>
      )}
      {data && (
        <div role="status">
          <b>{data.estado}</b>
          {data.registro && (
            <p>
              {data.registro.razon_social} · {data.registro.estado} ·{" "}
              {data.registro.condicion} · Corte {data.registro.corte}
            </p>
          )}
          <p>
            <a href={data.fuente} target="_blank" rel="noreferrer">
              Fuente oficial SUNAT ↗
            </a>
          </p>
        </div>
      )}
    </div>
  );
}

function Directorio({ editable }) {
  const [tipo, setTipo] = useState("jurídica"),
    [q, setQ] = useState(""),
    [pagina, setPagina] = useState(1);
  const state = useConsulta(
    "/proveedores?" + new URLSearchParams({ q, pagina, tipo, limite: 12 }),
  );
  return (
    <div className="ig-stack">
      <div className="ig-controls">
        <div role="group" aria-label="Tipo de proveedor" className="ig-segment">
          {[
            ["jurídica", "Empresas"],
            ["natural", "Personas naturales"],
          ].map(([k, t]) => (
            <button
              key={k}
              aria-pressed={tipo === k}
              onClick={() => {
                setTipo(k);
                setPagina(1);
              }}
            >
              {t}
            </button>
          ))}
        </div>
        <label className="ig-search">
          <span>Buscar proveedor</span>
          <input
            value={q}
            placeholder="Razón social o RUC"
            onChange={(e) => {
              setQ(e.target.value);
              setPagina(1);
            }}
          />
        </label>
      </div>
      <section className="ig-box">
        <h2>
          Directorio de {tipo === "natural" ? "personas naturales" : "empresas"}
        </h2>
        <Carga state={state}>
          {(d) => (
            <>
              <div className="ig-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Proveedor</th>
                      <th>RUC sintético</th>
                      <th>Perfil</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.items.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <a href={"#proveedores/" + p.id}>{p.razon_social}</a>
                        </td>
                        <td>{p.ruc}</td>
                        <td>{p.tipo}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!d.items.length && (
                <p>Sin coincidencias con los filtros seleccionados.</p>
              )}
              <div className="ig-pager">
                <span>{d.total} registros</span>
                <button
                  disabled={pagina === 1}
                  onClick={() => setPagina((p) => p - 1)}
                >
                  Anterior
                </button>
                <span>
                  {pagina} / {Math.max(1, Math.ceil(d.total / 12))}
                </span>
                <button
                  disabled={pagina * 12 >= d.total}
                  onClick={() => setPagina((p) => p + 1)}
                >
                  Siguiente
                </button>
              </div>
            </>
          )}
        </Carga>
      </section>
      {editable && (
        <details className="ig-box">
          <summary>Verificar en padrón público offline</summary>
          <Publico />
        </details>
      )}
    </div>
  );
}

function Grafo({ caso }) {
  const consulta = useConsulta("/conflictos/" + caso.id + "/grafo");
  const [nodo, setNodo] = useState(null),
    [zoom, setZoom] = useState(100);
  return (
    <Carga state={consulta}>
      {(g) => (
        <section aria-label="Ruta del vínculo sintético">
          <div className="ig-controls">
            <label>
              Escala del grafo
              <select
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
              >
                {[80, 100, 125, 150].map((v) => (
                  <option key={v} value={v}>
                    {v} %
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="ig-scroll">
            <div
              className="ig-graph"
              style={{
                minWidth: Math.round((520 * zoom) / 100),
                fontSize: zoom + "%",
              }}
            >
              {g.nodos.map((n, i) => (
                <React.Fragment key={n.id}>
                  {i > 0 && <span aria-hidden="true">→</span>}
                  <button
                    aria-pressed={nodo === n.id}
                    onClick={() => setNodo(n.id)}
                  >
                    <small>
                      {
                        [
                          caso.rol,
                          "Familiar · grado " + caso.grado,
                          caso.cargo,
                          "Convocatoria",
                        ][i]
                      }
                    </small>
                    {n.nombre}
                  </button>
                </React.Fragment>
              ))}
            </div>
          </div>
          {nodo != null && (
            <p role="status">
              {g.aristas
                .filter((a) => a.desde === nodo || a.hasta === nodo)
                .map(
                  (a) =>
                    g.nodos[a.desde].nombre +
                    " → " +
                    a.relacion +
                    " → " +
                    g.nodos[a.hasta].nombre,
                )
                .join(" · ")}
              . Evidencia {g.evidencia}.
            </p>
          )}
        </section>
      )}
    </Carga>
  );
}

function Conflictos({ declaraciones, editable, id }) {
  const [rev, setRev] = useState(0),
    [seleccion, setSeleccion] = useState(id ? Number(id) : null);
  const state = useConsulta("/conflictos", rev);
  const [error, setError] = useState(""),
    [ok, setOk] = useState(""),
    [busy, setBusy] = useState(false);
  async function guardar(e, caso) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    setOk("");
    try {
      await request("/declaraciones", {
        method: "POST",
        body: JSON.stringify({
          vinculo_id: caso.id,
          accion: f.get("accion"),
          motivo: f.get("motivo"),
        }),
      });
      setOk("Revisión registrada.");
      setRev((v) => v + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ig-stack">
      {ok && <p role="status">{ok}</p>}
      {error && (
        <p className="ig-error" role="alert">
          {error}
        </p>
      )}
      <Carga state={state}>
        {(d) => {
          if (!d.items.length)
            return (
              <div className="ig-box">
                Sin vinculaciones verificables al corte.
              </div>
            );
          const c = d.items.find((x) => x.id === seleccion) || d.items[0];
          return (
            <>
              <div className="ig-controls">
                <label>
                  Vinculación
                  <select
                    value={c.id}
                    onChange={(e) => setSeleccion(Number(e.target.value))}
                  >
                    {d.items.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.proceso} · {i.proveedor}
                      </option>
                    ))}
                  </select>
                </label>
                <Etiqueta>Corte {d.corte}</Etiqueta>
              </div>
              <section className="ig-box">
                <div className="ig-heading">
                  <div>
                    <small>{c.proceso}</small>
                    <h2>{c.proveedor}</h2>
                  </div>
                  <Etiqueta>{c.estado}</Etiqueta>
                </div>
                {!declaraciones && (
                  <>
                    <Grafo key={c.id} caso={c} />
                    <p className="ig-muted">
                      {c.evidencia} · Desde {c.desde}
                    </p>
                    {c.senales.map((s) => (
                      <div className="ig-signal" key={s.regla}>
                        <strong>{s.regla}</strong>
                        <p>{s.motivo}</p>
                      </div>
                    ))}
                  </>
                )}
                <a href={"#proveedores/" + c.proveedor_id}>
                  Consultar ficha del proveedor →
                </a>
              </section>
              {editable && (
                <section className="ig-box">
                  <h3>Registrar revisión humana</h3>
                  <form className="ig-form" onSubmit={(e) => guardar(e, c)}>
                    <label>
                      Acción
                      <select name="accion">
                        {[
                          "aclaración solicitada",
                          "conflicto declarado",
                          "sin conflicto declarado",
                          "abstención registrada",
                          "descargo solicitado",
                          "cierre justificado",
                        ].map((x) => (
                          <option key={x}>{x}</option>
                        ))}
                      </select>
                    </label>
                    <label className="ig-wide">
                      Justificación
                      <textarea
                        name="motivo"
                        minLength="8"
                        maxLength="1000"
                        required
                      />
                    </label>
                    <button disabled={busy} className="ig-primary">
                      Registrar revisión
                    </button>
                  </form>
                </section>
              )}
              <section className="ig-box">
                <h3>Declaraciones y actuaciones</h3>
                {c.historial.length ? (
                  c.historial.map((h) => (
                    <div key={h.id} className="ig-factor">
                      <b>{h.accion}</b>
                      <p>{h.motivo}</p>
                      <small>
                        {h.responsable} ·{" "}
                        {new Date(h.fecha).toLocaleString("es-PE", {
                          timeZone: "America/Lima",
                        })}
                      </small>
                    </div>
                  ))
                ) : (
                  <p className="ig-muted">
                    Aún no se han registrado actuaciones para este vínculo.
                  </p>
                )}
              </section>
            </>
          );
        }}
      </Carga>
    </div>
  );
}

export default function Integridad({
  vista = "proveedores",
  id,
  usuario,
  rol,
}) {
  const editable = ["administrador", "analista"].includes(rol ?? usuario?.rol);
  const identificador = id || window.location.hash.split("/")[1];
  if (vista === "proveedores")
    return identificador ? (
      <Ficha key={identificador} id={identificador} editable={editable} />
    ) : (
      <Directorio editable={editable} />
    );
  return (
    <Conflictos
      key={vista + String(identificador || "")}
      id={identificador}
      declaraciones={vista === "declaraciones"}
      editable={editable}
    />
  );
}
