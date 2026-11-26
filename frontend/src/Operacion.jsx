import React, { useState } from "react";
import { ExternalLink, ArrowRight, Check, RefreshCw } from "lucide-react";
import { useData, Load } from "./Expedientes";
import { request } from "./api";

export function Fuentes({ usuario }) {
  const data = useData("/fuentes"),
    [registro, setRegistro] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function verificar(e) {
    e.preventDefault();
    const ruc = new FormData(e.currentTarget).get("ruc");
    setError("");
    setRegistro(null);
    setBusy(true);
    try {
      setRegistro(
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
    <>
      <section className="surface">
        <h2>Catálogo de fuentes</h2>
        <Load state={data}>
          {(d) => (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fuente</th>
                    <th>Modalidad</th>
                    <th>Disponibilidad</th>
                  </tr>
                </thead>
                <tbody>
                  {d.items.map((f) => (
                    <tr key={f.nombre}>
                      <td>
                        <b>{f.nombre}</b>
                        <small>{f.detalle}</small>
                        {f.url && (
                          <a href={f.url} target="_blank" rel="noreferrer">
                            Fuente oficial <ExternalLink size={12} />
                          </a>
                        )}
                      </td>
                      <td>{f.tipo}</td>
                      <td>{f.estado}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Load>
      </section>
      {usuario.rol !== "consulta" && (
        <section className="surface">
          <h2>Consulta registral pública</h2>
          <p>
            Consulta el archivo SUNAT importado por el operador. Este resultado
            se mantiene separado del análisis sintético.
          </p>
          <form className="filters" onSubmit={verificar}>
            <label>
              RUC de persona jurídica
              <input name="ruc" pattern="20[0-9]{9}" required maxLength={11} />
            </label>
            <button disabled={busy}>Consultar padrón local</button>
          </form>
          {error && <p role="alert">{error}</p>}
          {registro && (
            <p role="status">
              <b>{registro.estado}</b>
              {registro.registro &&
                " · " +
                  [
                    registro.registro.razon_social,
                    registro.registro.estado,
                    registro.registro.condicion,
                    registro.registro.corte,
                  ].join(" · ")}
            </p>
          )}
        </section>
      )}
    </>
  );
}
function Lista({ items, marcar }) {
  return items.length ? (
    <div>
      {items.map((a) => (
        <div key={a.clave} className="notice-item">
          <div>
            <small>
              {a.familia} · {a.codigo} · {a.referencia}
            </small>
            <h3>{a.titulo}</h3>
            <p>{a.detalle}</p>
            <a href={a.enlace}>
              Abrir registro <ArrowRight size={13} />
            </a>
          </div>
          {marcar &&
            (a.leida ? (
              <small>Leído</small>
            ) : (
              <button onClick={() => marcar(a.clave)}>
                <Check size={13} /> Marcar leído
              </button>
            ))}
        </div>
      ))}
    </div>
  ) : (
    <p className="empty">Sin señales para esta consulta.</p>
  );
}
export function Notificaciones({ usuario }) {
  const [version, setVersion] = useState(0),
    [grupo, setGrupo] = useState(""),
    [pend, setPend] = useState(false),
    [error, setError] = useState("");
  const data = useData("/notificaciones", version);
  const marcar = async (clave) => {
    try {
      await request("/notificaciones/" + clave + "/leer", { method: "POST" });
      setVersion((n) => n + 1);
    } catch (e) {
      setError(e.message);
    }
  };
  return (
    <section className="surface">
      <div className="section-top">
        <div>
          <h2>Bandeja de revisión</h2>
          <p>
            Señales documentales, de integridad y patrimonio. Incluye los doce
            expedientes pendientes con mayor prioridad.
          </p>
        </div>
        <button onClick={() => setVersion((n) => n + 1)}>
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>
      <div className="filters">
        <label>
          Familia
          <select value={grupo} onChange={(e) => setGrupo(e.target.value)}>
            <option value="">Todas</option>
            {[
              "Documentos",
              "Patrimonio",
              "Integridad",
              "Prevención",
              "Expedientes",
            ].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <button aria-pressed={pend} onClick={() => setPend(!pend)}>
          {pend ? "Mostrar todos" : "Solo no leídos"}
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      <Load state={data}>
        {(d) => (
          <Lista
            items={d.items.filter(
              (a) => (!grupo || a.familia === grupo) && (!pend || !a.leida),
            )}
            marcar={usuario.rol === "consulta" ? null : marcar}
          />
        )}
      </Load>
    </section>
  );
}
export function Asistente() {
  const [tema, setTema] = useState("Documentos");
  const data = useData("/asistente?tema=" + encodeURIComponent(tema));
  return (
    <section className="surface">
      <h2>Consultar evidencia</h2>
      <p>
        Elige una pregunta para consultar los registros disponibles en este
        equipo.
      </p>
      <label>
        Pregunta
        <select value={tema} onChange={(e) => setTema(e.target.value)}>
          {Object.entries({
            Documentos: "¿Qué diferencias documentales requieren revisión?",
            Integridad: "¿Qué vínculos están registrados?",
            Patrimonio: "¿Qué concesiones tienen obligaciones pendientes?",
            Prevención: "¿Qué señales preventivas requieren revisión?",
            Expedientes: "¿Qué expedientes requieren atención prioritaria?",
          }).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <Load state={data}>{(d) => <Lista items={d.items} />}</Load>
    </section>
  );
}
