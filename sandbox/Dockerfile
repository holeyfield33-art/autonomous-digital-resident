# The Resident's own machine. Only the workspace is mounted from the host; controller state,
# credentials and the Docker socket never enter this container.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash ca-certificates curl wget git jq ripgrep tree less file unzip zip \
        build-essential sqlite3 nodejs npm procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        requests httpx beautifulsoup4 lxml numpy pandas matplotlib scipy sympy \
        pyyaml rich pytest networkx

ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg HOME=/root
WORKDIR /workspace
CMD ["sleep", "infinity"]
