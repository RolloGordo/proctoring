#!/bin/bash
# Levanta la web contra el entorno de carga (API en :8080, Supabase local en :54321),
# solo en 127.0.0.1:5173: no se ve desde internet. Uso: video/web-local.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
ANON=$(supabase status -o env 2>/dev/null | sed -n 's/^ANON_KEY="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p')
[ -n "$ANON" ] || { echo "Supabase local no está arriba"; exit 1; }
docker build -q -t proctoring-web:carga \
  --build-arg VITE_API_URL=http://localhost:8080 \
  --build-arg VITE_SUPABASE_URL=http://localhost:54321 \
  --build-arg VITE_SUPABASE_PUBLISHABLE_KEY="$ANON" apps/web
docker rm -f web-carga >/dev/null 2>&1 || true
docker run -d --name web-carga -p 127.0.0.1:5173:80 \
  -v "$PWD/loadtests/video/cabeceras-carga.conf:/etc/nginx/cabeceras.conf:ro" proctoring-web:carga
echo "web de carga en http://localhost:5173"
