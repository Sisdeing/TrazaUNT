import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronDown,
  Download,
  FileText,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Upload,
  X,
} from "lucide-react";
import { request } from "../api";
import "./traza.css";

// Trazabilidad integrada en la aplicación (v5.1). Reemplaza la página aparte
// trazabilidad.html: misma API, pero solo muestra las acciones válidas para el
// estado de cada fase y agrupa la información en cuatro pestañas.

const ESTADO_FASE = {
  pendiente: ["Pendiente", "gris"],
  en_ejecucion: ["En curso", "azul"],
  en_revision: ["En revisión", "azul"],
  observada: ["Observada", "ambar"],
  en_subsanacion: ["En subsanación", "ambar"],
  validada: ["Con visto bueno", "azul"],
  cerrada: ["Cerrada", "verde"],
  reabierta: ["Reabierta", "ambar"],
  cancelada: ["Cancelada", "gris"],
};
const ESTADO_REQ = {
  pendiente: ["Falta documento", "gris"],
  presentado: ["Por verificar", "azul"],
  validado: ["Verificado", "verde"],
  observado: ["Observado", "ambar"],
};
const EVENTO = {
  crear_expediente: "Expediente creado",
  iniciar: "Fase iniciada",
  cargar_documento: "Documento subido",
  verificar: "Documento verificado",
  observar: "Observación registrada",
  subsanar: "Subsanación presentada",
  cerrar_observacion: "Subsanación verificada",
  visto_bueno: "Visto bueno",
  pago: "Pago registrado",
  cerrar: "Fase cerrada",
  reabrir: "Fase reabierta",
  asignar: "Responsable asignado",
  revision_alerta: "Alerta revisada",
  hecho_publicado: "Hito publicado",
  asiento_cid: "Asiento del cuaderno de obra",
};
const REGLA = {
  TZ01: "Se avanzó sin cerrar la fase anterior",
  TZ02: "Requisito obligatorio sin verificar",
  TZ04: "Pago sin conformidad completa",
  TZ05: "Observación pendiente en una fase que ya avanzó",
  TZ06: "Una misma cuenta en funciones que deben estar separadas",
  TZ08: "Plazo de la fase vencido",
  TZ09: "Monto pagado inconsistente",
  TZ11: "Avance sin verificación previa",
  TZ13: "Documento modificado: su huella ya no coincide",
  TZ14: "Fase reabierta más de una vez",
};
const EN_CURSO = ["en_ejecucion", "en_revision", "observada", "en_subsanacion"];
const SUBIR = [...EN_CURSO, "reabierta"];

const texto = (v) => String(v ?? "").replaceAll("_", " ");
const dinero = (v) =>
  v === "" || v == null
    ? "No disponible"
    : new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(Number(v));
const dia = (v) =>
  v
    ? new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeZone: "America/Lima" }).format(
        new Date(v.length === 10 ? v + "T12:00:00-05:00" : v),
      )
    : "Sin fecha";
const momento = (v) =>
  v
    ? new Intl.DateTimeFormat("es-PE", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "America/Lima",
      }).format(new Date(v))
    : "—";
const hoy = () => new Date().toISOString().slice(0, 10);
const origen = (e) =>
  e.datos?.origen === "publico" ? "publico" : e.datos?.sintetico ? "demo" : "local";
const ORIGEN = {
  publico: ["Fuente pública", "verde"],
  demo: ["Demostración", "ambar"],
  local: ["Registro local", "azul"],
};
const enviar = (path, body) =>
  request(path, {
    method: "POST",
    ...(body instanceof FormData ? { body } : { body: JSON.stringify(body) }),
  });

function Chip({ par, children }) {
  const [t, tono] = par || [children, "gris"];
  return <span className={"tz-chip " + tono}>{t}</span>;
}
function estadoFase(f, publico) {
  if (publico && f.estado === "pendiente") return ["Sin verificar", "gris"];
  return ESTADO_FASE[f.estado] || [texto(f.estado), "gris"];
}

/* ---------------------------------------------------------------- ventana */
function Ventana({ titulo, subtitulo, cerrar, children, ancho }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => d?.open && d.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={"tz-ventana " + (ancho ? "ancha" : "")}
      onClose={cerrar}
      onCancel={(e) => {
        e.preventDefault();
        cerrar();
      }}
      aria-label={titulo}
    >
      <div className="tz-ventana-top">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <small>{subtitulo}</small>}
        </div>
        <button type="button" className="tz-icono" aria-label="Cerrar" onClick={cerrar}>
          <X size={18} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function Formulario({ titulo, subtitulo, cerrar, enviarCon, boton = "Guardar", children, ayuda }) {
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  return (
    <Ventana titulo={titulo} subtitulo={subtitulo} cerrar={cerrar}>
      {ayuda && <p className="tz-ayuda">{ayuda}</p>}
      <form
        className="tz-form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (ocupado) return;
          setOcupado(true);
          setError("");
          try {
            await enviarCon(new FormData(e.currentTarget));
            cerrar();
          } catch (ex) {
            setError(ex.message);
          } finally {
            setOcupado(false);
          }
        }}
      >
        {children}
        {error && (
          <p className="tz-error" role="alert">
            {error}
          </p>
        )}
        <div className="tz-form-pie">
          <button type="button" onClick={cerrar}>
            Cancelar
          </button>
          <button className="tz-primario" disabled={ocupado}>
            {ocupado ? "Guardando…" : boton}
          </button>
        </div>
      </form>
    </Ventana>
  );
}

/* ------------------------------------------------------------------ lista */
function Lista({ escribe }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [vista, setVista] = useState(null);
  const [q, setQ] = useState("");
  const [anio, setAnio] = useState("");
  const [pagina, setPagina] = useState(1);
  const [nuevo, setNuevo] = useState(false);
  useEffect(() => {
    request("/trazabilidad")
      .then((d) => setDatos(d.items))
      .catch((e) => setError(e.message));
  }, []);
  const grupos = useMemo(() => {
    const items = datos || [];
    return {
      tramite: items.filter((e) => origen(e) !== "publico"),
      alertas: items.filter((e) => e.alertas > 0),
      publicos: items.filter((e) => origen(e) === "publico"),
      todos: items,
    };
  }, [datos]);
  if (error) return <p className="tz-error">{error}</p>;
  if (!datos) return <p className="tz-cargando">Cargando expedientes…</p>;
  const actual = vista || (grupos.tramite.length ? "tramite" : "todos");
  const anios = [...new Set(grupos[actual].map((e) => e.inicio?.slice(0, 4)).filter(Boolean))]
    .sort()
    .reverse();
  const filtrados = grupos[actual].filter(
    (e) =>
      (!anio || e.inicio?.slice(0, 4) === anio) &&
      (e.codigo +
        " " +
        e.nombre +
        " " +
        (e.area || "") +
        " " +
        (e.datos?.registro_publico?.id_fuente || "") +
        " " +
        (e.datos?.registro_publico?.codigo_convocatoria || ""))
        .toLowerCase()
        .includes(q.toLowerCase()),
  );
  const paginas = Math.max(1, Math.ceil(filtrados.length / 15));
  const p = Math.min(pagina, paginas);
  const VISTAS = [
    ["tramite", "En trámite"],
    ["alertas", "Con alertas"],
    ["publicos", "Registros públicos"],
    ["todos", "Todos"],
  ];
  return (
    <div className="tz">
      <p className="tz-intro">
        Cada contratación avanza por 8 fases. Abre un expediente para ver en qué fase va, qué
        documentos faltan y qué alertas tiene.
      </p>
      <div className="tz-barra">
        <div className="tz-segmentos" role="group" aria-label="Qué expedientes ver">
          {VISTAS.map(([k, t]) => (
            <button
              key={k}
              aria-pressed={actual === k}
              onClick={() => {
                setVista(k);
                setPagina(1);
                setAnio("");
              }}
            >
              {t} <b>{grupos[k].length}</b>
            </button>
          ))}
        </div>
        {escribe && (
          <button className="tz-primario" onClick={() => setNuevo(true)}>
            <Plus size={16} /> Nuevo expediente
          </button>
        )}
      </div>
      <div className="tz-filtros">
        <label className="tz-buscar">
          <Search size={16} aria-hidden="true" />
          <input
            aria-label="Buscar expediente"
            placeholder="Buscar por código, nombre o código SEACE"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPagina(1);
            }}
          />
        </label>
        {anios.length > 1 && (
          <select aria-label="Año" value={anio} onChange={(e) => (setAnio(e.target.value), setPagina(1))}>
            <option value="">Todos los años</option>
            {anios.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
        )}
      </div>
      <div className="tz-lista">
        {filtrados.slice((p - 1) * 15, p * 15).map((e) => {
          const cerradas = Math.round((e.avance * 8) / 100);
          return (
            <a key={e.id} className="tz-fila" href={"#trazabilidad/" + e.id}>
              <div className="tz-fila-txt">
                <small>
                  {e.codigo} · {texto(e.tipo)} · {e.inicio?.slice(0, 4) || "sin fecha"}
                </small>
                <strong>{e.nombre}</strong>
              </div>
              <Chip par={ORIGEN[origen(e)]} />
              <div className="tz-mini" aria-label={cerradas + " de 8 fases cerradas"}>
                <div className="tz-mini-barra">
                  {Array.from({ length: 8 }, (_, i) => (
                    <i key={i} className={i < cerradas ? "on" : ""} />
                  ))}
                </div>
                <small>{cerradas} de 8 fases</small>
              </div>
              <div className="tz-fila-alerta">
                {e.alertas > 0 ? (
                  <span className="tz-chip ambar">
                    <AlertTriangle size={13} /> {e.alertas} {e.alertas === 1 ? "alerta" : "alertas"}
                  </span>
                ) : (
                  <small>Sin alertas</small>
                )}
              </div>
            </a>
          );
        })}
        {!filtrados.length && <p className="tz-vacio">No hay expedientes con ese filtro.</p>}
      </div>
      {paginas > 1 && (
        <div className="tz-paginas">
          <small>
            {filtrados.length} expedientes · página {p} de {paginas}
          </small>
          <button disabled={p === 1} onClick={() => setPagina(p - 1)}>
            Anterior
          </button>
          <button disabled={p === paginas} onClick={() => setPagina(p + 1)}>
            Siguiente
          </button>
        </div>
      )}
      {actual === "publicos" && (
        <p className="tz-nota">
          Los registros públicos provienen de OCDS, SEACE y el Cuaderno de Obra Digital. No acreditan
          conformidades, pagos ni verificaciones internas: esas fases figuran como «sin verificar».
        </p>
      )}
      {nuevo && <NuevoExpediente cerrar={() => setNuevo(false)} />}
    </div>
  );
}

function NuevoExpediente({ cerrar }) {
  return (
    <Formulario
      titulo="Nuevo expediente"
      subtitulo="Se crean las 8 fases con sus requisitos según el tipo de contratación."
      cerrar={cerrar}
      boton="Crear expediente"
      enviarCon={async (fd) => {
        const d = Object.fromEntries(fd);
        const r = await enviar("/trazabilidad", d);
        location.hash = "#trazabilidad/" + r.id;
      }}
    >
      <label>
        Nombre
        <input name="nombre" required maxLength={200} placeholder="Ej.: Mantenimiento de ascensores 2026" />
      </label>
      <label>
        Objeto de la contratación
        <textarea name="objeto" required rows={2} maxLength={4000} />
      </label>
      <div className="tz-dos">
        <label>
          Área usuaria
          <input name="area" required maxLength={150} />
        </label>
        <label>
          Responsable principal
          <input name="responsable" required maxLength={150} />
        </label>
      </div>
      <div className="tz-tres">
        <label>
          Tipo
          <select name="tipo" defaultValue="servicios">
            <option value="servicios">Servicios</option>
            <option value="bienes">Bienes</option>
            <option value="obras">Obras</option>
            <option value="concesion">Concesión</option>
            <option value="otros">Otro</option>
          </select>
        </label>
        <label>
          Fecha de inicio
          <input name="inicio" type="date" required defaultValue={hoy()} />
        </label>
        <label>
          Monto (S/)
          <input name="monto" type="number" min="0" step="0.01" required />
        </label>
      </div>
    </Formulario>
  );
}

/* ------------------------------------------------------- pasos (stepper) */
function Pasos({ exp, actual, elegir }) {
  const publico = origen(exp) === "publico";
  const alertasPorFase = {};
  exp.alertas
    .filter((a) => a.vigente && a.estado === "pendiente")
    .forEach((a) => (alertasPorFase[a.fase_id] = (alertasPorFase[a.fase_id] || 0) + 1));
  return (
    <ol className="tz-pasos" aria-label="Fases del expediente">
      {exp.fases.map((f) => {
        const [t, tono] = estadoFase(f, publico);
        return (
          <li key={f.id} className={tono + (f.id === actual ? " actual" : "")}>
            <button onClick={() => elegir(f.id)} aria-current={f.id === actual ? "step" : undefined}>
              <span className="tz-punto">
                {f.estado === "cerrada" ? <Check size={15} strokeWidth={3} /> : f.orden}
                {alertasPorFase[f.id] > 0 && <i className="tz-punto-alerta" aria-label="Con alertas" />}
              </span>
              <span className="tz-paso-nombre">{f.nombre}</span>
              <small>{t}</small>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/* --------------------------------------------------------- detalle fase */
function siguientePaso(exp, f) {
  const anteriorAbierta = exp.fases.find((x) => x.orden < f.orden && x.estado !== "cerrada");
  const obs = f.observaciones.filter((o) => o.estado !== "cerrada");
  const faltan = f.requisitos.filter((q) => q.obligatorio && q.estado !== "validado");
  if (["pendiente", "reabierta"].includes(f.estado))
    return anteriorAbierta
      ? {
          texto: `Esta fase podrá iniciarse cuando se cierre «${anteriorAbierta.nombre}».`,
          accion: "iniciar",
          etiqueta: "Iniciar fase",
          bloqueado: true,
        }
      : {
          texto:
            f.estado === "reabierta"
              ? "La fase fue reabierta. Iníciala de nuevo para corregir y volver a verificar."
              : "Inicia la fase para poder subir sus documentos.",
          accion: "iniciar",
          etiqueta: "Iniciar fase",
        };
  if (EN_CURSO.includes(f.estado)) {
    if (obs.length)
      return {
        texto: `Hay ${obs.length} ${obs.length === 1 ? "observación" : "observaciones"} por resolver. Subsánalas y verifica la corrección.`,
      };
    if (faltan.length)
      return {
        texto: `Faltan ${faltan.length} de ${f.requisitos.length} requisitos por verificar. Sube cada documento y verifícalo.`,
      };
    return {
      texto: "Todos los requisitos están verificados. Ya puedes dar el visto bueno.",
      accion: "visto_bueno",
      etiqueta: "Dar visto bueno",
    };
  }
  if (f.estado === "validada") {
    const pagado = exp.eventos.some((e) => e.fase_id === f.id && e.accion === "pago");
    if (f.orden === 7 && !pagado) {
      const conformidad = exp.fases.find((x) => x.orden === 6);
      return conformidad && conformidad.estado !== "cerrada"
        ? {
            texto: "Para registrar el pago, primero debe cerrarse la fase de Conformidad.",
            accion: "pago",
            etiqueta: "Registrar pago",
            bloqueado: true,
          }
        : { texto: "Registra el pago antes de cerrar la fase.", accion: "pago", etiqueta: "Registrar pago" };
    }
    return { texto: "La fase tiene visto bueno. Ciérrala para pasar a la siguiente.", accion: "cerrar", etiqueta: "Cerrar fase" };
  }
  if (f.estado === "cerrada") return { texto: "Fase cerrada. Todo quedó registrado.", hecho: true };
  return { texto: "Sin acciones disponibles." };
}

function Fase({ exp, f, escribe, abrir }) {
  const publico = origen(exp) === "publico";
  const paso = siguientePaso(exp, f);
  const [menu, setMenu] = useState(false);
  const vencida = f.limite && f.limite < hoy() && f.estado !== "cerrada";
  const obsAbiertas = (q) =>
    f.observaciones.some((o) => o.estado !== "cerrada" && (o.requisito_id == null || o.requisito_id === q.id));
  const extras = [
    !["pendiente", "cerrada"].includes(f.estado) && ["observar", "Registrar observación"],
    f.estado !== "cerrada" && ["asignar", "Cambiar responsable o plazo"],
    ["validada", "cerrada"].includes(f.estado) && ["reabrir", "Reabrir fase"],
  ].filter(Boolean);
  const eventos = exp.eventos.filter((e) => e.fase_id === f.id).slice().reverse();
  const [todos, setTodos] = useState(false);
  return (
    <section className="tz-fase">
      <div className="tz-fase-top">
        <div>
          <small>
            Fase {f.orden} de {exp.fases.length} · {f.codigo}
          </small>
          <h2>{f.nombre}</h2>
          <p className="tz-meta">
            Responsable: <b>{f.responsable || "Sin asignar"}</b>
            <span>·</span>
            Plazo:{" "}
            <b className={vencida ? "tz-rojo" : ""}>
              {f.limite ? dia(f.limite) : "No documentado"}
              {vencida && " (vencido)"}
            </b>
          </p>
        </div>
        <Chip par={estadoFase(f, publico)} />
      </div>

      {escribe && (
        <div className={"tz-siguiente " + (paso.hecho ? "hecho" : "")}>
          <div>
            <small>{paso.hecho ? "Estado" : "Siguiente paso"}</small>
            <p>{paso.texto}</p>
          </div>
          <div className="tz-siguiente-botones">
            {paso.accion && (
              <button
                className="tz-primario"
                disabled={paso.bloqueado}
                onClick={() => abrir({ tipo: "accion", accion: paso.accion, fase: f })}
              >
                {paso.etiqueta}
              </button>
            )}
            {extras.length > 0 && (
              <div className="tz-menu">
                <button aria-expanded={menu} onClick={() => setMenu(!menu)}>
                  Más acciones <ChevronDown size={15} />
                </button>
                {menu && (
                  <div className="tz-menu-lista" role="menu">
                    {extras.map(([a, t]) => (
                      <button
                        key={a}
                        role="menuitem"
                        onClick={() => {
                          setMenu(false);
                          abrir({ tipo: "accion", accion: a, fase: f });
                        }}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <h3>Requisitos</h3>
      <ul className="tz-requisitos">
        {f.requisitos.map((q) => {
          const docs = f.documentos.filter((d) => d.requisito_id === q.id);
          const ultimo = docs.at(-1);
          const puedeSubir = escribe && SUBIR.includes(f.estado);
          const puedeVerificar =
            escribe && EN_CURSO.includes(f.estado) && ultimo && q.estado !== "validado" && !obsAbiertas(q);
          return (
            <li key={q.id} className={"tz-req " + (ESTADO_REQ[q.estado]?.[1] || "gris")}>
              <span className="tz-req-icono" aria-hidden="true">
                {q.estado === "validado" ? <Check size={15} strokeWidth={3} /> : <FileText size={15} />}
              </span>
              <div className="tz-req-txt">
                <strong>
                  {q.nombre}
                  {!q.obligatorio && <small> (opcional)</small>}
                </strong>
                {ultimo ? (
                  <a href={`/api/trazabilidad/${exp.id}/documentos/${ultimo.id}`}>
                    <Download size={13} /> {ultimo.nombre} · versión {ultimo.version} · {dia(ultimo.fecha)}
                  </a>
                ) : (
                  <small>Todavía no se sube ningún documento.</small>
                )}
              </div>
              <Chip par={ESTADO_REQ[q.estado] || [texto(q.estado), "gris"]} />
              <div className="tz-req-botones">
                {puedeSubir && (
                  <button onClick={() => abrir({ tipo: "subir", fase: f, requisito: q })}>
                    <Upload size={14} /> {ultimo ? "Nueva versión" : "Subir"}
                  </button>
                )}
                {puedeVerificar && (
                  <button
                    className="tz-secundario"
                    onClick={() =>
                      abrir({ tipo: "accion", accion: "verificar", fase: f, requisito: q, documento: ultimo })
                    }
                  >
                    <Check size={14} /> Verificar
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {f.observaciones.length > 0 && (
        <>
          <h3>Observaciones</h3>
          <div className="tz-observaciones">
            {f.observaciones.map((o) => (
              <article key={o.id} className={"tz-obs " + (o.estado === "cerrada" ? "cerrada" : "")}>
                <div className="tz-obs-top">
                  <strong>OBS-{o.id}</strong>
                  <Chip par={["Gravedad " + texto(o.severidad), o.severidad === "alta" ? "rojo" : "ambar"]} />
                  <Chip
                    par={
                      o.estado === "cerrada"
                        ? ["Resuelta", "verde"]
                        : o.estado === "respondida"
                          ? ["Subsanación por verificar", "azul"]
                          : ["Pendiente", "ambar"]
                    }
                  />
                </div>
                <p>{o.descripcion}</p>
                <small>
                  Debe atender: {o.responsable} · plazo {dia(o.limite)} · registró {o.autor}
                </small>
                {o.respuestas.map((r, i) => (
                  <p key={i} className="tz-respuesta">
                    <b>{EVENTO[r.accion] || texto(r.accion)}</b> · {r.actor} · {momento(r.fecha)}
                    <br />
                    {r.texto}
                  </p>
                ))}
                {escribe && f.estado !== "cerrada" && o.estado !== "cerrada" && (
                  <div className="tz-obs-botones">
                    {o.estado === "pendiente" && (
                      <button onClick={() => abrir({ tipo: "accion", accion: "subsanar", fase: f, observacion: o })}>
                        Presentar subsanación
                      </button>
                    )}
                    {o.estado === "respondida" && (
                      <>
                        <button
                          className="tz-secundario"
                          onClick={() => abrir({ tipo: "accion", accion: "cerrar_observacion", fase: f, observacion: o })}
                        >
                          <Check size={14} /> Verificar subsanación
                        </button>
                        <button onClick={() => abrir({ tipo: "accion", accion: "subsanar", fase: f, observacion: o })}>
                          Agregar respuesta
                        </button>
                      </>
                    )}
                  </div>
                )}
              </article>
            ))}
          </div>
        </>
      )}

      {publico && <HitosPublicos exp={exp} f={f} />}

      <h3>Actividad de la fase</h3>
      {eventos.length ? (
        <ol className="tz-actividad">
          {(todos ? eventos : eventos.slice(0, 5)).map((e) => (
            <Evento key={e.id} e={e} />
          ))}
        </ol>
      ) : (
        <p className="tz-vacio">Aún no hay actividad en esta fase.</p>
      )}
      {eventos.length > 5 && (
        <button className="tz-enlace" onClick={() => setTodos(!todos)}>
          {todos ? "Ver menos" : `Ver las ${eventos.length} actuaciones`}
        </button>
      )}
    </section>
  );
}

function Evento({ e, fase }) {
  const t = e.datos?.titulo || e.datos?.actividad || EVENTO[e.accion] || texto(e.accion);
  return (
    <li className="tz-evento">
      <span className="tz-evento-punto" aria-hidden="true" />
      <div>
        <strong>{t}</strong>
        {fase && <small className="tz-evento-fase">{fase}</small>}
        <small>
          {momento(e.fecha)}
          {e.efectiva && e.efectiva !== e.fecha && ` · fecha efectiva ${e.efectiva.slice(0, 10)}`} · {e.responsable || e.actor}
          {e.responsable && e.actor !== e.responsable && ` (cuenta ${e.actor})`}
        </small>
        {e.datos?.justificacion && <p>{e.datos.justificacion}</p>}
        {e.accion === "pago" && (
          <p>
            Autorizado {dinero(e.datos.autorizado)} · pagado {dinero(e.datos.pagado)}
          </p>
        )}
      </div>
    </li>
  );
}

function HitosPublicos({ exp, f }) {
  const hitos = exp.eventos.filter((e) => e.fase_id === f.id && e.accion === "hecho_publicado");
  const fuentes = (exp.datos?.registro_publico?.fuentes || []).filter((x) => x.fase === f.orden);
  if (!hitos.length && !fuentes.length) return null;
  return (
    <div className="tz-publico">
      <h3>Lo que dice la fuente pública</h3>
      {hitos.map((e) => (
        <p key={e.id}>
          <b>{e.efectiva?.slice(0, 10)}</b> · {e.datos.actividad}
        </p>
      ))}
      <Fuentes lista={fuentes} />
    </div>
  );
}

function Fuentes({ lista }) {
  const seguro = (u) => {
    try {
      const x = new URL(u);
      return x.protocol === "https:" ? x.href : "";
    } catch {
      return "";
    }
  };
  const items = (lista || []).filter((x) => seguro(x.url) || x.archivo);
  if (!items.length) return null;
  return (
    <ul className="tz-fuentes">
      {items.map((x, i) => (
        <li key={i}>
          {seguro(x.url) ? (
            <a href={seguro(x.url)} target="_blank" rel="noopener noreferrer">
              {x.titulo}
            </a>
          ) : (
            x.titulo
          )}{" "}
          <small>· {x.tipo}</small>
        </li>
      ))}
    </ul>
  );
}

/* ---------------------------------------------------------------- pestañas */
function Alertas({ exp, escribe, abrir }) {
  const vigentes = exp.alertas.filter((a) => a.vigente);
  const historicas = exp.alertas.filter((a) => !a.vigente);
  const fase = (id) => exp.fases.find((f) => f.id === id);
  if (!exp.alertas.length)
    return (
      <p className="tz-vacio grande">
        Este expediente no tiene alertas. Usa «Revisar alertas» después de cada cambio importante.
      </p>
    );
  const tarjeta = (a) => {
    const origenFase = fase(a.evidencia?.origen_fase_id);
    const pendiente = a.vigente && a.estado === "pendiente";
    return (
      <article key={a.id} className={"tz-alerta " + (pendiente ? "" : "revisada")}>
        <div className="tz-alerta-top">
          <span className="tz-codigo">{a.regla}</span>
          <strong>{REGLA[a.regla] || a.regla}</strong>
          <Chip
            par={
              !a.vigente
                ? ["Ya no aplica", "gris"]
                : a.estado === "pendiente"
                  ? ["Por revisar", "ambar"]
                  : a.estado === "descartada"
                    ? ["Descartada", "gris"]
                    : ["Revisada", "verde"]
            }
          />
        </div>
        <p>{a.descripcion}</p>
        <small>
          Detectada en: <b>{fase(a.fase_id)?.nombre}</b>
          {origenFase && origenFase.id !== a.fase_id && (
            <>
              {" "}
              · posible origen: <b>{origenFase.nombre}</b>
            </>
          )}
        </small>
        <div className="tz-alerta-botones">
          <button onClick={() => abrir({ tipo: "incidente", alerta: a })}>Ver qué pasó</button>
          {escribe && pendiente && (
            <button className="tz-secundario" onClick={() => abrir({ tipo: "revision", alerta: a })}>
              Registrar revisión
            </button>
          )}
        </div>
      </article>
    );
  };
  return (
    <div className="tz-alertas">
      <p className="tz-ayuda">
        Una alerta es una señal para revisar, no una acusación. Toda alerta se cierra con una decisión
        justificada que queda en el historial.
      </p>
      {vigentes.map(tarjeta)}
      {historicas.length > 0 && (
        <details className="tz-detalles">
          <summary>Alertas que ya no aplican ({historicas.length})</summary>
          {historicas.map(tarjeta)}
        </details>
      )}
    </div>
  );
}

function Documentos({ exp }) {
  const filas = exp.fases.flatMap((f) =>
    f.documentos.map((d) => ({ ...d, fase: f, requisito: f.requisitos.find((q) => q.id === d.requisito_id) })),
  );
  if (!filas.length) return <p className="tz-vacio grande">Todavía no se subió ningún documento.</p>;
  return (
    <div className="tz-tabla">
      <table>
        <thead>
          <tr>
            <th>Documento</th>
            <th>Fase · requisito</th>
            <th>Versión</th>
            <th>Subido por</th>
            <th>Estado</th>
            <th title="Huella digital SHA-256">Huella</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((d) => (
            <tr key={d.id}>
              <td>
                <a href={`/api/trazabilidad/${exp.id}/documentos/${d.id}`}>
                  <Download size={13} /> {d.nombre}
                </a>
              </td>
              <td>
                {d.fase.orden}. {d.fase.nombre}
                <small>{d.requisito?.nombre}</small>
              </td>
              <td>v{d.version}</td>
              <td>
                {d.autor}
                <small>
                  {d.registrado_por} · {dia(d.fecha)}
                </small>
              </td>
              <td>
                <Chip par={d.estado === "validado" ? ["Verificado", "verde"] : [texto(d.estado), "azul"]} />
              </td>
              <td>
                <code title={d.sha256}>{d.sha256.slice(0, 12)}…</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Historial({ exp }) {
  const nombre = (id) => {
    const f = exp.fases.find((x) => x.id === id);
    return f ? `Fase ${f.orden} · ${f.nombre}` : "Expediente";
  };
  return (
    <ol className="tz-actividad completo">
      {exp.eventos
        .slice()
        .reverse()
        .map((e) => (
          <Evento key={e.id} e={e} fase={nombre(e.fase_id)} />
        ))}
    </ol>
  );
}

function InfoPublica({ exp }) {
  const r = exp.datos?.registro_publico;
  const c = exp.datos?.cid;
  const asientos = exp.eventos.filter((v) => v.accion === "asiento_cid");
  return (
    <div className="tz-info">
      {r && (
        <section>
          <h3>Información publicada</h3>
          <dl className="tz-dl">
            <div>
              <dt>Procedimiento</dt>
              <dd>{r.id_fuente}</dd>
            </div>
            {r.codigo_convocatoria && (
              <div>
                <dt>Código SEACE</dt>
                <dd>{r.codigo_convocatoria}</dd>
              </div>
            )}
            {r.modalidad && (
              <div>
                <dt>Modalidad</dt>
                <dd>{r.modalidad}</dd>
              </div>
            )}
            <div>
              <dt>Valor referencial</dt>
              <dd>{dinero(exp.monto)}</dd>
            </div>
            <div>
              <dt>Proveedores</dt>
              <dd>{r.proveedores?.join(", ") || "No incorporados en la fuente"}</dd>
            </div>
          </dl>
          {r.analisis_historico && (
            <p className="tz-ayuda">
              Atipicidad estadística frente a {r.analisis_historico.categoria}: percentil{" "}
              {r.analisis_historico.percentil_atipicidad}
              {r.analisis_historico.senal ? " (se sugiere revisión)" : " (sin señal)"}. No acredita irregularidad.
            </p>
          )}
          <h4>Documentos y enlaces de la fuente</h4>
          <Fuentes lista={r.fuentes} />
        </section>
      )}
      {c && (
        <section>
          <h3>Cuaderno de Obra Digital (CID)</h3>
          <dl className="tz-dl">
            <div>
              <dt>Contrato</dt>
              <dd>
                {c.numero_contrato} ({c.contrato})
              </dd>
            </div>
            <div>
              <dt>Contratista</dt>
              <dd>{c.contratista}</dd>
            </div>
            <div>
              <dt>Monto</dt>
              <dd>{dinero(c.monto)}</dd>
            </div>
            <div>
              <dt>Asientos</dt>
              <dd>
                {c.asientos} ({c.primer_asiento} a {c.ultimo_asiento})
              </dd>
            </div>
          </dl>
          <p className="tz-ayuda">
            Procedencia: {c.conjunto} · {c.archivo}. Vinculado por código de contrato exacto; cada asiento
            conserva su archivo, hoja y fila.
          </p>
          <details className="tz-detalles">
            <summary>Ver los {asientos.length} asientos</summary>
            <ol className="tz-asientos">
              {asientos.map((v) => (
                <li key={v.id}>
                  <b>{v.efectiva?.slice(0, 10)}</b> · {v.datos.titulo}
                  <small>
                    {v.datos.archivo} · {v.datos.hoja} · fila {v.datos.fila}
                  </small>
                </li>
              ))}
            </ol>
          </details>
        </section>
      )}
    </div>
  );
}

/* ------------------------------------------------------ ventanas de acción */
const TITULO = {
  iniciar: "Iniciar fase",
  verificar: "Verificar documento",
  observar: "Registrar observación",
  subsanar: "Presentar subsanación",
  cerrar_observacion: "Verificar subsanación",
  visto_bueno: "Dar visto bueno",
  pago: "Registrar pago",
  cerrar: "Cerrar fase",
  reabrir: "Reabrir fase",
  asignar: "Cambiar responsable o plazo",
};
const SUGERIDO = {
  iniciar: "Inicio de la fase.",
  verificar: "Documento revisado y conforme con lo requerido.",
  visto_bueno: "Requisitos verificados y sin observaciones pendientes.",
  cerrar: "Fase concluida.",
  cerrar_observacion: "La corrección atiende lo observado.",
};

function VentanaAccion({ exp, op, cerrar, actualizar }) {
  const { accion, fase: f, requisito, documento, observacion } = op;
  const docs = f.documentos;
  return (
    <Formulario
      titulo={TITULO[accion]}
      subtitulo={`Fase ${f.orden} · ${f.nombre}`}
      cerrar={cerrar}
      boton={TITULO[accion]}
      ayuda={
        accion === "reabrir"
          ? "Reabrir deja constancia en el historial. Si una fase se reabre más de una vez, se genera una alerta."
          : accion === "pago"
            ? "Si lo pagado no coincide con lo autorizado o supera el monto del expediente, se genera una alerta."
            : accion === "visto_bueno"
              ? "El visto bueno confirma que todos los requisitos están verificados."
              : null
      }
      enviarCon={async (fd) => {
        const d = Object.fromEntries(fd);
        for (const k of ["requisito_id", "documento_id", "observacion_id", "limite"]) if (!d[k]) delete d[k];
        for (const k of ["requisito_id", "documento_id", "observacion_id"]) if (d[k]) d[k] = Number(d[k]);
        actualizar(
          await enviar(`/trazabilidad/${exp.id}/fases/${f.id}/accion`, { ...d, accion, revision: f.revision }),
        );
      }}
    >
      {accion === "verificar" && (
        <div className="tz-resumen-doc">
          <FileText size={18} />
          <div>
            <strong>{requisito.nombre}</strong>
            <small>
              {documento.nombre} · versión {documento.version} · subido por {documento.autor}
            </small>
          </div>
          <input type="hidden" name="requisito_id" value={requisito.id} />
          <input type="hidden" name="documento_id" value={documento.id} />
        </div>
      )}
      {observacion && (
        <div className="tz-resumen-doc">
          <AlertTriangle size={18} />
          <div>
            <strong>OBS-{observacion.id}</strong>
            <small>{observacion.descripcion}</small>
          </div>
          <input type="hidden" name="observacion_id" value={observacion.id} />
        </div>
      )}
      {accion === "observar" && (
        <label>
          ¿Sobre qué requisito?
          <select name="requisito_id" defaultValue={requisito?.id || ""}>
            <option value="">Toda la fase</option>
            {f.requisitos.map((q) => (
              <option key={q.id} value={q.id}>
                {q.nombre}
              </option>
            ))}
          </select>
        </label>
      )}
      {accion === "subsanar" && docs.length > 0 && (
        <label>
          Documento que sustenta la corrección (opcional)
          <select name="documento_id" defaultValue="">
            <option value="">Ninguno</option>
            {docs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.nombre} · v{d.version}
              </option>
            ))}
          </select>
        </label>
      )}
      {accion === "pago" && (
        <div className="tz-dos">
          <label>
            Monto autorizado (S/)
            <input name="monto_autorizado" type="number" min="0" step="0.01" required />
          </label>
          <label>
            Monto pagado (S/)
            <input name="monto_pagado" type="number" min="0" step="0.01" required />
          </label>
        </div>
      )}
      {["observar", "asignar"].includes(accion) && (
        <div className={accion === "observar" ? "tz-tres" : "tz-dos"}>
          <label>
            {accion === "observar" ? "¿Quién debe corregir?" : "Nuevo responsable"}
            <input name="responsable" required maxLength={150} defaultValue={accion === "asignar" ? f.responsable : ""} />
          </label>
          <label>
            {accion === "observar" ? "Plazo para corregir" : "Nuevo plazo (opcional)"}
            <input name="limite" type="date" required={accion === "observar"} min={hoy()} />
          </label>
          {accion === "observar" && (
            <label>
              Gravedad
              <select name="severidad" defaultValue="media">
                <option value="baja">Baja</option>
                <option value="media">Media</option>
                <option value="alta">Alta</option>
              </select>
            </label>
          )}
        </div>
      )}
      <label>
        {accion === "observar"
          ? "¿Qué se observa?"
          : accion === "subsanar"
            ? "¿Qué se corrigió?"
            : accion === "reabrir"
              ? "¿Por qué se reabre?"
              : "Comentario"}
        <textarea name="justificacion" required rows={3} maxLength={4000} defaultValue={SUGERIDO[accion] || ""} />
      </label>
    </Formulario>
  );
}

function VentanaSubir({ exp, op, usuario, cerrar, actualizar }) {
  const { fase: f, requisito: q } = op;
  return (
    <Formulario
      titulo="Subir documento"
      subtitulo={`${q.nombre} · Fase ${f.orden} · ${f.nombre}`}
      cerrar={cerrar}
      boton="Subir documento"
      ayuda="Se guarda la huella digital (SHA-256) del archivo. Si alguien lo cambia después, el sistema lo detecta."
      enviarCon={async (fd) => {
        fd.set("requisito_id", q.id);
        actualizar(await enviar(`/trazabilidad/${exp.id}/fases/${f.id}/documentos`, fd));
      }}
    >
      <label>
        Archivo (PDF, DOCX, XLSX, CSV o TXT)
        <input name="archivo" type="file" required accept=".pdf,.docx,.xlsx,.csv,.txt" />
      </label>
      <label>
        Autor del documento
        <input name="autor" required maxLength={150} defaultValue={usuario?.nombre || ""} />
      </label>
    </Formulario>
  );
}

function VentanaRevision({ exp, alerta, cerrar, actualizar }) {
  return (
    <Formulario
      titulo="Registrar revisión"
      subtitulo={`${alerta.regla} · ${REGLA[alerta.regla] || ""}`}
      cerrar={cerrar}
      boton="Guardar revisión"
      enviarCon={async (fd) =>
        actualizar(
          await enviar(`/trazabilidad/${exp.id}/alertas/${alerta.id}/revision`, {
            ...Object.fromEntries(fd),
            revision: 0,
          }),
        )
      }
    >
      <fieldset className="tz-opciones">
        <legend>Decisión</legend>
        <label>
          <input type="radio" name="accion" value="revisada" defaultChecked required />
          <span>
            <b>Revisada</b>
            <small>Se analizó y se tomó una acción (corrección, derivación, etc.).</small>
          </span>
        </label>
        <label>
          <input type="radio" name="accion" value="descartada" />
          <span>
            <b>Descartada</b>
            <small>Se verificó que no hay problema.</small>
          </span>
        </label>
      </fieldset>
      <label>
        Justificación (mínimo 15 caracteres)
        <textarea name="justificacion" required minLength={15} rows={3} maxLength={4000} />
      </label>
    </Formulario>
  );
}

function VentanaIncidente({ exp, alerta, cerrar }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    request(`/trazabilidad/${exp.id}/alertas/${alerta.id}/incidente`).then(setD, (e) => setError(e.message));
  }, [exp.id, alerta.id]);
  const nombre = (id) => exp.fases.find((f) => f.id === id)?.nombre;
  return (
    <Ventana titulo="¿Qué pasó?" subtitulo={`${alerta.regla} · ${REGLA[alerta.regla] || ""}`} cerrar={cerrar} ancho>
      {error && <p className="tz-error">{error}</p>}
      {!d && !error && <p className="tz-cargando">Reconstruyendo lo ocurrido…</p>}
      {d && (
        <div className="tz-incidente">
          <p>{d.alerta.descripcion}</p>
          <dl className="tz-dl">
            <div>
              <dt>Se detectó en</dt>
              <dd>{nombre(d.alerta.fase_id)}</dd>
            </div>
            <div>
              <dt>Posible origen</dt>
              <dd>{nombre(d.alerta.evidencia?.origen_fase_id)}</dd>
            </div>
            <div>
              <dt>Etapas que podrían verse afectadas</dt>
              <dd>{d.posteriores.join(", ") || "Ninguna"}</dd>
            </div>
          </dl>
          <h3>Actuaciones relacionadas</h3>
          <ol className="tz-actividad">
            {d.eventos
              .slice()
              .reverse()
              .map((e) => (
                <Evento key={e.id} e={e} fase={nombre(e.fase_id)} />
              ))}
          </ol>
          <p className="tz-ayuda">{d.recomendacion}</p>
        </div>
      )}
    </Ventana>
  );
}

/* ------------------------------------------------------------- informe */
function Informe({ exp }) {
  return (
    <div className="tz-informe" aria-hidden="true">
      <h1>Informe de trazabilidad · {exp.codigo}</h1>
      <p>
        {exp.nombre} · {exp.area} · {dinero(exp.monto)} · generado {momento(new Date().toISOString())}
      </p>
      {exp.fases.map((f) => (
        <section key={f.id}>
          <h2>
            {f.orden}. {f.nombre} — {estadoFase(f, origen(exp) === "publico")[0]}
          </h2>
          <p>Responsable: {f.responsable}</p>
          <ul>
            {f.requisitos.map((q) => (
              <li key={q.id}>
                {q.nombre}: {ESTADO_REQ[q.estado]?.[0] || q.estado}
              </li>
            ))}
          </ul>
          {f.observaciones.map((o) => (
            <p key={o.id}>
              OBS-{o.id} ({o.estado}): {o.descripcion}
            </p>
          ))}
        </section>
      ))}
      <h2>Alertas</h2>
      {exp.alertas.length ? (
        <ul>
          {exp.alertas.map((a) => (
            <li key={a.id}>
              {a.regla} · {a.descripcion} · {a.vigente ? a.estado : "no vigente"}
            </li>
          ))}
        </ul>
      ) : (
        <p>Sin alertas.</p>
      )}
      <h2>Cronología</h2>
      <ul>
        {exp.eventos.map((e) => (
          <li key={e.id}>
            {momento(e.fecha)} · {EVENTO[e.accion] || texto(e.accion)} · {e.responsable || e.actor}
          </li>
        ))}
      </ul>
      <p>Revisión humana obligatoria. Las alertas no acreditan responsabilidad.</p>
    </div>
  );
}

/* ------------------------------------------------------------- detalle */
function Detalle({ id, usuario, escribe }) {
  const [exp, setExp] = useState(null);
  const [error, setError] = useState("");
  const [faseId, setFaseId] = useState(null);
  const [tab, setTab] = useState("fases");
  const [op, setOp] = useState(null);
  const [analizando, setAnalizando] = useState(false);
  const [aviso, setAviso] = useState("");
  useEffect(() => {
    request("/trazabilidad/" + encodeURIComponent(id))
      .then((e) => {
        setExp(e);
        // Abre la primera fase que no esté cerrada: es donde está el trabajo.
        setFaseId((e.fases.find((f) => f.estado !== "cerrada") || e.fases[0]).id);
      })
      .catch((e) => setError(e.message));
  }, [id]);
  if (error)
    return (
      <div className="tz">
        <a href="#trazabilidad" className="tz-volver">
          <ArrowLeft size={15} /> Expedientes
        </a>
        <p className="tz-error">{error}</p>
      </div>
    );
  if (!exp) return <p className="tz-cargando">Cargando expediente…</p>;
  const f = exp.fases.find((x) => x.id === faseId) || exp.fases[0];
  const pend = exp.alertas.filter((a) => a.vigente && a.estado === "pendiente").length;
  const docs = exp.fases.reduce((n, x) => n + x.documentos.length, 0);
  const cerradas = exp.fases.filter((x) => x.estado === "cerrada").length;
  const conFuentes = !!(exp.datos?.registro_publico || exp.datos?.cid);
  const TABS = [
    ["fases", "Fases"],
    ["alertas", "Alertas", pend],
    ["documentos", "Documentos", docs],
    ["historial", "Historial"],
    ...(conFuentes ? [["fuentes", "Fuente pública"]] : []),
  ];
  const actualizar = (nuevo) => {
    const antes = exp.fases.find((x) => x.id === f.id);
    const ahora = nuevo.fases.find((x) => x.id === f.id);
    setExp(nuevo);
    setAviso("");
    // Al cerrar una fase se pasa directamente a la siguiente.
    if (antes?.estado !== "cerrada" && ahora?.estado === "cerrada") {
      const sig = nuevo.fases.find((x) => x.orden === ahora.orden + 1);
      if (sig) {
        setFaseId(sig.id);
        setAviso(`«${ahora.nombre}» quedó cerrada. Sigue con la fase ${sig.orden}: ${sig.nombre}.`);
      }
    }
  };
  return (
    <div className="tz">
      <a href="#trazabilidad" className="tz-volver">
        <ArrowLeft size={15} /> Expedientes
      </a>
      <header className="tz-cabecera">
        <div className="tz-cabecera-txt">
          <small>
            {exp.codigo} · {texto(exp.tipo)}
          </small>
          <h2>{exp.nombre}</h2>
          <p>
            {exp.area} · {dinero(exp.monto)} · inicio {dia(exp.inicio)}
          </p>
        </div>
        <div className="tz-cabecera-der">
          <Chip par={ORIGEN[origen(exp)]} />
          <div className="tz-cabecera-botones">
            {escribe && (
              <button
                disabled={analizando}
                onClick={async () => {
                  setAnalizando(true);
                  try {
                    const nuevo = await enviar(`/trazabilidad/${exp.id}/analizar`);
                    const n = nuevo.alertas.filter((a) => a.vigente && a.estado === "pendiente").length;
                    setExp(nuevo);
                    setAviso(n ? `Revisión terminada: ${n} ${n === 1 ? "alerta" : "alertas"} por revisar.` : "Revisión terminada: sin alertas pendientes.");
                  } catch (e) {
                    setAviso(e.message);
                  } finally {
                    setAnalizando(false);
                  }
                }}
              >
                <RefreshCw size={15} /> {analizando ? "Revisando…" : "Revisar alertas"}
              </button>
            )}
            <button onClick={() => window.print()}>
              <Printer size={15} /> Imprimir
            </button>
          </div>
        </div>
        <div className="tz-resumen">
          <div>
            <b>
              {cerradas}/{exp.fases.length}
            </b>
            <small>fases cerradas</small>
          </div>
          <div>
            <b>{docs}</b>
            <small>documentos</small>
          </div>
          <div className={pend ? "alerta" : ""}>
            <b>{pend}</b>
            <small>alertas por revisar</small>
          </div>
        </div>
      </header>
      {aviso && (
        <p className="tz-aviso" role="status">
          {aviso}
          <button className="tz-icono" aria-label="Cerrar aviso" onClick={() => setAviso("")}>
            <X size={15} />
          </button>
        </p>
      )}
      <Pasos
        exp={exp}
        actual={f.id}
        elegir={(fid) => {
          setFaseId(fid);
          setTab("fases");
        }}
      />
      <div className="tz-tabs" role="tablist" aria-label="Secciones del expediente">
        {TABS.map(([k, t, n]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
            {t}
            {n > 0 && <span className={"tz-n " + (k === "alertas" ? "ambar" : "")}>{n}</span>}
          </button>
        ))}
      </div>
      {tab === "fases" && <Fase key={f.id + "-" + f.revision} exp={exp} f={f} escribe={escribe} abrir={setOp} />}
      {tab === "alertas" && <Alertas exp={exp} escribe={escribe} abrir={setOp} />}
      {tab === "documentos" && <Documentos exp={exp} />}
      {tab === "historial" && <Historial exp={exp} />}
      {tab === "fuentes" && <InfoPublica exp={exp} />}
      {op?.tipo === "accion" && <VentanaAccion exp={exp} op={op} cerrar={() => setOp(null)} actualizar={actualizar} />}
      {op?.tipo === "subir" && (
        <VentanaSubir exp={exp} op={op} usuario={usuario} cerrar={() => setOp(null)} actualizar={actualizar} />
      )}
      {op?.tipo === "revision" && (
        <VentanaRevision exp={exp} alerta={op.alerta} cerrar={() => setOp(null)} actualizar={actualizar} />
      )}
      {op?.tipo === "incidente" && <VentanaIncidente exp={exp} alerta={op.alerta} cerrar={() => setOp(null)} />}
      <Informe exp={exp} />
    </div>
  );
}

export default function Trazabilidad({ id, usuario }) {
  const escribe = ["administrador", "analista"].includes(usuario?.rol);
  return id ? <Detalle key={id} id={id} usuario={usuario} escribe={escribe} /> : <Lista escribe={escribe} />;
}
