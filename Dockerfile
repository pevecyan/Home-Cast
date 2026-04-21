# Stage 1: Build Vue UI
FROM node:20-alpine AS ui-build
WORKDIR /build
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Stage 2: Python app + nginx
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx ffmpeg curl unzip && \
    curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY run.py ./
COPY CHANGELOG.json ./
COPY config.docker.yaml ./config.yaml

# Copy built UI
COPY --from=ui-build /build/dist /var/www/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Create cache and data directories
RUN mkdir -p /app/cache /app/data

EXPOSE 5050

# Use --network host when running so speakers can reach this server
# docker run --network host -e HOSTNAME=http://YOUR_LAN_IP home-cast
CMD sh -c "python run.py & nginx -g 'daemon off;'"
