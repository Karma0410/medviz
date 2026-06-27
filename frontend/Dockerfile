# ===== STAGE 1: build =====
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ENV VITE_API_BASE_URL=http://localhost/api
ENV VITE_API_WS_URL=ws://localhost/ws

RUN npm run build

# ===== STAGE 2: nginx serve =====
FROM nginx:alpine

RUN rm -rf /usr/share/nginx/html/*

COPY --from=builder /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]