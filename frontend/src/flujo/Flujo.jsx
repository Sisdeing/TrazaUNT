import React, { useState } from "react";
import { Asistente } from "./Asistente";
import { Comparacion, Postulantes } from "./Comparacion";
import { Documentos } from "./Documentos";
import {
  Carga,
  Datos,
  ErrorAccion,
  Estado,
  Pager,
  Panel,
  Tabla,
  fecha,
  label,
  money,
  post,
  useAccion,
  useConsulta,
} from "./Comun";
import "./flujo.css";
import { ListaCoincidencias } from "../Coincidencias";
export { Concesiones } from "./Concesiones";

const acciones = {
  borrador: ["abierta", "Abrir registro interno"],
  abierta: ["cerrada", "Cerrar recepción"],
  cerrada: ["en_evaluacion", "Iniciar evaluación"],
  en_evaluacion: ["resultado_registrado", "Registrar resultado ficticio"],
};
const puedeEscribir = (usuario) =>
  ["analista", "administrador"].includes(usuario?.rol);
function Lista({ write }) {
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const args = new URLSearchParams({ ...filters, pagina: page, tamano: 25 });
  const query = useConsulta("/convocatorias?" + args);
  return (
    <>
      <div className="fl-toolbar">
        <form
          className="fl-filter"
          onSubmit={(e) => {
            e.preventDefault();
            setFilters(
              Object.fromEntries(
                [...new FormData(e.currentTarget)].filter(([, v]) => v),
              ),
            );
            setPage(1);
          }}
        >
          <label>
            Buscar convocatoria
            <input
              type="search"
              name="q"
              placeholder="Nombre o código"
              maxLength="120"
            />
          </label>
          <label>
            Estado
            <select name="estado">
              <option value="">Todos</option>
              {[...Object.keys(acciones), "resultado_registrado"].map((k) => (
                <option key={k} value={k}>
                  {label(k)}
                </option>
              ))}
            </select>
          </label>
          <button>Aplicar filtros</button>
        </form>
        {write && (
          <a className="fl-button fl-primary" href="#convocatorias/nueva">
            Nueva convocatoria
          </a>
        )}
      </div>
      <Panel title="Convocatorias registradas">
        <Carga query={query}>
          {(d) => (
            <>
              <Tabla
                headers={[
                  "Convocatoria",
                  "Área",
                  "Modalidad",
                  "Cierre",
                  "Estado",
                ]}
                rows={d.items.map((c) => (
                  <tr key={c.id}>
                    <th scope="row">
                      <a href={"#convocatorias/" + c.id}>{c.nombre}</a>
                      <small>{c.codigo}</small>
                    </th>
                    <td>{c.area}</td>
                    <td>{c.modalidad}</td>
                    <td>{fecha(c.cierre)}</td>
                    <td>
                      <Estado value={c.estado} />
                    </td>
                  </tr>
                ))}
                empty="No hay convocatorias con estos filtros."
              />
              <Pager data={d} setPage={setPage} />
            </>
          )}
        </Carga>
      </Panel>
    </>
  );
}

function Transicion({ ficha, done }) {
  const next = acciones[ficha.estado];
  const action = useAccion();
  if (!next) return null;
  function guardar(e) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    const payload = {
      estado: next[0],
      version: ficha.version,
      motivo: data.motivo,
    };
    if (data.postulante_id) payload.postulante_id = Number(data.postulante_id);
    action.run(async () => {
      await post("/convocatorias/" + ficha.id + "/estado", payload);
      done();
    });
  }
  return (
    <details className="fl-fold">
      <summary>{next[1]}</summary>
      <form onSubmit={guardar}>
        {next[0] === "resultado_registrado" && (
          <label>
            Postulante seleccionado por el comité
            <select name="postulante_id" required defaultValue="">
              <option value="">Selecciona un postulante</option>
              {ficha.postulantes.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.razon_social}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Motivo del cambio
          <textarea required minLength="8" maxLength="1000" name="motivo" />
        </label>
        <ErrorAccion error={action.error} />
        <button className="fl-primary" disabled={action.busy}>
          Confirmar cambio de estado
        </button>
      </form>
    </details>
  );
}
function Revisiones({ ficha, write, refresh }) {
  const action = useAccion();
  function registrar(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    const payload = { motivo: values.motivo };
    if (values.postulante_id)
      payload.postulante_id = Number(values.postulante_id);
    action.run(async () => {
      await post("/convocatorias/" + ficha.id + "/revision", payload);
      refresh();
    });
  }
  return (
    <>
      {write &&
        ["abierta", "cerrada", "en_evaluacion"].includes(ficha.estado) && (
          <Panel title="Registrar revisión humana">
            <form onSubmit={registrar}>
              <label>
                Alcance
                <select name="postulante_id">
                  <option value="">Convocatoria completa</option>
                  {ficha.postulantes.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.razon_social}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Justificación y referencia a la evidencia
                <textarea
                  name="motivo"
                  required
                  minLength="8"
                  maxLength="1000"
                />
              </label>
              <ErrorAccion error={action.error} />
              <button disabled={action.busy} className="fl-primary">
                Guardar revisión
              </button>
            </form>
          </Panel>
        )}
      <Panel title="Historial de actuaciones">
        <Tabla
          headers={["Fecha", "Acción", "Responsable", "Justificación"]}
          rows={ficha.historial.map((h, i) => (
            <tr key={i}>
              <td>{fecha(h.fecha)}</td>
              <td>{label(h.accion)}</td>
              <td>{h.autor}</td>
              <td>{h.motivo || "—"}</td>
            </tr>
          ))}
          empty="Aún no hay actuaciones registradas."
        />
      </Panel>
    </>
  );
}
function Bases({ ficha, write, editar, refresh }) {
  return (
    <>
      <Panel
        title="Datos del proceso"
        action={
          write &&
          ficha.estado === "borrador" && (
            <button onClick={editar}>Editar borrador</button>
          )
        }
      >
        <p>{ficha.objeto}</p>
        {ficha.descripcion && <p className="fl-help">{ficha.descripcion}</p>}
        <Datos
          items={[
            ["Modalidad", ficha.modalidad],
            ["Área responsable", ficha.area],
            ["Responsable", ficha.responsable],
            ["Importe referencial", money(ficha.presupuesto)],
            ["Plazo", ficha.duracion_meses + " meses"],
            ["Apertura", fecha(ficha.apertura)],
            ["Cierre", fecha(ficha.cierre)],
            ["Versión", ficha.version],
            ...(ficha.ubicacion ? [["Ubicación", ficha.ubicacion]] : []),
          ]}
        />
        {write && <Transicion ficha={ficha} done={refresh} />}
        {ficha.resultado && (
          <div className="fl-outcome">
            <h3>Resultado registrado</h3>
            <p>
              {
                ficha.postulantes.find(
                  (p) => p.id === ficha.resultado.postulante_id,
                )?.razon_social
              }
            </p>
            <p>{ficha.resultado.motivo}</p>
            {ficha.resultado.concesion_id && (
              <a href={"#concesiones/" + ficha.resultado.concesion_id}>
                Abrir seguimiento de la concesión →
              </a>
            )}
          </div>
        )}
      </Panel>
      <div className="fl-split">
        <Panel title="Requisitos de admisibilidad">
          <ul className="fl-list">
            {ficha.requisitos.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </Panel>
        <Panel title="Criterios de evaluación">
          <Tabla
            headers={["Criterio", "Peso"]}
            rows={ficha.criterios.map((c, i) => (
              <tr key={i}>
                <th scope="row">{c.nombre}</th>
                <td>{c.peso} %</td>
              </tr>
            ))}
          />
        </Panel>
      </div>
      <Panel title="Intervinientes">
        <Tabla
          headers={["Nombre", "Función"]}
          rows={ficha.intervinientes.map((p, i) => (
            <tr key={i}>
              <td>{p.nombre}</td>
              <td>{p.rol}</td>
            </tr>
          ))}
        />
      </Panel>
    </>
  );
}

function Ficha({ id, usuario }) {
  const [tab, setTab] = useState("Bases");
  const [doc, setDoc] = useState(null);
  const [version, setVersion] = useState(0);
  const [editar, setEditar] = useState(false);
  const query = useConsulta(
    "/convocatorias/" + encodeURIComponent(id),
    version,
  );
  const refresh = () => setVersion((v) => v + 1);
  const write = puedeEscribir(usuario);
  const tabs = [
    "Bases",
    "Postulantes",
    ...(usuario?.rol !== "consulta" ? ["Documentos"] : []),
    "Comparación",
    "Coincidencias",
    "Revisiones",
  ];
  return (
    <Carga query={query}>
      {(f) =>
        editar && write && f.estado === "borrador" ? (
          <Asistente
            original={f}
            alSalir={() => {
              setEditar(false);
              refresh();
            }}
          />
        ) : (
          <>
            <a href="#convocatorias" className="fl-back">
              ← Convocatorias
            </a>
            <div className="fl-title">
              <div>
                <small>{f.codigo}</small>
                <h2>{f.nombre}</h2>
              </div>
              <Estado value={f.estado} />
            </div>
            <div
              className="fl-tabs"
              role="group"
              aria-label="Secciones de la convocatoria"
            >
              {tabs.map((t) => (
                <button
                  key={t}
                  aria-pressed={tab === t}
                  onClick={() => setTab(t)}
                >
                  {t}
                  {t === "Coincidencias" && f.coincidencias?.length > 0 && (
                    <span className="fl-count">
                      {f.coincidencias.filter((x) => x.estado === "pendiente").length}
                    </span>
                  )}
                </button>
              ))}
            </div>
            {tab === "Bases" && (
              <Bases
                ficha={f}
                write={write}
                editar={() => setEditar(true)}
                refresh={refresh}
              />
            )}
            {tab === "Postulantes" && (
              <Postulantes ficha={f} write={write} refresh={refresh} />
            )}
            {tab === "Documentos" && (
              <Documentos
                ficha={f}
                write={write}
                refresh={refresh}
                seleccion={doc}
                setSeleccion={setDoc}
              />
            )}
            {tab === "Comparación" && (
              <Comparacion
                ficha={f}
                usuario={usuario}
                version={version}
                abrir={(id) => {
                  setDoc(id);
                  setTab("Documentos");
                }}
              />
            )}
            {tab === "Coincidencias" && (
              <Panel title="Coincidencias detectadas automáticamente">
                <p className="fl-help">
                  Se recalculan al registrar intervinientes o empresas. Cada coincidencia
                  requiere una revisión humana justificada; ninguna constituye por sí sola un
                  conflicto de intereses.
                </p>
                <ListaCoincidencias items={f.coincidencias || []} onCambio={refresh} />
              </Panel>
            )}
            {tab === "Revisiones" && (
              <Revisiones ficha={f} write={write} refresh={refresh} />
            )}
          </>
        )
      }
    </Carga>
  );
}
export function Convocatorias({ id, usuario }) {
  if (!puedeEscribir(usuario))
    return (
      <p role="status">
        El expediente de evaluación requiere un perfil de analista o
        administrador.
      </p>
    );
  return (
    <div className="flujo">
      {id === "nueva" ? (
        puedeEscribir(usuario) ? (
          <Asistente />
        ) : (
          <p>La creación requiere un perfil autorizado.</p>
        )
      ) : id ? (
        <Ficha key={id} id={id} usuario={usuario} />
      ) : (
        <Lista write={puedeEscribir(usuario)} />
      )}
    </div>
  );
}
