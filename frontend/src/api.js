export const VERSION = "5.1.0";
export async function request(path, options = {}) {
  const headers = new Headers(options.headers);
  if (options.method && options.method !== "GET")
    headers.set("X-Traza-Client", "react");
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  )
    headers.set("Content-Type", "application/json");
  let response;
  try {
    response = await fetch("/api" + path, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch (e) {
    if (e?.name === "AbortError") throw e;
    // Heurística 9: explicar qué pasó y cómo seguir, sin mensajes técnicos.
    throw new Error(
      "No se pudo conectar con TrazaUNT. Revisa que el programa siga abierto (iniciar.bat) y vuelve a intentarlo.",
    );
  }
  if (!response.ok) {
    const info = await response.json().catch(() => ({}));
    // «Not Found» sin más detalle significa que el servidor no conoce la ruta: casi siempre
    // queda abierta una versión anterior de TrazaUNT (heurística 9: decir cómo resolverlo).
    if (response.status === 404 && info.detail === "Not Found")
      throw new Error(
        "Esta función no existe en el servidor que está abierto: parece una versión anterior de TrazaUNT. Cierra todas las ventanas negras de TrazaUNT, vuelve a abrir iniciar.bat y recarga con Ctrl + F5.",
      );
    if (response.status === 401 && !path.startsWith("/sesion"))
      window.dispatchEvent(new Event("sesion-caducada"));
    throw new Error(
      typeof info.detail === "string"
        ? info.detail
        : "Revisa los campos enviados y vuelve a intentarlo.",
    );
  }
  return response.json();
}
export async function download(tipo) {
  const response = await fetch("/api/exportar/" + tipo);
  if (!response.ok) throw new Error("No se pudo descargar el informe.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = tipo + ".csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
