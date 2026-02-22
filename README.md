# 🛡️ GekOsint v5.0

Bot de Telegram para investigación OSINT (Open Source Intelligence). Modular, cloud-ready, con acceso controlado.

## 🚀 Características

### Módulos OSINT
| Módulo | Descripción |
|--------|-------------|
| 🔍 **IP Lookup** | Geolocalización, ISP, ASN, WHOIS, puertos abiertos, blacklist check, links OSINT |
| 📱 **Phone Intel** | Análisis de número, operadora, ubicación, Truecaller, validación, formatos |
| 👤 **Username Search** | Búsqueda en 50+ plataformas + Telegram lookup detallado |
| 📧 **Email Analysis** | Reputación, brechas de datos, DNS security, Gravatar, análisis de usuario |
| 💚 **WhatsApp OSINT** | Registro WA, foto de perfil, spam reports, Business check, links OSINT |
| 🌍 **Geo Tracker** | Genera enlace trampa para obtener ubicación GPS del objetivo |
| 📸 **Camera Trap** | Genera enlace trampa para capturar foto de cámara frontal |
| 🖼️ **EXIF Data** | Extracción completa de metadatos, GPS, hash, configuración de cámara |

### Seguridad
- 🔒 **Acceso controlado** — Solo 6 usuarios autorizados (hardcodeado)
- 🚨 **Alertas al admin** — Notificación de intentos de acceso no autorizado
- 📋 **Logging completo** — Registro de todas las acciones

### Deploy
- ☁️ **Cloud-Ready** — Compatible con Railway, Render, Fly.io, Heroku
- 🐳 **Docker** — Dockerfile incluido
- 💻 **Local** — Funciona en Windows/Linux/Mac
- 🔄 **Webhook + Polling** — Detecta automáticamente el entorno

---

## ⚡ Instalación Rápida

### 1. Clonar repositorio
```bash
git clone https://github.com/tu-usuario/GekOsint.git
cd GekOsint
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar
```bash
# Copiar ejemplo de configuración
cp .env.example .env

# Editar .env con tu token de Telegram
# GEKOSINT_TOKEN=tu_token_de_botfather
```

### 4. Configurar usuarios autorizados
Edita [`config.py`](config.py:30) y reemplaza los IDs placeholder:
```python
ALLOWED_USERS = {
    111111111,   # Usuario 1 — REEMPLAZAR con ID real
    222222222,   # Usuario 2 — REEMPLAZAR con ID real
    ...
}
```
> Obtén tu ID enviando `/start` a `@userinfobot` en Telegram.

### 5. Ejecutar
```bash
python bot.py
```

---

## ☁️ Deploy en la Nube (Sin PC)

### Railway (Recomendado)
1. Crea cuenta en [railway.app](https://railway.app)
2. Conecta tu repositorio de GitHub
3. Agrega variable de entorno: `GEKOSINT_TOKEN=tu_token`
4. Deploy automático ✅

### Render
1. Crea cuenta en [render.com](https://render.com)
2. New > Web Service > Conecta GitHub
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python bot.py`
5. Agrega variable: `GEKOSINT_TOKEN=tu_token`

### Docker
```bash
docker build -t gekosint .
docker run -e GEKOSINT_TOKEN=tu_token gekosint
```

---

## 📁 Estructura del Proyecto

```
GekOsint/
├── bot.py                    # Punto de entrada principal
├── config.py                 # Configuración y control de acceso
├── requirements.txt          # Dependencias Python
├── Dockerfile                # Para deploy con Docker
├── Procfile                  # Para Heroku/Railway
├── .env.example              # Ejemplo de variables de entorno
│
├── handlers/
│   └── commands.py           # Handlers de Telegram (start, callbacks, mensajes)
│
├── modules/
│   ├── ip_lookup.py          # Análisis de IP (geoloc, WHOIS, puertos, blacklist)
│   ├── phone_lookup.py       # Análisis de teléfono (phonenumbers, Truecaller)
│   ├── username_search.py    # Búsqueda en 50+ plataformas
│   ├── email_analysis.py     # Análisis de email (reputación, brechas, DNS)
│   ├── whatsapp_osint.py     # OSINT de WhatsApp
│   ├── exif_extract.py       # Extracción de metadatos EXIF
│   ├── tracking.py           # Generador de páginas tracking
│   └── tracking_templates.py # Templates HTML para Geo/Cam
│
├── ui/
│   ├── menus.py              # Menús InlineKeyboard de Telegram
│   └── templates.py          # Formateo de respuestas (estilo dashboard)
│
├── utils/
│   ├── apis.py               # Deploy HTML (Vercel/Catbox/0x0) + URL shortener
│   └── simple_server.py      # Servidor web simple (opcional)
│
└── pages/                    # Archivos HTML generados (gitignored)
```

---

## 🔧 Variables de Entorno

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `GEKOSINT_TOKEN` | ✅ | Token del bot de Telegram |
| `VERCEL_TOKEN` | ❌ | Token de Vercel para deploy de tracking |
| `RAPIDAPI_KEY` | ❌ | Key de RapidAPI para Truecaller |
| `LOG_LEVEL` | ❌ | Nivel de logging (INFO/DEBUG) |

---

## 📋 Comandos del Bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Menú principal con todas las herramientas |
| `/help` | Igual que /start |

---

## ⚠️ Disclaimer

Este bot es para **investigación ética y educativa**. El uso indebido es responsabilidad del usuario. Respeta las leyes de tu jurisdicción.

---

## 📝 Licencia

Uso privado. No redistribuir sin autorización.
