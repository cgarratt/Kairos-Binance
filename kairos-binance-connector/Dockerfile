FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY market_data.py market_intelligence.py macro_fibo.py cycle_phase.py server.py ./
EXPOSE 10000
CMD ["python", "server.py"]
