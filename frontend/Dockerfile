# ClinicFlow frontend image.
#
# Multi-stage: Node builds the bundle, then only the static output is copied into
# an Nginx runtime. The build toolchain (node_modules, the compiler) never reaches
# the final image, which is both smaller and a smaller attack surface for Trivy.

# ---------- stage 1: build ----------
FROM node:22-alpine AS build

WORKDIR /app

# package files first so npm ci is cached independently of source changes
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- stage 2: runtime ----------
# nginx-unprivileged runs as uid 101 and listens on 8080, so no root is involved.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Backend address is substituted into the config at container start, so the same
# image works in Docker Compose and in Kubernetes without a rebuild.
ENV BACKEND_URL=http://backend:8000

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:8080/healthz || exit 1
