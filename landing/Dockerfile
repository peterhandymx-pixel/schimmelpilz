FROM node:22-alpine AS build
WORKDIR /app
COPY landing/package.json landing/pnpm-lock.yaml landing/pnpm-workspace.yaml landing/.npmrc ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY landing ./
RUN pnpm exec vite build

FROM nginx:1.27-alpine
COPY --from=build /app/dist/client /usr/share/nginx/html
EXPOSE 80
