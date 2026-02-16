
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("📡 IP Lookup", callback_data='menu_ip'),
            InlineKeyboardButton("📱 Phone Intel", callback_data='menu_phone')
        ],
        [
            InlineKeyboardButton("👤 User Search", callback_data='menu_user'),
            InlineKeyboardButton("📧 Email Check", callback_data='menu_email')
        ],
        [
            InlineKeyboardButton("📍 Geo Tracker", callback_data='menu_geo'),
            InlineKeyboardButton("📸 Cam Trap", callback_data='menu_cam')
        ],
        [
            InlineKeyboardButton("📂 EXIF Data", callback_data='menu_exif'),
            InlineKeyboardButton("ℹ️ About", callback_data='menu_about')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver al Panel", callback_data='start')]])
