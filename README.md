# 🛡️ GekOsint v6.1

Bot de Telegram para investigación OSINT (Open Source Intelligence). Modular, cloud-ready, con acceso controlado y rate limiting por usuario.

---

## 🚀 Módulos disponibles

| Módulo | Descripción |
|--------|-------------|
| 🔍 **IP Lookup** | Geolocalización, ISP, ASN, WHOIS, puertos (Shodan), blacklist (AbuseIPDB, VirusTotal, GreyNoise) |
| 📱 **Phone Intel** | Caller ID, operadora, tipo de línea (VOIP detection), región exacta por lada, spam score multi-fuente (Truecaller, SpamCalls, Tellows), evaluación de riesgo consolidada |
| 👤 **Username Search** | Búsqueda en 50+ plataformas + lookup detallado en Telegram |
| 📧 **Email Analysis** | Reputación, brechas de datos, DNS security (SPF/DMARC), Gravatar, análisis del alias |
| 💚 **WhatsApp OSINT** | Estado de registro, foto de perfil, spam reports, cuenta Business |
| 🌍 **Geo Tracker** | Genera enlace trampa para obtener ubicación GPS del objetivo |
| 📸 **Camera Trap** | Genera enlace trampa para capturar foto de cámara frontal |
| 🖼️ **EXIF Data** | Extracción completa de metadatos, GPS, configuración de cámara |
| 🧑‍💼 **People Search** | Nombre → perfiles en 20+ redes, dorks Google, bases OSINT |
| 🌐 **Domain/DNS** | WHOIS, registros A/MX/NS, DNSSEC, SPF/DMARC, IP History |
| 🛰️ **Geo Localización** | IP, coordenadas, Google Maps URLs, análisis WebRTC |
| 📶 **WiFi Scanner** | Redes cercanas para triangulación |
| 🐙 **GitHub Recon** | Perfil, repos, organizaciones, correos expuestos y actividad |
| 📸 **Instagram OSINT** | Perfil, bio, seguidores, publicaciones (cookies de sesión opcionales) |
| 👥 **Facebook OSINT** | Perfil público, recovery hints, foto y metadata de Pages |
| ✉️ **Gmail/Google OSINT** | Nombre, foto, Gaia ID y servicios (cookies opcionales) |
| 🎵 **TikTok OSINT** | Perfil, estadísticas, bio y verificación |
| 📬 **Email Recon** | Brechas, reputación, alias y proveedor |
| 🧠 **Universal Recon** | Ejecuta todos los módulos relevantes en paralelo y consolida el reporte |

---

## ⚡ Instalación rápida

### 1. Clonar el repositorio
```bash
git clone https://github.com/kurihuer/GekOsint.git
cd GekOsint
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
```bash
cp .env.example .env
# Edita .env con tu editor preferido
```

Variables **mínimas** para funcionar:
```env
GEKOSINT_TOKEN=tu_token_de_botfather
ADMIN_ID=tu_telegram_id
```

> **¿Cómo obtengo mi Telegram ID?** Envía `/start` a [@userinfobot](https://t.me/userinfobot).

### 4. Ejecutar
```bash
python bot.py
```

---

## 🔧 Variables de entorno

| Variable | Obligatoria | Módulo | Descripción |
|----------|:-----------:|--------|-------------|
| `GEKOSINT_TOKEN` | ✅ | Todos | Token del bot (BotFather) |
| `ADMIN_ID` | ✅ | Acceso | Tu Telegram ID (administrador) |
| `GEKOSINT_ALLOWED` | ❌ | Acceso | IDs extra autorizados, separados por comas |
| `RATE_LIMIT_SECONDS` | ❌ | Rate limit | Cooldown entre consultas (default: 5s) |
| `RATE_LIMIT_BURST` | ❌ | Rate limit | Consultas rápidas antes del cooldown (default: 3) |
| `LOG_LEVEL` | ❌ | Bot | INFO / DEBUG / WARNING (default: INFO) |
| `PUBLIC_URL` | ❌ | Tracker | URL pública del servidor (Railway, Render…) |
| `WEBHOOK_SECRET` | ❌ | Seguridad | Secreto del webhook (`X-Telegram-Bot-Api-Secret-Token`). Si no se define, se deriva del token del bot |
| `WEBHOOK_URL` | ❌ | Bot | URL para modo webhook en lugar de polling |
| `GITHUB_TOKEN` | ❌ | Tracker | Scope `gist` — hosting de tracking pages |
| `VERCEL_TOKEN` | ❌ | Tracker | Alternativa a GitHub para hosting |
| `RAPIDAPI_KEY` | ❌ | Phone | Truecaller API (caller-ID real) |
| `NUMVERIFY_KEY` | ❌ | Phone | Validación avanzada de números |
| `HUNTER_KEY` | ❌ | Email | Verificación Hunter.io |
| `SHODAN_API_KEY` | ❌ | IP | Puertos abiertos e información de servicios |
| `GREYNOISE_API_KEY` | ❌ | IP | Clasificación de IPs (ruido/actores maliciosos) |
| `ABUSEIPDB_KEY` | ❌ | IP | Reportes de abuso |
| `VT_API_KEY` | ❌ | IP | Reputación VirusTotal |
| `IPSTACK_KEY` | ❌ | IP | Geolocalización alternativa |

---

## 📋 Comandos del bot

| Comando | Acceso | Descripción |
|---------|--------|-------------|
| `/start` | Usuarios | Menú principal |
| `/help` | Usuarios | Igual que `/start` |
| `/admin` | Admin | Panel de administración |
| `/admin add ID` | Admin | Añadir usuario autorizado |
| `/admin remove ID` | Admin | Eliminar usuario |
| `/admin stats` | Admin | Ver estadísticas |

---

## ☁️ Deploy en la nube (sin PC)

### Mantener la instancia despierta (plan Free)

El plan Free de Koyeb escala a cero tras ~65 minutos sin tráfico: el bot deja de responder hasta que alguien abre la URL. El repo incluye `.github/workflows/keepalive.yml`, que hace una petición cada 10 minutos a la URL pública y evita el deep sleep. No requiere configuración: se activa solo al estar en `main`.

### Railway (recomendado)
1. Crea cuenta en [railway.app](https://railway.app)
2. Conecta tu repositorio de GitHub
3. Agrega las variables de entorno desde el dashboard
4. Deploy automático ✅

### Render
1. Crea cuenta en [render.com](https://render.com)
2. New → Web Service → conecta GitHub
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python bot.py`
5. Agrega variables de entorno

### Docker
```bash
docker build -t gekosint .
docker run -e GEKOSINT_TOKEN=tu_token -e ADMIN_ID=tu_id gekosint
```

### Docker Compose
```bash
cp .env.example .env
# Edita .env
docker-compose up -d
```

---

## 📁 Estructura del proyecto

```
GekOsint/
├── bot.py                    # Punto de entrada
├── config.py                 # Configuración central (sin IDs hardcodeados)
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── .env.example              # Plantilla de variables de entorno
│
├── handlers/
│   └── commands.py           # Handlers de Telegram + control de acceso + rate limit
│
├── modules/
│   ├── ip_lookup.py          # IP: geoloc, WHOIS, puertos, blacklist
│   ├── phone_lookup.py       # Phone: caller-ID, spam multi-fuente, riesgo
│   ├── username_search.py    # Username: 50+ plataformas + Telegram
│   ├── email_analysis.py     # Email: reputación, brechas, DNS
│   ├── whatsapp_osint.py     # WhatsApp: registro, foto, spam
│   ├── exif_extract.py       # EXIF: metadatos, GPS, cámara
│   ├── geolocation.py        # Geoloc: IP, coords, Maps, WebRTC
│   ├── dns_lookup.py         # DNS: WHOIS, registros, seguridad
│   ├── people_search.py      # People: redes, dorks, bases OSINT
│   ├── tracking.py           # Generador de tracking pages
│   └── tracking_templates.py # HTML templates para Geo/Cam
│
├── ui/
│   ├── menus.py              # Menús InlineKeyboard
│   └── templates.py          # Formateadores de respuesta (HTML para Telegram)
│
└── utils/
    ├── access.py             # Gestión de usuarios con caché en memoria
    ├── rate_limit.py         # Rate limiter por usuario (ventana deslizante)
    ├── parse.py              # Parseo de texto (teléfono, IP, hostname)
    ├── apis.py               # Deploy HTML + URL shortener
    └── server.py             # Servidor de archivos interno
```

---

## 🔒 Seguridad

- **Sin IDs hardcodeados**: todos los accesos se configuran vía variables de entorno o `/admin`
- **Rate limiting**: cooldown configurable por usuario para proteger las APIs externas
- **Notificación de intentos**: el admin recibe alertas de accesos no autorizados
- **`authorized_users.json` en `.gitignore`**: los usuarios añadidos en runtime no se suben al repo
- **Caché de accesos**: la lista de usuarios se mantiene en memoria (lectura de disco máx. 1 vez/min)

---

## 🛠️ Troubleshooting

**El bot no responde**
- Verifica que `GEKOSINT_TOKEN` esté configurado correctamente
- Comprueba que no haya otra instancia corriendo (error 409 Conflict)

**Acceso denegado a usuarios correctos**
- Asegúrate de que `ADMIN_ID` sea tu ID numérico (no username)
- Añade usuarios con `/admin add ID` o configura `GEKOSINT_ALLOWED=ID1,ID2`

**Phone Intel no encuentra el nombre**
- El caller-ID requiere `RAPIDAPI_KEY` para resultados de Truecaller API
- Sin ella, usa scraping web (resultados más limitados pero funcionales)

**Geo/Cam Tracker no genera enlace**
- Requiere `GITHUB_TOKEN` (scope `gist`) o `VERCEL_TOKEN`
- En local, necesitas `PUBLIC_URL` apuntando a tu IP pública

**Error 429 en APIs**
- Aumenta `RATE_LIMIT_SECONDS` en `.env` para reducir el ritmo de consultas

---

## ⚠️ Aviso legal

Este bot es para **investigación ética y educativa**. El usuario es responsable del uso que haga del software. Respeta las leyes de privacidad y protección de datos de tu jurisdicción.

---

## 📝 Changelog

### v6.1
- `utils/access.py`: **bug crítico** — la caché de autorizados partía de `_cache_ts = 0.0` y `time.monotonic()` es cercano a 0 en instancias recién arrancadas, así que durante el primer minuto la lista quedaba **vacía y se negaba el acceso a todos** (admins incluidos). Ahora se carga al primer uso.
- `bot.py`: `secret_token` en el webhook — Telegram firma cada update con `X-Telegram-Bot-Api-Secret-Token`; las peticiones sin la cabecera correcta reciben **403** (antes cualquiera podía inyectar updates falsos).
- `.github/workflows/keepalive.yml`: ping automático cada 10 minutos para que la instancia Free de Koyeb no entre en deep sleep.
- `.gitignore`: ignora `*.db-journal`, `*.db-wal`, `*.db-shm` y `*.db.test`; `!.env.example` para que la plantilla no quede ignorada.
- Limpieza: fuera `gekosint.db.test`, `gekosint.db-journal` y la plantilla vacía de `.trae/`.
- `README.md`: módulos que faltaban (GitHub, Instagram, Facebook, Gmail, TikTok, Email Recon, Universal), `WEBHOOK_SECRET` y esta sección.

### v6.0
- `config.py`: eliminados IDs hardcodeados — todo vía variables de entorno
- `utils/rate_limit.py`: rate limiter por usuario con ventana deslizante
- `utils/parse.py`: extracción limpia de teléfono/IP/hostname (antes inline en handler)
- `utils/access.py`: caché en memoria para reducir lecturas de disco
- `modules/phone_lookup.py`: reescritura completa — VOIP detection, Tellows, riesgo consolidado, datos del país enriquecidos, detección regional ampliada (México, España, Colombia, Perú, Chile, Venezuela, Argentina)
- `ui/templates.py`: formato unificado con iconos, secciones claras y barra de riesgo visual
- `handlers/commands.py`: rate limit integrado, bug fix en modo EXIF (ya no queda "atrapado"), log con `exc_info`
- `.env.example`: documentación completa de todas las variables
- `README.md`: reescritura con troubleshooting, tabla de variables completa, estructura actualizada
