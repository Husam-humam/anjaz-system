FROM node:20-alpine

ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

RUN adduser -D -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

COPY --chown=appuser:appuser . .

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["npm", "run", "dev"]
