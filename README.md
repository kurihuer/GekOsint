
# 🛡️ GekOsint v4.0

> **Herramienta Avanzada de Inteligencia de Código Abierto (OSINT) para Telegram.**  
> Diseñada para analistas de ciberseguridad, investigadores éticos y equipos de Red Teaming.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 🚀 Capacidades

El bot integra múltiples módulos de inteligencia en una interfaz estilo "Dashboard Cybersec":

- **📡 IP Intelligence**: Geolocalización, detección de VPN/Proxy, análisis de riesgo y datos de ISP.
- **📱 Phone Number Intel**: Análisis de portabilidad, operador, tipo de línea y geolocalización (Soporte LATAM mejorado).
- **👤 Username Recon**: Búsqueda concurrente en más de 20 redes sociales y plataformas (GitHub, Twitter, Instagram, etc.).
- **📧 Email Analysis**: Verificación de reputación, detección de correos desechables, registros MX y comprobación de brechas.
- **📍 Tracking & Geo**: Generación de enlaces trampa (Honey Links) para obtener IP, coordenadas GPS precisas y captura de cámara (con consentimiento simulado).
- **📂 EXIF Metadata**: Extracción de metadatos ocultos en imágenes (Modelo de cámara, GPS, Fecha original).

---

## 🛠️ Instalación y Despliegue

### Opción 1: Docker (Recomendado)
Ideal para VPS (Ubuntu/Debian) o despliegue local limpio.

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/gekosint.git
cd gekosint

# 2. Configurar variables
cp .env.example .env
# Edita .env y pon tu TOKEN de Telegram

# 3. Desplegar
docker-compose up -d --build
```

### Opción 2: Local (Python)
Para desarrollo o pruebas rápidas.

```bash
pip install -r requirements.txt
python bot.py
```

### Opción 3: Hosting Gratuito (Railway/Render)
Este proyecto incluye `Dockerfile` y `requirements.txt` optimizados.
1. Haz un fork de este repo.
2. Conéctalo a tu cuenta de **Railway** o **Render**.
3. Define la variable de entorno `GEKOSINT_TOKEN`.
4. ¡Deploy!

---

## ⚙️ Configuración (.env)

Crea un archivo `.env` en la raíz:

```ini
# Obligatorio
GEKOSINT_TOKEN=tu_token_de_botfather

# Opcional (Mejora resultados)
LOG_LEVEL=INFO
```

---

## 🔒 Aviso Legal

Esta herramienta ha sido desarrollada con fines puramente **educativos y de diagnóstico de seguridad**. 
El uso de **GekOsint** para atacar objetivos sin consentimiento previo mutuo es ilegal. Es responsabilidad del usuario final obedecer todas las leyes locales, estatales y federales aplicables. Los desarrolladores no asumen ninguna responsabilidad y no son responsables de ningún mal uso o daño causado por este programa.

---

**Desarrollado con 💻 por el equipo GekOsint.**
