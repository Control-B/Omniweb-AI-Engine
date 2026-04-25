FROM node:20-slim AS base
WORKDIR /app
ENV NODE_ENV=production

FROM base AS deps
COPY package.json ./
RUN corepack enable && pnpm install

FROM deps AS build
COPY . .
RUN pnpm prisma:generate && pnpm build

FROM base AS runner
COPY --from=build /app /app
EXPOSE 3000
CMD ["pnpm", "start"]
