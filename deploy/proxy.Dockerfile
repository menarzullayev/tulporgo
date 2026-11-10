# syntax=docker/dockerfile:1
# Caddy: automatic HTTPS for the domain, serves the Mini App build and proxies /api to the API container.
FROM node:22-alpine AS miniapp
WORKDIR /src
COPY apps/miniapp/package.json apps/miniapp/package-lock.json ./
RUN npm ci
COPY apps/miniapp ./
# the Mini App lives under /app/ (settings.miniapp_url)
RUN npm run build -- --base=/app/

FROM caddy:2.10-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=miniapp /src/dist /srv/app
