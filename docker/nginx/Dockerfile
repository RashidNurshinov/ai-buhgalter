# Multi-stage: сборка фронтенда + nginx
FROM node:20-alpine AS frontend-build

WORKDIR /app

# Копируем package.json и устанавливаем зависимости
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit

# Копируем исходный код фронтенда
COPY frontend/ ./

# Собираем production build
RUN npm run build

# === Nginx ===
FROM nginx:alpine

# Удаляем дефолтный конфиг
RUN rm /etc/nginx/conf.d/default.conf

# Копируем наш конфиг
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Копируем собранный фронтенд
COPY --from=frontend-build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]