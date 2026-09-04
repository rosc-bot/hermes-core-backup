FROM node:20-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production \
    PORT=4888 \
    HOST=0.0.0.0

# 运行时系统依赖与 Noto 字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-extra \
    fontconfig \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libjpeg62-turbo \
    libgif7 \
    librsvg2-2 \
    libpixman-1-0 \
    libvips42 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

COPY . .

EXPOSE 4888

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:4888/health || exit 1

CMD ["node", "index.js"]
