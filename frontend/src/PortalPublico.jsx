import React, { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Building2, FileCheck2, HardHat, Landmark, Search } from "lucide-react";
import { Load, useData } from "./Expedientes";
import "./portal.css";

const moneda = new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" });
const numero = new Intl.NumberFormat("es-PE");
const dinero = (v) => (v === "" || v == null ? "No disponible" : moneda.format(Number(v)));
const dia = (v) =>
  v ? new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeZone: "America/Lima" }).format(new Date(v.slice(0, 10) + "T12:00:00-05:00")) : "—";

function descargarPeriodos(periodos) {
  const csv = ["origen,anio,contrataciones,monto_pen", ...periodos.map(
    (p) => ["sintetico", p.anio, p.contrataciones, p.monto].join(","),
  )].join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = "contrataciones-por-anio.csv";
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Indicadores({ tipos, estados, alertas_atendidas, alertas_totales }) {
  return <div className="portal-indicadores">
    <section aria-labelledby="portal-tipos">
      <h3 id="portal-tipos">Contrataciones por tipo de proceso</h3>
      <ul>{tipos.map(({ tipo, contrataciones, monto }) =>
        <li key={tipo}>{tipo} · {numero.format(contrataciones)} · {moneda.format(monto)}</li>
      )}</ul>
    </section>
    <section aria-labelledby="portal-estados">
      <h3 id="portal-estados">Convocatorias por estado</h3>
      <ul>{estados.map(({ estado, cantidad }) =>
        <li key={estado}>{estado.replaceAll("_", " ")} · {numero.format(cantidad)}</li>
      )}</ul>
    </section>
    <section aria-labelledby="portal-alertas">
      <h3 id="portal-alertas">Alertas atendidas</h3>
      <p>{alertas_totales ? new Intl.NumberFormat("es-PE", { style: "percent" }).format(alertas_atendidas / alertas_totales) : "Sin alertas"}</p>
      <small>{alertas_atendidas} de {alertas_totales} alertas vigentes</small>
    </section>
  </div>;
}

function Contrataciones() {
  const datos = useData("/publico/contrataciones");
  const [anio, seleccionar] = useState("");
  return (
    <section className="portal-panel" aria-labelledby="resumen-publico">
      <Load state={datos}>
        {({ periodos, ...indicadores }) => {
          const visibles = anio ? periodos.filter((p) => p.anio === anio) : periodos;
          return <>
            <div className="portal-filtro">
              <h2 id="resumen-publico">Contrataciones registradas por año</h2>
              <div><label htmlFor="periodo-publico">Año</label> <select id="periodo-publico" value={anio} onChange={(e) => seleccionar(e.target.value)}>
                <option value="">Todos los años</option>
                {periodos.map((p) => <option key={p.anio}>{p.anio}</option>)}
              </select></div>
            </div>
            <p className="portal-nota">Las cifras se calculan a partir de registros sintéticos.</p>
            <button className="portal-csv" onClick={() => descargarPeriodos(visibles)} disabled={!visibles.length}>Descargar CSV</button>
            {visibles.length ? <div className="table-wrap"><table>
              <thead><tr><th scope="col">Año</th><th scope="col">Contrataciones</th><th scope="col">Monto registrado</th></tr></thead>
              <tbody>{visibles.map((p) => <tr key={p.anio}>
                <th scope="row">{p.anio}</th>
                <td>{numero.format(p.contrataciones)}</td>
                <td>{moneda.format(p.monto)}</td>
              </tr>)}</tbody>
            </table></div> : <p>No hay registros para el período seleccionado.</p>}
            <Indicadores {...indicadores} />
          </>;
        }}
      </Load>
    </section>
  );
}

function Convocatorias() {
  const datos = useData("/publico/convocatorias");
  return (
    <section className="portal-panel">
      <h2>Convocatorias</h2>
      <Load state={datos}>
        {(d) => <>
          <p className="portal-nota">{d.aviso}</p>
          <div className="pt-convocatorias">
            {d.items.map((c) => (
              <article key={c.codigo}>
                <small>{c.codigo} · {c.modalidad}</small>
                <h3>{c.nombre}</h3>
                <span className={"pt-estado " + c.estado}>{c.estado_texto}</span>
                <dl>
                  <div><dt>Recepción</dt><dd>{dia(c.apertura)} – {dia(c.cierre)}</dd></div>
                  <div><dt>Importe referencial</dt><dd>{moneda.format(c.importe_referencial)}</dd></div>
                  <div><dt>Empresas postulantes</dt><dd>{c.postulantes}</dd></div>
                  <div><dt>Resultado</dt><dd>{c.resultado || "Aún no registrado"}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        </>}
      </Load>
    </section>
  );
}

function ListaExpedientes() {
  const [q, setQ] = useState("");
  const [buscar, setBuscar] = useState("");
  const [origen, setOrigen] = useState("");
  const [pagina, setPagina] = useState(1);
  const datos = useData(`/publico/expedientes?pagina=${pagina}&q=${encodeURIComponent(buscar)}&procedencia=${origen}`);
  return (
    <section className="portal-panel">
      <h2>Trazabilidad de expedientes</h2>
      <p className="portal-nota">Consulta las fases, fechas, documentos (con su huella digital) y fuentes de cada expediente. No se publican nombres de personas.</p>
      <form className="pt-buscar" onSubmit={(e) => { e.preventDefault(); setBuscar(q); setPagina(1); }}>
        <label><Search size={15} /> <input aria-label="Buscar expediente" placeholder="Código, objeto o código SEACE" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <select aria-label="Procedencia" value={origen} onChange={(e) => { setOrigen(e.target.value); setPagina(1); }}>
          <option value="">Toda procedencia</option>
          <option value="publica">Fuente pública (OECE / SEACE)</option>
          <option value="demo">Casos de demostración</option>
          <option value="local">Registros de la universidad</option>
        </select>
        <button>Buscar</button>
      </form>
      <Load state={datos}>
        {(d) => <>
          <div className="table-wrap"><table>
            <thead><tr><th>Expediente</th><th>Tipo</th><th>Monto</th><th>Avance</th><th>Procedencia</th></tr></thead>
            <tbody>{d.items.map((e) => (
              <tr key={e.id}>
                <th scope="row">
                  <a href={"#publico/trazabilidad/" + e.id}>{e.codigo}</a>
                  <small>{e.referencia ? e.referencia + " · " : ""}{e.nombre}</small>
                  {e.cuaderno_obra && <small className="pt-cid"><HardHat size={12} /> Con cuaderno de obra digital</small>}
                </th>
                <td>{e.tipo}</td>
                <td>{dinero(e.monto)}</td>
                <td>{e.fases_cerradas}/{e.fases} fases · {numero.format(e.actuaciones)} actuaciones</td>
                <td>{e.procedencia_texto}</td>
              </tr>
            ))}</tbody>
          </table></div>
          {!d.items.length && <p>Sin resultados.</p>}
          <div className="pt-paginas">
            <button disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
            <span>Página {pagina} de {Math.max(1, Math.ceil(d.total / d.tamano))} · {numero.format(d.total)} expedientes</span>
            <button disabled={pagina * d.tamano >= d.total} onClick={() => setPagina(pagina + 1)}>Siguiente</button>
          </div>
        </>}
      </Load>
    </section>
  );
}

function DetalleExpediente({ id }) {
  const datos = useData("/publico/expedientes/" + id);
  return (
    <section className="portal-panel">
      <a href="#publico/trazabilidad" className="pt-volver"><ArrowLeft size={14} /> Todos los expedientes</a>
      <Load state={datos}>
        {(e) => <>
          <small className="pt-codigo">{e.codigo}{e.referencia ? " · " + e.referencia : ""}</small>
          <h2>{e.nombre}</h2>
          <p className="portal-nota">{e.procedencia_texto} · {e.tipo} · {dinero(e.monto)} · Inicio {dia(e.inicio)}</p>
          <ol className="pt-fases">
            {e.fases.map((f) => (
              <li key={f.orden} className={f.estado}>
                <b>{f.orden}. {f.nombre}</b>
                <span>{f.estado.replaceAll("_", " ")}</span>
                <small>{f.desde ? `${dia(f.desde)} – ${dia(f.hasta)}` : "Sin actuaciones publicadas"} · {f.actuaciones} actuaciones · {f.documentos} documentos</small>
              </li>
            ))}
          </ol>
          {e.cuaderno_obra && (
            <div className="pt-obra">
              <HardHat size={18} />
              <div>
                <b>Cuaderno de Obra Digital: {numero.format(e.cuaderno_obra.asientos)} asientos</b>
                <p>Contrato {e.cuaderno_obra.contrato} ({e.cuaderno_obra.numero_contrato}) · {e.cuaderno_obra.contratista}. Asientos del {dia(e.cuaderno_obra.primer_asiento)} al {dia(e.cuaderno_obra.ultimo_asiento)}; vigencia publicada hasta {dia(e.cuaderno_obra.vigencia_final)}.</p>
                <small>Fuente: {e.cuaderno_obra.conjunto} · {e.cuaderno_obra.archivo}</small>
              </div>
            </div>
          )}
          <div className="pt-columnas">
            <div>
              <h3>Cronología</h3>
              <ol className="pt-cronologia">
                {e.cronologia.slice().reverse().slice(0, 60).map((c, i) => (
                  <li key={i}><small>{dia(c.fecha)}{c.fase ? " · " + c.fase : ""}</small><b>{c.actividad}</b><em>{c.fuente}</em></li>
                ))}
              </ol>
              {e.cronologia.length > 60 && <p className="portal-nota">Se muestran las 60 actuaciones más recientes de {e.cronologia.length}.</p>}
            </div>
            <div>
              <h3><FileCheck2 size={16} /> Documentos</h3>
              {e.documentos.length ? <ul className="pt-docs">{e.documentos.map((d, i) => (
                <li key={i}><b>{d.nombre}</b> · v{d.version}<small>{d.fase} · {dia(d.fecha)}</small><code title={d.sha256}>{d.sha256.slice(0, 16)}…</code></li>
              ))}</ul> : <p className="portal-nota">Sin documentos incorporados.</p>}
              <h3>Fuentes</h3>
              {e.fuentes.length ? <ul className="pt-docs">{e.fuentes.map((f, i) => (
                <li key={i}>{f.url ? <a href={f.url} target="_blank" rel="noreferrer">{f.titulo}</a> : <b>{f.titulo}</b>}<small>{f.tipo}</small></li>
              ))}</ul> : <p className="portal-nota">Registro de la universidad.</p>}
              <h3>Control</h3>
              <p>{e.alertas.vigentes} alertas vigentes · {e.alertas.atendidas} atendidas por la universidad.</p>
            </div>
          </div>
          <p className="portal-nota">{e.aviso}</p>
        </>}
      </Load>
    </section>
  );
}

const SECCIONES = [
  ["contrataciones", "Contrataciones"],
  ["convocatorias", "Convocatorias"],
  ["trazabilidad", "Trazabilidad"],
];

export default function PortalPublico() {
  const leer = () => location.hash.replace(/^#publico\/?/, "").split("/");
  const [[seccion, id], setRuta] = useState(leer());
  useEffect(() => {
    const cambio = () => { setRuta(leer()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", cambio);
    return () => window.removeEventListener("hashchange", cambio);
  }, []);
  const actual = SECCIONES.some(([k]) => k === seccion) ? seccion : "contrataciones";
  return (
    <div className="portal">
      <header className="portal-header">
        <div className="portal-wrap portal-nav">
          <div className="portal-identidad">
            <Landmark size={25} aria-hidden="true" />
            <div><strong>TrazaUNT</strong><small>Universidad Nacional de Trujillo · Transparencia</small></div>
          </div>
          <div className="pt-accesos">
            <a className="portal-equipo" href="/?vista=equipo&perfil=empresa"><Building2 size={15} aria-hidden="true" /> Acceso empresas</a>
            <a className="portal-equipo" href="/?vista=equipo">Acceso universidad <ArrowRight size={16} aria-hidden="true" /></a>
          </div>
        </div>
        <nav className="portal-wrap pt-tabs" aria-label="Secciones de transparencia">
          {SECCIONES.map(([k, t]) => (
            <a key={k} href={"#publico/" + k} aria-current={actual === k ? "page" : undefined}>{t}</a>
          ))}
        </nav>
      </header>
      <main className="portal-wrap">
        {!id && <section className="portal-intro">
          <span className="portal-etiqueta">Datos de demostración</span>
          <h1>Transparencia en contrataciones</h1>
          <p>Consulta cuántas contrataciones se registraron y cuál fue su monto por año, el estado de las convocatorias y la trazabilidad de cada expediente.</p>
        </section>}
        {id && <div className="pt-espacio" />}
        {actual === "contrataciones" && <Contrataciones />}
        {actual === "convocatorias" && <Convocatorias />}
        {actual === "trazabilidad" && (id ? <DetalleExpediente key={id} id={id} /> : <ListaExpedientes />)}
      </main>
      <footer className="portal-wrap portal-pie">TrazaUNT · Consulta pública de demostración · No se publican datos personales</footer>
    </div>
  );
}
