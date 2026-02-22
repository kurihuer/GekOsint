
# GekOsint v5.0 Project Memory

## Architecture
- **Framework**: `python-telegram-bot` v20+ (Async)
- **Structure**: Modular
  - `modules/`: Core OSINT logic (IP, Phone, Username, Email, WhatsApp, Tracking, EXIF)
  - `ui/`: Visual components (menus, message templates)
  - `handlers/`: Telegram interactions (commands, callbacks)
  - `utils/`: Helpers (APIs deploy, URL shortener)
- **Deployment**: Docker + Cloud (Railway/Render/Fly.io) + Local
- **Access Control**: Hardcoded whitelist of 6 user IDs in `config.py`

## Key Conventions
- **Python Compatibility**: Python 3.11+ using `asyncio.run()` with explicit async contexts.
- **UI Style**: "Cybersec Dashboard" (Bold headers, emojis, clean lines)
- **Concurrency**: `concurrent.futures` for multi-site lookups (Username search, 20 workers)
- **Async I/O**: `httpx` for external API calls (deploy, URL shortening). `requests` for sync modules.
- **Bot Loop**: Uses `asyncio.run(run_bot())` with manual lifecycle management. Supports both Polling (local) and Webhook (cloud).
- **Tracking**: HTML pages generated in `pages/`, deployed via multiple services (Vercel [Primary], Catbox, 0x0.st) with automatic fallback.
- **String Formatting**: When using `.format()` on strings containing JavaScript or CSS, always double the curly braces `{{ }}` to avoid `KeyError`.
- **File Downloads**: In `python-telegram-bot` v20+, use `download_to_memory(BytesIO())`.
- **Env Vars**: managed via `config.py` and `.env`. Access control is hardcoded, NOT in .env.

## Modules
- **IP**: IP-API + ipinfo.io + WHOIS (RDAP) + DNSBL blacklist check + port scan + risk analysis
- **Phone**: `phonenumbers` lib + regional custom parsing + Truecaller (RapidAPI) + validation
- **Username**: Direct HTTP checks to 50+ profile URLs (Threaded, 20 workers) + Telegram API lookup
- **Email**: emailrep.io + XposedOrNot breaches + DNS security (SPF/DMARC) + Gravatar + domain age + local part analysis
- **WhatsApp**: wa.me registration check + spam reports (SpamCalls, WhoCalledMe, Tellows) + Business detection + social presence
- **Tracking**: HTML injection with Geo/Cam capabilities via `tracking_templates.py`. Multi-service deploy (Vercel -> Catbox -> 0x0.st).
- **EXIF**: Full metadata extraction using `Pillow`. GPS, camera settings, hash, orientation, flash mode.

## UI & UX
- **Templates**: All response formatting centralized in `ui/templates.py` with "Cybersec Dashboard" styling.
- **Menus**: Interactive InlineKeyboards defined in `ui/menus.py`.

## Commands
- `/start`: Main menu
- `/help`: Documentation

## Access Control
- Hardcoded in `config.py` → `ALLOWED_USERS` set
- 6 user slots with placeholder IDs
- Admin (first user) receives unauthorized access alerts
- All unauthorized attempts are logged and notified

## Deploy
- **Local**: `python bot.py` (Polling mode)
- **Cloud**: Auto-detects Railway/Render/Fly.io environment, uses Webhook if `WEBHOOK_URL` is set
- **Docker**: `docker build -t gekosint . && docker run -e GEKOSINT_TOKEN=xxx gekosint`
