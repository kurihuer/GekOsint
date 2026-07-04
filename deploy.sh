
#!/bin/bash
echo "🛡️ Desplegando GekOsint..."

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no instalado. Instalando..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# Construir y levantar
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "✅ Bot desplegado correctamente."
