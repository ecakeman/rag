FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --default-timeout=180 --retries 8 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r /app/requirements.txt
COPY app /app/app
ENV PYTHONPATH=/app \
    KNOWLEDGE_HTTP_ADDR=0.0.0.0:8000
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
