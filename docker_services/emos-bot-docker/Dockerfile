FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "python-telegram-bot[job-queue]==22.8" \
    "apscheduler>=3.10.4,<3.12.0" \
    requests==2.33.0 \
    pytz==2026.3.post1

COPY emos_bot.py emos_db.py ./

CMD ["python", "emos_bot.py"]
