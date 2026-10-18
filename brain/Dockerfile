FROM node:22-slim

# python3 + httpx для шлюза, git/ripgrep — инструменты, которые ждёт Claude Code.
# В Debian python3-certifi берёт системное хранилище сертификатов,
# поэтому CA Минцифры (для TLS к MAX) достаточно добавить в систему.
# Проверку TLS НЕ отключаем — только добавляем доверенный корень.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-httpx git ripgrep ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY certs/russian_trusted_root_ca.pem /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
COPY certs/russian_trusted_sub_ca.pem /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt
RUN update-ca-certificates

ARG CLAUDE_CODE_VERSION=2.1.302
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} && npm cache clean --force

WORKDIR /app
COPY bot.py .

# Не root: Claude Code работает под обычным пользователем node.
USER node

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
  CMD python3 -c "import os,time,sys; f='/tmp/gateway_heartbeat'; sys.exit(0 if os.path.exists(f) and time.time()-float(open(f).read())<120 else 1)"

CMD ["python3", "-u", "bot.py"]
