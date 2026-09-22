/**
 * Capa de acceso a datos del navegador.
 *
 * El navegador no conoce la existencia de FastAPI: llama a los endpoints
 * proxy de Django, que adjuntan el JWT guardado en la sesion firmada. Asi el
 * token nunca se expone a JavaScript y no se necesita configurar CORS.
 */
(function (window, document) {
  "use strict";

  function getCookie(name) {
    const match = document.cookie.match(
      new RegExp("(^|;\\s*)" + name + "=([^;]*)")
    );
    return match ? decodeURIComponent(match[2]) : null;
  }

  async function parseResponse(response) {
    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }

    if (response.status === 401) {
      // La sesion expiro: se recarga para que Django redirija al login.
      window.location.reload();
      throw new Error("Tu sesion expiro. Inicia sesion nuevamente.");
    }

    if (!response.ok) {
      const message =
        (payload && (payload.error || payload.detail)) ||
        "No se pudo completar la operacion (HTTP " + response.status + ").";
      throw new Error(message);
    }

    return payload;
  }

  async function classify(blob) {
    const form = new FormData();
    const extension = (blob.type || "image/jpeg").split("/")[1] || "jpg";
    form.append("image", blob, "captura." + extension);

    const response = await fetch("/api/clasificar/", {
      method: "POST",
      headers: { "X-CSRFToken": getCookie("csrftoken") || "" },
      body: form,
      credentials: "same-origin",
    });

    return parseResponse(response);
  }

  async function binsGuide() {
    const response = await fetch("/api/guia/", {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    return parseResponse(response);
  }

  window.PuntoLimpioApi = { classify, binsGuide };
})(window, document);
