FROM node:22-alpine AS build

WORKDIR /app

COPY package.json tsconfig.base.json /app/
COPY apps/widget/package.json /app/apps/widget/package.json

RUN npm install

COPY apps/widget /app/apps/widget

RUN npm --workspace @rag/widget run build

FROM nginx:1.27-alpine

COPY infra/nginx/widget.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/widget/dist /usr/share/nginx/html
