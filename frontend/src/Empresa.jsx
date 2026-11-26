import React, { useEffect, useState } from "react";
import { Building2, CheckCircle2, Circle, CircleDot, FileUp, LogOut, ArrowLeft, Send } from "lucide-react";
import { request } from "./api";
import { useConsulta, Carga, useAccion, ErrorAccion, post, money, fecha, Estado, Datos } from "./flujo/Comun";


function Etapas({ etapas }) {
  return (
    <ol className="em-etapas" aria-label="Avance de la convocatoria">
      {etapas.map((e) => (
        <li key={e.clave} className={e.estado}>
          {e.estado === "completa" ? <CheckCircle2 size={18} /> : e.estado === "actual" ? <CircleDot size={18} /> : <Circle size={18} />}
          <span>{e.nombre}</span>
        </li>
      ))}
    </ol>
  );
}

function Tarjeta({ c }) {
  return (
    <a className="em-card" href={"#empresa/" + c.id}>
      <small>{c.codigo} · {c.modalidad}</small>
      <h3>{c.nombre}</h3>
      <div className="em-chips">
        <Estado value={c.estado_texto} />
        {c.postulado && <Estado value={c.admision_texto} />}
        {c.resultado === "seleccionada" && <span className="fl-state ok">Seleccionada</span>}
        {c.resultado === "no_seleccionada" && <span className="fl-state neutral">No seleccionada</span>}
      </div>
      <p>
        Recepción del {fecha(c.apertura)} al {fecha(c.cierre)}
        {c.postulado ? ` · ${c.documentos} documento(s) presentado(s)` : ""}
      </p>
      <span className="em-link">{c.postulado ? "Ver seguimiento" : "Ver bases y postular"} →</span>
    </a>
  );
}

function Inicio({ version }) {
  const query = useConsulta("/empresa/resumen", version);
  return (
    <Carga query={query}>
      {(d) => (
        <>
          <section className="em-hero">
            <Building2 size={26} />
            <div>
              <h1>{d.empresa.razon_social}</h1>
              <p>RUC {d.empresa.ruc} · Consulta el avance de tus postulaciones y la revisión de tus documentos.</p>
            </div>
          </section>
          <h2 className="em-titulo">Mis postulaciones</h2>
          {d.postulaciones.length ? (
            <div className="em-grid">{d.postulaciones.map((c) => <Tarjeta key={c.id} c={c} />)}</div>
          ) : (
            <p className="fl-empty">Aún no has postulado a una convocatoria.</p>
          )}
          <h2 className="em-titulo">Convocatorias con recepción abierta</h2>
          {d.disponibles.length ? (
            <div className="em-grid">{d.disponibles.map((c) => <Tarjeta key={c.id} c={c} />)}</div>
          ) : (
            <p className="fl-empty">No hay convocatorias abiertas en este momento.</p>
          )}
        </>
      )}
    </Carga>
  );
}

function Postular({ c, done }) {
  const action = useAccion();
  function enviar(e) {
    e.preventDefault();
    const v = Object.fromEntries(new FormData(e.currentTarget));
    action.run(async () => {
      await post(`/empresa/convocatorias/${c.id}/postulacion`, { oferta: v.oferta, experiencia: Number(v.experiencia) });
      done();
    });
  }
  return (
    <section className="fl-panel em-postular">
      <h2>Postular a esta convocatoria</h2>
      <p className="fl-help">Al registrar tu postulación, la universidad comparará automáticamente los datos de tu empresa con los de las personas que intervienen en el proceso, como control preventivo.</p>
      <form onSubmit={enviar} className="fl-grid">
        <label>
          Oferta económica (S/)
          <input name="oferta" type="number" min="0.01" step="0.01" required />
        </label>
        <label>
          Años de experiencia
          <input name="experiencia" type="number" min="0" max="150" required />
        </label>
        <div className="em-acciones">
          <ErrorAccion error={action.error} />
          <button className="solid" disabled={action.busy}><Send size={15} /> Registrar postulación</button>
        </div>
      </form>
    </section>
  );
}

function Subir({ c, done }) {
  const action = useAccion();
  function enviar(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    action.run(async () => {
      await request(`/empresa/convocatorias/${c.id}/documentos`, { method: "POST", body: form });
      e.target.reset();
      done();
    });
  }
  return (
    <form onSubmit={enviar} className="em-subir">
      <label>
        Tipo de documento
        <select name="tipo" required defaultValue="propuesta">
          <option value="propuesta">Propuesta técnica o económica</option>
          <option value="anexo">Anexo</option>
          <option value="garantia">Garantía</option>
          <option value="otro">Otro</option>
        </select>
      </label>
      <label>
        Archivo (PDF, Word, Excel, CSV o TXT · máx. 4 MiB)
        <input name="archivo" type="file" required accept=".pdf,.docx,.xlsx,.csv,.txt" />
      </label>
      <ErrorAccion error={action.error} />
      <button className="solid" disabled={action.busy}><FileUp size={15} /> Presentar documento</button>
    </form>
  );
}

function Detalle({ id }) {
  const [version, setVersion] = useState(0);
  const query = useConsulta("/empresa/convocatorias/" + id, version);
  const refrescar = () => setVersion((v) => v + 1);
  return (
    <Carga query={query}>
      {(c) => (
        <>
          <a href="#empresa" className="em-volver"><ArrowLeft size={15} /> Mis postulaciones</a>
          <div className="em-cabecera">
            <div>
              <small>{c.codigo} · {c.modalidad} · {c.area}</small>
              <h1>{c.nombre}</h1>
            </div>
            <Estado value={c.estado_texto} />
          </div>
          <Etapas etapas={c.etapas} />
          <p className="notice">{c.aviso}</p>
          {c.puede_postular && <Postular c={c} done={refrescar} />}
          {c.postulado && (
            <div className="em-dos">
              <section className="fl-panel">
                <h2>Estado de mi postulación</h2>
                <div className="em-admision">
                  <span>Admisión</span>
                  <Estado value={c.admision_texto} />
                </div>
                {c.resultado && (
                  <div className="em-admision">
                    <span>Resultado</span>
                    <span className={"fl-state " + (c.resultado === "seleccionada" ? "ok" : "neutral")}>
                      {c.resultado === "seleccionada" ? "Tu empresa fue seleccionada" : "No seleccionada"}
                    </span>
                  </div>
                )}
                {c.admisiones.length > 0 && (
                  <ol className="em-decisiones">
                    {c.admisiones.slice().reverse().map((a, i) => (
                      <li key={i}>
                        <b>{a.estado_texto}</b> · {fecha(a.fecha)}
                        <p>{a.motivo}</p>
                      </li>
                    ))}
                  </ol>
                )}
                <Datos items={[
                  ["Oferta presentada", money(c.postulacion.oferta)],
                  ["Experiencia declarada", c.postulacion.experiencia + " años"],
                  ["Fecha de postulación", fecha(c.postulacion.fecha)],
                ]} />
              </section>
              <section className="fl-panel">
                <h2>Mis documentos</h2>
                <div className="fl-table">
                  <table>
                    <thead>
                      <tr><th>Documento</th><th>Versión</th><th>Revisión</th><th>Integridad</th></tr>
                    </thead>
                    <tbody>
                      {c.documentos_propios.map((d) => (
                        <tr key={d.id}>
                          <th scope="row">{d.nombre}<small>{d.tipo} · {fecha(d.fecha)}</small></th>
                          <td>v{d.version}</td>
                          <td><Estado value={d.estado_texto} /></td>
                          <td>Huella registrada</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!c.documentos_propios.length && <p className="fl-empty">Aún no presentaste documentos.</p>}
                {c.estado === "abierta" && <Subir c={c} done={refrescar} />}
              </section>
            </div>
          )}
          <div className="em-dos">
            <section className="fl-panel">
              <h2>Información general</h2>
              <p>{c.objeto}</p>
              {c.descripcion && <p className="fl-help">{c.descripcion}</p>}
              <Datos items={[
                ["Importe referencial", money(c.presupuesto)],
                ["Plazo", c.duracion_meses + " meses"],
                ["Recepción", `${fecha(c.apertura)} – ${fecha(c.cierre)}`],
                ["Ubicación", c.ubicacion || "—"],
                ["Comité", c.comite],
              ]} />
              <h3>Requisitos de admisibilidad</h3>
              <ul className="fl-list">{c.requisitos.map((r) => <li key={r}>{r}</li>)}</ul>
              <h3>Criterios de evaluación</h3>
              <ul className="fl-list">{c.criterios.map((k) => <li key={k.nombre}>{k.nombre} · {k.peso} %</li>)}</ul>
            </section>
            <section className="fl-panel">
              <h2>Historial</h2>
              <ol className="em-timeline">
                {c.historial.map((h, i) => (
                  <li key={i} className={h.tipo}>
                    <small>{fecha(h.fecha)}</small>
                    <b>{h.titulo}</b>
                    {h.detalle && <p>{h.detalle}</p>}
                  </li>
                ))}
              </ol>
            </section>
          </div>
        </>
      )}
    </Carga>
  );
}

export default function EmpresaApp({ usuario, onSalir }) {
  const [ruta, setRuta] = useState(location.hash.slice(1) || "empresa");
  useEffect(() => {
    const cambio = () => {
      setRuta(location.hash.slice(1) || "empresa");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", cambio);
    return () => window.removeEventListener("hashchange", cambio);
  }, []);
  const [, id] = ruta.split("/");
  return (
    <div className="em-shell">
      <header className="em-top">
        <a href="#empresa" className="wordmark" aria-label="TrazaUNT, portal de empresas">
          <img src="/assets/brand.svg" alt="" />
          <strong>Traza<span>UNT</span></strong>
          <em>Portal de empresas</em>
        </a>
        <div className="em-cuenta">
          <span className="demo-pill"><i />Datos sintéticos</span>
          <span><b>{usuario.nombre}</b><small>Perfil empresa</small></span>
          <button onClick={onSalir}><LogOut size={15} /> Salir</button>
        </div>
      </header>
      <main className="em-main" id="contenido">
        {id ? <Detalle key={id} id={id} /> : <Inicio />}
      </main>
      <footer className="em-pie">
        TrazaUNT · Universidad Nacional de Trujillo · Solo ves la información de tu propia empresa.
      </footer>
    </div>
  );
}
