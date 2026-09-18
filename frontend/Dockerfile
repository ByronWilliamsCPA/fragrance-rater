# Multi-stage Dockerfile for Fragrance Rater Frontend
# Based on FastAPI full-stack template best practices

# =============================================================================
# Stage 1: Dependencies
# =============================================================================
FROM node:22-alpine AS deps

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production=false

# =============================================================================
# Stage 2: Builder
# =============================================================================
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY . .

# Build arguments for environment configuration
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# Build the application
RUN npm run build

# =============================================================================
# Stage 3: Development (optional - for docker-compose dev)
# =============================================================================
FROM node:22-alpine AS development

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev)
RUN npm ci

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# =============================================================================
# Stage 4: Production (nginx)
# =============================================================================
# #CRITICAL: build-tooling: this must stay the LAST stage in the file. CI
# (ByronWilliamsCPA/.github's python-docker.yml) builds this Dockerfile
# without a --target flag, so Docker's "no target = build the last stage"
# default is the only thing that makes CI produce the nginx image instead
# of the Vite dev server above. Local dev is unaffected either way since
# docker-compose.yml/docker-compose.prod.yml both pin target: by name.
# #VERIFY before adding any stage after this one, confirm CI still ends up
# publishing the production (nginx, port 80) image, not development.
FROM nginx:alpine AS production

# Metadata labels
LABEL org.opencontainers.image.title="Fragrance Rater Frontend"
LABEL org.opencontainers.image.description="Personal fragrance evaluation and recommendation system for family use with LLM-powered recommendations"
LABEL org.opencontainers.image.authors="Byron Williams <byron@williamshome.family>"

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create non-root user for nginx
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup && \
    chown -R appuser:appgroup /var/cache/nginx && \
    chown -R appuser:appgroup /var/log/nginx && \
    chown -R appuser:appgroup /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appgroup /var/run/nginx.pid

# Expose port 80
EXPOSE 80

# Health check
# #CRITICAL: external resources: busybox wget resolves "localhost" via
# /etc/hosts, which lists ::1 before 127.0.0.1, and unlike curl it does not
# fall back to the next address on connection failure. nginx's "listen 80;"
# binds IPv4-only, so wget's IPv6 attempt gets connection-refused and the
# healthcheck fails every time even though the app is serving fine over
# IPv4. Traefik's Docker provider excludes unhealthy containers from
# routing entirely, so this alone can take the app offline (404, not a
# backend-level 502) despite nginx working. Using 127.0.0.1 forces IPv4.
# #VERIFY after any base-image bump, confirm 127.0.0.1 is still reachable
# and nginx still binds IPv4 (docker inspect --format
# '{{json .State.Health}}' should show Status "healthy", not "unhealthy").
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/health || exit 1

# Run as non-root user
USER appuser

CMD ["nginx", "-g", "daemon off;"]
