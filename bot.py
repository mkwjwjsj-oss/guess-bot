import os
import random
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

MIN_NUM = 1
MAX_NUM = 50
MAX_ATTEMPTS = 6

web_app = Flask(__name__)


@web_app.route("/")
def index():
    return "OK", 200


def start_web() -> None:
    port = int(os.environ.get("PORT", "10000"))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


@dataclass
class GameSession:
    secret: int
    attempts: Dict[int, int] = field(default_factory=dict)
    active: bool = True


games: Dict[int, GameSession] = {}


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "أهلاً بك في لعبة تخمين الأرقام (1 - 50).\n"
        "/game - بدء جولة جديدة\n"
        "/guess <رقم> - تخمين رقم (مثال: /guess 25)\n"
        f"لكل لاعب {MAX_ATTEMPTS} محاولات."
    )


async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    games[chat_id] = GameSession(secret=random.randint(MIN_NUM, MAX_NUM), active=True)
    await update.message.reply_text(
        f"بدأت جولة جديدة! الرقم بين {MIN_NUM} و {MAX_NUM}. لكل لاعب {MAX_ATTEMPTS} محاولات. أرسل /guess 25"
    )


async def guess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    name = update.effective_user.first_name or "لاعب"

    session: Optional[GameSession] = games.get(chat_id)
    if not session or not session.active:
        await update.message.reply_text("لا توجد جولة نشطة. أرسل /game لبدء لعبة جديدة.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("استخدم الأمر هكذا: /guess 25")
        return

    try:
        val = int(context.args[0])
    except ValueError:
        await update.message.reply_text("أدخل رقماً صحيحاً فقط، مثل: /guess 15")
        return

    if val < MIN_NUM or val > MAX_NUM:
        await update.message.reply_text(f"الرقم يجب أن يكون بين {MIN_NUM} و {MAX_NUM}.")
        return

    used = session.attempts.get(user_id, 0)
    if used >= MAX_ATTEMPTS:
        await update.message.reply_text(f"{name}، لقد أنهيت محاولاتك ({MAX_ATTEMPTS}) في هذه الجولة.")
        return

    used += 1
    session.attempts[user_id] = used
    left = MAX_ATTEMPTS - used

    if val == session.secret:
        session.active = False
        await update.message.reply_text(
            f"مبروك {name}! الرقم الصحيح هو {session.secret} وقد خمنته في المحاولة {used}. أرسل /game لجولة جديدة."
        )
        return

    hint = "أكبر" if val < session.secret else "أصغر"
    all_done = len(session.attempts) > 0 and all(a >= MAX_ATTEMPTS for a in session.attempts.values())
    if all_done:
        session.active = False
        await update.message.reply_text(
            f"انتهت محاولات جميع اللاعبين! الرقم الصحيح كان {session.secret}. أرسل /game لبدء جولة جديدة."
        )
        return

    await update.message.reply_text(f"{name}: الرقم السري {hint} من {val}. المحاولات المتبقية لك: {left}")


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN غير موجود")

    threading.Thread(target=start_web, daemon=True).start()

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("game", game_cmd))
    app.add_handler(CommandHandler("guess", guess_cmd))

    print("RUNNING", flush=True)
    app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)


if __name__ == "__main__":
    main()
