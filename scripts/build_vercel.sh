#!/usr/bin/env bash
# Build opcional para Vercel: recolecta los estaticos de Django.
#
# WhiteNoise ya sirve los archivos desde STATICFILES_DIRS gracias a
# WHITENOISE_USE_FINDERS=True, por lo que este script solo es necesario si se
# habilita CompressedManifestStaticFilesStorage en produccion.
#
# Uso local:  bash scripts/build_vercel.sh
set -euo pipefail

cd "$(dirname "$0")/../frontend"

echo "==> Recolectando archivos estaticos de Django"
python manage.py collectstatic --noinput --clear

echo "==> Build completado"
