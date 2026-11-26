import React, { useState } from "react";
import { ArrowLeft, ChevronRight, FileText } from "lucide-react";
import { ErrorAccion, Estado, Panel, fecha, label, money, post, useAccion } from "./Comun";
import { Registro } from "./Comparacion";
import { AdjuntarA, Evidencia } from "./Documentos";
import { ListaCoincidencias } from "../Coincidencias";

// v5.1: cada empresa tiene su ficha con datos, admisión, documentos y coincidencias.
// Reemplaza la pestaña «Documentos» con su tabla «Vinculado a».

const DECISIONES = [
  ["admitida", "Admitir", "La empresa sigue en el proceso."],
  ["observada", "Observar", "Debe subsanar algo para seguir."],
  ["no_admitida", "No admitir", "Queda fuera del proceso."],
];
// Una coincidencia toca a la empresa si cualquiera de sus dos lados es la empresa o
// una persona vinculada a ella (representante, socio).
const rucs = (x) => [x?.ruc, x?.empresa?.ruc].filter(Boolean);
const coincidenciasDe = (ficha, p) =>
  (ficha.coincidencias || []).filter((c) => [...rucs(c.sujeto_a), ...rucs(c.sujeto_b)].includes(p.ruc));
const documentosDe = (ficha, p) => ficha.documentos.filter((d) => d.postulante_id === p.id);

function Admision({ ficha, p, done }) {
  const [decision, setDecision] = useState("");
  const action = useAccion();
  return (
    <div className="fl-admision">
      <div className="fl-admision-botones" role="group" aria-label="Decisión de admisión">
        {DECISIONES.map(([k, t]) => (
          <button
            key={k}
            type="button"
            className={"fl-decision " + k}
            aria-pressed={decision === k}
            onClick={() => setDecision(decision === k ? "" : k)}
          >
            {t}
          </button>
        ))}
      </div>
      {decision && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const motivo = new FormData(e.currentTarget).get("motivo");
            action.run(async () => {
              await post("/convocatorias/" + ficha.id + "/postulantes/" + p.id + "/admision", {
                estado: decision,
                motivo,
              });
              setDecision("");
              done();
            });
          }}
        >
          <p className="fl-help">{DECISIONES.find((x) => x[0] === decision)[2]}</p>
          <label>
            Motivo (la empresa verá este texto)
            <textarea name="motivo" required minLength="8" maxLength="2000" rows="3" />
          </label>
          <ErrorAccion error={action.error} />
          <div className="fl-actions">
            <button type="button" onClick={() => setDecision("")}>
              Cancelar
            </button>
            <button className="fl-primary" disabled={action.busy}>
              Registrar decisión
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function FichaEmpresa({ ficha, p, write, refresh, volver, docInicial }) {
  const [doc, setDoc] = useState(docInicial || null);
  const decide = write && ["abierta", "cerrada", "en_evaluacion"].includes(ficha.estado);
  const docs = documentosDe(ficha, p);
  const coinc = coincidenciasDe(ficha, p);
  const ultima = p.admisiones?.at(-1);
  return (
    <>
      <button className="fl-link fl-volver" onClick={volver}>
        <ArrowLeft size={14} /> Todas las empresas
      </button>
      <section className="fl-panel fl-empresa">
        <div className="fl-heading">
          <div>
            <small>Empresa postulante · RUC {p.ruc}</small>
            <h2>{p.razon_social}</h2>
          </div>
          <Estado value={p.admision_texto || "Pendiente de revisión"} />
        </div>
        <dl className="fl-datos">
          <div>
            <dt>Representante</dt>
            <dd>{p.representante || "No registrado"}</dd>
          </div>
          <div>
            <dt>Oferta económica</dt>
            <dd>{money(p.oferta)}</dd>
          </div>
          <div>
            <dt>Experiencia</dt>
            <dd>{p.experiencia != null ? p.experiencia + " años" : "No evaluado"}</dd>
          </div>
          <div>
            <dt>Postuló</dt>
            <dd>{fecha(p.fecha)}</dd>
          </div>
        </dl>
        {ultima && (
          <p className="fl-motivo">
            <b>Motivo comunicado a la empresa:</b> {ultima.motivo}
          </p>
        )}
        {decide && (
          <>
            <h3>Decisión de admisión</h3>
            <Admision ficha={ficha} p={p} done={refresh} />
          </>
        )}
      </section>

      <Panel title={`Documentos de la empresa (${docs.length})`}>
        {write && ficha.estado === "abierta" && (
          <AdjuntarA
            ficha={ficha}
            postulante={p.id}
            onSaved={(id) => {
              setDoc(id);
              refresh();
            }}
          />
        )}
        {docs.length ? (
          <ul className="fl-docs">
            {docs.map((d) => (
              <li key={d.id} className={doc === d.id ? "abierto" : ""}>
                <FileText size={18} aria-hidden="true" />
                <div>
                  <strong>{d.nombre}</strong>
                  <small>
                    {label(d.tipo)} · versión {d.version} · {Math.ceil(d.tamano / 1024)} KB
                  </small>
                </div>
                <Estado value={d.estado} />
                <button onClick={() => setDoc(doc === d.id ? null : d.id)}>
                  {doc === d.id ? "Ocultar" : "Revisar"}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="fl-empty">Esta empresa todavía no presenta documentos.</p>
        )}
      </Panel>
      {doc && docs.some((d) => d.id === doc) && (
        <Evidencia
          key={doc}
          id={doc}
          write={write && !["resultado_registrado", "cancelada"].includes(ficha.estado)}
          volver={() => setDoc(null)}
          actualizar={refresh}
        />
      )}

      <Panel title={`Coincidencias con esta empresa (${coinc.length})`}>
        {coinc.length ? (
          <ListaCoincidencias items={coinc} onCambio={refresh} />
        ) : (
          <p className="fl-empty">No se detectaron coincidencias con esta empresa.</p>
        )}
      </Panel>
    </>
  );
}

export function Postulantes({ ficha, write, refresh, empresa, setEmpresa, docInicial }) {
  const p = ficha.postulantes.find((x) => x.id === empresa);
  if (p)
    return (
      <FichaEmpresa
        key={p.id}
        ficha={ficha}
        p={p}
        write={write}
        refresh={refresh}
        volver={() => setEmpresa(null)}
        docInicial={docInicial}
      />
    );
  return (
    <Panel title={`Empresas postulantes (${ficha.postulantes.length})`}>
      {write && ficha.estado === "abierta" && <Registro ficha={ficha} done={refresh} />}
      {ficha.postulantes.length ? (
        <ul className="fl-empresas">
          {ficha.postulantes.map((x) => {
            const docs = documentosDe(ficha, x).length;
            const coinc = coincidenciasDe(ficha, x).filter((c) => c.estado === "pendiente").length;
            return (
              <li key={x.id}>
                <button className="fl-empresa-fila" onClick={() => setEmpresa(x.id)}>
                  <div>
                    <strong>{x.razon_social}</strong>
                    <small>
                      RUC {x.ruc} · Representante: {x.representante || "No registrado"}
                    </small>
                  </div>
                  <span className="fl-empresa-dato">
                    {money(x.oferta)}
                    <small>oferta</small>
                  </span>
                  <span className="fl-empresa-dato">
                    {docs}
                    <small>{docs === 1 ? "documento" : "documentos"}</small>
                  </span>
                  <span className="fl-empresa-chips">
                    <Estado value={x.admision_texto || "Pendiente de revisión"} />
                    {coinc > 0 && (
                      <span className="fl-state warn">
                        {coinc} {coinc === 1 ? "coincidencia" : "coincidencias"}
                      </span>
                    )}
                  </span>
                  <ChevronRight size={18} aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="fl-empty">Aún no se han registrado postulantes.</p>
      )}
      <p className="fl-help">
        Haz clic en una empresa para ver sus documentos, decidir su admisión y revisar sus
        coincidencias. El sistema compara automáticamente personas y empresas al registrar cada
        postulante.
      </p>
    </Panel>
  );
}

export function DocumentosBases({ ficha, write, refresh }) {
  const [doc, setDoc] = useState(null);
  const docs = ficha.documentos.filter((d) => !d.postulante_id);
  return (
    <>
      <Panel title={`Documentos de las bases (${docs.length})`}>
        {write && ficha.estado === "borrador" && (
          <AdjuntarA
            ficha={ficha}
            onSaved={(id) => {
              setDoc(id);
              refresh();
            }}
          />
        )}
        {docs.length ? (
          <ul className="fl-docs">
            {docs.map((d) => (
              <li key={d.id} className={doc === d.id ? "abierto" : ""}>
                <FileText size={18} aria-hidden="true" />
                <div>
                  <strong>{d.nombre}</strong>
                  <small>
                    {label(d.tipo)} · versión {d.version} · {Math.ceil(d.tamano / 1024)} KB
                  </small>
                </div>
                <Estado value={d.estado} />
                <button onClick={() => setDoc(doc === d.id ? null : d.id)}>
                  {doc === d.id ? "Ocultar" : "Revisar"}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="fl-empty">Aún no se adjuntan las bases.</p>
        )}
      </Panel>
      {doc && (
        <Evidencia
          key={doc}
          id={doc}
          write={write && !["resultado_registrado", "cancelada"].includes(ficha.estado)}
          volver={() => setDoc(null)}
          actualizar={refresh}
        />
      )}
    </>
  );
}
