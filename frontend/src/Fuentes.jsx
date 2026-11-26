import React, { useState } from "react";
import { Database, ExternalLink, HardHat } from "lucide-react";
import { useConsulta, Carga, Pager, money, fecha } from "./flujo/Comun";

const numero = (n) => new Intl.NumberFormat("es-PE").format(n ?? 0);

function Conjunto({ c }) {
  return (
    <article className="fu-conjunto">
      <header>
        <Database size={18} />
        <div>
          <h3>{c.nombre}</h3>
          <small>{c.tipo}</small>
        </div>
        {c.url && (
          <a href={c.url} target="_blank" rel="noreferrer">
            Fuente oficial <ExternalLink size={12} />
          </a>
        )}
      </header>
      <p>{c.detalle}</p>
      {c.archivos.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Archivo de origen</th>
                <th>Filas leídas</th>
                <th>Universidades</th>
                {c.archivos.some((a) => a.contratos != null) && <th>Contratos</th>}
                <th>UNT</th>
              </tr>
            </thead>
            <tbody>
              {c.archivos.map((a) => (
                <tr key={a.archivo}>
                  <td><code>{a.archivo}</code></td>
                  <td>{numero(a.filas)}</td>
                  <td>{a.universidades != null ? numero(a.universidades) : "—"}</td>
                  {c.archivos.some((x) => x.contratos != null) && <td>{numero(a.contratos)}</td>}
                  <td>{numero(a.unt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {c.metodo && <p className="fu-metodo"><b>Método:</b> {c.metodo} {c.generado && <>· Generado el {fecha(c.generado)}</>}</p>}
    </article>
  );
}

function ContratosCid({ vinculados }) {
  const [q, setQ] = useState("");
  const [buscar, setBuscar] = useState("");
  const [soloUnt, setSoloUnt] = useState(false);
  const [page, setPage] = useState(1);
  const query = useConsulta(`/fuentes/cid?pagina=${page}&tamano=15&solo_unt=${soloUnt}&q=${encodeURIComponent(buscar)}`);
  return (
    <section className="surface">
      <div className="section-top">
        <div>
          <h2><HardHat size={18} /> Obras universitarias en el Cuaderno de Obra Digital</h2>
          <p>Contratos de obra de universidades públicas. Cada registro indica el archivo y las filas de origen.</p>
        </div>
      </div>
      <form className="filters fu-filtros" onSubmit={(e) => { e.preventDefault(); setBuscar(q); setPage(1); }}>
        <label>
          Buscar entidad, obra o contratista
          <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={120} />
        </label>
        <label className="fu-check">
          <input type="checkbox" checked={soloUnt} onChange={(e) => { setSoloUnt(e.target.checked); setPage(1); }} />
          Solo Universidad Nacional de Trujillo
        </label>
        <button>Buscar</button>
      </form>
      <Carga query={query}>
        {(d) => (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Entidad y obra</th>
                    <th>Contratista</th>
                    <th>Monto</th>
                    <th>Asientos</th>
                    <th>Procedencia</th>
                  </tr>
                </thead>
                <tbody>
                  {d.items.map((c) => (
                    <tr key={c.codigo_contrato}>
                      <td>
                        <b>{c.entidad}</b>
                        <small className="fu-objeto">{c.objeto}</small>
                        <small>Contrato {c.codigo_contrato} · {c.numero_contrato} · {c.ubicacion}</small>
                        {vinculados[c.codigo_contrato] && (
                          <a href={"#trazabilidad/" + vinculados[c.codigo_contrato]}>Ver expediente vinculado →</a>
                        )}
                      </td>
                      <td>{c.contratista}<small>{c.tipo_proveedor}</small></td>
                      <td>{money(c.monto)}</td>
                      <td>
                        {numero(c.asientos)}
                        <small>{c.primer_asiento} a {c.ultimo_asiento}</small>
                      </td>
                      <td>
                        {c.fuentes.map((f) => (
                          <small key={f.archivo}><code>{f.archivo}</code> · filas {numero(f.fila_min)}–{numero(f.fila_max)}</small>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager data={d} setPage={setPage} />
          </>
        )}
      </Carga>
    </section>
  );
}

export default function Fuentes() {
  const query = useConsulta("/fuentes/catalogo");
  return (
    <Carga query={query}>
      {(d) => (
        <>
          <p className="notice">{d.aviso}</p>
          <div className="fu-grid">
            {d.conjuntos.map((c) => (
              <Conjunto key={c.nombre} c={c} />
            ))}
          </div>
          <ContratosCid vinculados={d.cid_vinculados} />
        </>
      )}
    </Carga>
  );
}
