import React, { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  Building2,
  Check,
  ChevronRight,
  Layers,
  Scale,
  Search,
  ShieldAlert,
  Split,
  Users,
} from "lucide-react";
import { request } from "../api";
import {
  Aviso,
  Ayuda,
  Cargando,
  ErrorAmigable,
  EstadoRevision,
  FiltrosActivos,
  Prioridad,
  Vacio,
  Ventana,
  dia,
  mensajeAmigable,
} from "../ui/Ui";

// Centro de alertas v5.1: un solo lugar para las señales de reglas, coincidencias y
// trazabilidad, agrupadas en cinco categorías y con su evidencia explicada.

export const ICONOS = {
  fraccionamiento: Split,
  colusion: Users,
  conflicto: Scale,
  concentracion: Layers,
  control: ShieldAlert,
};
const ESTADOS = [
  ["abiertas", "Por atender (pendientes y en revisión)"],
  ["pendiente", "Pendiente de revisión"],
  ["en_revision", "En revisión"],
  ["revisada", "Revisada"],
  ["descartada", "Descartada"],
  ["", "Todas"],
];
const INICIAL = { categoria: "", prioridad: "", estado: "abiertas", desde: "", hasta: "", q: "" };
const enviar = (path, body) =>
  request(path, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) });

export function TarjetaAlerta({ a, abrir }) {
  const Icono = ICONOS[a.categoria] || ShieldAlert;
  return (
    <article className={"ca-tarjeta " + a.prioridad}>
      <div className="ca-icono" aria-hidden="true">
        <Icono size={18} />
      </div>
      <div className="ca-cuerpo">
        <div className="ca-linea">
          <Prioridad valor={a.prioridad} corto />
          <span className="ca-categoria">{a.categoria_texto}</span>
          <span className="ca-codigo">{a.codigo}</span>
          <EstadoRevision valor={a.estado} />
        </div>
        <h3>{a.titulo}</h3>
        <p className="ca-desc">{a.descripcion}</p>
        <p className="ca-meta">
          {a.empresas.length > 0 ? (
            a.empresas.map((e, i) =>
              e.id ? (
                <a key={i} href={"#empresas/" + e.id} onClick={(ev) => ev.stopPropagation()}>
                  <Building2 size={13} /> {e.nombre}
                </a>
              ) : (
                <span key={i}>
                  <Building2 size={13} /> {e.nombre}
                </span>
              ),
            )
          ) : (
            <span>Sin empresa vinculada</span>
          )}
          <span>
            {a.proceso.tipo}: {a.proceso.codigo}
          </span>
          <span>Fecha del hecho: {dia(a.fecha_hecho)}</span>
        </p>
      </div>
      <button className="ca-ver" onClick={() => abrir(a.uid)}>
        Ver detalle <ChevronRight size={15} />
      </button>
    </article>
  );
}

function Detalle({ uid, cerrar, alCambiar, escribe }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [decision, setDecision] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [errorForm, setErrorForm] = useState("");
  const [confirmar, setConfirmar] = useState(null);
  useEffect(() => {
    request("/centro-alertas/" + encodeURIComponent(uid)).then(setD, (e) => setError(e));
  }, [uid]);
  async function tomar() {
    setOcupado(true);
    try {
      const n = await enviar(`/centro-alertas/${uid}/tomar`);
      setD(n);
      alCambiar("La alerta pasó a «En revisión». Quedó registrado quién la tomó.");
    } catch (e) {
      setErrorForm(mensajeAmigable(e));
    } finally {
      setOcupado(false);
    }
  }
  async function guardar() {
    setOcupado(true);
    setErrorForm("");
    try {
      const n = await enviar(`/centro-alertas/${uid}/decision`, confirmar);
      setD(n);
      setDecision("");
      setConfirmar(null);
      alCambiar(n.estado === "revisada" ? "Revisión registrada en el historial." : "Alerta descartada con su justificación.");
    } catch (e) {
      setErrorForm(mensajeAmigable(e));
      setConfirmar(null);
    } finally {
      setOcupado(false);
    }
  }
  return (
    <Ventana titulo={d ? d.titulo : "Detalle de la alerta"} subtitulo={d ? `${d.uid} · ${d.categoria_texto}` : uid} cerrar={cerrar} ancha>
      <ErrorAmigable error={error} />
      {!d && !error && <Cargando texto="Reuniendo la evidencia…" />}
      {d && (
        <div className="ca-detalle">
          <div className="ca-linea">
            <Prioridad valor={d.prioridad} />
            <EstadoRevision valor={d.estado} />
            <span className="ca-codigo">Regla {d.codigo}</span>
          </div>
          <p className="ca-aviso">{d.aviso}</p>

          <section>
            <h3>Por qué se generó</h3>
            {d.explicacion.observado && <p>{d.explicacion.observado}</p>}
            {d.explicacion.criterio && (
              <p className="ca-criterio">
                <b>Criterio de detección:</b> {d.explicacion.criterio}
              </p>
            )}
            <p className="ca-criterio">
              <b>Sobre esta categoría:</b> {d.categoria_ayuda}
            </p>
          </section>

          {d.indicadores.length > 0 && (
            <section>
              <h3>Indicadores que activaron la alerta</h3>
              <dl className="ca-indicadores">
                {d.indicadores.map((x, i) => (
                  <div key={i}>
                    <dt>{x.nombre}</dt>
                    <dd>{x.valor}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          <section className="ca-dos">
            <div>
              <h3>Empresas involucradas</h3>
              {d.empresas.length ? (
                <ul className="ca-lista">
                  {d.empresas.map((e, i) => (
                    <li key={i}>
                      {e.id ? <a href={"#empresas/" + e.id}>{e.nombre}</a> : e.nombre}
                      <small>RUC {e.ruc || "no disponible"}</small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="ca-nd">No hay una empresa vinculada a esta señal.</p>
              )}
            </div>
            <div>
              <h3>Proceso relacionado</h3>
              <p>
                <a href={d.proceso.enlace}>
                  {d.proceso.tipo} {d.proceso.codigo} <ArrowRight size={13} />
                </a>
                <small className="ca-bloque">{d.proceso.nombre}</small>
                <small className="ca-bloque">{d.proceso.entidad}</small>
              </p>
            </div>
          </section>

          <section>
            <h3>Evidencias y registros relacionados</h3>
            <div className="ca-tabla">
              <table>
                <thead>
                  <tr>
                    <th>Registro</th>
                    <th>Fecha</th>
                    <th>Monto</th>
                    <th>Detalle</th>
                  </tr>
                </thead>
                <tbody>
                  {d.registros.map((r, i) => (
                    <tr key={i}>
                      <td>
                        {r.enlace ? <a href={r.enlace}>{r.codigo}</a> : r.codigo}
                        <small>{r.tipo}</small>
                      </td>
                      <td>{r.fecha ? dia(r.fecha) : "—"}</td>
                      <td>{r.monto || "—"}</td>
                      <td>{r.detalle}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {d.explicacion.revisar && (
            <section className="ca-revisar">
              <h3>Qué revisar</h3>
              <p>{d.explicacion.revisar}</p>
            </section>
          )}

          <section>
            <h3>Historial de la alerta</h3>
            <ol className="ca-historial">
              {d.historial.map((h, i) => (
                <li key={i}>
                  <b>{h.accion}</b> · {h.autor} · {h.fecha ? dia(h.fecha) : "fecha no disponible"}
                  {h.texto && <p>{h.texto}</p>}
                </li>
              ))}
            </ol>
          </section>

          {escribe && ["pendiente", "en_revision"].includes(d.estado) && (
            <section className="ca-acciones">
              <h3>Registrar la revisión</h3>
              {d.estado === "pendiente" && (
                <p className="ca-ayuda">
                  Si vas a analizarla, tómala primero: así el equipo sabe que alguien ya la está revisando.{" "}
                  <button onClick={tomar} disabled={ocupado}>
                    Tomar para revisión
                  </button>
                </p>
              )}
              <div className="ca-decisiones" role="group" aria-label="Decisión">
                <button aria-pressed={decision === "revisada"} className="ca-decision revisada" onClick={() => setDecision("revisada")}>
                  <Check size={15} /> Revisada: amerita seguimiento
                </button>
                <button aria-pressed={decision === "descartada"} className="ca-decision descartada" onClick={() => setDecision("descartada")}>
                  Descartada: no hay problema
                </button>
              </div>
              {decision && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    setConfirmar({ decision, justificacion: new FormData(e.currentTarget).get("justificacion").trim() });
                  }}
                >
                  <label>
                    Justificación (mínimo 15 caracteres, cita la evidencia revisada)
                    <textarea name="justificacion" required minLength={15} maxLength={2000} rows={3} />
                  </label>
                  {errorForm && (
                    <p className="ca-error" role="alert">
                      {errorForm}
                    </p>
                  )}
                  <div className="ca-pie">
                    <button type="button" onClick={() => setDecision("")}>
                      Cancelar
                    </button>
                    <button className="ui-primario" disabled={ocupado}>
                      Continuar
                    </button>
                  </div>
                </form>
              )}
              {!decision && errorForm && (
                <p className="ca-error" role="alert">
                  {errorForm}
                </p>
              )}
              {confirmar && (
                <div className="ca-confirmar" role="alertdialog" aria-label="Confirmar decisión">
                  <p>
                    Vas a marcar esta alerta como <b>{confirmar.decision === "revisada" ? "revisada" : "descartada"}</b>
                    {d.ids?.length > 1 ? ` (se aplica a los ${d.ids.length} registros del patrón)` : ""}. La decisión queda en el
                    historial con tu nombre y no se puede borrar. ¿Confirmas?
                  </p>
                  <div className="ca-pie">
                    <button onClick={() => setConfirmar(null)}>Volver</button>
                    <button className="ui-primario" onClick={guardar} disabled={ocupado}>
                      {ocupado ? "Guardando…" : "Sí, registrar"}
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </Ventana>
  );
}

export default function CentroAlertas({ usuario, id }) {
  const escribe = ["administrador", "analista"].includes(usuario?.rol);
  const [f, setF] = useState(() =>
    id?.startsWith("cat-") ? { ...INICIAL, categoria: id.slice(4) } : INICIAL,
  );
  const [buscar, setBuscar] = useState("");
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState(id && !id.startsWith("cat-") ? id : null);
  const [version, setVersion] = useState(0);
  const [aviso, setAviso] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setF((x) => (x.q === buscar ? x : { ...x, q: buscar })), 250);
    return () => clearTimeout(t);
  }, [buscar]);
  useEffect(() => {
    let vivo = true;
    setDatos((x) => (x ? { ...x, cargando: true } : x));
    const qs = new URLSearchParams({ ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)), pagina, tamano: 15 });
    request("/centro-alertas?" + qs).then(
      (d) => vivo && (setDatos(d), setError("")),
      (e) => vivo && setError(e),
    );
    return () => {
      vivo = false;
    };
  }, [f, pagina, version]);
  const cambiar = (k, v) => {
    setF((x) => ({ ...x, [k]: v }));
    setPagina(1);
  };
  const avisar = useCallback((t) => {
    setAviso(t);
    setVersion((v) => v + 1);
  }, []);
  const cerrarAviso = useCallback(() => setAviso(""), []);
  if (error && !datos) return <ErrorAmigable error={error} reintentar={() => setVersion((v) => v + 1)} />;
  if (!datos) return <Cargando texto="Cargando el centro de alertas…" />;
  if (!datos.resumen) return <ErrorAmigable error="La respuesta del servidor no tiene el formato esperado. Actualiza la página." />;
  const r = datos.resumen;
  const etiquetaEstado = ESTADOS.find(([k]) => k === f.estado)?.[1];
  return (
    <div className="ca">
      <Aviso texto={aviso} cerrar={cerrarAviso} />
      <p className="ca-intro">
        Aquí se reúnen todas las señales del sistema. <b>Son indicios para revisar, no pruebas</b>: cada una explica qué
        se observó, qué registros la originaron y qué conviene verificar.{" "}
        <Ayuda etiqueta="¿Cómo se detectan?">
          Las reglas comparan los registros de contrataciones (montos, fechas, proveedores y pagos), las personas y empresas
          de cada convocatoria y los controles de cada fase del expediente. Una alerta se cierra solo con una decisión
          humana justificada, que queda en el historial.
        </Ayuda>
      </p>

      <div className="ca-categorias">
        {Object.entries(r.por_categoria).map(([k, c]) => {
          const Icono = ICONOS[k];
          return (
            <button
              key={k}
              className={"ca-cat" + (f.categoria === k ? " activa" : "")}
              aria-pressed={f.categoria === k}
              onClick={() => cambiar("categoria", f.categoria === k ? "" : k)}
              title={c.ayuda}
            >
              <span className="ca-cat-top">
                <Icono size={17} aria-hidden="true" />
                <b>{c.abiertas}</b>
              </span>
              <span className="ca-cat-nombre">{c.nombre}</span>
              <small>{c.abiertas === 1 ? "1 por atender" : `${c.abiertas} por atender`} · {c.total} en total</small>
            </button>
          );
        })}
      </div>

      <div className="ca-prioridades" aria-label="Alertas por atender según prioridad">
        {["alta", "media", "baja"].map((p) => (
          <button key={p} className={"ca-prio " + p} aria-pressed={f.prioridad === p} onClick={() => cambiar("prioridad", f.prioridad === p ? "" : p)}>
            <Prioridad valor={p} corto /> <b>{r.por_prioridad[p] || 0}</b> por atender
          </button>
        ))}
      </div>

      <div className="ca-filtros">
        <label className="ca-buscar">
          <Search size={16} aria-hidden="true" />
          <input
            aria-label="Buscar alerta"
            placeholder="Buscar por empresa, RUC, proceso o código"
            value={buscar}
            onChange={(e) => {
              setBuscar(e.target.value);
              setPagina(1);
            }}
          />
        </label>
        <label>
          Estado
          <select value={f.estado} onChange={(e) => cambiar("estado", e.target.value)}>
            {ESTADOS.map(([k, t]) => (
              <option key={k} value={k}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          Prioridad
          <select value={f.prioridad} onChange={(e) => cambiar("prioridad", e.target.value)}>
            <option value="">Todas</option>
            <option value="alta">Alta</option>
            <option value="media">Media</option>
            <option value="baja">Baja</option>
          </select>
        </label>
        <label>
          Desde
          <input type="date" value={f.desde} max={f.hasta || undefined} onChange={(e) => cambiar("desde", e.target.value)} />
        </label>
        <label>
          Hasta
          <input type="date" value={f.hasta} min={f.desde || undefined} onChange={(e) => cambiar("hasta", e.target.value)} />
        </label>
      </div>
      <FiltrosActivos
        filtros={[
          ["categoria", r.por_categoria[f.categoria]?.nombre, f.categoria],
          ["prioridad", "Prioridad " + f.prioridad, f.prioridad],
          ["estado", etiquetaEstado, f.estado && f.estado !== "abiertas" ? f.estado : ""],
          ["desde", "Desde " + dia(f.desde), f.desde],
          ["hasta", "Hasta " + dia(f.hasta), f.hasta],
          ["q", "«" + f.q + "»", f.q],
        ]}
        quitar={(k) => {
          if (k === "q") setBuscar("");
          cambiar(k, k === "estado" ? "abiertas" : "");
        }}
        limpiar={() => {
          setBuscar("");
          setF(INICIAL);
          setPagina(1);
        }}
      />

      <p className="ca-conteo" aria-live="polite">
        {datos.cargando ? "Actualizando…" : `${datos.total} ${datos.total === 1 ? "alerta" : "alertas"}`}
        {f.estado === "abiertas" ? " por atender" : ""}, ordenadas por prioridad.
      </p>
      <ErrorAmigable error={error} />
      <div className="ca-lista-alertas">
        {datos.items.map((a) => (
          <TarjetaAlerta key={a.uid} a={a} abrir={setAbierta} />
        ))}
        {!datos.items.length && (
          <Vacio titulo="No hay alertas con estos filtros">
            Prueba quitando algún filtro o eligiendo «Todas» en el estado.
          </Vacio>
        )}
      </div>
      {datos.total > datos.tamano && (
        <div className="ca-paginas">
          <button disabled={pagina === 1} onClick={() => setPagina(pagina - 1)}>
            Anterior
          </button>
          <span>
            Página {pagina} de {Math.ceil(datos.total / datos.tamano)}
          </span>
          <button disabled={pagina * datos.tamano >= datos.total} onClick={() => setPagina(pagina + 1)}>
            Siguiente
          </button>
        </div>
      )}
      {abierta && (
        <Detalle
          key={abierta}
          uid={abierta}
          escribe={escribe}
          cerrar={() => {
            setAbierta(null);
            if (location.hash.startsWith("#alertas/") && !location.hash.startsWith("#alertas/cat-"))
              history.replaceState(null, "", "#alertas");
          }}
          alCambiar={avisar}
        />
      )}
    </div>
  );
}

// Bloque destacado para el resumen ejecutivo.
export function AlertasDestacadas() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    request("/centro-alertas?estado=abiertas&tamano=4").then(setD, setError);
  }, []);
  if (error || (d && !d.resumen)) return null;
  if (!d) return <Cargando texto="Cargando alertas…" />;
  const r = d.resumen;
  return (
    <section className="ca-destacadas" aria-labelledby="ca-destacadas-titulo">
      <div className="ca-destacadas-top">
        <div>
          <h2 id="ca-destacadas-titulo">
            <ShieldAlert size={20} aria-hidden="true" /> {r.abiertas} alertas por atender
          </h2>
          <p>
            <b className="ca-txt-alta">{r.por_prioridad.alta || 0} de prioridad alta</b> · {r.por_prioridad.media || 0} media ·{" "}
            {r.por_prioridad.baja || 0} baja. Son indicios para revisión humana, no conclusiones.
          </p>
        </div>
        <a className="ui-boton-primario" href="#alertas">
          Abrir centro de alertas <ArrowRight size={15} />
        </a>
      </div>
      <div className="ca-categorias compacta">
        {Object.entries(r.por_categoria).map(([k, c]) => {
          const Icono = ICONOS[k];
          return (
            <a key={k} className="ca-cat" href={"#alertas/cat-" + k} title={c.ayuda}>
              <span className="ca-cat-top">
                <Icono size={16} aria-hidden="true" />
                <b>{c.abiertas}</b>
              </span>
              <span className="ca-cat-nombre">{c.nombre}</span>
            </a>
          );
        })}
      </div>
      <h3 className="ca-sub">Las más urgentes</h3>
      <ul className="ca-urgentes">
        {d.items.map((a) => (
          <li key={a.uid}>
            <a href={"#alertas/" + a.uid}>
              <Prioridad valor={a.prioridad} corto />
              <span>
                <b>{a.titulo}</b>
                <small>
                  {a.empresas[0]?.nombre || a.proceso.nombre} · {a.proceso.codigo}
                </small>
              </span>
              <ChevronRight size={16} aria-hidden="true" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
