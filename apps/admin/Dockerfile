FROM node:22-alpine AS build

WORKDIR /app

COPY package.json tsconfig.base.json /app/
COPY apps/admin/package.json /app/apps/admin/package.json

RUN npm install

COPY apps/admin /app/apps/admin

RUN npm --workspace @rag/admin run build

FROM nginx:1.27-alpine

COPY infra/nginx/admin.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/admin/dist /usr/share/nginx/html
