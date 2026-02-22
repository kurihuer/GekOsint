FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero (cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Crear directorio de páginas
RUN mkdir -p pages

# Puerto para webhook (Railway/Render)
EXPOSE 8443

# Ejecutar bot
CMD ["python", "bot.py"]
