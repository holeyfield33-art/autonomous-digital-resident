FROM python:3.11-slim@sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce
WORKDIR /app
COPY requirements-lock.txt pyproject.toml README.md LICENSE ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY agent ./agent
COPY SOUL.md ./SOUL.md
RUN pip install --no-deps . && mkdir -p /data/state /data/workspace && chown -R 65534:65534 /data
USER 65534:65534
CMD ["resident", "demo", "--home", "/data/state", "--workspace", "/data/workspace", "--interval", "0"]
