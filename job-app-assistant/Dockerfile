FROM node:22-slim AS web-build
WORKDIR /app/web
COPY web/package*.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM node:22-slim
WORKDIR /app

COPY server/package*.json ./server/
RUN cd server && npm install --omit=dev
# Chromium headless (+ ses dépendances système) pour générer les PDF (lettre, CV).
RUN cd server && npx playwright install --with-deps chromium

COPY server/ ./server/
COPY --from=web-build /app/web/dist ./web/dist

WORKDIR /app/server
ENV NODE_ENV=production
EXPOSE 8787
CMD ["node", "src/index.js"]
