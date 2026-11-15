# Web del docente y del examen, servida por nginx en el VPS (antes Vercel).
# Las VITE_* se hornean al construir: son públicas (la clave de Supabase es la
# publicable, con RLS detrás), así que van como argumentos de construcción.
FROM node:22-alpine AS construir
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/cabeceras.conf /etc/nginx/cabeceras.conf
COPY --from=construir /web/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
