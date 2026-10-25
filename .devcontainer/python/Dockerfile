FROM python:3.12-slim
WORKDIR /workspaces/enterprise-doc-qa/ai
ENV PYTHONUNBUFFERED=1 PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
COPY ai/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
EXPOSE 8000
