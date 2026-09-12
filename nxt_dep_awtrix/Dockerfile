FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY prim_client.py /app/prim_client.py
COPY nxt_dep_awtrix.py /app/nxt_dep_awtrix.py
COPY logging.conf /app/logging.conf

CMD ["python3", "/app/nxt_dep_awtrix.py"]
