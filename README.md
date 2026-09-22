# Taller 4 — Clasificador de Residuos en Punto Limpio

Aplicacion web que clasifica residuos a partir de una fotografia tomada con la
camara del dispositivo y responde con la categoria, el tipo de residuo y el
color del contenedor donde debe depositarse.

## Problema real

Mala separacion de basura en la fuente por desconocimiento del usuario.

## Stack

| Capa | Tecnologia |
|------|------------|
| Frontend | Django (vistas, plantillas HTML5, `getUserMedia` para captura de camara) |
| Backend | FastAPI (inferencia del modelo, validacion Pydantic, Swagger en `/docs`) |
| Modelo | MobileNetV2 preentrenado (ImageNet / TrashNet) |
| Autenticacion | Login/Password con JWT emitido por FastAPI |
| Despliegue | Vercel Serverless Functions (`vercel.json`) |

## Estructura

```
.
├── backend/            # API FastAPI (modelo + autenticacion + Swagger)
│   ├── app/
│   └── api/            # entrypoint Serverless para Vercel
├── frontend/           # Cliente Django (UI + captura de camara)
│   ├── config/
│   └── web/
├── vercel.json
└── README.md
```

## Endpoints principales

- `POST /api/v1/classify-waste` — procesa la foto y devuelve la clasificacion.
- `GET /api/v1/bins-guide` — guia de reciclaje y colores de contenedor.

Documentacion interactiva en `/docs`.
