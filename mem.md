
# GekOsint Project Memory

## Architecture
- **Framework**: `python-telegram-bot` v20+ (Async)
- **Structure**: Modular
  - `modules/`: Core OSINT logic (IP, Phone, Username, Tracking)
  - `ui/`: Visual components (menus, message templates)
  - `handlers/`: Telegram interactions (commands, callbacks)
  - `utils/`: Helpers (APIs, deployment)
- **Deployment**: Dockerized (Alpine based)

## Key Conventions
- **UI Style**: "Cybersec Dashboard" (Bold headers, emojis, clean lines)
- **Concurrency**: `concurrent.futures` for multi-site lookups (Username search)
- **Tracking**: HTML pages generated in `pages/`, deployed via free APIs (Netlify/File.io)
- **Env Vars**: managed via `config.py` and `.env`

## Modules
- **IP**: IP-API + simulated risk analysis
- **Phone**: `phonenumbers` lib + regional custom parsing
- **Username**: Direct HTTP checks to profile URLs (Threaded)
- **Tracking**: HTML injection with Geo/Cam capabilities via `tracking_templates.py`. Deployments via Netlify API or File.io fallback.
- **EXIF**: Metadata extraction using `Pillow` library.

## UI & UX
- **Templates**: All response formatting is centralized in `ui/templates.py` to maintain consistent "Cybersec Dashboard" styling.
- **Menus**: Interactive InlineKeyboards defined in `ui/menus.py`.

## Commands
- `/start`: Main menu
- `/help`: Documentation
