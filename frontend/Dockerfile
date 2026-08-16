# Phase 12: containerized frontend, for `docker compose up` local bring-up
# only. Not a deployment artifact yet - registry push is deferred to
# Phase 13. Multi-stage: build the static Vite bundle with Node, then serve
# it with nginx - the built output is plain static files, so shipping a
# Node runtime (or the dev server) in the final image would be unjustified
# weight for what's ultimately HTML/CSS/JS.

FROM node:24-alpine AS build
WORKDIR /app

# Install dependencies first so this layer only invalidates when
# package*.json actually change, not on every source edit.
COPY package.json package-lock.json* ./
# --legacy-peer-deps: pre-existing (not introduced by Phase 12) peer-range
# mismatch - openapi-typescript@7.13.0 declares `peer typescript@"^5.x"`,
# but this project pins `typescript@~6.0.2`. openapi-typescript is a
# devDependency-only, build-time-only CLI codegen tool (see
# `npm run generate:api`) that has no runtime interaction with TypeScript's
# compiler API, so the mismatch is real but not exploitable/breaking in
# practice - documented in SECURITY.md rather than papered over by
# downgrading typescript project-wide for one dev tool's stale peer range.
RUN npm ci --legacy-peer-deps

COPY . .

# VITE_API_BASE_URL is baked in at build time (Vite inlines import.meta.env
# values into the bundle - there is no server-side env at runtime for a
# static build). Defaults to the same http://localhost:8000 the app already
# uses for local `npm run dev` (see src/api/client.ts) - the backend
# container publishes that same port, so the browser reaches it identically
# whether the frontend is served by Vite's dev server or this image.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# 127.0.0.1, not localhost: this Alpine image's `localhost` resolves to
# ::1 (IPv6) first, but nginx (see nginx.conf) only binds 0.0.0.0:80
# (IPv4) - `wget http://localhost/healthz` connection-refuses on the IPv6
# attempt even though the server is up and reachable on IPv4. Caught by
# the real `docker compose up` smoke test, not by `curl`ing the healthz
# endpoint from the host, which goes through the IPv4 port mapping either
# way and never exercises this path.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1
