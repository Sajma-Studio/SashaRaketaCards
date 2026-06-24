import asyncio
import time
import os
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database import Database

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8005204734:AAHab4UCbClN50vu7hLTeufLUhs7Iaa3gfs"
MY_ID = 7518373450 
ADMINS = [7507020081]   
DB_URL = os.getenv("DATABASE_URL", "ВАШ_URL")
GLOBAL_COOLDOWN = 60
BLACK_LIST = []
BOT_ACTIVE = True

bot = Bot(token=TOKEN)
dp = Dispatcher()
db = Database(DB_URL)

# --- КЛАВІАТУРИ ---
def get_main_keyboard(user_id):
    if user_id in BLACK_LIST:
        return ReplyKeyboardRemove()
    buttons = [
        [KeyboardButton(text="🃏 Картка"),     KeyboardButton(text="👤 Профіль")],
        [KeyboardButton(text="🏆 Топ"),        KeyboardButton(text="🎁 Подарунок")],
        [KeyboardButton(text="🎰 Казино")],
        [KeyboardButton(text="⚔️ Дуель"),     
        [KeyboardButton(text="❓ Допомога")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ЛОГІКА КАРТОК ---
def get_card_rarity():
    r = random.random() * 100
    if r <= 0.1:  return "🛠 УНІКАЛЬНА",  250, "🔥"
    if r <= 1.0:  return "💎 ЛЕГЕНДАРНА", 200, "👑"
    if r <= 10.0: return "🟡 ЕПІЧНА",     100, "🌟"
    if r <= 20.0: return "🟣 РІДКІСНА",    50, "✨"
    if r <= 45.0: return "🔵 НЕЗВИЧАЙНА",  30, "🔹"
    return              "⚪️ ЗВИЧАЙНА",     15, "▫️"

# --- УТИЛІТИ ---
def escape_md(text: str) -> str:
    special = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{c}" if c in special else c for c in str(text))

def today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def streak_bonus(streak: int) -> int:
    return min(streak, 10) * 10  # +10% за день, макс +100%

# ================================================================
# ХЕНДЛЕРИ
# ================================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)
    db._ensure_lottery_column()
    await message.answer(
        f"👋 Привіт, {escape_md(message.from_user.first_name)}\\!\n"
        f"Готовий збирати колекцію трофеїв?\n\n"
        f"Натисни *❓ Допомога* щоб дізнатись всі команди\\!",
        reply_markup=get_main_keyboard(uid),
        parse_mode="MarkdownV2"
    )

# --- ЗМІНА ІМЕНІ ---
@dp.message(F.text.regexp(r"(?i)^ім'я\s+(.+)$"))
async def change_name(message: types.Message):
    uid = message.from_user.id
    new_name = message.text.split(maxsplit=1)[1].strip()
    if len(new_name) > 30:
        return await message.reply("❌ Ім'я занадто довге\\! Максимум 30 символів\\.", parse_mode="MarkdownV2")
    db.set_user_name(uid, new_name)
    await message.reply(f"✅ Ім'я змінено на: *{escape_md(new_name)}*", parse_mode="MarkdownV2")

# --- ПРОФІЛЬ ---
@dp.message(F.text == "👤 Профіль")
async def show_profile(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)

    coins, msgs = db.get_user_data(uid)
    rank        = db.get_user_rank(uid)
    collected   = db.get_total_collected(uid)
    total       = db.get_total_players()
    streak, _   = db.get_streak_data(uid)
    achievements = db.get_user_achievements(uid)

    ach_list = [f"{i+1}\\. {escape_md(a)}" for i, a in enumerate(achievements)]
    ach_str  = "\n".join(ach_list) if ach_list else "Немає нагород 🎖"

    user_name = db.get_user_name(uid) or message.from_user.full_name

    caption = (
        f"👤 *Ім'я:* {escape_md(user_name)}\n"
        f"🆔 *ID:* `{uid}`\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🏆 *Трофеїв:* {escape_md(str(coins))}\n"
        f"🥇 *Місце в топі:* \\#{escape_md(str(rank))}\n"
        f"✉️ *Повідомлень:* `{msgs}`\n"
        f"🃏 *Колекція:* `{collected}/{total}`\n"
        f"🔥 *Стрік:* `{streak}` дн\\.\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🎖 *Нагороди:*\n{ach_str}"
    )
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count > 0:
            await message.answer_photo(photos.photos[0][-1].file_id, caption=caption, parse_mode="MarkdownV2")
            return
    except Exception:
        pass
    await message.answer(caption, parse_mode="MarkdownV2")

# --- КАРТКА ---
@dp.message(F.text == "🃏 Картка")
async def give_card(message: types.Message):
    if not BOT_ACTIVE:
        return
    try:
        uid = message.from_user.id
        db.update_user(uid, message.from_user.full_name)
        now = time.time()
        last_time = db.get_last_card_time(uid)
        if now - last_time < GLOBAL_COOLDOWN:
            wait = int(GLOBAL_COOLDOWN - (now - last_time))
            return await message.reply(f"⏳ Зачекай *{wait}* сек\\.", parse_mode="MarkdownV2")

        target = db.get_random_user()
        if not target:
            return await message.reply("База порожня\\!", parse_mode="MarkdownV2")

        rarity, bonus, icon = get_card_rarity()

        db.add_to_collection(uid, target[0], rarity)
        db.add_coins(uid, bonus)
        db.set_last_card_time(uid, now)

        await message.answer(
            f"🎊 *ТОБІ ВИПАЛА КАРТКА\\!*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👤 Гравець: `{escape_md(target[1])}`\n"
            f"{icon} Рідкість: *{escape_md(rarity)}*\n"
            f"🏆 Бонус: \\+{bonus} трофеїв",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        await message.reply(f"❌ Помилка: {escape_md(str(e))}", parse_mode="MarkdownV2")

# --- ЩОДЕННИЙ ПОДАРУНОК ---
@dp.message(F.text == "🎁 Подарунок")
async def daily_gift(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)
    now = time.time()
    last_gift = db.get_last_gift_time(uid)

    if now - last_gift < 86400:
        remaining = int(86400 - (now - last_gift))
        h = remaining // 3600
        m = (remaining % 3600) // 60
        return await message.reply(
            f"🎁 Наступний подарунок через *{escape_md(str(h))}г {escape_md(str(m))}хв*",
            parse_mode="MarkdownV2"
        )

    streak, last_day = db.get_streak_data(uid)
    today     = today_str()
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    if last_day == yesterday:
        streak += 1
    elif last_day != today:
        streak = 1

    db.update_streak(uid, streak, today)

    base    = random.randint(50, 500)
    pct     = streak_bonus(streak)
    bonus   = int(base * pct / 100)
    total_r = base + bonus

    db.add_coins(uid, total_r)
    db.set_last_gift_time(uid, now)

    streak_line = (
        f"🔥 Стрік: *{streak}* дн\\. \\(\\+{pct}% бонус\\)" if streak > 1
        else "🔥 Стрік: *1* день — приходь завтра за бонусом\\!"
    )
    await message.answer(
        f"🎁 *ЩОДЕННИЙ ПОДАРУНОК\\!*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"Базовий: *\\+{escape_md(str(base))}* 🏆\n"
        f"Стрік бонус: *\\+{escape_md(str(bonus))}* 🏆\n"
        f"Разом: *\\+{escape_md(str(total_r))}* 🏆\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"{streak_line}",
        parse_mode="MarkdownV2"
    )

# --- ТОП ---
@dp.message(F.text == "🏆 Топ")
async def show_top(message: types.Message):
    top_users = db.get_leaderboard()
    res = "🏆 *ТОП\\-10 ГРАВЦІВ \\(Трофеї\\):*\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, user in enumerate(top_users, 1):
        icon = medals.get(i, f"{i}\\.")
        res += f"{icon} {escape_md(user[0])} — *{escape_md(str(user[1]))}* 🏆\n"
    await message.answer(res, parse_mode="MarkdownV2")

# --- КАЗИНО (КНОПКА) ---
@dp.message(F.text == "🎰 Казино")
async def casino_menu(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)
    coins, _ = db.get_user_data(uid)
    await message.reply(
        f"🎰 *КАЗИНО*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"💰 Баланс: *{escape_md(str(coins))}* 🏆\n\n"
        f"🎲 `казино <ставка>` — 50/50, виграш \\+50% від ставки\n"
        f"🪙 `монетка` — безкоштовно кожні 5 хв, орел або решка",
        parse_mode="MarkdownV2"
    )

# --- ДУЕЛЬ (КНОПКА) ---
@dp.message(F.text == "⚔️ Дуель")
async def duel_menu(message: types.Message):
    await message.reply(
        "⚔️ *ДУЕЛЬ*\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Виклич суперника\\! Шанс виграшу — рівно *50/50*\\.\n\n"
        "📌 `дуель <айді> <ставка>` — виклик\n"
        "✅ `прийняти` — прийняти виклик\n"
        "❌ `відхилити` — відхилити",
        parse_mode="MarkdownV2"
    )

# --- ДОПОМОГА ---
@dp.message(F.text == "❓ Допомога")
async def help_all(message: types.Message):
    text = (
        "❓ *КОМАНДИ*\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "*🃏 Картки:*\n"
        "🃏 Картка — отримати картку\n"
        "🎁 Подарунок — щоденний бонус\n\n"
        "*🎮 Ігри:*\n"
        "`казино <ставка>` — 50/50\n"
        "`лотерея` — квиток з магазину\n"
        "`монетка` — кожні 5 хв безкоштовно\n"
        "`дуель <айді> <ставка>` — виклик\n"
        "`прийняти` / `відхилити`\n\n"
        "*👤 Профіль:*\n"
        "`ім'я <нікнейм>` — змінити ім'я\n"
        "`мій топ` — моє місце\n"
        "`топ <номер>` — хто на місці N\n\n"
        "*💸 Економіка:*\n"
        "`передати <айді> <к\\-сть>`\n"
        "`купити 1` — лотерейний квиток\n\n"
        "🏆 Топ"
    )
    await message.reply(text, parse_mode="MarkdownV2")

# ================================================================
# АКТИВНІ ДУЕЛІ та МОНЕТКА
# ================================================================
duels = {}
last_coin_flip: dict[int, float] = {}

# ================================================================
# УНІВЕРСАЛЬНИЙ ОБРОБНИК
# ================================================================
@dp.message()
async def universal_handler(message: types.Message):
    global BOT_ACTIVE, GLOBAL_COOLDOWN

    uid = message.from_user.id
    if uid in BLACK_LIST:
        return

    db.update_user(uid, message.from_user.full_name)
    db._ensure_lottery_column()

    if not message.text:
        db.update_message_count(uid)
        return

    original_parts = message.text.split()
    text_lower     = message.text.lower().split()
    cmd            = text_lower[0] if text_lower else ""

    # ================================================================
    # КОМАНДИ ДЛЯ ВСІХ
    # ================================================================

    # --- МОНЕТКА ---
    if cmd == "монетка":
        now = time.time()
        last = last_coin_flip.get(uid, 0)
        cooldown = 300
        if now - last < cooldown:
            wait = int(cooldown - (now - last))
            return await message.reply(
                f"🪙 Монетка відпочиває ще *{escape_md(str(wait))}* сек\\.",
                parse_mode="MarkdownV2"
            )
        last_coin_flip[uid] = now
        win = random.random() < 0.5
        if win:
            prize = random.randint(10, 50)
            db.add_coins(uid, prize)
            await message.reply(
                f"🪙 *ОРЕЛ\\!* Ти виграв *\\+{prize}* 🏆",
                parse_mode="MarkdownV2"
            )
        else:
            await message.reply(
                "🪙 *РЕШКА\\!* Нічого не виграв, але й не програв\\. Удачі наступного разу\\!",
                parse_mode="MarkdownV2"
            )
        return

    # --- КАЗИНО ---
    if cmd == "казино" and len(text_lower) > 1:
        try:
            bet = int(text_lower[1])
            if bet <= 0:
                return await message.reply("❌ Ставка має бути більше 0\\.", parse_mode="MarkdownV2")
            coins, _ = db.get_user_data(uid)
            if coins < bet:
                return await message.reply(
                    f"❌ Недостатньо трофеїв\\. У тебе *{escape_md(str(coins))}* 🏆",
                    parse_mode="MarkdownV2"
                )
            win = random.random() < 0.5
            if win:
                prize = bet // 2
                db.add_coins(uid, prize)
                await message.reply(
                    f"🎰 *ВИГРАШ\\!*\n"
                    f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                    f"Ставка: *{escape_md(str(bet))}* 🏆\n"
                    f"Прибуток: *\\+{escape_md(str(prize))}* 🏆\n"
                    f"🍀 Удача на твоєму боці\\!",
                    parse_mode="MarkdownV2"
                )
            else:
                db.add_coins(uid, -bet)
                await message.reply(
                    f"🎰 *ПРОГРАШ\\!*\n"
                    f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                    f"Ставка: *{escape_md(str(bet))}* 🏆\n"
                    f"Збиток: *\\-{escape_md(str(bet))}* 🏆\n"
                    f"😔 Спробуй ще раз\\!",
                    parse_mode="MarkdownV2"
                )
        except (ValueError, IndexError):
            await message.reply("❌ Використання: `казино <ставка>`", parse_mode="MarkdownV2")
        return

    # --- ПЕРЕДАТИ ---
    if cmd == "передати" and len(text_lower) > 2:
        try:
            target_id = int(text_lower[1])
            amount    = int(text_lower[2])
            if amount <= 0:
                return await message.reply("❌ Сума має бути більше нуля\\.", parse_mode="MarkdownV2")
            if target_id == uid:
                return await message.reply("❌ Не можна передавати собі\\.", parse_mode="MarkdownV2")
            coins, _ = db.get_user_data(uid)
            if coins < amount:
                return await message.reply(
                    f"❌ Недостатньо трофеїв\\. У тебе *{escape_md(str(coins))}* 🏆",
                    parse_mode="MarkdownV2"
                )
            target_name = db.get_user_name(target_id)
            if not target_name:
                return await message.reply("❌ Гравця не знайдено\\.", parse_mode="MarkdownV2")
            db.add_coins(uid, -amount)
            db.add_coins(target_id, amount)
            sender_name = db.get_user_name(uid) or message.from_user.full_name
            await message.reply(
                f"✅ Передано *{escape_md(str(amount))}* 🏆 → *{escape_md(target_name)}*",
                parse_mode="MarkdownV2"
            )
            try:
                await bot.send_message(
                    target_id,
                    f"🎁 *{escape_md(sender_name)}* передав тобі *{escape_md(str(amount))}* 🏆",
                    parse_mode="MarkdownV2"
                )
            except Exception:
                pass
        except (ValueError, IndexError):
            await message.reply("❌ Використання: `передати <айді> <кількість>`", parse_mode="MarkdownV2")
        return

    # --- ТОП МІСЦЕ ---
    if cmd == "топ" and len(text_lower) > 1:
        try:
            place = int(text_lower[1])
            if place < 1:
                return await message.reply("❌ Місце має бути більше 0\\.", parse_mode="MarkdownV2")
            result = db.get_user_at_rank(place)
            if not result:
                return await message.reply(
                    f"❌ На місці *{escape_md(str(place))}* нікого немає\\.",
                    parse_mode="MarkdownV2"
                )
            name, coins_val = result
            await message.reply(
                f"🥇 *Місце \\#{escape_md(str(place))}*\n"
                f"👤 {escape_md(name)}\n"
                f"🏆 {escape_md(str(coins_val))} трофеїв",
                parse_mode="MarkdownV2"
            )
        except (ValueError, IndexError):
            await message.reply("❌ Використання: `топ <номер>`", parse_mode="MarkdownV2")
        return

    # --- МІЙ ТОП ---
    if cmd == "мій" and len(text_lower) > 1 and text_lower[1] == "топ":
        rank  = db.get_user_rank(uid)
        total = db.get_total_players()
        coins, _ = db.get_user_data(uid)
        name  = db.get_user_name(uid) or message.from_user.full_name
        await message.reply(
            f"📍 *{escape_md(name)}*\n"
            f"Місце: *\\#{escape_md(str(rank))}* з {escape_md(str(total))}\n"
            f"🏆 {escape_md(str(coins))} трофеїв",
            parse_mode="MarkdownV2"
        )
        return

    # --- ДУЕЛЬ: ВИКЛИК ---
    if cmd == "дуель" and len(text_lower) > 2:
        try:
            target_id = int(text_lower[1])
            bet       = int(text_lower[2])
            if target_id == uid:
                return await message.reply("❌ Не можна викликати себе\\.", parse_mode="MarkdownV2")
            if bet <= 0:
                return await message.reply("❌ Ставка має бути більше 0\\.", parse_mode="MarkdownV2")
            coins, _ = db.get_user_data(uid)
            if coins < bet:
                return await message.reply(
                    f"❌ Недостатньо трофеїв\\. У тебе *{escape_md(str(coins))}* 🏆",
                    parse_mode="MarkdownV2"
                )
            target_name = db.get_user_name(target_id)
            if not target_name:
                return await message.reply("❌ Гравця не знайдено\\.", parse_mode="MarkdownV2")
            target_coins, _ = db.get_user_data(target_id)
            if target_coins < bet:
                return await message.reply(
                    "❌ У суперника недостатньо трофеїв для цієї ставки\\.",
                    parse_mode="MarkdownV2"
                )
            my_name = db.get_user_name(uid) or message.from_user.full_name
            duels[target_id] = {
                "challenger_id":   uid,
                "challenger_name": my_name,
                "bet":             bet,
                "time":            time.time()
            }
            await message.reply(
                f"⚔️ Виклик надіслано *{escape_md(target_name)}* на *{escape_md(str(bet))}* 🏆",
                parse_mode="MarkdownV2"
            )
            try:
                await bot.send_message(
                    target_id,
                    f"⚔️ *{escape_md(my_name)}* викликає тебе на дуель\\!\n"
                    f"🏆 Ставка: *{escape_md(str(bet))}* трофеїв\n\n"
                    f"Відповідай: `прийняти` або `відхилити`",
                    parse_mode="MarkdownV2"
                )
            except Exception:
                pass
        except (ValueError, IndexError):
            await message.reply("❌ Використання: `дуель <айді> <ставка>`", parse_mode="MarkdownV2")
        return

    # --- ДУЕЛЬ: ПРИЙНЯТИ ---
    if cmd == "прийняти":
        duel = duels.get(uid)
        if not duel:
            return await message.reply("❌ У тебе немає активних викликів\\.", parse_mode="MarkdownV2")
        if time.time() - duel["time"] > 120:
            del duels[uid]
            return await message.reply("❌ Час виклику вийшов\\.", parse_mode="MarkdownV2")

        challenger_id = duel["challenger_id"]
        bet = duel["bet"]
        del duels[uid]

        c_coins, _ = db.get_user_data(challenger_id)
        t_coins, _ = db.get_user_data(uid)
        if c_coins < bet or t_coins < bet:
            return await message.reply("❌ У когось не вистачає трофеїв\\.", parse_mode="MarkdownV2")

        winner_id = random.choice([challenger_id, uid])
        loser_id  = uid if winner_id == challenger_id else challenger_id
        winner_name = db.get_user_name(winner_id) or "?"
        loser_name  = db.get_user_name(loser_id)  or "?"

        db.add_coins(winner_id,  bet)
        db.add_coins(loser_id,  -bet)

        result_text = (
            f"⚔️ *РЕЗУЛЬТАТ ДУЕЛІ\\!*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🏆 Ставка: *{escape_md(str(bet))}* трофеїв\n\n"
            f"🥇 Переможець: *{escape_md(winner_name)}*\n"
            f"💀 Переможений: *{escape_md(loser_name)}*\n\n"
            f"*\\+{escape_md(str(bet))}* 🏆 → {escape_md(winner_name)}"
        )
        await message.answer(result_text, parse_mode="MarkdownV2")
        try:
            await bot.send_message(challenger_id, result_text, parse_mode="MarkdownV2")
        except Exception:
            pass
        return

    # --- ДУЕЛЬ: ВІДХИЛИТИ ---
    if cmd == "відхилити":
        duel = duels.get(uid)
        if not duel:
            return await message.reply("❌ У тебе немає активних викликів\\.", parse_mode="MarkdownV2")
        challenger_id = duel["challenger_id"]
        del duels[uid]
        my_name = db.get_user_name(uid) or message.from_user.full_name
        await message.reply("✅ Ти відхилив виклик\\.", parse_mode="MarkdownV2")
        try:
            await bot.send_message(
                challenger_id,
                f"😔 *{escape_md(my_name)}* відхилив твій виклик\\.",
                parse_mode="MarkdownV2"
            )
        except Exception:
            pass
        return

    # --- Лічильник повідомлень ---
    db.update_message_count(uid)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
