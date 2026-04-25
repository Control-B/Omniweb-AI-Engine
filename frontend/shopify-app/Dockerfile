FROM node:20-slim AS base
WORKDIR /app
ENV NODE_ENV=production
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends openssl \
  && rm -rf /var/lib/apt/lists/*

FROM base AS deps
RUN corepack enable && corepack prepare pnpm@9.6.0 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM deps AS build
COPY . .
RUN pnpm prisma:generate && pnpm build

FROM deps AS dev
WORKDIR /app
ENV NODE_ENV=development
COPY . .
RUN pnpm prisma:generate
EXPOSE 3000
CMD ["pnpm", "dev"]

FROM base AS runner
RUN corepack enable && corepack prepare pnpm@9.6.0 --activate
COPY --from=build /app /app
EXPOSE 3000
CMD ["pnpm", "start"]
