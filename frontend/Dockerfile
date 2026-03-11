FROM node:22-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build
RUN npm prune --omit=dev

FROM node:22-slim

WORKDIR /app

COPY --from=builder /app/build build
COPY --from=builder /app/node_modules node_modules
COPY --from=builder /app/package.json .

ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

EXPOSE 3000

CMD ["node", "build"]
