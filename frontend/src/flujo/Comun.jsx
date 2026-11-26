import React, { useEffect, useState } from "react";
import { request } from "../api";

export const money = (value) =>
  value == null
    ? "No evaluado"
    : new Intl.NumberFormat("es-PE", {
        style: "currency",
        currency: "PEN",
      }).format(value);
export const label = (value) =>
  String(value || "No evaluado")
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
export const fecha = (value) =>
  value
    ? new Intl.DateTimeFormat("es-PE", {
        dateStyle: "medium",
        timeZone: "America/Lima",
      }).format(
        new Date(value.length === 10 ? value + "T12:00:00-05:00" : value),
      )
    : "Sin fecha";

export function useConsulta(path, revision = 0) {
  const [result, setResult] = useState({ loading: true });
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setResult({ loading: true });
    request(path, { signal: controller.signal })
      .then((data) => {
        if (active) setResult({ data });
      })
      .catch((error) => {
        if (active) setResult({ error: error.message });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, revision]);
  return result;
}

export function Carga({ query, children }) {
  if (query.loading)
    return (
      <p className="fl-loading" role="status">
        Cargando información…
      </p>
    );
  if (query.error)
    return (
      <p className="fl-error" role="alert">
        {query.error}
      </p>
    );
  return children(query.data);
}

export function useAccion() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = React.useRef(false);
  const run = async (task) => {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await task();
    } catch (e) {
      setError(e.message || "No se pudo completar la operación.");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  return { busy, error, run };
}
export function ErrorAccion({ error }) {
  return error ? (
    <p className="fl-error" role="alert">
      {error}
    </p>
  ) : null;
}
export const post = (path, body, method = "POST") =>
  request(path, {
    method,
    headers: { "X-Traza-Client": "react" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
export function Estado({ value }) {
  value = typeof value === "string" ? value.toLowerCase() : value;
  let tone = "neutral";
  if (
    [
      "abierta",
      "analizado",
      "vigente",
      "cumplida",
      "pagado",
      "pagada",
      "confirmado por el analista",
      "evidencia encontrada",
      "verificado",
      "activo",
      "activa",
      "localizado",
      "admitida",
      "revisado por la universidad",
      "aclarada sin incidencia",
      "resultado registrado",
    ].includes(value)
  )
    tone = "ok";
  if (
    [
      "pendiente",
      "requiere_revision",
      "en_evaluacion",
      "parcial",
      "en_revision",
      "pendiente de revisión",
      "no localizada",
      "por vencer",
      "observada",
      "en revisión por la universidad",
      "recepción abierta",
    ].includes(value)
  )
    tone = "warn";
  if (
    [
      "vencida",
      "vencido",
      "mora",
      "error_lectura",
      "incumplida",
      "no admitida",
      "derivada a revisión de integridad",
    ].includes(value)
  )
    tone = "risk";
  return <span className={"fl-state " + tone}>{label(value)}</span>;
}
export function Panel({ title, action, children }) {
  return (
    <section className="fl-panel">
      {title && (
        <div className="fl-heading">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Tabla({ headers, rows, empty = "Sin registros." }) {
  return rows.length ? (
    <div className="fl-table" tabIndex="0">
      <table>
        <thead>
          <tr>
            {headers.map((h) => (
              <th scope="col" key={h}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  ) : (
    <p className="fl-empty">{empty}</p>
  );
}
export function Datos({ items }) {
  return (
    <dl className="fl-datos">
      {items.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v ?? "No evaluado"}</dd>
        </div>
      ))}
    </dl>
  );
}
export function Pager({ data, setPage }) {
  if (data.total <= data.tamano) return null;
  return (
    <div className="fl-actions fl-pager">
      <button
        disabled={data.pagina <= 1}
        onClick={() => setPage(data.pagina - 1)}
      >
        Anterior
      </button>
      <span>
        Página {data.pagina} de {Math.ceil(data.total / data.tamano)}
      </span>
      <button
        disabled={data.pagina * data.tamano >= data.total}
        onClick={() => setPage(data.pagina + 1)}
      >
        Siguiente
      </button>
    </div>
  );
}
