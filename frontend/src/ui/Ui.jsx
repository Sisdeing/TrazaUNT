import React, { useEffect, useRef, useState } from "react";
import { AlertTriangle, CircleHelp, Inbox, Loader2, X } from "lucide-react";

// Componentes compartidos v5.1: un mismo significado se ve igual en toda la aplicación
// (heurística 4 de Nielsen: consistencia y estándares).

export const PRIORIDAD = { alta: "Prioridad alta", media: "Prioridad media", baja: "Prioridad baja" };
export const ESTADO = {
  pendiente: "Pendiente de revisión",
  en_revision: "En revisión",
  revisada: "Revisada",
  descartada: "Descartada",
};

export function Prioridad({ valor, corto = false }) {
  return (
    <span className={"ui-prioridad " + valor} title={PRIORIDAD[valor]}>
      <i aria-hidden="true" />
      {corto ? { alta: "Alta", media: "Media", baja: "Baja" }[valor] || valor : PRIORIDAD[valor] || valor}
    </span>
  );
}
export function EstadoRevision({ valor, texto }) {
  return <span className={"ui-estado " + valor}>{texto || ESTADO[valor] || valor}</span>;
}

export function Cargando({ texto = "Cargando información…" }) {
  return (
    <p className="ui-cargando" role="status">
      <Loader2 size={16} className="ui-gira" aria-hidden="true" /> {texto}
    </p>
  );
}

// Heurística 9: el mensaje explica qué pasó y cómo seguir, sin jerga técnica.
export function mensajeAmigable(error) {
  const m = String(error?.message || error || "");
  if (/Failed to fetch|NetworkError|Load failed|conexión/i.test(m))
    return "No se pudo conectar con TrazaUNT. Revisa que el programa siga abierto (iniciar.bat) y vuelve a intentarlo.";
  if (/Inicia sesión/i.test(m)) return "Tu sesión terminó. Vuelve a ingresar para continuar.";
  return m || "No se pudo completar la operación. Vuelve a intentarlo.";
}
export function ErrorAmigable({ error, reintentar }) {
  if (!error) return null;
  return (
    <div className="ui-error" role="alert">
      <AlertTriangle size={17} aria-hidden="true" />
      <p>{mensajeAmigable(error)}</p>
      {reintentar && <button onClick={reintentar}>Reintentar</button>}
    </div>
  );
}
export function Vacio({ titulo, children }) {
  return (
    <div className="ui-vacio">
      <Inbox size={22} aria-hidden="true" />
      <strong>{titulo}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}
export function Ayuda({ children, etiqueta = "¿Qué significa?" }) {
  const [abierta, setAbierta] = useState(false);
  return (
    <span className="ui-ayuda">
      <button
        type="button"
        className="ui-ayuda-boton"
        aria-expanded={abierta}
        aria-label={etiqueta || "Más información"}
        onClick={() => setAbierta(!abierta)}
      >
        <CircleHelp size={14} aria-hidden="true" /> {etiqueta}
      </button>
      {abierta && (
        <span className="ui-ayuda-texto" role="note">
          {children}
        </span>
      )}
    </span>
  );
}

// Aviso efímero de confirmación (heurística 1: visibilidad del estado del sistema).
export function Aviso({ texto, cerrar }) {
  useEffect(() => {
    if (!texto) return;
    const t = setTimeout(cerrar, 5000);
    return () => clearTimeout(t);
  }, [texto, cerrar]);
  if (!texto) return null;
  return (
    <div className="ui-aviso" role="status">
      {texto}
      <button className="ui-icono" aria-label="Cerrar aviso" onClick={cerrar}>
        <X size={15} />
      </button>
    </div>
  );
}

export function Ventana({ titulo, subtitulo, cerrar, children, ancha = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open && d.showModal) d.showModal();
    return () => d?.open && d.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={"ui-ventana" + (ancha ? " ancha" : "")}
      aria-label={titulo}
      onCancel={(e) => {
        e.preventDefault();
        cerrar();
      }}
    >
      <div className="ui-ventana-top">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <small>{subtitulo}</small>}
        </div>
        <button className="ui-icono" aria-label="Cerrar" onClick={cerrar}>
          <X size={18} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

// Filtros activos visibles, cada uno con su «×» (heurísticas 3 y 6).
export function FiltrosActivos({ filtros, quitar, limpiar }) {
  const activos = filtros.filter(([, , v]) => v);
  if (!activos.length) return null;
  return (
    <div className="ui-filtros-activos" aria-label="Filtros activos">
      <span>Filtros:</span>
      {activos.map(([k, etiqueta]) => (
        <button key={k} className="ui-filtro" onClick={() => quitar(k)} aria-label={"Quitar filtro " + etiqueta}>
          {etiqueta} <X size={13} aria-hidden="true" />
        </button>
      ))}
      <button className="ui-enlace" onClick={limpiar}>
        Limpiar todo
      </button>
    </div>
  );
}

const corto = (n) =>
  n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + " M" : n >= 1e3 ? Math.round(n / 1e3) + " mil" : String(Math.round(n));

// Gráfico de barras en SVG, con título, descripción y valores rotulados (heurística 10).
export function Barras({ titulo, descripcion, datos, formato = corto, color = "azul", vacio = "Sin datos para el periodo." }) {
  const max = Math.max(0, ...datos.map((d) => d.valor));
  return (
    <figure className="ui-grafico">
      <figcaption>
        <strong>{titulo}</strong>
        {descripcion && <small>{descripcion}</small>}
      </figcaption>
      {!datos.length || max === 0 ? (
        <p className="ui-grafico-vacio">{vacio}</p>
      ) : (
        <div className="ui-barras" role="img" aria-label={titulo + ": " + datos.map((d) => `${d.etiqueta} ${formato(d.valor)}`).join(", ")}>
          {datos.map((d) => (
            <div key={d.etiqueta} className="ui-barra" title={`${d.etiqueta}: ${formato(d.valor)}`}>
              <span className="ui-barra-valor">{d.valor ? formato(d.valor) : ""}</span>
              <span className={"ui-barra-relleno " + (d.color || color)} style={{ height: `${Math.max(d.valor ? 4 : 0, (100 * d.valor) / max)}%` }} />
              <span className="ui-barra-etiqueta">{d.etiqueta}</span>
            </div>
          ))}
        </div>
      )}
    </figure>
  );
}

// Barras horizontales para comparar categorías.
export function BarrasH({ titulo, descripcion, datos, vacio = "Sin datos." }) {
  const max = Math.max(0, ...datos.map((d) => d.valor));
  return (
    <figure className="ui-grafico">
      <figcaption>
        <strong>{titulo}</strong>
        {descripcion && <small>{descripcion}</small>}
      </figcaption>
      {max === 0 ? (
        <p className="ui-grafico-vacio">{vacio}</p>
      ) : (
        <ul className="ui-barras-h">
          {datos.map((d) => (
            <li key={d.etiqueta}>
              <span>{d.etiqueta}</span>
              <span className="ui-barra-h-pista">
                <span className={"ui-barra-h " + (d.color || "azul")} style={{ width: `${(100 * d.valor) / max}%` }} />
              </span>
              <b>{d.valor}</b>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

export const mesCorto = (m) => {
  const [a, n] = String(m).split("-");
  return ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"].at(Number(n) - 1) + " " + a.slice(2);
};
export const soles = (v) =>
  v == null ? "No disponible" : new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(v);
export const dia = (v) =>
  v
    ? new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeZone: "America/Lima" }).format(
        new Date(String(v).length === 10 ? v + "T12:00:00-05:00" : v),
      )
    : "No disponible";
