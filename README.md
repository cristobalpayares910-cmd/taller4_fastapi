# EcoScan IA — Clasificador de Residuos 🗑️♻️

Aplicación web que **clasifica residuos a partir de una fotografía** tomada con
la cámara del dispositivo y responde con la categoría, el tipo de residuo y el
**color del contenedor** donde debe depositarse.

- **Problema real:** mala separación de basura en la fuente por desconocimiento del usuario.
- **Modelo preentrenado:** MobileNetV2 (ImageNet / TrashNet).

---

## 🧱 Stack

| Capa | Tecnología |
|------|------------|
| Frontend | **Django 5/6** — vistas, plantillas HTML5 y JS con `getUserMedia` |
| Backend | **FastAPI** — inferencia del modelo, validación con **Pydantic v2** y **Swagger** en `/docs` |
| Autenticación | Login/Password con **JWT** (bcrypt + python-jose) |
| Base de datos | SQLite + SQLAlchemy 2.x |
| Despliegue | **Vercel** Serverless Functions (`vercel.json`) |

## 🏗️ Arquitectura

```
Navegador ──getUserMedia──> JS ──POST /api/clasificar/──> Django ──HTTP/JWT──> FastAPI ──> MobileNetV2
   ▲                                                         │
   └────────────────── JSON de clasificación ────────────────┘
```

Django actúa como *backend for frontend*: guarda el JWT en una **sesión firmada
por cookie** y lo reenvía en la cabecera `Authorization`. El navegador nunca ve
el token ni necesita CORS.

```
.
├── backend/                    # API FastAPI
│   ├── api/index.py            # entrypoint Serverless (Vercel)
│   ├── app/
│   │   ├── main.py             # app factory, middlewares, Swagger
│   │   ├── config.py           # settings por variables de entorno
│   │   ├── database.py         # engine + sesión SQLAlchemy
│   │   ├── models.py           # User, Classification
│   │   ├── schemas.py          # esquemas Pydantic (contrato de la API)
│   │   ├── security.py         # bcrypt + JWT
│   │   ├── deps.py             # dependencias (usuario actual)
│   │   ├── errors.py           # manejadores de errores
│   │   ├── middleware.py       # timing y cache
│   │   ├── ml/                 # modelo, taxonomía y clasificador
│   │   └── routers/            # auth.py, waste.py
│   ├── requirements.txt
│   └── requirements-ml.txt     # TensorFlow (opcional, solo local)
├── frontend/                   # Cliente Django
│   ├── api/index.py            # entrypoint Serverless (Vercel)
│   ├── config/                 # settings, urls, wsgi, asgi
│   ├── web/
│   │   ├── views.py            # páginas + proxy JSON hacia FastAPI
│   │   ├── api_client.py       # cliente HTTP (httpx)
│   │   ├── decorators.py       # sesión y control de acceso
│   │   ├── templates/
│   │   └── static/{css,js}/    # styles.css, camera.js, classify.js, api.js
│   └── tests/
├── scripts/build_vercel.sh
└── vercel.json
```

---

## 🚀 Puesta en marcha local

Se necesitan **dos procesos**: el backend (puerto `8001`) y el frontend (`8000`).

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # y edita SECRET_KEY
python -m uvicorn app.main:app --reload --port 8001
```

- Swagger interactivo: <http://127.0.0.1:8001/docs>
- Healthcheck: <http://127.0.0.1:8001/health>

### 2. Frontend (Django)

```bash
cd frontend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                    # y edita DJANGO_SECRET_KEY
python manage.py runserver 8000
```

Abre <http://127.0.0.1:8000>, crea una cuenta y entra a **Clasificar**.

> 📷 La cámara requiere `https://` o `localhost`. Si el navegador la bloquea,
> usa el botón **Subir archivo**.

### 3. (Opcional) Modelo real de deep learning

```bash
cd backend && pip install -r requirements-ml.txt
```

Con TensorFlow instalado el servicio usa MobileNetV2 de verdad. Para usar pesos
ya afinados con TrashNet, coloca el archivo y define la ruta:

```env
TRASHNET_MODEL_PATH=./models/mobilenetv2_trashnet.h5
```

---

## 🔌 Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|:----:|-------------|
| `POST` | `/api/v1/auth/register` | — | Crea la cuenta |
| `POST` | `/api/v1/auth/login` | — | Login (form, compatible con **Authorize** de Swagger) |
| `POST` | `/api/v1/auth/login/json` | — | Login con JSON |
| `GET` | `/api/v1/auth/me` | ✅ | Perfil del usuario del token |
| `POST` | `/api/v1/classify-waste` | ✅ | Procesa la foto y clasifica el residuo |
| `GET` | `/api/v1/history` | ✅ | Historial de clasificaciones |
| `GET` | `/api/v1/bins-guide` | — | Instrucciones de reciclaje y colores |
| `GET` | `/health` | — | Estado del servicio y motor de inferencia |

### Ejemplo: `POST /api/v1/classify-waste`

```bash
curl -X POST http://127.0.0.1:8001/api/v1/classify-waste \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@botella.jpg"
```

```json
{
  "id": 12,
  "category": "Recyclable",
  "type": "Plastic Bottle",
  "bin_color": "Blue",
  "bin_name": "Contenedor azul (plasticos y latas)",
  "instructions": "Enjuaga el envase, quita la tapa y aplicalo para reducir volumen.",
  "confidence": 0.93,
  "engine": "heuristic",
  "material": "plastic",
  "top_k": [{"type": "Aluminum Can", "confidence": 0.21}]
}
```

### Esquema de colores (EcoScan IA)

| Color | Categoría | Acepta |
|-------|-----------|--------|
| 🔵 `Blue` | Recyclable | Botellas plásticas, latas de aluminio |
| 🟡 `Yellow` | Recyclable | Papel, cartón |
| 🟢 `Green` | Recyclable | Vidrio |
| 🟤 `Brown` | Organic | Restos orgánicos |
| ⚫ `Black` | Non-Recyclable | Residuo de rechazo |
| 🔴 `Red` | Hazardous | Residuos peligrosos |

---

## 🧠 Motor de inferencia (degradación en cascada)

El campo `engine` de cada respuesta indica **con qué modelo se clasificó**, para
no presentar resultados como algo que no son:

1. **`trashnet`** — MobileNetV2 afinado con TrashNet (6 clases). Se activa cuando
   existe el archivo indicado en `TRASHNET_MODEL_PATH`.
2. **`mobilenet-imagenet`** — MobileNetV2 preentrenado en ImageNet; las clases
   reconocidas se traducen a familias de residuos mediante un mapeo semántico
   (p. ej. `water_bottle → plastic`, `wine_bottle → glass`).
3. **`heuristic`** — respaldo determinista por color, saturación y brillo. Se usa
   cuando TensorFlow no está instalado, como ocurre en Vercel Serverless
   (límite de ~250 MB por función).

---

## 🧪 Pruebas

```bash
# Pruebas de todo (usando el entorno con las dependencias de ambos servicios)
python -m venv --system-site-packages .venv
.venv/Scripts/pip install -r backend/requirements.txt -r frontend/requirements.txt

cd backend  && ../.venv/Scripts/python -m unittest discover -s tests -v   # 33 pruebas
cd frontend && ../.venv/Scripts/python -m unittest discover -s tests -v   # 20 pruebas
```

En Linux/macOS reemplaza `.venv/Scripts/python` por `.venv/bin/python`.

Las pruebas se **omiten solas** si falta una dependencia opcional (`httpx`,
`whitenoise`, `PIL`, `tensorflow`), de modo que `unittest discover` nunca falla
por un módulo ausente:

| Suite | Cubre |
| --- | --- |
| `backend/tests/test_classifier.py` | Taxonomía, normalización de clases y las 3 categorías |
| `backend/tests/test_security.py` | Hash de contraseñas y ciclo de vida del JWT |
| `backend/tests/test_api.py` | Flujo completo sobre la app real: registro, login, foto, historial y errores |
| `frontend/tests/test_api_client.py` | Cliente HTTP: token, multipart y traducción de errores |
| `frontend/tests/test_views.py` | Vistas de Django: control de acceso, sesión y proxy a la API |

---

## ☁️ Despliegue en Vercel

`vercel.json` define dos funciones Serverless Python y el enrutamiento:

```json
"routes": [
  { "src": "/api/v1/(.*)", "dest": "backend/api/index.py" },
  { "src": "/(docs|redoc|openapi.json|health)", "dest": "backend/api/index.py" },
  { "src": "/(.*)", "dest": "frontend/api/index.py" }
]
```

```bash
npm i -g vercel
vercel            # preview
vercel --prod     # producción
```

### Variables de entorno obligatorias en Vercel

**Backend** → `backend/api/index.py`

| Variable | Ejemplo |
|----------|---------|
| `SECRET_KEY` | clave larga y aleatoria para firmar los JWT |
| `CORS_ORIGINS` | `https://tu-proyecto.vercel.app` |
| `DATABASE_URL` | `sqlite:////tmp/ecoscan.db` (valor por defecto en Vercel) |
| `DEBUG` | `0` en producción — es la variable del **backend**, no la del frontend |
| `MAX_UPLOAD_MB` | `4` — Vercel corta el cuerpo de la petición en 4.5 MB |

**Frontend** → `frontend/api/index.py`

| Variable | Ejemplo |
|----------|---------|
| `DJANGO_SECRET_KEY` | debe ser **fija**: si cambia, las sesiones se invalidan |
| `DJANGO_DEBUG` | `0` en producción. Ojo: la variable se llama `DJANGO_DEBUG`, **no** `DEBUG` |
| `ALLOWED_HOSTS` | `.vercel.app` — **obligatorio** en cuanto `DJANGO_DEBUG=0`, si no todas las peticiones devuelven 400 `DisallowedHost` |
| `CSRF_TRUSTED_ORIGINS` | `https://tu-proyecto.vercel.app` |
| `FASTAPI_BASE_URL` | `https://tu-proyecto.vercel.app` |
| `MAX_UPLOAD_BYTES` | `4194304` (4 MiB) — Vercel corta el cuerpo de la petición en 4.5 MB |

### Notas de producción

- **Sistema de archivos:** solo `/tmp` es escribible. `config.py` (backend) y
  `settings.py` (frontend) cambian la ruta de SQLite automáticamente cuando
  detectan la variable `VERCEL`.
- **Estáticos:** WhiteNoise los sirve desde `STATICFILES_DIRS`
  (`WHITENOISE_USE_FINDERS=True`). Si prefieres el almacenamiento comprimido con
  manifiesto, ejecuta `bash scripts/build_vercel.sh` en el build.
- **Modelo real:** TensorFlow no cabe en el límite de 250 MB de Vercel. Para
  servir MobileNetV2 real, despliega el backend en un host con contenedores
  (Render, Railway, Fly.io) con `requirements-ml.txt`.
- **Tamaño de las fotos:** las funciones de Vercel cortan el cuerpo de la
  petición en **4.5 MB**, así que el límite de la aplicación se fija en 4 MiB
  (`MAX_UPLOAD_MB` en el backend y `MAX_UPLOAD_BYTES` en el frontend, ambos
  valores deben coincidir). Así el usuario recibe el mensaje de la app y no un
  `413` del proveedor.
- **`requirements.txt` duplicado por función:** Vercel no resuelve el include
  `-r ../requirements.txt` (falla con `Error parsing included file`), así que
  `backend/api/requirements.txt` y `frontend/api/requirements.txt` repiten la
  lista de su servicio. Al tocar `backend/requirements.txt` o
  `frontend/requirements.txt`, replica el cambio en el archivo de la función.
- **SQLite en `/tmp` es efímero y por instancia:** los usuarios registrados se
  pierden en cada arranque en frío y no se comparten entre instancias. Para
  persistencia real, apunta `DATABASE_URL` a un Postgres (Neon, Supabase) y
  añade su driver a `backend/requirements.txt`.

---

## 🔐 Seguridad

- Contraseñas con **bcrypt** (nunca en texto plano).
- **JWT** firmados con `HS256` y expiración configurable (8 h por defecto).
- Sesión de Django con **cookie firmada** `HttpOnly`; el token no llega a JS.
- Validación de tamaño, tipo MIME y contenido real de cada imagen (PIL).
- Errores homogéneos en JSON sin filtrar trazas internas.

---

## 📜 Historial de commits

| # | Commit |
|---|--------|
| 1 | `init: estructura base django frontend y fastapi backend` |
| 2 | `feat: modulo de autenticacion de usuario y control de acceso` |
| 3 | `feat: carga e inferencia del modelo preentrenado en fastapi` |
| 4 | `docs: esquemas pydantic y documentacion de endpoints en swagger` |
| 5 | `feat: interfaz ui en django y captura de stream de cámara en js` |
| 6 | `feat: integracion http entre cliente django y servidor fastapi` |
| 7 | `fix: optimizacion de respuesta, manejo de errores y ui polish` |
| 8 | `deploy: configuracion vercel.json y pruebas finales de produccion` |
| 9 | `fix: build de Vercel y renombrado de la app a EcoScan IA` |

## 👥 Equipo

Taller 4 — 15 horas de desarrollo (7.5 h por integrante).
