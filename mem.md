
# GekOsint Project Memory

## Architecture
- **Framework**: `python-telegram-bot` v20+ (Async)
- **Structure**: Modular
  - `modules/`: Core OSINT logic (IP, Phone, Username, etc)
  - `ui/`: Visual components (templates, keyboards)
  - `handlers/`: Telegram interactions
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
- **Username**: Direct HTTP checks to profile URLs
- **EXIF**: `Pillow` library

## Commands
- `/start`: Main menu
- `/help`: Documentation
