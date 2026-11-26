import { AlertasDestacadas } from "./alertas/CentroAlertas";
import React, { useState, useEffect, useRef } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BellRing,
  Building2,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronRight,
  CircleAlert,
  FileStack,
  Landmark,
  ListFilter,
  ScanLine,
  ScrollText,
  Wallet,
} from "lucide-react";
import { Load, useData } from "./Expedientes";

export const soles = (n) =>
  new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: "PEN",
    maximumFractionDigits: 0,
  }).format(n);
const numero = (n) => new Intl.NumberFormat("es-PE").format(n);
const meses = [
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Oct",
  "Nov",
  "Dic",
];
const colors = { alta: "#D8261A", media: "#E6AD09", baja: "#12377B" };
const titulos = {
  R01: "Posible fraccionamiento",
  R02: "Concentración de adjudicaciones",
  R03: "Pago con sustento incompleto",
  R04: "Monto próximo al umbral",
  R05: "Fechas incoherentes",
  R06: "Proveedor de reciente constitución",
};
const monthLabel = (mes) => meses[Number(mes.slice(-2)) - 1];
const corto = (n) =>
  n >= 1e6
    ? "S/ " +
      (n / 1e6).toLocaleString("es-PE", { maximumFractionDigits: 2 }) +
      " M"
    : soles(n);

function Curva({ serie, modo }) {
  const [activo, setActivo] = useState(null);
  const keys = modo === "monto" ? ["monto"] : ["alta", "media", "baja"];
  const holder = useRef(null),
    [width, setWidth] = useState(690);
  useEffect(() => {
    if (!holder.current || !window.ResizeObserver) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(290, Math.round(entry.contentRect.width))),
    );
    observer.observe(holder.current);
    return () => observer.disconnect();
  }, [serie?.length]);
  if (!serie?.length)
    return <p className="empty">Sin observaciones para el periodo.</p>;
  const W = width,
    H = 178,
    x0 = 52,
    y0 = 12,
    y1 = 145,
    x1 = W - 18;
  const max = Math.max(
    1,
    ...serie.flatMap((s) => keys.map((k) => Number(s[k]))),
  );
  const escala = 10 ** Math.floor(Math.log10(max));
  const techo = Math.ceil(max / escala) * escala;
  const x = (i) => x0 + ((x1 - x0) * i) / Math.max(1, serie.length - 1);
  const y = (v) => y1 - ((y1 - y0) * v) / techo;
  const puntos = (k) => serie.map((s, i) => [x(i), y(s[k])]);
  const path = (k) =>
    puntos(k)
      .map(([px, py], i) => (i ? "L" : "M") + px + " " + py)
      .join(" ");
  const index = activo != null && activo < serie.length ? activo : null;
  return (
    <>
      <svg
        ref={holder}
        className="plot"
        viewBox={"0 0 " + W + " " + H}
        role="img"
        aria-label={
          modo === "monto"
            ? "Monto contratado por mes"
            : "Alertas por mes del expediente y severidad"
        }
      >
        <defs>
          <linearGradient id="relleno-traza" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#0A2FFF" stopOpacity=".29" />
            <stop offset="1" stopColor="#0A2FFF" stopOpacity=".015" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((i) => {
          const val = (techo * i) / 4;
          return (
            <g key={i}>
              <line
                x1={x0}
                y1={y(val)}
                x2={x1}
                y2={y(val)}
                stroke="#e5eaf0"
                strokeDasharray="3 4"
              />
              <text x={x0 - 9} y={y(val) + 4} textAnchor="end">
                {modo === "monto"
                  ? (val / 1e6).toLocaleString("es-PE", {
                      maximumFractionDigits: 2,
                    }) + " M"
                  : numero(val)}
              </text>
            </g>
          );
        })}
        <path
          d={
            path(keys[0]) +
            " L" +
            x(serie.length - 1) +
            " " +
            y1 +
            " L" +
            x0 +
            " " +
            y1 +
            " Z"
          }
          fill="url(#relleno-traza)"
        />
        {keys.map((k) => (
          <g key={k}>
            <path
              d={path(k)}
              fill="none"
              stroke={colors[k] || colors.alta}
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeDasharray={k === "media" ? "5 4" : undefined}
            />
            {puntos(k).map(([px, py], i) => (
              <circle
                key={i}
                cx={px}
                cy={py}
                r={index === i ? 4.8 : 2.6}
                fill="white"
                stroke={colors[k] || colors.alta}
                strokeWidth="1.8"
              />
            ))}
          </g>
        ))}
        {serie.map((s, i) => (
          <g key={s.mes}>
            <text x={x(i)} y={168} textAnchor="middle">
              {width > 440 || i % 2 === 0 || i === serie.length - 1
                ? monthLabel(s.mes)
                : ""}
            </text>
            <rect
              x={x(i) - 15}
              y={y0}
              height={y1 - y0 + 7}
              width="30"
              fill="transparent"
              tabIndex="0"
              role="button"
              aria-label={
                s.mes + ", " + keys.map((k) => k + " " + s[k]).join(", ")
              }
              onFocus={() => setActivo(i)}
              onBlur={() => setActivo(null)}
              onMouseEnter={() => setActivo(i)}
              onMouseLeave={() => setActivo(null)}
              onClick={() => setActivo(i)}
            />
          </g>
        ))}
      </svg>
      <div className="plot-key" aria-live="polite">
        {index != null ? (
          <b>
            {serie[index].mes} ·{" "}
            {keys
              .map((k) =>
                k === "monto"
                  ? soles(serie[index][k])
                  : k + " " + serie[index][k],
              )
              .join(" · ")}
          </b>
        ) : (
          keys.map((k) => (
            <span key={k}>
              <i style={{ background: colors[k] || colors.alta }} />
              {k === "monto" ? "Monto contratado" : "Prioridad " + k}
            </span>
          ))
        )}
      </div>
    </>
  );
}
function Distribucion({ d }) {
  let offset = 0;
  return (
    <section className="surface distribution">
      <h2>Prioridad de las señales</h2>
      <p>Señales vigentes de las reglas en el periodo</p>
      <div className="ring">
        <svg
          viewBox="0 0 120 120"
          role="img"
          aria-label={d.alertas + " alertas"}
        >
          <circle
            cx="60"
            cy="60"
            r="46"
            fill="none"
            stroke="#edf1f6"
            strokeWidth="12"
          />
          {Object.keys(colors).map((k) => {
            const cuota =
              ((d.severidades[k] || 0) / Math.max(d.alertas, 1)) * 100;
            const inicio = offset;
            offset += cuota;
            return (
              <circle
                key={k}
                cx="60"
                cy="60"
                r="46"
                pathLength="100"
                fill="none"
                stroke={colors[k]}
                strokeWidth="12"
                strokeDasharray={cuota + " " + (100 - cuota)}
                strokeDashoffset={-inicio}
                transform="rotate(-90 60 60)"
              />
            );
          })}
        </svg>
        <div>
          <strong>{numero(d.alertas)}</strong>
          <span>Alertas</span>
        </div>
      </div>
      <div className="severity-legend">
        {Object.keys(colors).map((k) => (
          <span key={k}>
            <i style={{ background: colors[k] }} />
            {k}
            <b>{d.severidades[k] || 0}</b>
          </span>
        ))}
      </div>
    </section>
  );
}
function Indicador({ icon: Icon, label, value, detail, tone }) {
  return (
    <div className="kpi">
      <div>
        <span className={"glyph " + tone}>
          <Icon size={17} />
        </span>
        <h3>{label}</h3>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
function Analitica({ d }) {
  const [modo, setModo] = useState("alertas");
  return (
    <div className="analytics-grid">
      <section className="surface evolution">
        <div className="section-top">
          <div>
            <h2>
              {modo === "monto"
                ? "Evolución de contrataciones"
                : "Evolución de las señales"}
            </h2>
            <p>
              {modo === "monto"
                ? "Importe contratado por mes del expediente"
                : "Señales por mes del expediente y severidad"}
            </p>
          </div>
          <div className="segmented">
            {["alertas", "monto"].map((k) => (
              <button
                key={k}
                aria-pressed={modo === k}
                onClick={() => setModo(k)}
              >
                {k === "monto" ? "Monto" : "Alertas"}
              </button>
            ))}
          </div>
        </div>
        <Curva serie={d.serie} modo={modo} />
      </section>
      <Distribucion d={d} />
    </div>
  );
}
function Economia({ d }) {
  const c = d.concentracion;
  return (
    <>
      <div className="kpis">
        <Indicador
          icon={Wallet}
          tone="blue"
          label="Monto analizado"
          value={corto(d.monto)}
          detail={soles(d.monto)}
        />
        <Indicador
          icon={ChartNoAxesCombined}
          tone="teal"
          label="Concentración HHI"
          value={c.hhi ?? "Sin datos"}
          detail="Suma de cuotas porcentuales al cuadrado"
        />
        <Indicador
          icon={Building2}
          tone="gold"
          label="Cinco principales"
          value={c.top5 == null ? "Sin datos" : c.top5 + " %"}
          detail="Participación en el monto contratado"
        />
        <Indicador
          icon={FileStack}
          tone="purple"
          label="Postor único"
          value={c.un_postor}
          detail="Expedientes con un solo postor"
        />
      </div>
      {!!c.ranking.length && (
        <section className="surface">
          <h2>Participación por proveedor</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Proveedor</th>
                  <th>Contratado</th>
                  <th>Cuota</th>
                </tr>
              </thead>
              <tbody>
                {c.ranking.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <a href={"#proveedores/" + p.id}>{p.nombre}</a>
                    </td>
                    <td>{soles(p.monto)}</td>
                    <td>{p.cuota} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <section className="surface">
        <h2>Áreas con señales de revisión</h2>
        {d.areas.map(([a, n]) => (
          <div className="rank" key={a}>
            <span>{a}</span>
            <meter value={n} max={Math.max(1, d.areas[0][1])} />
            <b>{n}</b>
          </div>
        ))}
        {!d.areas.length && <p>Sin señales en la selección.</p>}
      </section>
    </>
  );
}
export default function Panel({ config, usuario, version, economia = false }) {
  const [f, setF] = useState({}),
    [filtrar, setFiltrar] = useState(false);
  const qs = new URLSearchParams(
    Object.entries(f).filter(([, v]) => v),
  ).toString();
  const state = useData("/dashboard" + (qs ? "?" + qs : ""), version);
  const set = (k, v) => setF((prev) => ({ ...prev, [k]: v }));
  return (
    <Load state={state}>
      {(d) => (
        <>
          <div className="page-heading">
            <div>
              <div className="overline">
                <i />
                Inteligencia institucional
              </div>
              <h1>
                {economia ? "Inteligencia económica" : "Resumen ejecutivo"}
              </h1>
              <p>
                {economia
                  ? "Concentración y participación en las contrataciones analizadas."
                  : "Contrataciones, alertas y prioridades de revisión."}
              </p>
            </div>
            <div className="head-actions">
              <label className="period">
                <CalendarDays size={15} />
                <select
                  aria-label="Periodo de expedientes"
                  value={f.periodo || ""}
                  onChange={(e) => set("periodo", e.target.value)}
                >
                  <option value="">Todo el periodo</option>
                  {d.opciones.periodos.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </label>
              <button className="solid" onClick={() => window.print()}>
                <ArrowDownToLine size={15} /> Exportar informe
              </button>
            </div>
          </div>
          <div className="tools-line">
            <button
              className={"filter-button " + (filtrar ? "selected" : "")}
              aria-expanded={filtrar}
              onClick={() => setFiltrar(!filtrar)}
            >
              <ListFilter size={15} /> Filtros {qs && "•"}
            </button>
            {qs && <button onClick={() => setF({})}>Limpiar filtros</button>}
          </div>
          {filtrar && (
            <div className="filter-grid">
              {[
                [
                  "entidad",
                  "Área",
                  config.entidades.map((e) => [e.id, e.nombre]),
                ],
                [
                  "categoria",
                  "Objeto",
                  d.opciones.categorias.map((x) => [x, x]),
                ],
                [
                  "tipo",
                  "Tipo de proceso",
                  d.opciones.tipos.map((x) => [x, x]),
                ],
                [
                  "estado",
                  "Estado de alerta",
                  [["pendiente", "Pendiente de revisión"], ["confirmada", "Revisada"], ["descartada", "Descartada"]],
                ],
                [
                  "severidad",
                  "Prioridad",
                  [["alta", "Alta"], ["media", "Media"], ["baja", "Baja"]],
                ],
              ].map(([k, label, op]) => (
                <label key={k}>
                  {label}
                  <select
                    value={f[k] || ""}
                    onChange={(e) => set(k, e.target.value)}
                  >
                    <option value="">Todos</option>
                    {op.map(([v, t]) => (
                      <option key={v} value={v}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          )}
          {economia ? (
            <Economia d={d} />
          ) : (
            <>
              <section className="summary-box">
                <div className="summary-icon">
                  <ScanLine size={22} />
                </div>
                <div>
                  <h2>Lectura del periodo</h2>
                  <p>
                    Se analizaron <b>{numero(d.contrataciones)} contrataciones sintéticas</b>{" "}
                    por <b>{soles(d.monto)}</b>.{" "}
                    {d.pendientes ? (
                      <>
                        <b>{numero(d.contratos_con_alerta)} contrataciones</b> presentan al menos
                        una señal de las reglas ({numero(d.pendientes)} señales sin revisar). En el
                        centro de alertas las señales de un mismo patrón se agrupan en un solo caso.
                      </>
                    ) : (
                      "La selección no tiene alertas pendientes."
                    )}
                  </p>
                </div>
              </section>
              {usuario.rol !== "auditor" && <AlertasDestacadas />}
              <h2 className="group-title">Actividad de contratación</h2>
              <div className="kpis">
                <Indicador
                  icon={Wallet}
                  tone="blue"
                  label="Monto analizado"
                  value={corto(d.monto)}
                  detail="Soles contratados"
                />
                <Indicador
                  icon={FileStack}
                  tone="teal"
                  label="Contrataciones"
                  value={numero(d.contrataciones)}
                  detail="En el periodo seleccionado"
                />
                <Indicador
                  icon={Building2}
                  tone="purple"
                  label="Proveedores"
                  value={numero(d.proveedores)}
                  detail="Con contratación registrada"
                />
                <Indicador
                  icon={BellRing}
                  tone="gold"
                  label="Señales sin revisar"
                  value={numero(d.pendientes)}
                  detail="De las reglas sobre contrataciones"
                />
              </div>
              <h2 className="group-title">Análisis de riesgo</h2>
              <Analitica d={d} />
              {usuario.rol !== "auditor" && d.escenario && (
                <div className="focus-grid">
                  {d.escenario && (
                    <section className="case-panel">
                      <div className="case-icon">
                        <Landmark size={24} />
                      </div>
                      <small>CONVOCATORIA DE DEMOSTRACIÓN</small>
                      <h2>Concesión de cafetería universitaria</h2>
                      <p>
                        Consulta las bases, contrasta propuestas y documenta la
                        revisión del comité.
                      </p>
                      <a href={"#convocatorias/" + d.escenario.id}>
                        Abrir convocatoria <ArrowRight size={15} />
                      </a>
                    </section>
                  )}
                </div>
              )}
              <h2 className="group-title">
                Cartera institucional · corte {d.corte}
              </h2>
              <div className="portfolio">
                {[
                  ["Convocatorias abiertas", d.cartera.abiertas],
                  ["Expedientes con trazabilidad", d.cartera.expedientes],
                  ["Alertas de expedientes", d.cartera.alertas_tz],
                  ["Coincidencias pendientes", d.cartera.coincidencias],
                  ["Concesiones activas", d.cartera.concesiones],
                ].map(([t, n]) => (
                  <div key={t}>
                    <strong>{n}</strong>
                    <span>{t}</span>
                  </div>
                ))}
              </div>
            </>
          )}
          <p className="print-only">
            Origen simulado · Responsable {usuario.nombre} ·{" "}
            {new Date().toLocaleString("es-PE", { timeZone: "America/Lima" })}{" "}
            (Lima) · Informe TRZ-RES · TrazaUNT 5.0
          </p>
        </>
      )}
    </Load>
  );
}
