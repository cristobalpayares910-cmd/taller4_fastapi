/**
 * Controlador de la pantalla de clasificacion.
 *
 * Orquesta los botones, el stream de la camara y la vista previa. La llamada
 * al backend se delega en `window.PuntoLimpioApi.classify`, que se inyecta
 * desde `api.js`.
 */
(function (window, document) {
  "use strict";

  const elements = {
    video: document.getElementById("camera"),
    canvas: document.getElementById("snapshot"),
    preview: document.getElementById("preview"),
    status: document.getElementById("camera-status"),
    result: document.getElementById("result"),
    start: document.getElementById("btn-start"),
    captureBtn: document.getElementById("btn-capture"),
    retake: document.getElementById("btn-retake"),
    stop: document.getElementById("btn-stop"),
    switchBtn: document.getElementById("btn-switch"),
    fileInput: document.getElementById("file-input"),
  };

  if (!elements.video) return;

  let currentBlob = null;
  const api = window.PuntoLimpioApi;

  function setStatus(message, tone) {
    elements.status.textContent = message;
    elements.status.dataset.tone = tone || "info";
  }

  function showError(message) {
    setStatus(message, "error");
    elements.result.hidden = true;
  }

  function resetPreview() {
    currentBlob = null;
    elements.preview.hidden = true;
    elements.retake.hidden = true;
    elements.captureBtn.disabled = !camera.isActive;
    elements.result.hidden = true;
  }

  const camera = new window.CameraCapture(elements.video, elements.canvas, {
    maxWidth: 1080,
    quality: 0.9,
    onStatus: (message) => setStatus(message),
    onError: (message) => showError(message),
  });

  /** Muestra la imagen capturada y habilita la clasificacion. */
  function previewImage(blob) {
    currentBlob = blob;
    const url = URL.createObjectURL(blob);
    elements.preview.onload = () => URL.revokeObjectURL(url);
    elements.preview.src = url;
    elements.preview.hidden = false;
    elements.video.hidden = true;
    elements.retake.hidden = false;
    elements.captureBtn.disabled = true;
    setStatus("Imagen lista. Presiona \"Clasificar residuo\".", "ok");
  }

  elements.start.addEventListener("click", async () => {
    elements.video.hidden = false;
    resetPreview();
    try {
      await camera.start();
      elements.captureBtn.disabled = false;
    } catch (error) {
      showError(error.message);
    }
  });

  elements.captureBtn.addEventListener("click", async () => {
    try {
      previewImage(await camera.capture());
    } catch (error) {
      showError(error.message);
    }
  });

  elements.retake.addEventListener("click", () => {
    resetPreview();
    elements.video.hidden = false;
    elements.captureBtn.disabled = !camera.isActive;
    setStatus(
      camera.isActive
        ? "Camara activa. Centra el residuo y captura."
        : "Enciende la camara para capturar."
    );
  });

  elements.stop.addEventListener("click", () => {
    camera.stop();
    resetPreview();
  });

  if (elements.switchBtn) {
    elements.switchBtn.addEventListener("click", async () => {
      try {
        await camera.switchCamera();
      } catch (error) {
        showError(error.message);
      }
    });
  }

  // Alternativa a la camara: subir una foto existente.
  if (elements.fileInput) {
    elements.fileInput.addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      if (file) previewImage(file);
    });
  }

  window.addEventListener("pagehide", () => camera.stop());

  // --- Clasificacion -------------------------------------------------------
  function renderResult(data) {
    elements.result.hidden = false;
    elements.result.innerHTML = "";

    const header = document.createElement("div");
    header.className = "result-header";
    header.innerHTML =
      '<span class="bin-chip" data-color="' +
      data.bin_color +
      '"></span>' +
      "<div><strong>" +
      data.type +
      "</strong><span class=\"muted\">" +
      data.category +
      " &middot; " +
      data.bin_name +
      "</span></div>";
    elements.result.appendChild(header);

    const confidence = document.createElement("p");
    confidence.className = "muted";
    confidence.textContent =
      "Confianza: " + Math.round((data.confidence || 0) * 100) + "% · motor: " +
      data.engine;
    elements.result.appendChild(confidence);

    const instructions = document.createElement("p");
    instructions.textContent = data.instructions;
    elements.result.appendChild(instructions);

    if (Array.isArray(data.top_k) && data.top_k.length) {
      const alternatives = document.createElement("p");
      alternatives.className = "muted small";
      alternatives.textContent =
        "Alternativas: " +
        data.top_k
          .map((item) => item.type + " (" + Math.round(item.confidence * 100) + "%)")
          .join(", ");
      elements.result.appendChild(alternatives);
    }
  }

  async function handleClassify() {
    if (!currentBlob) {
      showError("Primero captura o sube una imagen.");
      return;
    }
    if (!api || typeof api.classify !== "function") {
      setStatus(
        "Imagen capturada. La clasificacion se conecta al backend en el siguiente paso.",
        "warn"
      );
      return;
    }

    setStatus("Clasificando residuo...", "loading");
    try {
      renderResult(await api.classify(currentBlob));
      setStatus("Clasificacion completada.", "ok");
    } catch (error) {
      showError(error.message);
    }
  }

  const classifyBtn = document.getElementById("btn-classify");
  if (classifyBtn) classifyBtn.addEventListener("click", handleClassify);

  elements.video.hidden = true;
  elements.preview.hidden = true;
  setStatus("Enciende la camara o sube una fotografia para comenzar.");
})(window, document);
