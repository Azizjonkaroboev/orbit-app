import os
import asyncio
import asyncpg
from datetime import datetime, date
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "8475373683:AAEQCCSnI3jTWvsIzd8qJkg39BSUTcuquuI"
OWNER_ID = 6226218393
WALLET = "UQAG8cx9dXAWIfcoNUkdyki-Un9QzJxw3_xU8624H6OnZFMb"
WEBAPP_URL = "https://azizjonkaroboev.github.io/orbit-app/"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = None
pvp_room = {"players": {}, "running": False}

async def init_db():
    global db
    db = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            ton FLOAT DEFAULT 0,
            bit INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_checkin DATE,
            ref_id BIGINT DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            ref_earned FLOAT DEFAULT 0,
            total_ton FLOAT DEFAULT 0,
            total_bit INTEGER DEFAULT 0,
            wallet TEXT DEFAULT ''
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount FLOAT,
            wallet TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            status TEXT DEFAULT 'pending'
        )
    """)

async def get_user(user_id):
    return await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def create_user(user_id, username, ref_id=0):
    existing = await get_user(user_id)
    if not existing:
        await db.execute(
            "INSERT INTO users (user_id, username, ref_id) VALUES ($1, $2, $3)",
            user_id, username or "", ref_id
        )
        if ref_id and ref_id != user_id:
            ref = await get_user(ref_id)
            if ref:
                await db.execute(
                    "UPDATE users SET ref_count=ref_count+1 WHERE user_id=$1",
                    ref_id
                )
                try:
                    await bot.send_message(ref_id, "🎉 По твоей ссылке зашёл новый пользователь!")
                except:
                    pass
@dp.message(CommandStart())
async def start(msg: types.Message):
    args = msg.text.split()
    ref_id = 0
    if len(args) > 1:
        try:
            ref_id = int(args[1])
        except:
            pass
    await create_user(msg.from_user.id, msg.from_user.username, ref_id)
    user = await get_user(msg.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть Orbit", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="✅ Чек-ин", callback_data="checkin")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals"),
         InlineKeyboardButton(text="📤 Вывод", callback_data="withdraw")],
    ])
    await msg.answer(
        f"👋 Привет, {msg.from_user.first_name}!\n\n"
        f"🌍 Добро пожаловать в <b>Orbit</b>\n\n"
        f"💎 TON: <b>{user['ton']:.3f}</b>\n"
        f"🪙 BIT: <b>{user['bit']}</b>",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(F.data == "balance")
async def balance(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)
    await call.message.answer(
        f"💼 <b>Баланс:</b>\n\n"
        f"💎 TON: <b>{user['ton']:.3f}</b>\n"
        f"🪙 BIT: <b>{user['bit']}</b>\n"
        f"🔥 День: <b>{user['streak']}</b>\n"
        f"👥 Рефералов: <b>{user['ref_count']}</b>\n"
        f"💰 С рефералов: <b>{user['ref_earned']:.3f} TON</b>",
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "checkin")
async def checkin(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)
    today = date.today()
    last = user['last_checkin']
    if last == today:
        await call.answer("Уже забрал сегодня!", show_alert=True)
        return
    if last and (today - last).days == 1:
        new_streak = user['streak'] + 1
    else:
        new_streak = 1
    multi = min(1.0 + (new_streak - 1) * 0.1, 1.5)
    reward = int(30 * multi)
    await db.execute(
        "UPDATE users SET bit=bit+$1, streak=$2, last_checkin=$3, total_bit=total_bit+$1 WHERE user_id=$4",
        reward, new_streak, today, call.from_user.id
    )
    await call.message.answer(
        f"✅ <b>День {new_streak}!</b>\n\n"
        f"🪙 +{reward} BIT (×{multi:.1f})\n"
        f"🔥 Серия: {new_streak} дней",
        parse_mode="HTML"
    )
    await call.answer()
@dp.callback_query(F.data == "referrals")
async def referrals(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)
    link = f"https://t.me/Orbit_tonbot?start={call.from_user.id}"
    await call.message.answer(
        f"👥 <b>Рефералы</b>\n\n"
        f"Приглашено: <b>{user['ref_count']}</b>\n"
        f"Заработано: <b>{user['ref_earned']:.3f} TON</b>\n\n"
        f"Ссылка:\n<code>{link}</code>",
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)
    if user['ton'] < 0.5:
        await call.answer("Минимум 0.5 TON!", show_alert=True)
        return
    if not user['wallet']:
        await call.answer("Сначала подключи кошелёк в Mini App!", show_alert=True)
        return
    await call.message.answer(
        f"📤 <b>Вывод TON</b>\n\n"
        f"Баланс: <b>{user['ton']:.3f} TON</b>\n"
        f"Кошелёк: <code>{user['wallet']}</code>\n\n"
        f"Напиши сумму: /wd [сумма]\nПример: /wd 0.5",
        parse_mode="HTML"
    )
    await call.answer()

@dp.message(Command("wd"))
async def wd(msg: types.Message):
    user = await get_user(msg.from_user.id)
    if not user:
        return
    try:
        amount = float(msg.text.split()[1])
    except:
        await msg.answer("Формат: /wd 0.5")
        return
    if amount < 0.5:
        await msg.answer("Минимум 0.5 TON!")
        return
    if amount > user['ton']:
        await msg.answer("Недостаточно TON!")
        return
    await db.execute("UPDATE users SET ton=ton-$1 WHERE user_id=$2", amount, msg.from_user.id)
    await db.execute(
        "INSERT INTO withdrawals (user_id, amount, wallet) VALUES ($1, $2, $3)",
        msg.from_user.id, amount, user['wallet']
    )
    await msg.answer(f"✅ Заявка на вывод {amount:.3f} TON принята! До 24 часов.")
    await bot.send_message(
        OWNER_ID,
        f"📤 Заявка на вывод!\n"
        f"User: @{user['username']} ({msg.from_user.id})\n"
        f"Сумма: {amount:.3f} TON\n"
        f"Кошелёк: {user['wallet']}"
    )

@dp.message(Command("addton"))
async def addton(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return
    try:
        parts = msg.text.split()
        uid = int(parts[1])
        amount = float(parts[2])
        await db.execute(
            "UPDATE users SET ton=ton+$1, total_ton=total_ton+$1 WHERE user_id=$2",
            amount, uid
        )
        user = await get_user(uid)
        if user and user['ref_id']:
            ref_bonus = amount * 0.05
            await db.execute(
                "UPDATE users SET ton=ton+$1, ref_earned=ref_earned+$1 WHERE user_id=$2",
                ref_bonus, user['ref_id']
            )
        await msg.answer(f"✅ +{amount} TON → {uid}")
        try:
            await bot.send_message(uid, f"✅ Депозит зачислен: +{amount:.3f} TON")
        except:
            pass
    except Exception as e:
        await msg.answer(f"Ошибка: {e}\nФормат: /addton [user_id] [сумма]")

@dp.message(Command("users"))
async def users_count(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return
    count = await db.fetchval("SELECT COUNT(*) FROM users")
    await msg.answer(f"👥 Пользователей: {count}")

@dp.message(Command("pvp"))
async def pvp(msg: types.Message):
    parts = msg.text.split()
    if len(parts) < 2:
        players_text = ""
        if pvp_room["players"]:
            for uid, amt in pvp_room["players"].items():
                u = await get_user(uid)
                players_text += f"• @{u['username'] or uid}: {amt:.3f} TON\n"
        total = sum(pvp_room["players"].values())
        await msg.answer(
            f"⚔️ <b>PvP Рулетка</b>\n\n"
            f"Игроков: {len(pvp_room['players'])}\n"
            f"Банк: {total:.3f} TON\n\n"
            f"{players_text}\n"
            f"Ставка: /pvp [сумма]",
            parse_mode="HTML"
        )
        return
    try:
        amount = float(parts[1])
    except:
        await msg.answer("Пример: /pvp 0.5")
        return
    if amount < 0.01:
        await msg.answer("Минимум 0.01 TON!")
        return
    user = await get_user(msg.from_user.id)
    if not user:
        await msg.answer("Сначала /start")
        return
    if user['ton'] < amount:
        await msg.answer(f"Недостаточно TON! У тебя: {user['ton']:.3f}")
        return
    await db.execute("UPDATE users SET ton=ton-$1 WHERE user_id=$2", amount, msg.from_user.id)
    pvp_room["players"][msg.from_user.id] = pvp_room["players"].get(msg.from_user.id, 0) + amount
    total = sum(pvp_room["players"].values())
    await msg.answer(
        f"✅ Ставка: {amount:.3f} TON\n"
        f"⚔️ Игроков: {len(pvp_room['players'])}\n"
        f"🏦 Банк: {total:.3f} TON\n\n"
        f"{'⏱ Игра через 15 сек!' if len(pvp_room['players']) >= 2 else '⏳ Ждём игроков...'}"
    )
    if len(pvp_room["players"]) >= 2 and not pvp_room["running"]:
        pvp_room["running"] = True
        for uid in pvp_room["players"]:
            if uid != msg.from_user.id:
                try:
                    await bot.send_message(uid, "⚔️ Новый игрок! Игра через 15 сек!")
                except:
                    pass
        await asyncio.sleep(15)
        await pvp_spin()

async def pvp_spin():
    global pvp_room
    if len(pvp_room["players"]) < 2:
        for uid, amt in pvp_room["players"].items():
            await db.execute("UPDATE users SET ton=ton+$1 WHERE user_id=$2", amt, uid)
            try:
                await bot.send_message(uid, "😔 PvP отменён. TON возвращён!")
            except:
                pass
        pvp_room = {"players": {}, "running": False}
        return
    total = sum(pvp_room["players"].values())
    r = random.uniform(0, total)
    cum = 0
    winner_id = list(pvp_room["players"].keys())[0]
    for uid, amt in pvp_room["players"].items():
        cum += amt
        if r <= cum:
            winner_id = uid
            break
    prize = total * 0.95
    await db.execute(
        "UPDATE users SET ton=ton+$1, total_ton=total_ton+$1 WHERE user_id=$2",
        prize, winner_id
    )
    for uid, amt in pvp_room["players"].items():
        if uid == winner_id:
            try:
                await bot.send_message(uid,
                    f"🏆 Победа!\n💎 +{prize:.3f} TON\n🏦 Банк: {total:.3f} TON"
                )
            except:
                pass
        else:
            try:
                await bot.send_message(uid,
                    f"😔 Проигрыш\n💎 Ставка: {amt:.3f} TON\n🏆 Победитель получил {prize:.3f} TON"
                )
            except:
                pass
    pvp_room = {"players": {}, "running": False}

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())