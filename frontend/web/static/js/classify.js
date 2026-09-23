/**
 * Controlador de la pantalla de clasificación.
 *
 * Orquesta los botones, el stream de la cámara y la vista previa. La llamada
 * al backend se delega en `window.PuntoLimpioApi.classify`, que se inyecta
 * desde `api.js`. Se agregan animaciones dinámicas para mejorar la experiencia.
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
    cameraStage: document.getElementById("camera-stage"),
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

  /** Muestra la imagen capturada y habilita la clasificación. */
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

    // Animación de entrada para la vista previa
    elements.preview.style.animation = "none";
    elements.preview.offsetHeight; // Reflow
    elements.preview.style.animation = "scaleIn 0.4s ease-out";
  }

  elements.start.addEventListener("click", async () => {
    elements.video.hidden = false;
    resetPreview();
    try {
      await camera.start();
      elements.captureBtn.disabled = false;
      if (elements.cameraStage) {
        elements.cameraStage.classList.add("active");
      }
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
        ? "Cámara activa. Centra el residuo y captura."
        : "Enciende la cámara para capturar."
    );
  });

  elements.stop.addEventListener("click", () => {
    camera.stop();
    resetPreview();
    if (elements.cameraStage) {
      elements.cameraStage.classList.remove("active");
    }
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

  // Alternativa a la cámara: subir una foto existente.
  if (elements.fileInput) {
    elements.fileInput.addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      if (file) previewImage(file);
    });
  }

  window.addEventListener("pagehide", () => camera.stop());

  // --- Clasificación -------------------------------------------------------
  function renderResult(data) {
    elements.result.hidden = false;
    elements.result.innerHTML = "";

    // Animación de entrada para el resultado
    elements.result.style.animation = "none";
    elements.result.offsetHeight; // Reflow
    elements.result.style.animation = "scaleIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)";

    const score = data.confidence || 0;
    const isLowConfidence = score < 0.5 || data.engine === "heuristic";

    // Badge de confianza
    let confidenceBadgeClass = "badge-green";
    let confidenceLabel = "Alta";
    if (isLowConfidence) {
      confidenceBadgeClass = "badge-blue";
      confidenceLabel = "Baja";
    }

    const header = document.createElement("div");
    header.className = "result-header";
    header.innerHTML =
      '<span class="bin-chip" data-color="' + data.bin_color + '"></span>' +
      "<div>" +
      "<strong>" + data.type + "</strong>" +
      '<span class="muted">' +
      data.category + " · " + data.bin_name +
      "</span>" +
      "</div>";
    elements.result.appendChild(header);

    // Info de confianza con badge
    const confidenceInfo = document.createElement("div");
    confidenceInfo.style.cssText = "display:flex;align-items:center;gap:0.5rem;margin:0.5rem 0;";
    confidenceInfo.innerHTML =
      '<span class="badge ' + confidenceBadgeClass + '">' +
      "🎯 " + confidenceLabel + " · " + Math.round(score * 100) + "%" +
      "</span>" +
      '<span class="muted small">Motor: ' + data.engine + "</span>";
    elements.result.appendChild(confidenceInfo);

    // Barra de progreso animada de confianza
    const progressBar = document.createElement("div");
    progressBar.style.cssText =
      "width:100%;height:6px;background:rgba(46,125,50,0.1);border-radius:3px;overflow:hidden;margin:0.5rem 0;";
    const progressFill = document.createElement("div");
    progressFill.style.cssText =
      "height:100%;width:0%;border-radius:3px;transition:width 0.8s cubic-bezier(0.4,0,0.2,1);" +
      "background:linear-gradient(90deg, var(--primary), var(--accent));";
    progressBar.appendChild(progressFill);
    elements.result.appendChild(progressBar);

    // Animar la barra después de un frame
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        progressFill.style.width = Math.round(score * 100) + "%";
      });
    });

    // Hint de confianza baja
    if (isLowConfidence) {
      const hint = document.createElement("p");
      hint.className = "muted small";
      hint.style.cssText =
        "background:rgba(245,127,23,0.08);padding:0.6rem 0.8rem;border-radius:8px;border-left:3px solid var(--warning);margin:0.75rem 0;";
      hint.textContent =
        "⚠️ Confianza baja: centra solo el residuo en el recuadro, sin fondo " +
        "ni personas, y vuelve a capturar.";
      elements.result.appendChild(hint);
    }

    // Instrucciones
    const instructions = document.createElement("p");
    instructions.style.cssText = "margin:0.75rem 0 0;font-weight:600;";
    instructions.textContent = "📋 " + data.instructions;
    elements.result.appendChild(instructions);

    // Alternativas
    if (Array.isArray(data.top_k) && data.top_k.length) {
      const alternatives = document.createElement("p");
      alternatives.className = "muted small";
      alternatives.style.cssText = "margin-top:0.5rem;";
      alternatives.textContent =
        "🔄 Alternativas: " +
        data.top_k
          .map((item) => item.type + " (" + Math.round(item.confidence * 100) + "%)")
          .join(", ");
      elements.result.appendChild(alternatives);
    }

    // Scroll suave al resultado
    elements.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  /** Bloquea la interfaz y muestra el estado de carga durante la petición. */
  function setBusy(busy) {
    const buttons = document.querySelectorAll(".camera-actions .btn, #btn-classify");
    buttons.forEach((button) => {
      if (busy) {
        button.dataset.wasDisabled = button.disabled ? "1" : "0";
        button.disabled = true;
      } else if (button.dataset.wasDisabled === "0") {
        button.disabled = false;
      }
    });
    if (!busy && !camera.isActive && !currentBlob) {
      elements.captureBtn.disabled = true;
    }
    elements.result.setAttribute("aria-busy", busy ? "true" : "false");
  }

  async function handleClassify() {
    if (!currentBlob) {
      showError("Primero captura o sube una imagen.");
      return;
    }
    if (!api || typeof api.classify !== "function") {
      showError("No se pudo cargar el cliente de la API. Recarga la página.");
      return;
    }

    setBusy(true);
    setStatus("🌿 Clasificando residuo, un momento...", "loading");
    try {
      const data = await api.classify(currentBlob);
      renderResult(data);
      setStatus(
        "✅ Residuo clasificado: " + data.type + " → " + data.bin_name + ".",
        "ok"
      );
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(false);
      elements.preview.hidden = false;
    }
  }

  const classifyBtn = document.getElementById("btn-classify");
  if (classifyBtn) classifyBtn.addEventListener("click", handleClassify);

  elements.video.hidden = true;
  elements.preview.hidden = true;
  setStatus("📷 Enciende la cámara o sube una fotografía para comenzar.");
})(window, document);
