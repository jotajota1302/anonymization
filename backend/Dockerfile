FROM python:3.11-slim

# Dependencias del sistema: compilación de cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Modelo spaCy para NER en español (Presidio lo necesita)
RUN python -m spacy download es_core_news_lg

COPY . .

# Directorio para SQLite
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
