import React, { useRef, useState } from "react";
import {
  Carga,
  ErrorAccion,
  Estado,
  Panel,
  Tabla,
  fecha,
  label,
  post,
  useAccion,
  useConsulta,
} from "./Comun";
import { subir } from "./Asistente";

function RevisionCampo({ documento, indice, campo, done }) {
  const [estado, setEstado] = useState("confirmado");
  const action = useAccion();
  function enviar(e) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    action.run(async () => {
      await post("/documentos/" + documento.id + "/validar", {
        ...data,
        indice,
        revision: documento.revision,
      });
      done();
    });
  }
  return (
    <details>
      <summary>Revisar extracción</summary>
      <form className="fl-inline" onSubmit={enviar}>
        <label>
          Decisión
          <select
            name="estado"
            value={estado}
            onChange={(e) => setEstado(e.target.value)}
          >
            <option value="confirmado">Confirmar extracción</option>
            <option value="corregido">Corregir valor</option>
            <option value="descartado">Descartar extracción</option>
          </select>
        </label>
        {estado === "corregido" && (
          <label>
            Valor corregido
            <input
              required
              name="valor"
              defaultValue={campo.efectivo ?? campo.valor}
            />
          </label>
        )}
        <label>
          Justificación
          <input required minLength={8} name="motivo" />
        </label>
        <ErrorAccion error={action.error} />
        <button disabled={action.busy}>Guardar revisión del campo</button>
      </form>
    </details>
  );
}

export function Evidencia({ id, write, volver, actualizar }) {
  const [version, setVersion] = useState(0);
  const query = useConsulta("/documentos/" + id, version);
  const action = useAccion();
  function refrescar() {
    setVersion((v) => v + 1);
    actualizar();
  }
  return (
    <Panel
      title="Evidencia documental"
      action={<button onClick={volver}>Cerrar detalle</button>}
    >
      <Carga query={query}>
        {(d) => (
          <>
            <div className="fl-heading">
              <div>
                <h3>{d.nombre}</h3>
                <small>
                  Versión {d.version} · {fecha(d.fecha)}
                </small>
              </div>
              <Estado value={d.estado} />
            </div>
            <div className="fl-actions">
              <a
                className="fl-button"
                href={"/api/documentos/" + id + "/archivo"}
                download
              >
                Descargar original
              </a>
              {write && ["recibido", "error_lectura"].includes(d.estado) && (
                <button
                  className="fl-primary"
                  disabled={action.busy}
                  onClick={() =>
                    action.run(async () => {
                      await post("/documentos/" + id + "/analizar");
                      refrescar();
                    })
                  }
                >
                  {action.busy
                    ? "Analizando…"
                    : d.estado === "error_lectura"
                      ? "Reintentar análisis"
                      : "Analizar documento"}
                </button>
              )}
            </div>
            <ErrorAccion error={action.error} />
            {!!d.observaciones?.length && (
              <ul className="fl-list">
                {d.observaciones.map((o, i) => (
                  <li key={i}>{o}</li>
                ))}
              </ul>
            )}
            <h4>Campos extraídos</h4>
            {d.campos?.length ? (
              <div className="fl-evidencias">
                {d.campos.map((c, i) => (
                  <article key={i}>
                    <div className="fl-heading">
                      <h4>{label(c.campo)}</h4>
                      <Estado value={c.estado} />
                    </div>
                    <strong>
                      {c.estado === "descartado"
                        ? "Extracción descartada"
                        : String(c.efectivo ?? c.valor)}
                    </strong>
                    {(c.estado === "descartado" ||
                      (c.efectivo != null &&
                        String(c.valor) !== String(c.efectivo))) && (
                      <small>Valor original: {String(c.valor)}</small>
                    )}
                    <blockquote>
                      {c.fragmento}
                      <cite>{c.ubicacion}</cite>
                    </blockquote>
                    <small>
                      Confianza de extracción · {c.confianza ?? "No evaluado"}
                    </small>
                    {write && (
                      <RevisionCampo
                        documento={d}
                        indice={i}
                        campo={c}
                        done={refrescar}
                      />
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <p className="fl-empty">Sin campos extraídos en esta versión.</p>
            )}
            <details>
              <summary>Huella SHA-256 del archivo original</summary>
              <code className="fl-hash">{d.sha256}</code>
            </details>
          </>
        )}
      </Carga>
    </Panel>
  );
}

// Adjunta un archivo a un dueño fijo: las bases (postulante "") o una empresa concreta.
export function AdjuntarA({ ficha, postulante = "", onSaved }) {
  const tipos = postulante ? ["propuesta", "anexo", "garantia", "otro"] : ["bases"];
  const [tipo, setTipo] = useState(tipos[0]);
  const [file, setFile] = useState(null);
  const input = useRef(null);
  const action = useAccion();
  return (
    <details className="fl-fold">
      <summary>{postulante ? "Adjuntar documento de esta empresa" : "Adjuntar documento de bases"}</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          action.run(async () => {
            if (!file) throw new Error("Selecciona un archivo.");
            const d = await subir(ficha.id, file, tipo, postulante ? String(postulante) : "");
            setFile(null);
            if (input.current) input.current.value = "";
            onSaved(d.id);
          });
        }}
      >
        {tipos.length > 1 && (
          <label>
            Tipo de documento
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {tipos.map((v) => (
                <option key={v} value={v}>
                  {label(v)}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="fl-drop">
          {file ? file.name : "Selecciona un archivo"}
          <input
            ref={input}
            aria-label="Archivo documental"
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.csv"
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
          <small>PDF, DOCX, XLSX, CSV o TXT · Máximo 4 MiB</small>
        </label>
        <ErrorAccion error={action.error} />
        <button className="fl-primary" disabled={action.busy}>
          {action.busy ? "Guardando…" : "Guardar archivo"}
        </button>
      </form>
    </details>
  );
}

function Adjuntar({ ficha, onSaved }) {
  const [owner, setOwner] = useState("");
  const [tipo, setTipo] = useState("bases");
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const input = useRef(null);
  const action = useAccion();
  const draft = ficha.estado === "borrador";
  React.useEffect(() => {
    if (!draft && ficha.postulantes.length) {
      setOwner(String(ficha.postulantes[0].id));
      setTipo("propuesta");
    }
  }, [draft, ficha.postulantes]);
  if (!draft && !ficha.postulantes.length)
    return (
      <p className="fl-help">
        Registra un postulante para cargar su propuesta.
      </p>
    );
  function submit(e) {
    e.preventDefault();
    action.run(async () => {
      if (!file) throw new Error("Selecciona un archivo.");
      const d = await subir(ficha.id, file, tipo, owner);
      setFile(null);
      if (input.current) input.current.value = "";
      onSaved(d.id);
    });
  }
  return (
    <details className="fl-fold">
      <summary>Adjuntar documento</summary>
      <form onSubmit={submit}>
        <div className="fl-grid">
          <label>
            Vincular a
            <select
              value={owner}
              onChange={(e) => {
                setOwner(e.target.value);
                setTipo(e.target.value ? "propuesta" : "bases");
              }}
            >
              {draft && <option value="">Bases de la convocatoria</option>}
              {ficha.postulantes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.razon_social}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tipo de documento
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {(owner
                ? ["propuesta", "anexo", "garantia", "otro"]
                : ["bases"]
              ).map((v) => (
                <option key={v} value={v}>
                  {label(v)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label
          className={"fl-drop" + (drag ? " active" : "")}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            setFile(e.dataTransfer.files[0] || null);
          }}
        >
          {file ? file.name : "Arrastra un archivo o selecciónalo aquí"}
          <input
            ref={input}
            aria-label="Archivo documental"
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.csv"
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
          <small>PDF, DOCX, XLSX, CSV o TXT · Máximo 4 MiB</small>
        </label>
        <ErrorAccion error={action.error} />
        <button className="fl-primary" disabled={action.busy}>
          {action.busy ? "Guardando…" : "Guardar archivo"}
        </button>
      </form>
    </details>
  );
}

export function Documentos({ ficha, write, refresh, seleccion, setSeleccion }) {
  const postulante = (id) =>
    ficha.postulantes.find((p) => p.id === id)?.razon_social || "Convocatoria";
  return (
    <>
      {seleccion && (
        <Evidencia
          key={seleccion}
          id={seleccion}
          write={
            write &&
            !["resultado_registrado", "cancelada"].includes(ficha.estado)
          }
          volver={() => setSeleccion(null)}
          actualizar={refresh}
        />
      )}
      <Panel title="Archivo documental">
        {write && ["borrador", "abierta"].includes(ficha.estado) && (
          <Adjuntar
            ficha={ficha}
            onSaved={(id) => {
              setSeleccion(id);
              refresh();
            }}
          />
        )}
        <Tabla
          headers={["Documento", "Vinculado a", "Versión", "Estado", ""]}
          rows={ficha.documentos.map((d) => (
            <tr key={d.id}>
              <th scope="row">
                {d.nombre}
                <small>
                  {label(d.tipo)} · {Math.ceil(d.tamano / 1024)} KB
                </small>
              </th>
              <td>{postulante(d.postulante_id)}</td>
              <td>{d.version}</td>
              <td>
                <Estado value={d.estado} />
              </td>
              <td>
                <button onClick={() => setSeleccion(d.id)}>
                  Ver evidencia
                </button>
              </td>
            </tr>
          ))}
          empty="Aún no se han incorporado archivos a esta convocatoria."
        />
      </Panel>
    </>
  );
}
