FROM python:3.11-slim

WORKDIR /osw-eval

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt


COPY packages/ ./packages/
COPY inspicio_backend/ ./inspicio_backend/


RUN pip install -e ./packages/osw-data/

EXPOSE 8000

CMD ["python", "inspicio_backend/server.py"]