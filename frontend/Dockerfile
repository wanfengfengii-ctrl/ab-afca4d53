# ---- build stage ----
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

# ---- serve stage ----
FROM nginx:alpine

# Port nginx listens on inside the container; compose sets it from WEB_PORT.
# Only WEB_PORT may be substituted into the template so nginx runtime
# variables ($host, $remote_addr, ...) are preserved verbatim.
ENV WEB_PORT=8080 \
    NGINX_ENVSUBST_FILTER=^WEB_PORT$$

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 8080

# BusyBox wget is present in alpine; shell form expands $WEB_PORT at runtime.
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=12 \
    CMD wget -q -O /dev/null "http://127.0.0.1:${WEB_PORT}/" || exit 1
