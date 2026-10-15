FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY market_data.py server.py ./
EXPOSE 8000
CMD ["python", "server.py"]
