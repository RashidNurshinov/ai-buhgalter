FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# Healthcheck: процесс жив, если heartbeat-файл обновлялся в последние 120 сек.
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import os,time,sys; f='/tmp/gateway_heartbeat'; sys.exit(0 if os.path.exists(f) and time.time()-float(open(f).read())<120 else 1)"

CMD ["python", "-u", "bot.py"]
