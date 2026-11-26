import React, { useState } from "react";
import { ArrowLeftRight, ShieldAlert, ChevronDown } from "lucide-react";
import { useConsulta, Carga, useAccion, ErrorAccion, post, fecha } from "./flujo/Comun";

const NIVELES = { alta: "Alta", media: "Media", baja: "Baja" };

function Persona({ p }) {
  return (
    <div className="co-persona">
      <b>{p.nombre}</b>
      <small>
        {p.rol}
        {p.ruc ? " · RUC " + p.ruc : ""}
        {p.empresa ? " · " + p.empresa.nombre : ""}
      </small>
      <small className="co-fuente">Fuente: {p.fuente}</small>
    </div>
  );
}

function Evidencia({ e }) {
  const filas = [
    ["Campo comparado", e.campo],
    ["Valor A", e.valor_a],
    ["Valor B", e.valor_b],
    ["Términos en común", e.terminos?.join(", ")],
    ["Parentesco", e.parentesco ? `${e.parentesco}${e.grado ? " · grado " + e.grado : ""}` : null],
    ["Referencia documental", e.referencia],
    ["Vigente desde", e.desde],
    ["Declaración registrada", e.declaracion],
    ["Criterio", e.criterio],
  ].filter(([, v]) => v);
  return (
    <dl className="co-evidencia">
      {filas.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
      {e.reglas?.length > 0 && (
        <div>
          <dt>Señales del registro de integridad</dt>
          <dd>
            <ul>
              {e.reglas.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </dd>
        </div>
      )}
    </dl>
  );
}

function Revision({ item, alGuardar }) {
  const detalle = useConsulta("/coincidencias/" + item.id, item.estado);
  const action = useAccion();
  function guardar(ev) {
    ev.preventDefault();
    const datos = Object.fromEntries(new FormData(ev.currentTarget));
    action.run(async () => {
      const r = await post("/coincidencias/" + item.id + "/revision", datos);
      alGuardar(r);
    });
  }
  return (
    <div className="co-revision">
      <Carga query={detalle}>
        {(d) =>
          d.revisiones.length > 0 && (
            <ol className="co-historial">
              {d.revisiones.map((r, i) => (
                <li key={i}>
                  <b>{r.decision_texto}</b> · {r.autor} · {fecha(r.fecha)}
                  <p>{r.justificacion}</p>
                </li>
              ))}
            </ol>
          )
        }
      </Carga>
      {item.vigente && (
        <form onSubmit={guardar}>
          <fieldset className="co-decision">
            <legend>Decisión de la revisión humana</legend>
            <label>
              <input type="radio" name="decision" value="aclarada" required defaultChecked={item.estado !== "aclarada"} />
              Aclarada sin incidencia
            </label>
            <label>
              <input type="radio" name="decision" value="derivada" required />
              Derivar a revisión de integridad
            </label>
          </fieldset>
          <label>
            Justificación con referencia a la evidencia
            <textarea name="justificacion" required minLength="15" maxLength="2000"
              placeholder="Ej.: Se verificó el DNI en la declaración jurada; son personas distintas." />
          </label>
          <ErrorAccion error={action.error} />
          <button className="solid" disabled={action.busy}>Registrar revisión</button>
        </form>
      )}
    </div>
  );
}

export function TarjetaCoincidencia({ item, onCambio, mostrarConvocatoria = false }) {
  const [abierta, setAbierta] = useState(false);
  const [x, setX] = useState(item);
  return (
    <article className={"co-card nivel-" + x.nivel + (x.vigente ? "" : " no-vigente")}>
      <header>
        <span className={"co-nivel " + x.nivel}>{NIVELES[x.nivel]}</span>
        <span className="co-tipo">{x.tipo}</span>
        <h3>{x.titulo}</h3>
        <span className={"co-estado " + x.estado}>{x.estado_texto}</span>
      </header>
      {mostrarConvocatoria && x.convocatoria && (
        <a className="co-conv" href={"#convocatorias/" + x.convocatoria.id}>
          {x.convocatoria.codigo} · {x.convocatoria.nombre}
        </a>
      )}
      <div className="co-par">
        <Persona p={x.sujeto_a} />
        <ArrowLeftRight size={18} aria-label="coincide con" />
        <Persona p={x.sujeto_b} />
      </div>
      <p className="co-detalle">{x.detalle}</p>
      <button className="co-toggle" aria-expanded={abierta} onClick={() => setAbierta(!abierta)}>
        {abierta ? "Ocultar evidencia" : "Ver evidencia y revisar"} <ChevronDown size={14} />
      </button>
      {abierta && (
        <>
          <Evidencia e={x.evidencia} />
          <p className="co-aviso"><ShieldAlert size={14} /> {x.aviso}</p>
          <Revision
            item={x}
            alGuardar={(r) => {
              setX({ ...x, ...r });
              onCambio?.();
            }}
          />
        </>
      )}
      <small className="co-meta">Detectada automáticamente el {fecha(x.detectada)}</small>
    </article>
  );
}

export function ListaCoincidencias({ items, onCambio, mostrarConvocatoria }) {
  if (!items.length)
    return <p className="fl-empty">No hay coincidencias para revisar con este filtro.</p>;
  return (
    <div className="co-lista">
      {items.map((x) => (
        <TarjetaCoincidencia key={x.id + x.estado} item={x} onCambio={onCambio} mostrarConvocatoria={mostrarConvocatoria} />
      ))}
    </div>
  );
}

export default function Coincidencias() {
  const [estado, setEstado] = useState("pendiente");
  const [version, setVersion] = useState(0);
  const query = useConsulta("/coincidencias?estado=" + estado, version);
  return (
    <section className="surface">
      <div className="section-top">
        <div>
          <h2>Coincidencias entre personas y empresas</h2>
          <p>
            El sistema compara automáticamente intervinientes, representantes, documentos y
            domicilios cada vez que se registra una convocatoria o una empresa. Son señales para
            revisión, no conflictos confirmados.
          </p>
        </div>
        <div className="segmented">
          {[
            ["pendiente", "Pendientes"],
            ["revisadas", "Revisadas"],
            ["todas", "Todas"],
          ].map(([k, t]) => (
            <button key={k} aria-pressed={estado === k} onClick={() => setEstado(k)}>
              {t}
            </button>
          ))}
        </div>
      </div>
      <Carga query={query}>
        {(d) => (
          <>
            <div className="co-resumen">
              {Object.entries(d.por_nivel).map(([k, n]) => (
                <span key={k} className={"co-nivel " + k}>
                  {NIVELES[k]}: {n}
                </span>
              ))}
            </div>
            <ListaCoincidencias items={d.items} mostrarConvocatoria onCambio={() => setVersion((v) => v + 1)} />
          </>
        )}
      </Carga>
    </section>
  );
}
