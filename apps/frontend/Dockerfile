# --- build stage ---
FROM node:20-alpine AS build
WORKDIR /app

COPY apps/frontend/package.json apps/frontend/package.json
WORKDIR /app/apps/frontend
RUN npm install --no-audit --no-fund

COPY apps/frontend/. /app/apps/frontend/
RUN npm run build

# --- runtime stage ---
FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY --from=build /app/apps/frontend/dist /usr/share/nginx/html
COPY apps/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY apps/frontend/docker-entrypoint.sh /docker-entrypoint-custom.sh
RUN chmod +x /docker-entrypoint-custom.sh

ENV API_HOST=api

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

ENTRYPOINT ["/docker-entrypoint-custom.sh"]
