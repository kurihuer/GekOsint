from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("\U0001f50d IP Lookup", callback_data='menu_ip'),
            InlineKeyboardButton("\U0001f4f1 Phone Intel", callback_data='menu_phone')
        ],
        [
            InlineKeyboardButton("\U0001f464 Username Search", callback_data='menu_user'),
            InlineKeyboardButton("\U0001f4e7 Email Analysis", callback_data='menu_email')
        ],
        [
            InlineKeyboardButton("\U0001f30d Geo Tracker", callback_data='menu_geo'),
            InlineKeyboardButton("\U0001f4f8 Camera Trap", callback_data='menu_cam')
        ],
        [
            InlineKeyboardButton("\U0001f49a WhatsApp OSINT", callback_data='menu_wa'),
            InlineKeyboardButton("\U0001f5bc\ufe0f EXIF Data", callback_data='menu_exif')
        ],
        [
            InlineKeyboardButton("\U0001f310 Domain/DNS", callback_data='menu_dns'),
            InlineKeyboardButton("\U0001f9d1\u200d\U0001f4bc People Search", callback_data='menu_people')
        ],
        [
            InlineKeyboardButton("\U0001f4f7 IG OSINT", callback_data='menu_ig'),
            InlineKeyboardButton("\U0001f4bb GitHub Recon", callback_data='menu_github')
        ],
        [
            InlineKeyboardButton("\U0001f4e7 Gmail OSINT", callback_data='menu_gmail'),
            InlineKeyboardButton("\U0001f4d8 FB OSINT", callback_data='menu_fb')
        ],
        [
            InlineKeyboardButton("\U0001f4f9 TikTok OSINT", callback_data='menu_tiktok'),
            InlineKeyboardButton("\U0001f4e8 Email Recon",  callback_data='menu_emailrecon')
        ],
        [
            InlineKeyboardButton("\U0001f50d\U0001f4d0 Universal Recon", callback_data='menu_universal'),
        ],
        [
            InlineKeyboardButton("\u2139\ufe0f Acerca de", callback_data='menu_about')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_btn(show_export=False, show_pdf=False):
    btns = []
    if show_export:
        btns.append([InlineKeyboardButton("\U0001f4c4 Exportar Reporte (.txt)", callback_data='export_txt')])
    if show_pdf:
        btns.append([InlineKeyboardButton("\U0001f4c3 Exportar Reporte (.pdf)", callback_data='export_pdf')])
    btns.append([InlineKeyboardButton("\u2b05\ufe0f Volver al Menu Principal", callback_data='start')])
    return InlineKeyboardMarkup(btns)
