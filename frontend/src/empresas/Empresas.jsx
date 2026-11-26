import React, { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowUpDown, Building2, ChevronRight, RefreshCw, Search } from "lucide-react";
import { request } from "../api";
import { TarjetaAlerta } from "../alertas/CentroAlertas";
import {
  Ayuda,
  Barras,
  BarrasH,
  Cargando,
  ErrorAmigable,
  FiltrosActivos,
  Vacio,
  dia,
  mensajeAmigable,
  mesCorto,
  soles,
} from "../ui/Ui";

// Historial individual por empresa (v5.1). Usa solo los registros existentes del sistema;
// lo que no existe se informa como «no disponible».

const ORDENES = [
  ["alertas", "Más alertas por atender"],
  ["contratos", "Más contratos"],
  ["monto", "Mayor monto contratado"],
  ["nombre", "Nombre (A–Z)"],
];

function Lista() {
  const [q, setQ] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [orden, setOrden] = useState("alertas");
  const [pagina, setPagina] = useState(1);
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [intento, setIntento] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setBusqueda(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    let vivo = true;
    setD((x) => (x ? { ...x, cargando: true } : x));
    request(`/fichas-empresa?${new URLSearchParams({ q: busqueda, orden, pagina, tamano: 15 })}`).then(
      (r) => vivo && (setD(r), setError("")),
      (e) => vivo && setError(e),
    );
    return () => {
      vivo = false;
    };
  }, [busqueda, orden, pagina, intento]);
  return (
    <div className="hx">
      <p className="hx-intro">
        Busca una empresa para ver su historial: contratos, entidades, montos, postulaciones y alertas asociadas.
      </p>
      <div className="hx-filtros">
        <label className="hx-buscar">
          <Search size={16} aria-hidden="true" />
          <input
            aria-label="Buscar empresa"
            placeholder="Nombre o RUC de la empresa"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPagina(1);
            }}
            autoFocus
          />
        </label>
        <label>
          Ordenar por
          <select
            value={orden}
            onChange={(e) => {
              setOrden(e.target.value);
              setPagina(1);
            }}
          >
            {ORDENES.map(([k, t]) => (
              <option key={k} value={k}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </div>
      <FiltrosActivos filtros={[["q", "«" + busqueda + "»", busqueda]]} quitar={() => setQ("")} limpiar={() => setQ("")} />
      <ErrorAmigable error={error} reintentar={() => setIntento((n) => n + 1)} />
      {!d ? (
        !error && <Cargando texto="Cargando empresas…" />
      ) : (
        <>
          <p className="hx-conteo" aria-live="polite">
            {d.cargando ? "Actualizando…" : `${d.total} empresas registradas`}
          </p>
          {d.items.length ? (
            <div className="hx-tabla">
              <table>
                <thead>
                  <tr>
                    <th>Empresa</th>
                    <th>Contratos</th>
                    <th>Monto contratado</th>
                    <th>Entidades</th>
                    <th>Última contratación</th>
                    <th>Alertas por atender</th>
                    <th>
                      <span className="sr-only">Abrir</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {d.items.map((e) => (
                    <tr key={e.id} onClick={() => (location.hash = "#empresas/" + e.id)} className="hx-fila">
                      <td>
                        <a href={"#empresas/" + e.id} onClick={(ev) => ev.stopPropagation()}>
                          {e.nombre}
                        </a>
                        <small>RUC {e.ruc}</small>
                      </td>
                      <td>{e.contratos}</td>
                      <td>{e.contratos ? soles(e.monto) : "—"}</td>
                      <td>{e.entidades || "—"}</td>
                      <td>{e.ultima ? dia(e.ultima) : e.postulaciones ? "Solo postulaciones" : "—"}</td>
                      <td>{e.alertas ? <span className="hx-alertas">{e.alertas}</span> : <span className="hx-cero">0</span>}</td>
                      <td>
                        <ChevronRight size={16} aria-hidden="true" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Vacio titulo="No encontramos esa empresa">Revisa el nombre o escribe el RUC completo (11 dígitos).</Vacio>
          )}
          {d.total > d.tamano && (
            <div className="hx-paginas">
              <button disabled={pagina === 1} onClick={() => setPagina(pagina - 1)}>
                Anterior
              </button>
              <span>
                Página {pagina} de {Math.ceil(d.total / d.tamano)}
              </span>
              <button disabled={pagina * d.tamano >= d.total} onClick={() => setPagina(pagina + 1)}>
                Siguiente
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Indice({ empresa, ifp: inicial }) {
  const [ifp, setIfp] = useState(inicial);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [hecho, setHecho] = useState("");
  if (!ifp)
    return (
      <p className="hx-nd">
        El índice de fiabilidad solo se calcula para las empresas del registro de demostración.
      </p>
    );
  return (
    <div className="hx-ifp">
      <div className="hx-ifp-top">
        <div className="hx-ifp-valor">
          <b>{ifp.ifp == null ? "—" : Math.round(ifp.ifp)}</b>
          <small>de 100</small>
        </div>
        <div>
          <p>
            <b>{ifp.nivel}</b> · información disponible {Math.round(ifp.cobertura)} % · confianza {String(ifp.confianza).toLowerCase()}
          </p>
          <p className="hx-nota">
            Resume 7 aspectos de la empresa con pesos según el tipo de contratación. Con poca información el índice no es
            concluyente. Datos simulados.
          </p>
        </div>
        <button
          disabled={ocupado}
          onClick={async () => {
            setOcupado(true);
            setError("");
            try {
              const r = await request("/proveedores/verificar", {
                method: "POST",
                body: JSON.stringify({ ruc: empresa.ruc, modo: "demo", categoria: ifp.categoria || "servicios" }),
              });
              setIfp(r);
              setHecho("Evaluación registrada con tu nombre y la fecha de hoy.");
            } catch (e) {
              setError(mensajeAmigable(e));
            } finally {
              setOcupado(false);
            }
          }}
        >
          <RefreshCw size={14} /> {ocupado ? "Evaluando…" : "Evaluar de nuevo"}
        </button>
      </div>
      {hecho && (
        <p className="hx-ok" role="status">
          {hecho}
        </p>
      )}
      {error && (
        <p className="hx-error" role="alert">
          {error}
        </p>
      )}
      {ifp.impedimentos?.length > 0 && (
        <p className="hx-impedimento">
          <b>Posible impedimento:</b> {ifp.impedimentos.map((x) => x.referencia).join(", ")}. {ifp.impedimentos[0].accion}
        </p>
      )}
      <ul className="hx-dimensiones">
        {ifp.dimensiones?.map((x) => {
          // El backend expresa cada aspecto entre 0 y 1; se muestra sobre 100 como el índice.
          const v = x.valor == null ? null : Math.round((x.valor <= 1 ? x.valor * 100 : x.valor));
          return (
          <li key={x.clave}>
            <span>
              {x.nombre} <small>peso {x.peso} %</small>
            </span>
            <span className="hx-dim-pista">
              {v != null && <span className="hx-dim-barra" style={{ width: `${v}%` }} />}
            </span>
            <b>{v == null ? "Sin dato" : v}</b>
            {v == null && <small className="hx-dim-motivo">{x.motivo}</small>}
          </li>
          );
        })}
      </ul>
    </div>
  );
}

function Contratos({ items }) {
  const [orden, setOrden] = useState(["fecha", -1]);
  const lista = useMemo(() => {
    const [k, dir] = orden;
    return [...items].sort((a, b) => (a[k] > b[k] ? dir : a[k] < b[k] ? -dir : 0));
  }, [items, orden]);
  const th = (k, t) => (
    <th aria-sort={orden[0] === k ? (orden[1] > 0 ? "ascending" : "descending") : undefined}>
      <button className="hx-ordenar" onClick={() => setOrden([k, orden[0] === k ? -orden[1] : -1])}>
        {t} <ArrowUpDown size={12} aria-hidden="true" />
      </button>
    </th>
  );
  if (!items.length) return <Vacio titulo="Sin contratos en este periodo" />;
  return (
    <div className="hx-tabla">
      <table>
        <thead>
          <tr>
            {th("fecha", "Fecha")}
            {th("codigo", "Proceso")}
            {th("entidad", "Entidad")}
            {th("monto", "Monto")}
            {th("postores", "Postores")}
            <th>Alertas</th>
          </tr>
        </thead>
        <tbody>
          {lista.map((c) => (
            <tr key={c.id}>
              <td>{dia(c.fecha)}</td>
              <td>
                <a href={c.enlace}>{c.codigo}</a>
                <small>
                  {c.objeto} · {c.tipo}
                </small>
              </td>
              <td>{c.entidad}</td>
              <td>{soles(c.monto)}</td>
              <td>{c.postores}</td>
              <td>{c.alertas.length ? [...new Set(c.alertas)].map((x) => <span key={x} className="hx-regla">{x}</span>) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Ficha({ id }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [tipo, setTipo] = useState("");
  const [vista, setVista] = useState("resumen");
  useEffect(() => {
    request("/fichas-empresa/" + encodeURIComponent(id)).then(setD, setError);
  }, [id]);
  const filtrado = useMemo(() => {
    if (!d) return null;
    const dentro = (f) => (!desde || (f || "") >= desde) && (!hasta || (f || "") <= hasta);
    const contratos = d.contratos.filter((c) => dentro(c.fecha) && (!tipo || c.tipo === tipo));
    const alertas = d.alertas.filter((a) => dentro(a.fecha_hecho));
    const meses = {};
    for (const c of contratos) {
      const m = (meses[c.fecha.slice(0, 7)] ||= { monto: 0, contratos: 0, alertas: 0 });
      m.monto += c.monto;
      m.contratos += 1;
    }
    for (const a of alertas) if (a.fecha_hecho) (meses[a.fecha_hecho.slice(0, 7)] ||= { monto: 0, contratos: 0, alertas: 0 }).alertas += 1;
    return {
      contratos,
      alertas,
      meses: Object.entries(meses).sort(([a], [b]) => (a < b ? -1 : 1)),
      linea: d.linea_tiempo.filter((e) => dentro(e.fecha)),
    };
  }, [d, desde, hasta, tipo]);
  if (error)
    return (
      <div className="hx">
        <a href="#empresas" className="hx-volver">
          <ArrowLeft size={15} /> Empresas
        </a>
        <ErrorAmigable error={error} />
      </div>
    );
  if (!d) return <Cargando texto="Armando el historial de la empresa…" />;
  const e = d.empresa;
  const r = d.resumen;
  const tipos = [...new Set(d.contratos.map((c) => c.tipo))];
  const VISTAS = [
    ["resumen", "Resumen"],
    ["contratos", `Contratos (${filtrado.contratos.length})`],
    ["alertas", `Alertas (${filtrado.alertas.length})`],
    ["linea", "Línea de tiempo"],
    ["fiabilidad", "Índice de fiabilidad"],
  ];
  return (
    <div className="hx">
      <a href="#empresas" className="hx-volver">
        <ArrowLeft size={15} /> Todas las empresas
      </a>
      <header className="hx-cabecera">
        <div className="hx-cabecera-icono" aria-hidden="true">
          <Building2 size={26} />
        </div>
        <div>
          <small>RUC {e.ruc}</small>
          <h2>{e.nombre}</h2>
          <p>
            Representante: {e.representante || "No disponible"} · Domicilio: {e.domicilio || "No disponible"} · Constituida el{" "}
            {dia(e.constitucion)}
          </p>
        </div>
        <span className="hx-origen">{e.origen}</span>
      </header>

      <div className="hx-kpis">
        <div>
          <b>{r.participaciones}</b>
          <span>
            Participaciones{" "}
            <Ayuda etiqueta="">
              Contratos adjudicados más postulaciones a convocatorias. El sistema no guarda procesos en los que la empresa
              participó sin ganar fuera de las convocatorias.
            </Ayuda>
          </span>
        </div>
        <div>
          <b>{r.contratos}</b>
          <span>Contratos adjudicados</span>
        </div>
        <div>
          <b>{r.entidades}</b>
          <span>Entidades con las que contrató</span>
        </div>
        <div>
          <b>{r.contratos ? soles(r.monto_total) : "—"}</b>
          <span>Monto contratado</span>
        </div>
        <div className={r.alertas_abiertas ? "alerta" : ""}>
          <b>{r.alertas_abiertas}</b>
          <span>Alertas por atender ({r.alertas} en total)</span>
        </div>
      </div>

      <div className="hx-filtros">
        <label>
          Desde
          <input type="date" value={desde} max={hasta || undefined} onChange={(ev) => setDesde(ev.target.value)} />
        </label>
        <label>
          Hasta
          <input type="date" value={hasta} min={desde || undefined} onChange={(ev) => setHasta(ev.target.value)} />
        </label>
        {tipos.length > 1 && (
          <label>
            Tipo de contratación
            <select value={tipo} onChange={(ev) => setTipo(ev.target.value)}>
              <option value="">Todos</option>
              {tipos.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      <FiltrosActivos
        filtros={[
          ["desde", "Desde " + dia(desde), desde],
          ["hasta", "Hasta " + dia(hasta), hasta],
          ["tipo", tipo, tipo],
        ]}
        quitar={(k) => ({ desde: setDesde, hasta: setHasta, tipo: setTipo })[k]("")}
        limpiar={() => {
          setDesde("");
          setHasta("");
          setTipo("");
        }}
      />

      <div className="hx-tabs" role="tablist">
        {VISTAS.map(([k, t]) => (
          <button key={k} role="tab" aria-selected={vista === k} onClick={() => setVista(k)}>
            {t}
          </button>
        ))}
      </div>

      {vista === "resumen" && (
        <div className="hx-grid">
          <Barras
            titulo="Monto contratado por mes"
            descripcion="Suma de los contratos adjudicados en cada mes (soles)."
            datos={filtrado.meses.map(([m, v]) => ({ etiqueta: mesCorto(m), valor: v.monto }))}
            vacio="Sin contratos adjudicados en el periodo."
          />
          <Barras
            titulo="Contratos por mes"
            descripcion="Cantidad de contratos adjudicados en cada mes."
            datos={filtrado.meses.map(([m, v]) => ({ etiqueta: mesCorto(m), valor: v.contratos }))}
            formato={(n) => String(n)}
            vacio="Sin contratos adjudicados en el periodo."
          />
          <BarrasH
            titulo="Alertas por tipo"
            descripcion="Señales asociadas a la empresa, según su categoría."
            datos={Object.entries(d.categorias).map(([k, t]) => ({
              etiqueta: t,
              valor: filtrado.alertas.filter((a) => a.categoria === k).length,
              color: k === "conflicto" || k === "colusion" ? "rojo" : k === "fraccionamiento" || k === "concentracion" ? "dorado" : "azul",
            }))}
            vacio="La empresa no tiene alertas en el periodo."
          />
          <Barras
            titulo="Alertas en el tiempo"
            descripcion="Alertas según la fecha del hecho que las originó."
            datos={filtrado.meses.map(([m, v]) => ({ etiqueta: mesCorto(m), valor: v.alertas }))}
            formato={(n) => String(n)}
            color="dorado"
            vacio="La empresa no tiene alertas en el periodo."
          />
          <section className="hx-panel">
            <h3>Entidades con las que contrató</h3>
            {d.entidades.length ? (
              <ul className="hx-entidades">
                {d.entidades.map((x) => (
                  <li key={x.nombre}>
                    <span>{x.nombre}</span>
                    <small>
                      {x.contratos} {x.contratos === 1 ? "contrato" : "contratos"} · {soles(x.monto)}
                    </small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hx-nd">No disponible: la empresa no tiene contratos adjudicados registrados.</p>
            )}
          </section>
          <section className="hx-panel">
            <h3>Postulaciones a convocatorias</h3>
            {d.postulaciones.length ? (
              <ul className="hx-entidades">
                {d.postulaciones.map((x) => (
                  <li key={x.convocatoria}>
                    <a href={x.enlace}>{x.convocatoria}</a>
                    <small>
                      {x.nombre} · oferta {soles(x.oferta)} · admisión: {x.admision.replace("_", " ")}
                      {x.adjudicada ? " · adjudicada" : ""}
                    </small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hx-nd">No registra postulaciones a convocatorias.</p>
            )}
          </section>
          {d.limitaciones.length > 0 && (
            <ul className="hx-limitaciones">
              {d.limitaciones.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {vista === "contratos" && <Contratos items={filtrado.contratos} />}
      {vista === "alertas" &&
        (filtrado.alertas.length ? (
          <div className="ca-lista-alertas">
            {filtrado.alertas.map((a) => (
              <TarjetaAlerta key={a.uid} a={a} abrir={(uid) => (location.hash = "#alertas/" + uid)} />
            ))}
          </div>
        ) : (
          <Vacio titulo="Sin alertas en el periodo">Esta empresa no tiene señales asociadas con los filtros elegidos.</Vacio>
        ))}
      {vista === "linea" && (
        <ol className="hx-linea">
          {filtrado.linea.map((x, i) => (
            <li key={i} className={x.tipo}>
              <span className="hx-linea-punto" aria-hidden="true" />
              <div>
                <small>{dia(x.fecha)}</small>
                <strong>
                  {x.enlace ? <a href={x.enlace}>{x.titulo}</a> : x.uid ? <a href={"#alertas/" + x.uid}>{x.titulo}</a> : x.titulo}
                </strong>
                <p>{x.detalle}</p>
              </div>
            </li>
          ))}
          {!filtrado.linea.length && <Vacio titulo="Sin acontecimientos en el periodo" />}
        </ol>
      )}
      {vista === "fiabilidad" && <Indice empresa={e} ifp={d.ifp} />}
    </div>
  );
}

export default function Empresas({ id }) {
  return id ? <Ficha key={id} id={id} /> : <Lista />;
}
