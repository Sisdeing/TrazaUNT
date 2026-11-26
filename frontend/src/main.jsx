import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BellRing,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Database,
  Files,
  Home,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import "@fontsource-variable/inter";
import "./styles/tokens.css";
import "./styles.css";
import "./institucional.css";
import "./v5.css";
import { request } from "./api";
import {
  Detail,
  Ethics,
  History,
  Listing,
  Load,
  Pagination,
  useData,
} from "./Expedientes";
export { Badge, RevisionForm } from "./Expedientes";
import Acceso from "./Acceso";
import PortalPublico from "./PortalPublico";
import Panel from "./Panel";
import Coincidencias from "./Coincidencias";
import Fuentes from "./Fuentes";
import EmpresaApp from "./Empresa";
import { Convocatorias, Concesiones } from "./flujo/Flujo";
import Trazabilidad from "./traza/Trazabilidad";
import { Notificaciones } from "./Operacion";

// Navegación simplificada (v5): se retiraron Conflictos de interés, Declaraciones,
// Proveedores, Reportes, Inteligencia económica, Gobierno del modelo y Pronóstico.
// Sus datos se conservan en la base y siguen alimentando las coincidencias y alertas.
const grupos = [
  [
    "Inicio",
    [
      ["inicio", "Resumen ejecutivo", LayoutDashboard],
      ["alertas", "Alertas y coincidencias", BellRing],
    ],
  ],
  [
    "Contrataciones",
    [
      ["convocatorias", "Convocatorias", Landmark],
      ["trazabilidad", "Expedientes y trazabilidad", Workflow],
      ["concesiones", "Concesiones", Files],
    ],
  ],
];
// v5.1: «Datos y fuentes» y la «Bitácora» salen del menú principal. Las fuentes quedan
// como enlace al pie de la barra lateral y la bitácora solo la ve Administración.
const SECUNDARIAS = { fuentes: "Datos y fuentes", historial: "Bitácora de auditoría" };
const RETIRADAS = ["economia", "proveedores", "conflictos", "declaraciones", "reportes", "metricas", "predicciones", "asistente"];
const todos = grupos.flatMap(([, items]) => items);
function permitido(id, rol) {
  if (id === "historial") return rol === "administrador";
  if (rol === "auditor") return ["inicio", "etica"].includes(id);
  if (rol === "consulta") return ["inicio", "etica"].includes(id);
  return true;
}
function Busqueda({ cerrar }) {
  const [q, setQ] = useState(""),
    [resultado, setResultado] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    setResultado(null);
    setError("");
    if (q.trim().length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(
      () =>
        request("/buscar?q=" + encodeURIComponent(q.trim()), {
          signal: controller.signal,
        })
          .then(setResultado)
          .catch((e) => {
            if (e.name !== "AbortError") setError(e.message);
          }),
      220,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [q]);
  return (
    <>
      <div className="section-top">
        <h2>Búsqueda global</h2>
        <button
          className="icon-button"
          aria-label="Cerrar búsqueda"
          onClick={cerrar}
        >
          <X size={18} />
        </button>
      </div>
      <label>
        Buscar por nombre, código o RUC
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Escribe al menos dos caracteres"
        />
      </label>
      {error && <p role="alert">{error}</p>}
      {resultado?.items.map((x) => (
        <a key={x.ruta} href={x.ruta} className="result" onClick={cerrar}>
          <small>
            {x.tipo} · {x.codigo}
          </small>
          {x.titulo}
          <ChevronRight size={14} />
        </a>
      ))}
      {resultado && !resultado.items.length && <p>Sin coincidencias.</p>}
    </>
  );
}
function Alertas({ config, usuario, version }) {
  const [tab, setTab] = useState("coincidencias");
  return (
    <>
      <div className="segmented">
        {[
          ["coincidencias", "Coincidencias persona–empresa"],
          ["expedientes", "Alertas de contrataciones"],
          ["bandeja", "Señales por familia"],
        ].map(([k, t]) => (
          <button key={k} aria-pressed={tab === k} onClick={() => setTab(k)}>
            {t}
          </button>
        ))}
      </div>
      {tab === "coincidencias" && <Coincidencias />}
      {tab === "expedientes" && <Listing alerts config={config} version={version} />}
      {tab === "bandeja" && <Notificaciones usuario={usuario} />}
    </>
  );
}
function Auditoria({ version }) {
  const [tab, setTab] = useState("revisiones"),
    [page, setPage] = useState(1);
  const data = useData("/auditoria?pagina=" + page, version);
  return (
    <>
      <div className="segmented">
        <button
          aria-pressed={tab === "revisiones"}
          onClick={() => setTab("revisiones")}
        >
          Revisiones de alertas
        </button>
        <button
          aria-pressed={tab === "accesos"}
          onClick={() => setTab("accesos")}
        >
          Operaciones y accesos
        </button>
      </div>
      {tab === "revisiones" ? (
        <History version={version} />
      ) : (
        <section className="surface">
          <Load state={data}>
            {(d) => (
              <>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Hora de Lima</th>
                        <th>Cuenta</th>
                        <th>Operación</th>
                        <th>HTTP</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.items.map((x) => (
                        <tr key={x.id}>
                          <td>
                            {new Date(x.fecha).toLocaleString("es-PE", {
                              timeZone: "America/Lima",
                            })}
                          </td>
                          <td>{x.usuario}</td>
                          <td>
                            {x.accion} {x.ruta}
                          </td>
                          <td>{x.estado}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination data={d} page={page} setPage={setPage} />
              </>
            )}
          </Load>
        </section>
      )}
    </>
  );
}
export function App({ usuario, onSalir }) {
  const [ruta, setRuta] = useState(location.hash.slice(1) || "inicio"),
    [menu, setMenu] = useState(false),
    [mini, setMini] = useState(false),
    [dialog, setDialog] = useState(""),
    [version, setVersion] = useState(0),
    [notice, setNotice] = useState("");
  const modal = useRef(null),
    config = useData("/configuracion");
  const [page, id] = ruta.split("/");
  const nombre =
    todos.find(([k]) => k === page)?.[1] ||
    {
      ...SECUNDARIAS,
      etica: "Centro de confianza",
      avisos: "Señales por familia",
      expedientes: "Detalle de contratación",
    }[page] ||
    (RETIRADAS.includes(page) ? "Sección retirada" : null) ||
    "Página no encontrada";
  const grupo =
    grupos.find(([, items]) => items.some(([key]) => key === page))?.[0] ||
    (SECUNDARIAS[page] ? "Información" : "Espacio de trabajo");
  const esAuditor = usuario.rol === "auditor";
  useEffect(() => {
    const cambio = () => {
      setRuta(location.hash.slice(1) || "inicio");
      setMenu(false);
      setNotice("");
      setDialog("");
      window.scrollTo(0, 0);
    };
    const teclas = (e) => {
      if (e.key === "Escape") setMenu(false);
      if (
        !esAuditor &&
        (e.ctrlKey || e.metaKey) &&
        e.key.toLowerCase() === "k"
      ) {
        e.preventDefault();
        setDialog("buscar");
      }
    };
    window.addEventListener("hashchange", cambio);
    window.addEventListener("keydown", teclas);
    return () => {
      window.removeEventListener("hashchange", cambio);
      window.removeEventListener("keydown", teclas);
    };
  }, [esAuditor, usuario.rol]);
  useEffect(() => {
    if (dialog && !modal.current.open) modal.current.showModal();
    if (!dialog && modal.current.open) modal.current.close();
  }, [dialog]);
  function saved(msg) {
    setNotice(msg);
    setVersion((v) => v + 1);
  }
  function contenido(c) {
    if (RETIRADAS.includes(page))
      return (
        <p className="notice">
          Esta sección se retiró para simplificar la navegación. Sus datos se conservan y
          alimentan las <a href="#alertas">alertas y coincidencias</a>.
        </p>
      );
    if (!permitido(page, usuario.rol))
      return <p className="notice">Tu rol no tiene acceso a este módulo.</p>;
    switch (page) {
      case "inicio":
        return <Panel key={page} config={c} usuario={usuario} version={version} />;
      case "expedientes":
        return id ? (
          <Detail key={id} id={id} version={version} usuario={usuario} onSaved={saved} />
        ) : (
          <Listing key={page} config={c} version={version} />
        );
      case "alertas":
        return <Alertas config={c} usuario={usuario} version={version} />;
      case "convocatorias":
        return <Convocatorias key={id} id={id} usuario={usuario} />;
      case "trazabilidad":
        return <Trazabilidad key={id || "lista"} id={id} usuario={usuario} />;
      case "concesiones":
        return <Concesiones key={id} id={id} usuario={usuario} />;
      case "fuentes":
        return <Fuentes />;
      case "historial":
        return <Auditoria version={version} />;
      case "etica":
        return <Ethics />;
      case "avisos":
        return <Notificaciones usuario={usuario} />;
      default:
        return <a href="#inicio">Volver al resumen</a>;
    }
  }
  return (
    <div className={"app-shell " + (mini ? "compact" : "")}>
      <a
        className="skip"
        href="#contenido"
        onClick={(e) => {
          e.preventDefault();
          document.querySelector("#contenido")?.focus();
        }}
      >
        Saltar al contenido
      </a>
      {menu && (
        <button
          className="overlay"
          aria-label="Cerrar menú"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={"sidebar " + (menu ? "open" : "")}>
        <div className="mast">
          <a href="#inicio" className="wordmark" aria-label="TrazaUNT, inicio">
            <img src="/assets/brand.svg" alt="" />
            <strong>
              Traza<span>UNT</span>
            </strong>
          </a>
          <button
            className="collapse icon-button"
            aria-label={
              mini ? "Expandir barra lateral" : "Contraer barra lateral"
            }
            onClick={() => setMini(!mini)}
          >
            {mini ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>
        <nav aria-label="Navegación principal">
          {grupos.map(([g, items]) => {
            const list = items.filter(([k]) => permitido(k, usuario.rol));
            return (
              !!list.length && (
                <section className="nav-group" key={g}>
                  <h2>{g}</h2>
                  {list.map(([k, t, Icon]) => (
                    <a
                      key={k}
                      href={"#" + k}
                      aria-current={page === k ? "page" : undefined}
                      title={t}
                      className={page === k ? "active" : ""}
                    >
                      <Icon size={17} />
                      <span>{t}</span>
                    </a>
                  ))}
                </section>
              )
            );
          })}
        </nav>
        <div className="side-end">
          <a href="#fuentes" title="¿De dónde salen los datos?">
            <Database size={16} />
            <span>¿De dónde salen los datos?</span>
          </a>
          {usuario.rol === "administrador" && (
            <a href="#historial" title="Bitácora de auditoría">
              <ShieldCheck size={16} />
              <span>Bitácora de auditoría</span>
            </a>
          )}
          <a href="#etica" title="Centro de confianza">
            <BookOpen size={16} />
            <span>Centro de confianza</span>
          </a>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="mobile-toggle icon-button"
            aria-label="Abrir menú"
            aria-expanded={menu}
            onClick={() => setMenu(!menu)}
          >
            <Menu size={19} />
          </button>
          {!esAuditor && (
            <button
              className="global-search"
              onClick={() => setDialog("buscar")}
            >
              <Search size={16} />
              <span>Buscar en TrazaUNT…</span>
              <kbd>Ctrl K</kbd>
            </button>
          )}
          <div className="top-actions">
            <span className="demo-pill">
              <i />
              Datos sintéticos
            </span>
            {!esAuditor && (
              <a
                href="#alertas"
                className="icon-button"
                aria-label="Ver alertas y coincidencias"
              >
                <BellRing size={18} />
              </a>
            )}
            <button
              className="account"
              onClick={() => setDialog("cuenta")}
              aria-label={"Equipo de integridad · " + usuario.nombre}
            >
              <span className="initials">
                {usuario.nombre
                  .split(" ")
                  .slice(0, 2)
                  .map((x) => x[0])
                  .join("")}
              </span>
              <span>
                {usuario.nombre}
                <small>Universidad · {usuario.rol}</small>
              </span>
              <ChevronDown size={13} />
            </button>
          </div>
        </header>
        <main id="contenido" tabIndex="-1">
          {config.data?.entorno === "demo" && <div className="entorno">Entorno de demostración · Datos sintéticos</div>}
          <div className="crumb">
            <Home size={13} />
            <span>{grupo}</span>
            <ChevronRight size={11} />
            <b>{nombre}</b>
          </div>
          {page !== "inicio" && (
            <h1 className="module-title">
              {page === "expedientes" && id ? "Detalle del expediente" : nombre}
            </h1>
          )}
          {notice && (
            <div className="notice dismiss" role="status">
              {notice}
              <button onClick={() => setNotice("")} aria-label="Cerrar aviso">
                ×
              </button>
            </div>
          )}
          <Load state={config}>{contenido}</Load>
        </main>
        <footer>
          Los indicadores apoyan la revisión y no constituyen una
          determinación legal ni una acusación. Verifique en la
          fuente oficial.
        </footer>
      </div>
      <dialog
        ref={modal}
        onClose={() => setDialog("")}
        aria-label={dialog === "buscar" ? "Búsqueda global" : "Cuenta local"}
      >
        {dialog === "buscar" ? (
          <Busqueda cerrar={() => setDialog("")} />
        ) : (
          <>
            <div className="section-top">
              <h2>Cuenta local</h2>
              <button
                className="icon-button"
                aria-label="Cerrar"
                onClick={() => setDialog("")}
              >
                <X size={16} />
              </button>
            </div>
            <p>
              {usuario.nombre} · {usuario.rol}
            </p>
            <p>
              {usuario.rol === "administrador" && (
                <>
                  <a href="#historial">Bitácora de auditoría</a> ·{" "}
                </>
              )}
              <a href="#etica">Centro de confianza</a> · <a href="/">Consulta pública</a>
            </p>
            <button
              onClick={async () => {
                try {
                  await onSalir();
                } catch (e) {
                  setNotice(e.message);
                }
                setDialog("");
              }}
            >
              <LogOut size={15} /> Cerrar sesión
            </button>
          </>
        )}
      </dialog>
    </div>
  );
}
export function Raiz() {
  const equipo =
    new URLSearchParams(location.search).get("vista") === "equipo" ||
    (location.hash && !location.hash.startsWith("#publico"));
  if (!equipo) return <PortalPublico />;
  return (
    <Acceso>
      {(usuario, salir) =>
        usuario.rol === "empresa" ? (
          <EmpresaApp usuario={usuario} onSalir={salir} />
        ) : (
          <App usuario={usuario} onSalir={salir} />
        )
      }
    </Acceso>
  );
}
if (document.getElementById("root"))
  createRoot(document.getElementById("root")).render(<Raiz />);
