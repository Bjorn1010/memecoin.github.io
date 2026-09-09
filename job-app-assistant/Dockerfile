FROM node:22-slim AS web-build
WORKDIR /app/web
COPY web/package*.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM node:22-slim
WORKDIR /app

# better-sqlite3 a besoin d'outils de compilation natifs
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

COPY server/package*.json ./server/
RUN cd server && npm install --omit=dev

COPY server/ ./server/
COPY --from=web-build /app/web/dist ./web/dist

WORKDIR /app/server
ENV NODE_ENV=production
EXPOSE 8787
CMD ["node", "src/index.js"]
