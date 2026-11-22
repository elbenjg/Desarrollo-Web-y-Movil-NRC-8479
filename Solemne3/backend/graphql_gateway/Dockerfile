# Imagen del GraphQL Gateway privado.
FROM node:24-alpine
WORKDIR /app
COPY backend/graphql_gateway/package.json backend/graphql_gateway/package-lock.json ./
RUN npm ci --omit=dev
COPY backend/graphql_gateway/server.js .
