# Interface web do Hermes Sentinel (TanStack Start como servidor Node).
# Build a partir da raiz do repositório: docker build -f deploy/docker/web.Dockerfile .
FROM docker.io/oven/bun:1.3 AS build
WORKDIR /app
COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile
COPY . .
# "same-origin": a interface fala com a API pelo mesmo endereço (proxy do Compose ou Ingress do Helm)
ARG VITE_SENTINEL_API_URL=same-origin
ENV VITE_SENTINEL_API_URL=$VITE_SENTINEL_API_URL \
    NITRO_PRESET=node-server
RUN bun run build

FROM docker.io/library/node:22-slim AS runtime
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /app/.output ./.output
# Usuário "node" pelo número: o Kubernetes só valida runAsNonRoot com UID numérico
USER 1000
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
