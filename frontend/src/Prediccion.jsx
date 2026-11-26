import React, { useState } from "react";
import { Load, useData } from "./Expedientes";
import { request } from "./api";

export default function Prediccion({ usuario }) {
  const [rev, setRev] = useState(0),
    [busy, setBusy] = useState(false),
    [err, setErr] = useState("");
  const data = useData("/predicciones", rev);
  async function recalcular() {
    setBusy(true);
    try {
      await request("/predicciones/evaluar", { method: "POST" });
      setRev((v) => v + 1);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Load state={data}>
      {(d) => (
        <>
          <div className="summary-box">
            <div>
              <h2>TrazaPredict · Mora en contraprestaciones</h2>
              <p>{d.modelo.limite}</p>
            </div>
          </div>
          <section className="surface">
            <div className="section-top">
              <div>
                <h2>Próximas cuotas</h2>
                <p>{d.modelo.evento}</p>
              </div>
              {["analista", "administrador"].includes(usuario.rol) && (
                <button disabled={busy} onClick={recalcular}>
                  Actualizar evaluación
                </button>
              )}
            </div>
            {err && <p role="alert">{err}</p>}
            {d.items.map((x) => (
              <details key={x.id}>
                <summary>
                  <strong>{x.espacio}</strong> · {x.nivel}
                </summary>
                <p>
                  Corte {x.corte} ·{" "}
                  {x.horizonte
                    ? "Horizonte " + x.horizonte
                    : "Sin horizonte disponible"}{" "}
                  · {x.version}
                </p>
                {x.variables && (
                  <ul>
                    {d.modelo.variables.map((v, i) => (
                      <li key={v}>
                        {v} · {x.variables[i]}
                      </li>
                    ))}
                  </ul>
                )}
                <p>{x.accion}</p>
                <a href={"#concesiones/" + x.id}>Consultar cuotas y abonos →</a>
              </details>
            ))}
          </section>
          <section className="surface">
            <h2>Validación temporal del modelo</h2>
            <p>
              {d.modelo.fuente} Modelo seleccionado en validación:{" "}
              {d.modelo.algoritmo}.
            </p>
            <div className="table-wrap">
              <table>
                <caption>Resultados en la partición final de prueba</caption>
                <thead>
                  <tr>
                    {[
                      "Algoritmo",
                      "Precisión",
                      "Recall",
                      "F1",
                      "Precisión promedio",
                      "Brier",
                    ].map((x) => (
                      <th key={x}>{x}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(d.modelo.resultados).map(([n, m]) => (
                    <tr key={n}>
                      <th>{n}</th>
                      {["precision", "recall", "f1", "ap", "brier"].map((k) => (
                        <td key={k}>{m.prueba[k]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary>Periodos, observaciones y limitaciones</summary>
              {d.modelo.periodos.map(([a, b], i) => (
                <p key={a}>
                  {["Entrenamiento", "Validación", "Prueba"][i]} · {a} a {b} ·{" "}
                  {d.modelo.muestras[i]} observaciones
                </p>
              ))}
              <p>
                Las etiquetas deben haber madurado antes de iniciar el periodo
                siguiente. La prueba evalúa meses posteriores de la misma
                población simulada. La categoría orienta la revisión humana.
              </p>
            </details>
          </section>
        </>
      )}
    </Load>
  );
}
