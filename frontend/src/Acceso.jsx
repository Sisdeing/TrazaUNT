import React, { useEffect, useState } from "react";
import { ArrowRight, Building2, Landmark, LockKeyhole, Users } from "lucide-react";
import { request } from "./api";

const PERFILES = [
  ["universidad", "Universidad", Landmark, "Crea convocatorias, revisa documentos, admite empresas y atiende alertas y coincidencias."],
  ["empresa", "Empresa", Building2, "Consulta cómo va la convocatoria y la revisión de tus documentos."],
  ["publico", "Ciudadanía", Users, "Transparencia en contrataciones y trazabilidad de expedientes, sin cuenta."],
];
const EMPRESAS_DEMO = [
  ["empresa-aurora", "Servicios Campus Aurora"],
  ["empresa-horizonte", "Operaciones Horizonte"],
  ["empresa-nova", "Gestión Nova Campus"],
];

export default function Acceso({ children }) {
  const [usuario, setUsuario] = useState(null),
    [cargando, setCargando] = useState(true),
    [error, setError] = useState(""),
    [perfil, setPerfil] = useState(new URLSearchParams(location.search).get("perfil") === "empresa" ? "empresa" : "universidad"),
    [demo, setDemo] = useState(false);
  useEffect(() => {
    async function iniciar() {
      try {
        let data;
        if (location.hash.startsWith("#acceso=")) {
          const codigo = location.hash.slice(8);
          history.replaceState(null, "", location.pathname + location.search + "#inicio");
          data = await request("/sesion/local", { method: "POST", body: JSON.stringify({ codigo }) });
        } else data = await request("/sesion");
        setUsuario(data.usuario);
      } catch (e) {
        setError(e.message);
      } finally {
        setCargando(false);
      }
    }
    iniciar();
    request("/salud").then((s) => setDemo(s.entorno === "demo")).catch(() => {});
    const caducada = () => {
      setUsuario(null);
      setError("La sesión ha caducado. Vuelve a ingresar.");
    };
    window.addEventListener("sesion-caducada", caducada);
    return () => window.removeEventListener("sesion-caducada", caducada);
  }, []);
  function abrir(u) {
    if (u.rol === "empresa") location.hash = "empresa";
    else if (!location.hash || location.hash.startsWith("#empresa")) location.hash = "inicio";
    setUsuario(u);
  }
  async function entrar(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    setError("");
    setCargando(true);
    try {
      abrir((await request("/sesion/entrar", { method: "POST", body: JSON.stringify(values) })).usuario);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }
  async function entrarDemo(p) {
    setError("");
    setCargando(true);
    try {
      abrir((await request("/sesion/demo", { method: "POST", body: JSON.stringify({ perfil: p }) })).usuario);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }
  async function salir() {
    await request("/sesion/salir", { method: "POST" });
    history.replaceState(null, "", location.pathname + location.search);
    setUsuario(null);
  }
  if (usuario) return children(usuario, salir);
  return (
    <main className="acceso">
      <section className="acceso-marca">
        <img src="/assets/brand.svg" alt="" />
        <span className="login-brand">Traza<b>UNT</b></span>
        <h1>Trazabilidad, transparencia y control preventivo de contrataciones</h1>
        <p>Universidad Nacional de Trujillo · Cada perfil ve solo la información que le corresponde.</p>
        <small><LockKeyhole size={14} /> Entorno de demostración con datos sintéticos e información pública identificada.</small>
      </section>
      <section className="acceso-panel">
        <h2>¿Cómo quieres ingresar?</h2>
        <div className="acceso-perfiles" role="tablist">
          {PERFILES.map(([k, t, Icon, d]) => (
            <button key={k} role="tab" aria-selected={perfil === k} className={perfil === k ? "activo" : ""}
              onClick={() => (k === "publico" ? (location.href = "/") : setPerfil(k))}>
              <Icon size={20} />
              <b>{t}</b>
              <small>{d}</small>
            </button>
          ))}
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        {demo && (
          <div className="acceso-demo">
            <h3>Acceso rápido de demostración</h3>
            {perfil === "universidad" ? (
              <div className="acceso-botones">
                <button className="solid" disabled={cargando} onClick={() => entrarDemo("universidad")}>
                  Analista de la universidad <ArrowRight size={15} />
                </button>
                <button disabled={cargando} onClick={() => entrarDemo("administrador")}>Administración</button>
              </div>
            ) : (
              <div className="acceso-botones">
                {EMPRESAS_DEMO.map(([k, t]) => (
                  <button key={k} disabled={cargando} onClick={() => entrarDemo(k)}>{t} (demo)</button>
                ))}
              </div>
            )}
          </div>
        )}
        <details className="acceso-cuenta" open={!demo}>
          <summary>Ingresar con una cuenta local</summary>
          <form onSubmit={entrar}>
            <label>
              Usuario
              <input autoComplete="username" name="usuario" required />
            </label>
            <label>
              Contraseña
              <input autoComplete="current-password" name="clave" type="password" required />
            </label>
            <button className="solid" disabled={cargando}>
              {cargando ? "Conectando…" : "Iniciar sesión"} <ArrowRight size={16} />
            </button>
          </form>
        </details>
        <a className="acceso-publico" href="/">Consultar la transparencia sin cuenta →</a>
      </section>
    </main>
  );
}
