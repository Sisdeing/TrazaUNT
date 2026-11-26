import React, { useState } from "react";
import {
  Carga,
  Datos,
  ErrorAccion,
  Estado,
  Panel,
  Tabla,
  fecha,
  money,
  post,
  useAccion,
  useConsulta,
} from "./Comun";

function Simulador({ ficha }) {
  const [result, setResult] = useState(null);
  const [dirty, setDirty] = useState(false);
  const action = useAccion();
  function submit(event) {
    event.preventDefault();
    const payload = Object.fromEntries(
      Array.from(new FormData(event.currentTarget), ([k, v]) => [k, Number(v)]),
    );
    action.run(async () => {
      const data = await post("/concesiones/" + ficha.id + "/simular", payload);
      setResult(data);
      setDirty(false);
    });
  }
  return (
    <Panel title="Simulación financiera">
      <p className="fl-help">
        Ajusta los importes mensuales en soles para estimar el flujo del
        operador.
      </p>
      <form onSubmit={submit} onChange={() => setDirty(true)}>
        <div className="fl-grid">
          {[
            ["ingresos", "Ingresos", ficha.ingresos],
            ["costos", "Costos operativos", ficha.costos],
            ["contraprestacion", "Contraprestación", ficha.contraprestacion],
          ].map(([key, title, value]) => (
            <label key={key}>
              {title}
              <input
                required
                type="number"
                min="0"
                step="0.01"
                name={key}
                defaultValue={value}
              />
            </label>
          ))}
        </div>
        <ErrorAccion error={action.error} />
        <button className="fl-primary" disabled={action.busy}>
          Calcular escenarios
        </button>
      </form>
      {result && !dirty && (
        <>
          <p className="fl-help">{result.perspectiva}</p>
          <Tabla
            headers={[
              "Escenario",
              "Ingresos",
              "Costos",
              "Contraprestación",
              "Flujo",
            ]}
            rows={result.escenarios.map((r) => (
              <tr key={r.nombre}>
                <th scope="row">{r.nombre}</th>
                <td>{money(r.ingresos)}</td>
                <td>{money(r.costos)}</td>
                <td>{money(r.contraprestacion)}</td>
                <td>{money(r.flujo)}</td>
              </tr>
            ))}
          />
        </>
      )}
    </Panel>
  );
}

function RegistrarAbono({ ficha, done }) {
  const cuotas = ficha.pagos.filter(
    (p) => Number(p.exigible) > Number(p.pagado),
  );
  const [cuota, setCuota] = useState("");
  const action = useAccion();
  if (!cuotas.length || ficha.inicio > ficha.corte) return null;
  const actual = cuotas.find((c) => String(c.id) === cuota);
  function registrar(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    action.run(async () => {
      await post("/concesiones/" + ficha.id + "/pagos", {
        ...values,
        cuota_id: Number(cuota),
        monto: Number(values.monto),
      });
      done();
    });
  }
  return (
    <details className="fl-fold">
      <summary>Registrar abono</summary>
      <form onSubmit={registrar}>
        <div className="fl-grid">
          <label>
            Cuota
            <select
              required
              value={cuota}
              onChange={(e) => setCuota(e.target.value)}
            >
              <option value="">Selecciona una cuota</option>
              {cuotas.map((c) => (
                <option value={c.id} key={c.id}>
                  {fecha(c.fecha)} · {money(c.exigible)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Monto abonado (S/)
            <input
              required
              name="monto"
              type="number"
              min="0.01"
              step="0.01"
              max={
                actual
                  ? (Number(actual.exigible) - Number(actual.pagado)).toFixed(2)
                  : undefined
              }
            />
          </label>
          <label>
            Fecha de abono
            <input
              required
              name="fecha"
              type="date"
              min={ficha.inicio}
              max={ficha.corte}
            />
          </label>
          <label>
            Referencia del recibo
            <input required minLength={3} maxLength={80} name="referencia" />
          </label>
        </div>
        <ErrorAccion error={action.error} />
        <button disabled={action.busy} className="fl-primary">
          Guardar abono
        </button>
      </form>
    </details>
  );
}
function Ficha({ id, usuario }) {
  const [revision, setRevision] = useState(0);
  const query = useConsulta("/concesiones/" + encodeURIComponent(id), revision);
  return (
    <>
      <a href="#concesiones">← Concesiones</a>
      <Carga query={query}>
        {(c) => (
          <>
            <Panel title={c.espacio} action={<Estado value={c.estado} />}>
              <Datos
                items={[
                  ["Código", c.codigo],
                  ["Operador", c.proveedor],
                  ["Área", c.area],
                  ["Inicio", fecha(c.inicio)],
                  ["Vencimiento", fecha(c.fin)],
                  ["Fecha de corte", fecha(c.corte)],
                ]}
              />
              {c.convocatoria_id && (
                <a href={"#convocatorias/" + c.convocatoria_id}>
                  Ver convocatoria de origen →
                </a>
              )}
            </Panel>
            <Panel title="Seguimiento económico">
              <Datos
                items={[
                  ["Esperado al corte", money(c.esperado)],
                  ["Registrado", money(c.registrado)],
                  ["Saldo vencido", money(c.saldo_vencido)],
                  [
                    "Cumplimiento al corte",
                    c.cumplimiento == null
                      ? "No evaluado"
                      : c.cumplimiento + " %",
                  ],
                  ["Días de mora", c.dias_mora],
                  ["Garantía hasta", fecha(c.garantia_hasta)],
                ]}
              />
              {["administrador", "analista"].includes(usuario?.rol) && (
                <RegistrarAbono
                  ficha={c}
                  done={() => setRevision((v) => v + 1)}
                />
              )}
              <Tabla
                headers={["Fecha", "Exigible", "Registrado", "Estado"]}
                rows={c.pagos.map((p, i) => (
                  <tr key={i}>
                    <td>{fecha(p.fecha)}</td>
                    <td>{money(p.exigible)}</td>
                    <td>{money(p.pagado)}</td>
                    <td>
                      <Estado value={p.estado} />
                    </td>
                  </tr>
                ))}
                empty="Sin cuotas registradas."
              />
            </Panel>
            <Panel title="Obligaciones y vencimientos">
              <Tabla
                headers={["Obligación", "Vence", "Estado"]}
                rows={c.obligaciones.map((o, i) => (
                  <tr key={i}>
                    <th scope="row">{o.nombre}</th>
                    <td>{fecha(o.vence)}</td>
                    <td>
                      <Estado value={o.estado} />
                    </td>
                  </tr>
                ))}
                empty="Sin obligaciones registradas."
              />
            </Panel>
            {!!c.alertas.length && (
              <Panel title="Señales preventivas">
                <ul className="fl-list">
                  {c.alertas.map((a, i) => (
                    <li key={i}>
                      <strong>{a.codigo}</strong> · {a.motivo}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
            {["administrador", "analista"].includes(usuario?.rol) && (
              <Simulador ficha={c} />
            )}
          </>
        )}
      </Carga>
    </>
  );
}

function Lista() {
  const query = useConsulta("/concesiones");
  return (
    <Carga query={query}>
      {(data) => (
        <Panel
          title="Cartera de concesiones"
          action={<small>Corte {fecha(data.corte)}</small>}
        >
          <Tabla
            headers={[
              "Espacio",
              "Operador",
              "Vigencia",
              "Contraprestación",
              "Estado",
            ]}
            rows={data.items.map((c) => (
              <tr key={c.id}>
                <th scope="row">
                  <a href={"#concesiones/" + c.id}>{c.espacio}</a>
                  <small>{c.codigo}</small>
                </th>
                <td>{c.proveedor}</td>
                <td>
                  {fecha(c.inicio)} – {fecha(c.fin)}
                </td>
                <td>{money(c.contraprestacion)}</td>
                <td>
                  <Estado value={c.estado} />
                </td>
              </tr>
            ))}
            empty="Aún no hay concesiones registradas."
          />
        </Panel>
      )}
    </Carga>
  );
}
export function Concesiones({ id, usuario }) {
  return (
    <div className="flujo">
      {id ? <Ficha key={id} id={id} usuario={usuario} /> : <Lista />}
    </div>
  );
}
