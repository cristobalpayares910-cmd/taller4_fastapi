/**
 * Captura de camara con getUserMedia.
 *
 * Expone la clase `CameraCapture`, que encapsula el ciclo de vida del stream
 * (permisos, encendido, captura de un frame a JPEG y apagado) y delega los
 * errores a la pagina mediante callbacks. No realiza peticiones de red: la
 * integracion HTTP vive en `api.js`.
 */
(function (window) {
  "use strict";

  function buildConstraints(facingMode) {
    return {
      audio: false,
      video: {
        facingMode: { ideal: facingMode },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    };
  }

  /** Traduce los errores de la MediaDevices API a mensajes para el usuario. */
  function describeError(error) {
    if (!window.isSecureContext) {
      return "La camara requiere HTTPS o localhost. Abre la app con https://.";
    }
    switch (error && error.name) {
      case "NotAllowedError":
      case "SecurityError":
        return "Permiso de camara denegado. Habilitalo en el navegador y reintenta.";
      case "NotFoundError":
      case "DevicesNotFoundError":
        return "No se encontro ninguna camara disponible en este dispositivo.";
      case "NotReadableError":
      case "TrackStartError":
        return "La camara esta siendo usada por otra aplicacion.";
      case "OverconstrainedError":
        return "La camara no soporta la resolucion solicitada.";
      case "TypeError":
        return "No se pudo acceder a la camara en este contexto.";
      default:
        return (error && error.message) || "No se pudo acceder a la camara.";
    }
  }

  class CameraCapture {
    constructor(video, canvas, options) {
      options = options || {};
      this.video = video;
      this.canvas = canvas;
      this.maxWidth = options.maxWidth || 1080;
      this.quality = options.quality || 0.9;
      this.facingMode = options.facingMode || "environment";
      this.onStatus = options.onStatus || function () {};
      this.onError = options.onError || function () {};
      this.stream = null;
    }

    /** Indica si el navegador soporta captura de video. */
    static isSupported() {
      return Boolean(
        navigator.mediaDevices && navigator.mediaDevices.getUserMedia
      );
    }

    get isActive() {
      return Boolean(this.stream);
    }

    /** Solicita permiso y arranca el stream en el elemento <video>. */
    async start() {
      this.stop();

      if (!CameraCapture.isSupported()) {
        const error = new Error(
          "Este navegador no soporta getUserMedia. Sube una imagen desde archivo."
        );
        this.onError(error.message);
        throw error;
      }

      this.onStatus("Solicitando permiso de camara...");

      try {
        this.stream = await navigator.mediaDevices.getUserMedia(
          buildConstraints(this.facingMode)
        );
      } catch (error) {
        const message = describeError(error);
        this.onError(message);
        throw new Error(message);
      }

      this.video.srcObject = this.stream;
      this.video.classList.toggle("mirrored", this.facingMode === "user");

      try {
        await this.video.play();
      } catch (error) {
        // Algunos navegadores rechazan play() si no hay gesto de usuario.
        this.onError("Presiona de nuevo sobre el video para iniciar la vista.");
      }

      this.onStatus("Camara activa. Centra el residuo y captura.");
      return this.stream;
    }

    /** Alterna entre camara trasera y frontal. */
    async switchCamera() {
      this.facingMode = this.facingMode === "environment" ? "user" : "environment";
      if (this.isActive) {
        return this.start();
      }
      return null;
    }

    /** Dibuja el frame actual en el canvas y lo devuelve como Blob JPEG. */
    capture() {
      if (!this.isActive) {
        return Promise.reject(new Error("La camara no esta activa."));
      }

      const width = this.video.videoWidth;
      const height = this.video.videoHeight;
      if (!width || !height) {
        return Promise.reject(new Error("La camara aun no entrega imagen."));
      }

      const scale = Math.min(1, this.maxWidth / width);
      this.canvas.width = Math.round(width * scale);
      this.canvas.height = Math.round(height * scale);
      this.canvas
        .getContext("2d")
        .drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

      return new Promise((resolve, reject) => {
        this.canvas.toBlob(
          (blob) =>
            blob
              ? resolve(blob)
              : reject(new Error("No se pudo generar la imagen capturada.")),
          "image/jpeg",
          this.quality
        );
      });
    }

    /** Detiene todas las pistas del stream para liberar la camara. */
    stop() {
      if (!this.stream) return;
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
      this.video.srcObject = null;
      this.video.classList.remove("mirrored");
      this.onStatus("Camara apagada.");
    }
  }

  window.CameraCapture = CameraCapture;
  window.CameraCapture.describeError = describeError;
})(window);
