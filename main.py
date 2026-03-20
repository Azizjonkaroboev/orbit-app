import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import asyncpg
from datetime import datetime, timedelta

BOT_TOKEN = "8475373683:AAEQCCSnI3jTWvsIzd8qJkg39BSUTcuquuI"
DATABASE_URL = "postgresql://orbit_db_new_user:gJaa0sXHxYUilFUGrPIkxIdfr7lDMtUy@dpg-d6m6v9a4d50c73cmrlug-a.oregon-postgres.render.com/orbit_db_new"
OWNER_WALLET = "UQAG8cx9dXAWIfcoNUkdyki-Un9QzJxw3_xU8624H6OnZFMb"
OWNER_ID = 6226218393
TONCENTER_API = "https://toncenter.com/api/v2/getTransactions"
APP_URL = "https://azizjonkaroboev.github.io/orbit-app/"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = None

@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(status=200, headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    try:
        response = await handler(request)
    except web.HTTPException as ex:
        response = web.Response(status=ex.status, text=ex.reason)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def init_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            ton FLOAT DEFAULT 0,
            bit INTEGER DEFAULT 0,
            total_bit INTEGER DEFAULT 0,
            total_ton FLOAT DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_checkin TEXT DEFAULT '',
            ref_id BIGINT DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            ref_earned INTEGER DEFAULT 0,
            wallet TEXT DEFAULT '',
            ad1_count INTEGER DEFAULT 0,
            ad2_count INTEGER DEFAULT 0,
            ad_reset_date TEXT DEFAULT '',
            total_ads INTEGER DEFAULT 0,
            total_pvp_bet FLOAT DEFAULT 0,
            monthly_ads INTEGER DEFAULT 0,
            monthly_pvp_bet FLOAT DEFAULT 0,
            last_month_reset TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS processed_txs (
            tx_hash TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS pvp_bets (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            amount FLOAT,
            round_id INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS pvp_state (
            id INTEGER PRIMARY KEY DEFAULT 1,
            round_id INTEGER DEFAULT 1,
            running BOOLEAN DEFAULT FALSE,
            total FLOAT DEFAULT 0,
            started_at TIMESTAMP
        )
    """)
    await db.execute("""
        INSERT INTO pvp_state (id, round_id, running, total)
        VALUES (1, 1, FALSE, 0)
        ON CONFLICT (id) DO NOTHING
    """)
    logging.info("DB initialized")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    ref_id = 0
    if len(args) > 1:
        try:
            ref_id = int(args[1])
        except:
            pass
    user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", message.from_user.id)
    if not user:
        await db.execute(
            "INSERT INTO users (user_id, username, ref_id) VALUES ($1, $2, $3)",
            message.from_user.id,
            message.from_user.username or message.from_user.first_name,
            ref_id if ref_id != message.from_user.id else 0
        )
        if ref_id and ref_id != message.from_user.id:
            await db.execute("UPDATE users SET ref_count=ref_count+1 WHERE user_id=$1", ref_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Launch Orbit", web_app=types.WebAppInfo(url=APP_URL))],
        [InlineKeyboardButton(text="📢 Channel", url="https://t.me/orbit_tonvoin"),
         InlineKeyboardButton(text="💬 Support", url="https://t.me/Ventlp")],
    ])
    await message.answer(
        "👋 Welcome to Orbit!\n\n"
        "🌍 Orbit is a TON earning platform.\n"
        "⚔️ Play PvP and win TON!\n"
        "📺 Watch ads and earn BIT!\n"
        "👥 Invite friends and earn 5%!\n\n"
        "Press Launch Orbit to start! 🚀",
        reply_markup=kb,
    )

async def handle_health(request):
    return web.Response(text="OK")

async def handle_register(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        username = data.get("username", "")
        ref_id = data.get("ref_id", 0)
        if not user_id:
            return web.json_response({"error": "no user_id"})
        user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, ref_id) VALUES ($1, $2, $3)",
                user_id, username, ref_id if ref_id != user_id else 0,
            )
            user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            if ref_id and ref_id != user_id:
                await db.execute("UPDATE users SET ref_count=ref_count+1 WHERE user_id=$1", ref_id)
        return web.json_response({
            "ton": user["ton"],
            "bit": user["bit"],
            "streak": user["streak"],
            "ref_count": user["ref_count"],
            "ref_earned": user["ref_earned"],
            "wallet": user["wallet"] or "",
        })
    except Exception as e:
        logging.error(f"register error: {e}")
        return web.json_response({"error": str(e)})

async def handle_checkin(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return web.json_response({"error": "no user_id"})
        user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if not user:
            return web.json_response({"error": "user not found"})
        today = datetime.now().strftime("%Y-%m-%d")
        last = user["last_checkin"] or ""
        if last == today:
            return web.json_response({"error": "already_claimed"})
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last == yesterday:
            new_streak = user["streak"] + 1
        else:
            new_streak = 1
        await db.execute(
            "UPDATE users SET streak=$1, last_checkin=$2 WHERE user_id=$3",
            new_streak, today, user_id,
        )
        return web.json_response({"streak": new_streak, "success": True})
    except Exception as e:
        logging.error(f"checkin error: {e}")
        return web.json_response({"error": str(e)})

async def handle_user(request):
    try:
        user_id = int(request.match_info["user_id"])
        user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if not user:
            return web.json_response({"error": "not found"})
        return web.json_response({
            "ton": user["ton"],
            "bit": user["bit"],
            "streak": user["streak"],
            "ref_count": user["ref_count"],
            "ref_earned": user["ref_earned"],
            "wallet": user["wallet"] or "",
            "total_ads": user["total_ads"],
            "monthly_ads": user["monthly_ads"],
            "total_pvp_bet": user["total_pvp_bet"],
            "monthly_pvp_bet": user["monthly_pvp_bet"],
        })
    except Exception as e:
        return web.json_response({"error": str(e)})

async def handle_wallet(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        wallet = data.get("wallet", "")
        await db.execute("UPDATE users SET wallet=$1 WHERE user_id=$2", wallet, user_id)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"error": str(e)})

async def handle_withdraw(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = float(data.get("amount", 0))
        user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if not user:
            return web.json_response({"error": "not found"})
        if user["ton"] < amount:
            return web.json_response({"error": "insufficient"})
        if amount < 0.5:
            return web.json_response({"error": "min 0.5 TON"})
        await db.execute("UPDATE users SET ton=ton-$1 WHERE user_id=$2", amount, user_id)
        await bot.send_message(
            OWNER_ID,
            f"💸 Заявка на вывод\n"
            f"👤 @{user['username']} (ID: {user_id})\n"
            f"💰 {amount} TON\n"
            f"👛 {user['wallet']}",
        )
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"error": str(e)})

async def handle_ad_reward(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = int(data.get("amount", 0))
        user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if not user:
            return web.json_response({"error": "not found"})
        await db.execute(
            "UPDATE users SET bit=bit+$1, total_bit=total_bit+$1, total_ads=total_ads+1, monthly_ads=monthly_ads+1 WHERE user_id=$2",
            amount, user_id,
        )
        if user.get("ref_id", 0):
            ref_bonus = max(1, int(amount * 0.05))
            await db.execute(
                "UPDATE users SET bit=bit+$1, total_bit=total_bit+$1, ref_earned=ref_earned+$1 WHERE user_id=$2",
                ref_bonus, user["ref_id"],
            )
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"error": str(e)})

async def handle_friends(request):
    try:
        user_id = int(request.match_info["user_id"])
        rows = await db.fetch(
            "SELECT username, ton, bit FROM users WHERE ref_id=$1 ORDER BY bit DESC",
            user_id,
        )
        return web.json_response([dict(r) for r in rows])
    except Exception as e:
        return web.json_response([])

async def handle_leaderboard_ads(request):
    try:
        rows = await db.fetch("""
            SELECT username, monthly_ads FROM users
            WHERE monthly_ads > 0
            ORDER BY monthly_ads DESC LIMIT 10
        """)
        return web.json_response([dict(r) for r in rows])
    except Exception as e:
        return web.json_response([])

async def handle_leaderboard_pvp(request):
    try:
        rows = await db.fetch("""
            SELECT username, monthly_pvp_bet FROM users
            WHERE monthly_pvp_bet > 0
            ORDER BY monthly_pvp_bet DESC LIMIT 10
        """)
        return web.json_response([dict(r) for r in rows])
    except Exception as e:
        return web.json_response([])

async def handle_pvp_state(request):
    try:
        state = await db.fetchrow("SELECT * FROM pvp_state WHERE id=1")
        bets = await db.fetch("SELECT user_id, username, amount FROM pvp_bets")
        total = sum(b["amount"] for b in bets)
        return web.json_response({
            "round_id": 1 if not state else state["round_id"],
            "running": False if not state else state["running"],
            "total": total,
            "players": [
                {"username": b["username"], "amount": b["amount"], "user_id": b["user_id"]}
                for b in bets
            ],
        })
    except Exception as e:
        return web.json_response({
            "error": str(e), "round_id": 1,
            "running": False, "total": 0, "players": []
        })

async def handle_pvp_bet(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        amount = float(data.get("amount", 0))
        if amount < 0.01:
            return web.json_response({"error": "min 0.01 TON"})
        if amount > 100:
            return web.json_response({"error": "max 100 TON"})
        user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if not user:
            return web.json_response({"error": "not found"})
        if user["ton"] < amount:
            return web.json_response({"error": "insufficient TON"})
        state = await db.fetchrow("SELECT * FROM pvp_state WHERE id=1")
        round_id = state["round_id"]
        player_count = await db.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM pvp_bets WHERE round_id=$1", round_id
        )
        if player_count >= 20:
            return web.json_response({"error": "max 20 players"})
        player_total = await db.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM pvp_bets WHERE round_id=$1 AND user_id=$2",
            round_id, user_id
        )
        if player_total + amount > 100:
            return web.json_response({"error": "max 100 TON per player"})
        await db.execute("UPDATE users SET ton=ton-$1 WHERE user_id=$2", amount, user_id)
        await db.execute(
            "INSERT INTO pvp_bets (user_id, username, amount, round_id) VALUES ($1, $2, $3, $4)",
            user_id, user["username"], amount, round_id,
        )
        await db.execute(
            "UPDATE users SET total_pvp_bet=total_pvp_bet+$1, monthly_pvp_bet=monthly_pvp_bet+$1 WHERE user_id=$2",
            amount, user_id,
        )
        return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"pvp bet error: {e}")
        return web.json_response({"error": str(e)})

async def monitor_deposits():
    while True:
        try:
            await asyncio.sleep(30)
            async with aiohttp.ClientSession() as session:
                params = {"address": OWNER_WALLET, "limit": 50}
                async with session.get(TONCENTER_API, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    txs = data.get("result", [])
                    for tx in txs:
                        try:
                            tx_hash = tx.get("transaction_id", {}).get("hash", "")
                            if not tx_hash:
                                continue
                            exists = await db.fetchval(
                                "SELECT 1 FROM processed_txs WHERE tx_hash=$1", tx_hash
                            )
                            if exists:
                                continue
                            msg = tx.get("in_msg", {})
                            comment = msg.get("message", "")
                            amount_ton = int(msg.get("value", 0)) / 1e9
                            if comment and comment.startswith("orbit_dep_") and amount_ton >= 0.05:
                                uid = int(comment.replace("orbit_dep_", ""))
                                user = await db.fetchrow(
                                    "SELECT * FROM users WHERE user_id=$1", uid
                                )
                                if not user:
                                    continue
                                await db.execute(
                                    "INSERT INTO processed_txs (tx_hash) VALUES ($1)", tx_hash
                                )
                                await db.execute(
                                    "UPDATE users SET ton=ton+$1, total_ton=total_ton+$1 WHERE user_id=$2",
                                    amount_ton, uid
                                )
                                try:
                                    await bot.send_message(uid, f"✅ Deposit: +{amount_ton:.3f} TON")
                                except:
                                    pass
                        except Exception as e:
                            logging.error(f"TX error: {e}")
        except Exception as e:
            logging.error(f"Monitor error: {e}")

async def monthly_reset():
    while True:
        try:
            now = datetime.now()
            if now.day == 1 and now.hour == 0:
                await db.execute("UPDATE users SET monthly_ads=0, monthly_pvp_bet=0")
                await asyncio.sleep(3600)
            else:
                await asyncio.sleep(3600)
        except Exception as e:
            logging.error(f"monthly reset error: {e}")
            await asyncio.sleep(3600)

async def pvp_refund_checker():
    while True:
        try:
            await asyncio.sleep(10)
            state = await db.fetchrow("SELECT * FROM pvp_state WHERE id=1")
            if state and not state["running"]:
                round_id = state["round_id"]
                bets = await db.fetch(
                    "SELECT * FROM pvp_bets WHERE round_id=$1", round_id
                )
                if bets:
                    player_ids = list(set(b["user_id"] for b in bets))
                    if len(player_ids) == 1:
                        first_bet = min(bets, key=lambda b: b["created_at"])
                        elapsed = (datetime.now() - first_bet["created_at"]).total_seconds()
                        if elapsed >= 120:
                            for bet in bets:
                                await db.execute(
                                    "UPDATE users SET ton=ton+$1 WHERE user_id=$2",
                                    bet["amount"], bet["user_id"]
                                )
                            await db.execute(
                                "DELETE FROM pvp_bets WHERE round_id=$1", round_id
                            )
        except Exception as e:
            logging.error(f"pvp refund error: {e}")

async def start_web():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_health)
    app.router.add_post("/api/register", handle_register)
    app.router.add_post("/api/checkin", handle_checkin)
    app.router.add_get("/api/user/{user_id}", handle_user)
    app.router.add_post("/api/wallet", handle_wallet)
    app.router.add_post("/api/withdraw", handle_withdraw)
    app.router.add_post("/api/ad_reward", handle_ad_reward)
    app.router.add_get("/api/friends/{user_id}", handle_friends)
    app.router.add_get("/api/leaderboard/bit", handle_leaderboard_ads)
    app.router.add_get("/api/leaderboard/ton", handle_leaderboard_pvp)
    app.router.add_get("/api/pvp", handle_pvp_state)
    app.router.add_post("/api/pvp/bet", handle_pvp_bet)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"✅ Web server started on port {port}")

async def main():
    await init_db()
    await start_web()
    asyncio.create_task(monitor_deposits())
    asyncio.create_task(monthly_reset())
    asyncio.create_task(pvp_refund_checker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())