FROM node:22-bookworm

# Backend test suite needs a Python interpreter; PuLP ships its own CBC
# binaries in the wheel, so no extra solver package is required.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY run.sh smoke.py /opt/verify/
RUN chmod +x /opt/verify/run.sh

CMD ["/opt/verify/run.sh"]
