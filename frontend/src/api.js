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
  const response = await fetch("/api" + path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const info = await response.json().catch(() => ({}));
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
