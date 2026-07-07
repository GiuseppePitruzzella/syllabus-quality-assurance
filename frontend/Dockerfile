FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# `npm install` (not `npm ci`): the committed lockfile is generated on macOS and
# omits linux-only native optional deps (e.g. @emnapi/*), which makes the strict
# `npm ci` fail inside this linux image. `npm install` honours the lockfile and
# resolves the platform-appropriate optional deps at build time.
RUN npm install --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
