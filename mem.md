
# GekOsint Project Memory

## Architecture
- **Framework**: `python-telegram-bot` v20+ (Async)
- **Structure**: Modular
  - `modules/`: Core OSINT logic (IP, Phone, Username, Email, Tracking)
  - `ui/`: Visual components (menus, message templates)
  - `handlers/`: Telegram interactions (commands, callbacks)
  - `utils/`: Helpers (APIs, deployment)
- **Deployment**: Dockerized (Alpine based)

## Key Conventions
- **Python Compatibility**: Soporte para Python 3.14+ usando `asyncio.run()` y contextos asíncronos explícitos para evitar errores de `RuntimeError: There is no current event loop`.
- **UI Style**: "Cybersec Dashboard" (Bold headers, emojis, clean lines)
- **Concurrency**: `concurrent.futures` for multi-site lookups (Username search)
- **Async I/O**: `httpx` is used for external API calls (Tracking deployment) and `requests` for some synchronous utilities. Ensure `httpx` is in `requirements.txt`.
- **Bot Loop**: Uses `asyncio.run(run_bot())` with manual lifecycle management (`app.initialize()`, `app.start()`, `app.updater.start_polling()`) to ensure Windows compatibility and prevent "No current event loop" errors.
- **Tracking**: HTML pages generated in `pages/`, deployed via free APIs (Catbox [Primary], 0x0.st, File.io). Multiple fallbacks ensure reliability.
- **String Formatting**: When using `.format()` on strings containing JavaScript or CSS, always double the curly braces `{{ }}` to avoid `KeyError`.
- **File Downloads**: In `python-telegram-bot` v20+, use `download_to_memory(BytesIO())` instead of `download_as_bytearray()`.
- **String Formatting**: When using `.format()` on strings containing JavaScript or CSS, always double the curly braces `{{ }}` to avoid `KeyError`.
- **Env Vars**: managed via `config.py` and `.env`

## Modules
- **IP**: IP-API + simulated risk analysis
- **Phone**: `phonenumbers` lib + regional custom parsing
- **Username**: Direct HTTP checks to profile URLs (Threaded)
- **Email**: Domain analysis, reputation check, and deep search links.
- **Tracking**: HTML injection with Geo/Cam capabilities via `tracking_templates.py`. Async redundant deployment (File.io [Primary] -> Netlify [Fallback]).
- **EXIF**: Metadata extraction using `Pillow` library. Formatted in `ui/templates.py`.

## UI & UX
- **Templates**: All response formatting is centralized in `ui/templates.py` to maintain consistent "Cybersec Dashboard" styling.
- **Menus**: Interactive InlineKeyboards defined in `ui/menus.py`.

## Commands
- `/start`: Main menu
- `/help`: Documentation
