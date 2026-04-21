
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🔍 IP Lookup", callback_data='menu_ip'),
            InlineKeyboardButton("📱 Phone Intel", callback_data='menu_phone')
        ],
        [
            InlineKeyboardButton("👤 Username Search", callback_data='menu_user'),
            InlineKeyboardButton("📧 Email Analysis", callback_data='menu_email')
        ],
        [
            InlineKeyboardButton("🌍 Geo Tracker", callback_data='menu_geo'),
            InlineKeyboardButton("📸 Camera Trap", callback_data='menu_cam')
        ],
        [
            InlineKeyboardButton("💚 WhatsApp OSINT", callback_data='menu_wa'),
            InlineKeyboardButton("🖼️ EXIF Data", callback_data='menu_exif')
        ],
        [
            InlineKeyboardButton("🌐 Domain/DNS", callback_data='menu_dns'),
            InlineKeyboardButton("🧑‍💼 People Search", callback_data='menu_people')
        ],
        [
            InlineKeyboardButton("🛰️ Geo Localización", callback_data='menu_geoloc'),
            InlineKeyboardButton("📶 WiFi Scanner", callback_data='menu_wifi')
        ],
        [
            InlineKeyboardButton("ℹ️ Acerca de", callback_data='menu_about')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_btn(show_export=False):
    btns = []
    if show_export:
        btns.append([InlineKeyboardButton("📄 Exportar Reporte (.txt)", callback_data='export_txt')])
    btns.append([InlineKeyboardButton("⬅️ Volver al Menú Principal", callback_data='start')])
    return InlineKeyboardMarkup(btns)
