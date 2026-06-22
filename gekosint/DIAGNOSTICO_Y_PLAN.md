# 🛡️ GekOsint — Diagnóstico técnico y plan de mejora

**Fecha:** 2026-06-22 · **Versión auditada:** v6.1 (repo `kurihuer/GekOsint`)
**Entorno objetivo:** Koyeb (cloud) · deploy vía GitHub
**Auditor:** revisión estática de código (sin ejecución en esta sesión)

---

## 1. Resumen ejecutivo

El código **no está mal hecho**. Es modular, asíncrono donde toca, con rate-limit,
control de acceso y manejo de errores razonable. El problema de que "casi todos los
módulos devuelven vacío o poco" **no es un bug de programación generalizado**: es una
combinación de tres causas, y la principal es del *entorno*, no del código.

### Causa raíz #1 — Koyeb usa una IP de datacenter (la más importante)
Muchos módulos hacen *scraping* de sitios que **bloquean IPs de datacenter**:
Truecaller, Facebook, Google/Gmail, Instagram, SpamCalls, Tellows, etc.
Desde tu PC (IP residencial) responden; desde Koyeb devuelven 403 / captcha / HTML
distinto → el regex no encuentra nada → **el módulo "devuelve vacío" sin avisar**.
**Esto no se arregla solo con mejor código: se arregla con un PROXY residencial.**

### Causa raíz #2 — Scrapers frágiles (HTML que cambió)
Módulos que extraen datos con expresiones regulares sobre el HTML de un sitio
(`spamcalls.net`, `tellows.com`, `numbway.com`, `truecaller.com`...). Cuando el sitio
cambia su maquetado, el regex deja de coincidir. Hay que migrarlos a fuentes más
estables (APIs, JSON-LD, endpoints internos) y hacer que **fallen "ruidosamente"**
(que digan *"bloqueado / sin datos"* en vez de quedar vacíos en silencio).

### Causa raíz #3 — API keys / cookies faltantes
Caller-ID real necesita `RAPIDAPI_KEY`; IP enriquecida necesita Shodan/AbuseIPDB/VT;
IG/FB/Gmail necesitan **cookies de sesión** + proxy para los *recovery hints*.
Sin ellas el módulo corre pero entrega lo mínimo.

> **Conclusión honesta:** los módulos basados en **API/librería** se pueden dejar
> finos y fiables al 100% desde Koyeb. Los basados en **scraping de Meta/Google/
> Truecaller** *no se pueden garantizar al 100%* en cloud sin proxy residencial +
> cookies, porque depende de infraestructura ajena anti-bot. Lo que sí puedo hacer es
> robustecerlos, darles fallback y soporte de proxy para que rindan lo máximo posible.

---

## 2. Estado por módulo

Leyenda fiabilidad en Koyeb: 🟢 fiable · 🟡 parcial / mejorable · 🔴 bloqueado sin proxy+cookies

| Módulo | Tipo | Koyeb | Diagnóstico | Acción |
|---|---|:---:|---|---|
| **IP Lookup** | API | 🟢 | Sólido. `ip-api.com` + Shodan/AbuseIPDB/VT/GreyNoise. El escaneo de puertos por socket (`_get_open_ports`) es **lento y poco fiable desde cloud** (firewalls). | Quitar socket-scan o moverlo a Shodan; cachear; añadir IPinfo/IP2Location como fallback. |
| **Phone Intel** | Mixto | 🟡 | `phonenumbers` (offline) va perfecto. Pero caller-ID/spam dependen de **scraping** (Truecaller-web, SpamCalls, Tellows) → vacío en Koyeb. | Centralizar HTTP con proxy+reintentos; marcar claramente fuente; no inventar score. |
| **Username Search** | HTTP | 🟡 | **Falsos positivos/negativos.** El método "200 = existe" falla: IG/FB/TikTok/LinkedIn devuelven 200 con muro de login → marca "existe" siempre. | Reescribir con reglas por sitio (status + huella de "no existe"), validación más estricta. Gran mejora posible. |
| **Email Analysis** | API | 🟢 | Bueno. `emailrep.io` hoy está casi muerto/limitado (429). XposedOrNot y DNS van bien. | Quitar dependencia de emailrep, añadir más fuentes de brechas (LeakCheck público, HIBP si hay key). |
| **WhatsApp OSINT** | Scraping | 🔴 | `wa.me` da poco; el resto (SpamCalls, Tellows, Numbway, WhoCalledMe) **bloqueado en cloud**. Foto de perfil casi nunca sale. | Soporte proxy; ser honesto sobre lo que `wa.me` realmente expone (poco). |
| **EXIF + Face** | Librería | 🟢 | Pillow es local y fiable. La "detección de rostro heurística" es muy básica. | Robustecer parsing GPS/metadatos; mejorar o etiquetar la heurística como aproximada. |
| **Geo Localización** | API | 🟢 | OK (módulo ya recortado). | Añadir parseo de coords/URL Maps y reverse-geocoding. |
| **Domain / DNS** | API | 🟢 | Muy bien (Google DoH + RDAP). `whois.registrar` toma `port43` (no es el registrar real). | Corregir extracción de registrar/fechas desde entities RDAP; añadir DNSSEC real. |
| **People Search** | Dorks | 🟢 | Generador de dorks: funciona en cloud (no depende de scraping). | Ampliar dorks, añadir más bases OSINT, limpiar salida. |
| **GitHub Recon** | API | 🟢 | API de GitHub (async): excelente desde cloud, sobre todo con `GITHUB_TOKEN`. | Pulir; manejar rate-limit 403 con backoff. |
| **IG OSINT** | Scraping+cookies | 🔴 | Necesita `IG_SESSIONID` + proxy. Sin eso IG bloquea desde Koyeb. | Robustecer; fallback a datos públicos; mensaje claro si falta cookie/proxy. |
| **Gmail OSINT** | Scraping+cookies | 🔴 | Recovery hints bloqueados desde IP cloud (Google). Necesita cookies Google + proxy. | Igual: proxy obligatorio; degradar a Gravatar/links si no hay. |
| **FB OSINT** | Scraping+cookies | 🔴 | Meta muy agresivo. Sin proxy residencial + cookies FB → 0 datos. | Proxy + cookies; el `/admin proxy` ya ayuda a diagnosticar. |
| **TikTok OSINT** | Scraping | 🟡 | El endpoint público a veces responde desde cloud, a veces no. | Migrar a endpoint JSON más estable + proxy opcional. |
| **Email Recon** | HTTP multi | 🟡 | Chequeo de existencia en ~12 servicios: parte funciona desde cloud, parte bloquea. | Endurecer; timeouts por servicio; reporte claro de "bloqueado vs no-registrado". |
| **Geo Tracker / Camera Trap** | — | ✅ | **Funcionan. NO se tocan** (por tu indicación). | — |

---

## 3. Mejoras transversales ("máxima expresión")

Estas aplican a todos los módulos y son las que más suben la calidad:

1. **Capa HTTP única con proxy + reintentos + rotación de User-Agent.**
   Hoy cada módulo crea sus `requests.get` sueltos. Centralizar en `utils/http.py`:
   timeout estándar, reintentos con backoff, soporte automático de `PROXY_URL`,
   pool de User-Agents y headers realistas. Un solo cambio mejora *todos* los scrapers.

2. **Fallo ruidoso, no silencioso.** Cuando un sitio bloquea (403/429/captcha), el
   módulo debe devolver `status: "bloqueado"` y mostrarlo en Telegram, en vez de
   quedar vacío y parecer que "no encontró nada".

3. **Username Search de nivel pro.** Reglas de detección por sitio (como Sherlock/
   Maigret): combinación de status code + texto-huella de "no existe" + URL final.
   Esto elimina los falsos positivos actuales.

4. **Menos dependencia de sitios muertos.** Sustituir `emailrep.io`, regex frágiles
   de Tellows/SpamCalls por fuentes con JSON estable o APIs.

5. **Indicador de "qué falta".** Cada módulo ya devuelve `missing_keys`; mostrarlo
   siempre y, además, indicar si necesitaría **proxy** o **cookies** para rendir.

6. **Caché y rate-limit por fuente** para no quemar APIs ni que te bloqueen.

---

## 4. Lo que TÚ necesitas configurar en Koyeb para el 100%

| Para que rinda… | Necesitas en variables de entorno |
|---|---|
| Phone caller-ID real | `RAPIDAPI_KEY` (Truecaller) |
| IP enriquecida | `SHODAN_API_KEY`, `ABUSEIPDB_KEY`, `VT_API_KEY`, `GREYNOISE_API_KEY` |
| Email brechas Pro | `HUNTER_KEY` (+ opcional HIBP) |
| **FB / Gmail / IG (recovery hints)** | **`PROXY_URL` residencial** + cookies de sesión (`IG_SESSIONID`, `FB_C_USER`+`FB_XS`, `GOOGLE_*`) |
| Tracker hosting | `GITHUB_TOKEN` (gist) o `VERCEL_TOKEN` |

> El **proxy residencial** (Webshare, IPRoyal, etc.) es el desbloqueo #1 para FB/Gmail/
> IG/Truecaller en Koyeb. Sin él, esos 4-5 módulos seguirán limitados por más que se
> mejore el código.

---

## 5. Plan de implementación propuesto

**Fase 1 — Base (sube la calidad de todo):**
`utils/http.py` (proxy+reintentos+UA), fallo ruidoso, manejo de errores unificado.

**Fase 2 — Módulos 🟢/🟡 fiables en cloud (ganancia segura sin proxy):**
Username Search (anti-falsos-positivos), Email Analysis, DNS, People Search,
GitHub Recon, IP Lookup, Geo, EXIF.

**Fase 3 — Módulos 🔴 dependientes de proxy/cookies:**
Phone (scrapers), WhatsApp, FB, Gmail, IG, TikTok, Email Recon — robustecer +
soporte proxy + degradación clara.

**Fase 4 — Verificación:** prueba de arranque, revisión de imports, y guía de deploy.

---

## ⚠️ Nota importante sobre esta sesión
El entorno Linux para ejecutar/compilar el bot **no arrancó en esta sesión**, así que
las correcciones de código se entregan revisadas estáticamente. Como despliegas a
Koyeb, **revisa el build log del primer push** (o pruébalo local con `python bot.py`)
antes de confiar el 100%, y mantén el commit anterior para revertir si hiciera falta.
