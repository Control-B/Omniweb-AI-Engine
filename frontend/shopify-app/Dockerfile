FROM node:20-slim AS base
WORKDIR /app
ENV NODE_ENV=production
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends openssl \
  && rm -rf /var/lib/apt/lists/*

FROM base AS deps
RUN corepack enable && corepack prepare pnpm@9.6.0 --activate
COPY frontend/shopify-app/package.json frontend/shopify-app/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod=false

FROM deps AS build
COPY frontend/shopify-app/ ./
RUN pnpm prisma:generate && pnpm build

FROM deps AS dev
WORKDIR /app
ENV NODE_ENV=development
COPY frontend/shopify-app/ ./
RUN pnpm prisma:generate
EXPOSE 3000
CMD ["pnpm", "dev"]

FROM base AS runner
RUN corepack enable && corepack prepare pnpm@9.6.0 --activate
COPY --from=build /app /app
EXPOSE 3000
CMD ["pnpm", "start"]
