FROM python:3.9-slim
WORKDIR /app
COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY web/ .
CMD exec gunicorn -w 2 -b 0.0.0.0:$PORT server:app
