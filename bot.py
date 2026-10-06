# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3, random, time, json
from datetime import datetime

# ============ НАСТРОЙКИ ============
TOKEN = "vk1.a.v6vj5u-rSXJUC9AXuCk7LWUumtS9j5q6JZniSS9OYyg5UwzWUq5aE4KPDrp1RzQWFnswcI0IPRCn-1ScSqM4VqUyaJPWL09pNy8pcu6DtqZTzqG4kQEqKmafOpXH4Y4BAATnV3aHwIWs7AfUYfjy14NohuEHUbyYYrbh1E_YMdcSMzW1OJmKuvXQXBEF9oBnb5TyKTgtYKGsuyUTFhJ6Og"
GROUP_ID = 242006213
MAIN_OWNER = 889701916

# ============ БАЗА ============
conn = sqlite3.connect('bot.db', check_same_thread=False)
cur = conn.cursor()

def column_exists(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def add_col(table, col, definition):
    if not column_exists(table, col):
        try: cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        except Exception as e: print(f"Alter {table}.{col}: {e}")

def init_db():
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 100,
        warns INTEGER DEFAULT 0,
        role TEXT DEFAULT 'user',
        country TEXT DEFAULT NULL,
        citizenship TEXT DEFAULT NULL,
        army INTEGER DEFAULT 100000,
        war INTEGER DEFAULT 1000000,
        mute_until INTEGER DEFAULT 0,
        last_bonus INTEGER DEFAULT 0,
        rank TEXT DEFAULT 'Новобранец',
        biz INTEGER DEFAULT 0,
        biz_income INTEGER DEFAULT 0,
        biz_collect INTEGER DEFAULT 0,
        subscription INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS countries(
        name TEXT PRIMARY KEY,
        owner INTEGER,
        president INTEGER,
        treasury INTEGER DEFAULT 100000,
        army INTEGER DEFAULT 100000,
        cities INTEGER DEFAULT 1,
        taxes INTEGER DEFAULT 5,
        pvo INTEGER DEFAULT 0,
        border_open INTEGER DEFAULT 1,
        buildings TEXT DEFAULT '{}',
        projects TEXT DEFAULT '{}',
        alive INTEGER DEFAULT 1
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS giveaways(
        id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER, expire INTEGER,
        text TEXT, creator INTEGER, taken_by INTEGER DEFAULT NULL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS promos(
        code TEXT PRIMARY KEY, amount INTEGER, uses INTEGER, max_uses INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bans(
        user_id INTEGER PRIMARY KEY, reason TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS wars(
        id INTEGER PRIMARY KEY AUTOINCREMENT, attacker TEXT, defender TEXT,
        started INTEGER, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS coalitions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, leader INTEGER, members TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS elections(
        id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, active INTEGER DEFAULT 1,
        started INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT, election_id INTEGER,
        user_id INTEGER, votes INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS votes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, election_id INTEGER,
        voter INTEGER, candidate INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS members(
        user_id INTEGER PRIMARY KEY, country TEXT,
        position TEXT DEFAULT 'Гражданин')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS companies(
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER, country TEXT,
        name TEXT, income INTEGER DEFAULT 1000, balance INTEGER DEFAULT 0,
        last_collect INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stockpile(
        country TEXT PRIMARY KEY,
        food INTEGER DEFAULT 0, weapons INTEGER DEFAULT 0,
        resources INTEGER DEFAULT 0, fuel INTEGER DEFAULT 0,
        money INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS transports(
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER,
        type TEXT, count INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS country_army(
        country TEXT PRIMARY KEY,
        troops INTEGER DEFAULT 0, pvo INTEGER DEFAULT 0,
        rockets INTEGER DEFAULT 0, drones INTEGER DEFAULT 0)""")
    conn.commit()

init_db()

# ============ ХЕЛПЕРЫ ============
def get_user(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users(user_id) VALUES(?)", (uid,))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cur.fetchone()
    return r

def upd_balance(uid, amount):
    get_user(uid)
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
    conn.commit()

def get_balance(uid): return get_user(uid)[1]
def is_owner(uid): return uid == MAIN_OWNER

def is_admin(uid):
    if uid == MAIN_OWNER: return True
    cur.execute("SELECT role FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r and r[0] in ('admin','moder','owner')

def is_muted(uid):
    cur.execute("SELECT mute_until FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if r and r[0] > int(time.time()): return r[0] - int(time.time())
    return 0

def is_banned(uid):
    cur.execute("SELECT reason FROM bans WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else None

def peer_to_chat(peer_id):
    return peer_id - 2000000000 if peer_id >= 2000000000 else None

def fmt(n): return f"{n:,}".replace(",", " ")

def name_of(uid):
    try:
        u = vk.users.get(user_ids=uid)[0]
        return f"{u['first_name']} {u['last_name']}"
    except: return f"id{uid}"

def get_country(name):
    cur.execute("SELECT * FROM countries WHERE name=?", (name,))
    return cur.fetchone()

def get_country_of(uid):
    cur.execute("SELECT country FROM members WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else None

def get_stock(country):
    cur.execute("SELECT * FROM stockpile WHERE country=?", (country,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO stockpile(country) VALUES(?)", (country,))
        conn.commit()
        cur.execute("SELECT * FROM stockpile WHERE country=?", (country,))
        r = cur.fetchone()
    return r

def upd_stock(country, field, amount):
    get_stock(country)
    cur.execute(f"UPDATE stockpile SET {field}={field}+? WHERE country=?", (amount, country))
    conn.commit()

def get_carmy(country):
    cur.execute("SELECT * FROM country_army WHERE country=?", (country,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO country_army(country) VALUES(?)", (country,))
        conn.commit()
        cur.execute("SELECT * FROM country_army WHERE country=?", (country,))
        r = cur.fetchone()
    return r

def upd_carmy(country, field, amount):
    get_carmy(country)
    cur.execute(f"UPDATE country_army SET {field}={field}+? WHERE country=?", (amount, country))
    conn.commit()

def get_position(uid):
    cur.execute("SELECT position FROM members WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else None

def is_president(uid):
    country = get_country_of(uid)
    if not country: return False
    c = get_country(country)
    return c and c[2] == uid

def is_government(uid):
    pos = get_position(uid)
    return pos in ('Президент','Министр','Генерал','Губернатор')

# ============ VK ============
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

def send(peer_id, text, keyboard=None):
    try:
        vk.messages.send(peer_id=peer_id, message=text,
                         random_id=get_random_id(), keyboard=keyboard)
    except Exception as e: print(f"Send error: {e}")

def delete_message(peer_id, message_id):
    try: vk.messages.delete(message_ids=message_id, delete_for_all=1); return True
    except: return False

def kick_user(chat_id, user_id):
    try: vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id); return True
    except Exception as e: print(f"Kick: {e}"); return False

# ============ КЛАВИАТУРЫ ============
def kb_main():
    return json.dumps({"one_time": False, "buttons": [
        [{"action":{"type":"text","label":"💰 Баланс"},"color":"positive"},
         {"action":{"type":"text","label":"🏆 Топ"},"color":"positive"}],
        [{"action":{"type":"text","label":"🎰 Клуб"},"color":"primary"},
         {"action":{"type":"text","label":"🎲 Казино"},"color":"primary"}],
        [{"action":{"type":"text","label":"🌍 Страна"},"color":"secondary"},
         {"action":{"type":"text","label":"📘 Паспорт"},"color":"secondary"}],
        [{"action":{"type":"text","label":"🎁 Приз"},"color":"positive"},
         {"action":{"type":"text","label":"📋 Задания"},"color":"secondary"}],
        [{"action":{"type":"text","label":"📜 Устав"},"color":"secondary"},
         {"action":{"type":"text","label":"⚔️ Войны"},"color":"negative"}],
    ]}, ensure_ascii=False)

def kb_games():
    return json.dumps({"one_time": False, "buttons": [
        [{"action":{"type":"text","label":"🎰 Казино"},"color":"primary"},
         {"action":{"type":"text","label":"🪙 Монетка"},"color":"primary"}],
        [{"action":{"type":"text","label":"🎲 Кубик"},"color":"primary"},
         {"action":{"type":"text","label":"🍒 Слоты"},"color":"primary"}],
        [{"action":{"type":"text","label":"⚔️ Дуэль"},"color":"negative"},
         {"action":{"type":"text","label":"🎡 Рулетка"},"color":"primary"}],
        [{"action":{"type":"text","label":"◀️ Меню"},"color":"secondary"}],
    ]}, ensure_ascii=False)

def kb_country():
    return json.dumps({"one_time": False, "buttons": [
        [{"action":{"type":"text","label":"🌍 Страны"},"color":"primary"},
         {"action":{"type":"text","label":"📘 Паспорт"},"color":"primary"}],
        [{"action":{"type":"text","label":"🏛 Казна"},"color":"secondary"},
         {"action":{"type":"text","label":"🎖️ Армия"},"color":"secondary"}],
        [{"action":{"type":"text","label":"🗺 Гос.команды"},"color":"primary"},
         {"action":{"type":"text","label":"⚔️ Войны"},"color":"negative"}],
        [{"action":{"type":"text","label":"◀️ Меню"},"color":"secondary"}],
    ]}, ensure_ascii=False)

def kb_back():
    return json.dumps({"one_time": False, "buttons": [
        [{"action":{"type":"text","label":"◀️ Меню"},"color":"secondary"}]
    ]}, ensure_ascii=False)

# ============ ФОРМАТ ============
DIV = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
def header(t): return f"{DIV}\n     ⚔️ {t} ⚔️\n{DIV}"

def card(title, rows, footer=None):
    txt = header(title) + "\n"
    for k, v in rows: txt += f"  {k} ➜ {v}\n"
    txt += DIV
    if footer: txt += f"\n{footer}"
    return txt

TRANSPORT_PRICE = {"грузовик": 50000, "поезд": 250000, "корабль": 500000, "самолет": 1000000}
PRODUCTS = ("еда","оружие","ресурсы","топливо","деньги")
BUILDINGS = {
    "ферма": {"cost": 100000, "bonus": "food"},
    "завод": {"cost": 250000, "bonus": "resources"},
    "нефтевышка": {"cost": 300000, "bonus": "fuel"},
    "казарма": {"cost": 200000, "bonus": "army"},
    "радар": {"cost": 150000, "bonus": "pvo"},
    "госпиталь": {"cost": 180000, "bonus": "defense"},
}

# ============ ОБРАБОТКА ============
def handle_message(peer_id, uid, text, message_id=None):
    text = text.strip()
    low = text.lower()
    args = text.split()
    cmd = args[0].lower() if args else ""

    # Бан
    if is_banned(uid) and not is_owner(uid):
        ch = peer_to_chat(peer_id)
        if ch: kick_user(ch, uid)
        return

    # Мут
    if is_muted(uid) > 0 and not is_admin(uid):
        if message_id: delete_message(peer_id, message_id)
        return

    # ================= START =================
    if low in ("начать","start","/start","меню","◀️ меню"):
        get_user(uid)
        u = get_user(uid)
        send(peer_id,
            f"{header('БОЕВОЙ БОТ')}\n\n"
            f"  👤 {name_of(uid)}\n"
            f"  💰 {fmt(u[1])} 💵\n"
            f"  🎖️ {u[10]}\n"
            f"  🌍 {u[5] or 'нет гражданства'}\n\n"
            f"  🎯 Выберите действие\n"
            f"  📖 /help — все команды\n\n"
            f"🔥 В строй. Победа или смерть. 🔥",
            kb_main())
        return

    if cmd == "/help":
        send(peer_id,
            f"{header('КОМАНДЫ')}\n\n"
            f"💰 /баланс /топ /приз /передать /донат\n"
            f"🎁 /раздача /взять\n"
            f"🎲 /казино /дуэль /монетка /кубик /слоты\n"
            f"🌍 /страны /гражданство /паспорт /казна\n"
            f"⚔️ /войны /война /захват /мобилизация\n"
            f"🏛 /госскоманды — все команды страны\n"
            f"🎟️ /promo /promolist\n\n"
            f"  🛡️ Модерация: /warn /mute /kick /ban", kb_back())
        return

    # ================= ЭКОНОМИКА =================
    if cmd in ("/баланс","баланс","💰 баланс"):
        u = get_user(uid)
        send(peer_id, card("БАЛАНС", [
            ("👤", name_of(uid)), ("💰", f"{fmt(u[1])} 💵"),
            ("🎖️", u[10]), ("⚠️", f"{u[2]}/3 варна"),
            ("🌍", u[5] or "нет гражданства"),
        ]), kb_back()); return

    if cmd in ("/топ","топ","🏆 топ"):
        cur.execute("SELECT user_id,balance FROM users ORDER BY balance DESC LIMIT 10")
        rows = cur.fetchall()
        medals = ["🥇","🥈","🥉"] + ["🔹"]*7
        txt = header("ТОП-10 БОГАЧЕЙ") + "\n\n"
        for i,(u,b) in enumerate(rows):
            txt += f"  {medals[i]} {name_of(u)} — {fmt(b)} 💵\n"
        txt += f"\n{DIV}"
        send(peer_id, txt, kb_back()); return

    if cmd in ("/приз","приз","🎁 приз"):
        u = get_user(uid)
        last = u[9]
        if int(time.time()) - last < 3600:
            left = 3600 - (int(time.time()) - last)
            return send(peer_id, f"⏳ Приз через {left//60}м {left%60}с", kb_back())
        amount = random.randint(100, 900000)
        upd_balance(uid, amount)
        cur.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (int(time.time()), uid))
        conn.commit()
        send(peer_id, card("🎁 ПРИЗ", [
            ("💰","+"+fmt(amount)+" 💵"), ("💳",fmt(get_balance(uid))+" 💵"),
        ]), kb_back()); return

    if cmd == "/передать":
        if len(args) < 3: return send(peer_id, "📝 /передать <id> <сумма>")
        try:
            t = int(args[1].replace("@","").replace("[id","").split("|")[0].split("]")[0])
            a = int(args[2])
        except: return send(peer_id, "❌ Неверный формат")
        if a <= 0: return send(peer_id, "❌ Сумма > 0")
        if t == uid: return send(peer_id, "❌ Себе нельзя")
        if get_balance(uid) < a: return send(peer_id, "❌ Мало средств")
        upd_balance(uid, -a); upd_balance(t, a)
        send(peer_id, f"✅ Передано {fmt(a)} 💵 → {name_of(t)}", kb_back()); return

    if cmd == "/донат":
        send(peer_id, card("💎 ДОНАТ", [("⭐","500 000"),("💎","1 000 000")],
             f"Связь: @id{MAIN_OWNER}"), kb_back()); return

    if cmd == "/подписка":
        cur.execute("UPDATE users SET subscription=1 WHERE user_id=?", (uid,))
        conn.commit()
        send(peer_id, "📰 Подписка оформлена!", kb_back()); return

    if cmd == "/buybiz":
        u = get_user(uid)
        if u[11]: return send(peer_id, "🏢 Уже есть бизнес", kb_back())
        if get_balance(uid) < 500000: return send(peer_id, "❌ Нужно 500 000 💵", kb_back())
        upd_balance(uid, -500000)
        cur.execute("UPDATE users SET biz=1,biz_income=10000,biz_collect=? WHERE user_id=?",
                    (int(time.time()), uid))
        conn.commit()
        send(peer_id, "🏢 Бизнес куплен! 10 000 💵/час", kb_back()); return

    if cmd == "/mybiz":
        u = get_user(uid)
        if not u[11]: return send(peer_id, "❌ Нет бизнеса. /buybiz", kb_back())
        hrs = min((int(time.time())-u[13])//3600, 24)
        send(peer_id, card("🏢 БИЗНЕС", [
            ("💵 Доход", f"{fmt(u[12])}/час"),
            ("⏳ Накоплено", f"{fmt(hrs*u[12])} 💵"),
        ], "/collect"), kb_back()); return

    if cmd == "/collect":
        u = get_user(uid)
        if not u[11]: return send(peer_id, "❌ Нет бизнеса", kb_back())
        hrs = min((int(time.time())-u[13])//3600, 24)
        if hrs < 1: return send(peer_id, "⏳ Позже", kb_back())
        inc = hrs * u[12]; upd_balance(uid, inc)
        cur.execute("UPDATE users SET biz_collect=? WHERE user_id=?", (int(time.time()), uid))
        conn.commit()
        send(peer_id, f"💼 Собрано {fmt(inc)} 💵", kb_back()); return

    # ================= РАЗДАЧА =================
    if cmd == "/раздача":
        if not is_admin(uid): return send(peer_id, "❌ Только админы")
        if len(args) < 4: return send(peer_id, "📝 /раздача <сумма> <s|m|h|d> <текст>")
        try: a = int(args[1]); unit = args[2].lower()
        except: return send(peer_id, "❌ Ошибка")
        mult = {"s":1,"m":60,"h":3600,"d":86400}.get(unit,60)
        cur.execute("INSERT INTO giveaways(amount,expire,text,creator) VALUES(?,?,?,?)",
                    (a, int(time.time())+mult, " ".join(args[3:]), uid))
        conn.commit()
        send(peer_id, f"🎁 Раздача #{cur.lastrowid} на {fmt(a)} 💵", kb_back()); return

    if cmd == "/взять":
        cur.execute("SELECT id,amount FROM giveaways WHERE taken_by IS NULL AND expire>? ORDER BY id DESC LIMIT 1",
                    (int(time.time()),))
        g = cur.fetchone()
        if not g: return send(peer_id, "❌ Нет раздач", kb_back())
        cur.execute("UPDATE giveaways SET taken_by=? WHERE id=?", (uid, g[0]))
        conn.commit()
        upd_balance(uid, g[1])
        send(peer_id, f"🎉 +{fmt(g[1])} 💵 из раздачи #{g[0]}", kb_back()); return

    # ================= ИГРЫ =================
    if cmd in ("/казино","🎲 казино"):
        if len(args)<2: return send(peer_id,"📝 /казино <ставка>", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌ Мало средств", kb_games())
        if random.random()<0.45:
            upd_balance(uid,bet); send(peer_id, f"🎰 ПОБЕДА +{fmt(bet)} 💵", kb_games())
        else:
            upd_balance(uid,-bet); send(peer_id, f"🎰 Проигрыш -{fmt(bet)} 💵", kb_games())
        return

    if cmd in ("/монетка","🪙 монетка"):
        if len(args)<2: return send(peer_id,"📝 /монетка <ставка> [орёл|решка]", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌", kb_games())
        side = args[2].lower() if len(args)>2 else "орёл"
        if side not in ("орёл","решка"): side = "орёл"
        res = random.choice(["орёл","решка"])
        if res==side: upd_balance(uid,bet); send(peer_id, f"🪙 {res}! +{fmt(bet)} 💵", kb_games())
        else: upd_balance(uid,-bet); send(peer_id, f"🪙 {res}! -{fmt(bet)} 💵", kb_games())
        return

    if cmd in ("/кубик","🎲 кубик"):
        if len(args)<2: return send(peer_id,"📝 /кубик <ставка>", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌", kb_games())
        r=random.randint(1,6)
        if r>=4: upd_balance(uid,bet); send(peer_id, f"🎲 {r}! +{fmt(bet)}", kb_games())
        else: upd_balance(uid,-bet); send(peer_id, f"🎲 {r}! -{fmt(bet)}", kb_games())
        return

    if cmd in ("/слоты","🍒 слоты"):
        if len(args)<2: return send(peer_id,"📝 /слоты <ставка>", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌", kb_games())
        icons=["🍒","🍋","💎","7️⃣","⭐"]
        r=[random.choice(icons) for _ in range(3)]
        line=" │ ".join(r)
        if r[0]==r[1]==r[2]:
            upd_balance(uid,bet*5)
            send(peer_id, card("🍒 СЛОТЫ",[("🎰",f"║ {line} ║"),("💥",f"ДЖЕКПОТ +{fmt(bet*5)}")]), kb_games())
        elif r[0]==r[1] or r[1]==r[2]:
            upd_balance(uid,bet)
            send(peer_id, card("🍒 СЛОТЫ",[("🎰",f"║ {line} ║"),("✅",f"+{fmt(bet)}")]), kb_games())
        else:
            upd_balance(uid,-bet)
            send(peer_id, card("🍒 СЛОТЫ",[("🎰",f"║ {line} ║"),("❌",f"-{fmt(bet)}")]), kb_games())
        return

    if cmd in ("/дуэль","⚔️ дуэль"):
        if len(args)<3: return send(peer_id,"📝 /дуэль <id> <ставка>", kb_games())
        try:
            t=int(args[1].replace("@","").split("|")[0].split("]")[0]); bet=int(args[2])
        except: return send(peer_id,"❌", kb_games())
        if t==uid: return send(peer_id,"❌ Себе нельзя", kb_games())
        if get_balance(uid)<bet or get_balance(t)<bet:
            return send(peer_id,"❌ У кого-то мало средств", kb_games())
        if random.random()<0.5:
            upd_balance(uid,bet); upd_balance(t,-bet)
            send(peer_id, f"⚔️ {name_of(uid)} победил!", kb_games())
        else:
            upd_balance(uid,-bet); upd_balance(t,bet)
            send(peer_id, f"⚔️ {name_of(t)} победил!", kb_games())
        return

    game_map = {
        "/краш":"🚀 КРАШ","/дартс":"🎯 ДАРТС","/колесо":"🎡 КОЛЕСО",
        "/рулетка":"🎰 РУЛЕТКА","/блэкджек":"🃏 БЛЭКДЖЕК","/мины":"💣 МИНЫ",
        "/башня":"🏗 БАШНЯ","/кейс":"🎁 КЕЙС","/гонка":"🏎 ГОНКА","/рыбалка":"🎣 РЫБАЛКА",
    }
    if cmd in game_map:
        if len(args)<2: return send(peer_id, f"📝 {cmd} <ставка>", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌", kb_games())
        if random.random()<0.5:
            upd_balance(uid,bet); send(peer_id, f"{game_map[cmd]}: ✅ +{fmt(bet)} 💵", kb_games())
        else:
            upd_balance(uid,-bet); send(peer_id, f"{game_map[cmd]}: ❌ -{fmt(bet)} 💵", kb_games())
        return

    if cmd in ("/клуб","🎰 клуб"):
        send(peer_id, card("🎰 КЛУБ", [
            ("🎲","/казино"),("🪙","/монетка"),("🍒","/слоты"),("⚔️","/дуэль"),
        ], "/купитьклуб — 1 трон"), kb_games()); return

    if cmd == "/купитьклуб":
        if get_balance(uid)<1000000: return send(peer_id,"❌ Нужен 1 трон (1M 💵)", kb_back())
        upd_balance(uid,-1000000)
        send(peer_id,"💎 Клуб куплен!", kb_back()); return

    # ================= СТРАНЫ =================
    if cmd in ("/страны","/страна","🌍 страна"):
        cur.execute("SELECT name,treasury,cities,army FROM countries WHERE alive=1 ORDER BY cities DESC")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"🌍 Стран нет. /гражданство <название>", kb_country())
        txt = header("СТРАНЫ МИРА")+"\n\n"
        for i,(n,t,c,a) in enumerate(rows[:15],1):
            txt += f"  {i}. 🏳️ {n}\n     💰 {fmt(t)} | 🏙 {c} | 🎖️ {fmt(a)}\n"
        txt += f"\n{DIV}"
        send(peer_id, txt, kb_country()); return

    if cmd == "/гражданство":
        if len(args)<2: return send(peer_id,"📝 /гражданство <страна>", kb_country())
        country=" ".join(args[1:])
        cur.execute("SELECT name FROM countries WHERE name=?",(country,))
        if not cur.fetchone():
            cur.execute("""INSERT INTO countries(name,owner,president,treasury,army,cities)
                            VALUES(?,?,?,?,?,?)""",(country,uid,uid,100000,100000,1))
            cur.execute("INSERT INTO stockpile(country) VALUES(?)",(country,))
            cur.execute("INSERT INTO country_army(country) VALUES(?)",(country,))
            cur.execute("INSERT INTO members(user_id,country,position) VALUES(?,?,?)",
                        (uid,country,'Президент'))
            cur.execute("UPDATE country_army SET troops=100000 WHERE country=?",(country,))
            conn.commit()
            send(peer_id, f"🌍 Страна «{country}» создана!\n👑 Вы президент", kb_country())
        else:
            cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)",
                        (uid,country,'Гражданин'))
            conn.commit()
        cur.execute("UPDATE users SET citizenship=?,country=? WHERE user_id=?",(country,country,uid))
        conn.commit()
        send(peer_id, f"✅ Гражданство: {country}", kb_country()); return

    if cmd in ("/паспорт","📘 паспорт"):
        u=get_user(uid)
        pos = get_position(uid) or "—"
        send(peer_id, card("📘 ПАСПОРТ", [
            ("👤",name_of(uid)),("🆔",f"id{uid}"),
            ("🌍",u[5] or "нет гражданства"),
            ("💼",pos),("🎖️",u[10]),("💰",f"{fmt(u[1])} 💵"),
        ]), kb_country()); return

    if cmd in ("/казна","🏛 казна"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        co = get_country(c)
        st = get_stock(c)
        send(peer_id, card("🏛 КАЗНА", [
            ("🏳️",c),("💰",f"{fmt(co[3])} 💵"),
            ("🍞 Еда",f"{fmt(st[1])}"),("🔫 Оружие",f"{fmt(st[2])}"),
            ("⚙️ Ресурсы",f"{fmt(st[3])}"),("⛽ Топливо",f"{fmt(st[4])}"),
            ("🏙 Города",f"{co[5]}"),("📊 Налог",f"{co[6]}%"),
        ]), kb_country()); return

    if cmd in ("/армия","🎖️ армия"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        ca = get_carmy(c)
        send(peer_id, card("🎖️ АРМИЯ", [
            ("🏳️",c),("🪖 Войска",f"{fmt(ca[1])}"),
            ("🎯 ПВО",f"{fmt(ca[2])}"),("🚀 Ракеты",f"{fmt(ca[3])}"),
            ("🛸 Дроны",f"{fmt(ca[4])}"),
        ]), kb_country()); return

    if cmd in ("/граждане","/города","/правительство","/очки","/должности"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        if cmd == "/граждане":
            cur.execute("SELECT user_id,position FROM members WHERE country=?",(c,))
            rows = cur.fetchall()
            txt = header(f"ГРАЖДАНЕ {c}")+f"\n\n  Всего: {len(rows)}\n\n"
            for u,p in rows[:20]:
                txt += f"  👤 {name_of(u)} — {p}\n"
            txt += f"\n{DIV}"
            send(peer_id, txt, kb_country())
        elif cmd == "/города":
            co = get_country(c)
            send(peer_id, card(f"🏙 ГОРОДА {c}", [("🏙 Всего",f"{co[5]}")]), kb_country())
        elif cmd == "/правительство":
            cur.execute("SELECT user_id,position FROM members WHERE country=? AND position!='Гражданин'",(c,))
            rows = cur.fetchall()
            txt = header(f"ПРАВИТЕЛЬСТВО {c}")+"\n\n"
            if not rows: txt += "  (пусто)\n"
            for u,p in rows: txt += f"  👑 {name_of(u)} — {p}\n"
            txt += f"\n{DIV}"
            send(peer_id, txt, kb_country())
        elif cmd == "/должности":
            send(peer_id, card("💼 ДОЛЖНОСТИ", [
                ("👑","Президент"),("🏛","Министр"),("🎖️","Генерал"),
                ("🗺","Губернатор"),("👤","Гражданин"),
            ]), kb_country())
        else:
            send(peer_id, f"📊 {cmd}: информация доступна", kb_country())
        return

    if cmd == "/выборы":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        cur.execute("SELECT id,active FROM elections WHERE country=? AND active=1",(c,))
        e = cur.fetchone()
        if not e:
            return send(peer_id, f"🗳️ В {c} нет активных выборов.\nПрезидент может начать: /выборы начать", kb_country())
        cur.execute("SELECT user_id,votes FROM candidates WHERE election_id=? ORDER BY votes DESC",(e[0],))
        rows = cur.fetchall()
        txt = header(f"ВЫБОРЫ {c}")+"\n\n"
        if not rows: txt += "  (нет кандидатов)\n"
        for u,v in rows: txt += f"  🗳️ {name_of(u)} — {v} голосов\n"
        txt += f"\n{DIV}"
        send(peer_id, txt, kb_country()); return

    if cmd == "/выдвинуться":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1",(c,))
        e = cur.fetchone()
        if not e:
            cur.execute("INSERT INTO elections(country,started) VALUES(?,?)",(c,int(time.time())))
            conn.commit()
            e = (cur.lastrowid,)
        cur.execute("SELECT id FROM candidates WHERE election_id=? AND user_id=?",(e[0],uid))
        if cur.fetchone(): return send(peer_id,"❌ Вы уже кандидат", kb_country())
        cur.execute("INSERT INTO candidates(election_id,user_id) VALUES(?,?)",(e[0],uid))
        conn.commit()
        send(peer_id, f"🗳️ Вы выдвинулись в президенты {c}!", kb_country()); return

    if cmd == "/голос":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        if len(args)<2: return send(peer_id,"📝 /голос <id кандидата>", kb_country())
        try: cand = int(args[1])
        except: return send(peer_id,"❌ Неверный id", kb_country())
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1",(c,))
        e = cur.fetchone()
        if not e: return send(peer_id,"❌ Нет выборов", kb_country())
        cur.execute("SELECT id FROM votes WHERE election_id=? AND voter=?",(e[0],uid))
        if cur.fetchone(): return send(peer_id,"❌ Вы уже голосовали", kb_country())
        cur.execute("INSERT INTO votes(election_id,voter,candidate) VALUES(?,?,?)",(e[0],uid,cand))
        cur.execute("UPDATE candidates SET votes=votes+1 WHERE election_id=? AND user_id=?",(e[0],cand))
        conn.commit()
        send(peer_id, f"🗳️ Голос за {name_of(cand)} учтён!", kb_country()); return

    if cmd == "/компания":
        send(peer_id, "📢 Предвыборная кампания активна!", kb_country()); return

    if cmd == "/регистрация":
        if len(args)>=3 and args[1].lower()=="ооо":
            name = " ".join(args[2:])
            c = get_country_of(uid)
            if not c: return send(peer_id,"❌ Нужна страна", kb_country())
            cur.execute("INSERT INTO companies(owner,country,name) VALUES(?,?,?)",(uid,c,name))
            conn.commit()
            send(peer_id, f"🏢 ООО «{name}» зарегистрировано!", kb_country())
        else:
            send(peer_id, "📝 /регистрация ООО <название>", kb_country())
        return

    # ================= ПРАВИТЕЛЬСТВО =================
    if cmd == "/налоги":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        if len(args)<2: return send(peer_id,"📝 /налоги <0-50>")
        try: tax = max(0, min(50, int(args[1])))
        except: return send(peer_id,"❌")
        cur.execute("UPDATE countries SET taxes=? WHERE name=?",(tax,c))
        conn.commit()
        send(peer_id, f"📊 Налог установлен: {tax}%"); return

    if cmd in ("/улучшить_страну","/улучшитьстрану"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        co = get_country(c)
        if co[3] < 100000: return send(peer_id,"❌ Нужно 100 000 💵 в казне")
        cur.execute("UPDATE countries SET treasury=treasury-100000, cities=cities+1 WHERE name=?",(c,))
        conn.commit()
        send(peer_id, f"🏙 Город построен! Теперь: {co[5]+1}"); return

    if cmd == "/постройки":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        co = get_country(c)
        b = json.loads(co[9] or "{}")
        txt = header(f"ПОСТРОЙКИ {c}")+"\n\n"
        if not b: txt += "  (нет построек)\n"
        for k,v in b.items(): txt += f"  🏗 {k} — {v}\n"
        txt += "\n📝 /построить <название>"
        txt += f"\n{DIV}"
        send(peer_id, txt); return

    if cmd == "/построить":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        if len(args)<2: 
            txt = header("ДОСТУПНЫЕ ПОСТРОЙКИ")+"\n\n"
            for k,v in BUILDINGS.items():
                txt += f"  🏗 {k} — {fmt(v['cost'])} 💵\n"
            txt += f"\n{DIV}"
            return send(peer_id, txt)
        bname = args[1].lower()
        if bname not in BUILDINGS: return send(peer_id,"❌ Неизвестная постройка")
        co = get_country(c)
        cost = BUILDINGS[bname]['cost']
        if co[3] < cost: return send(peer_id,f"❌ Нужно {fmt(cost)} 💵")
        b = json.loads(co[9] or "{}")
        b[bname] = b.get(bname,0)+1
        cur.execute("UPDATE countries SET treasury=treasury-?, buildings=? WHERE name=?",
                    (cost, json.dumps(b,ensure_ascii=False), c))
        conn.commit()
        send(peer_id, f"🏗 Построено: {bname} (x{b[bname]})"); return

    if cmd == "/госпроект":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        if len(args)<2: return send(peer_id,"📝 /госпроект <название>")
        name = " ".join(args[1:])
        co = get_country(c)
        pr = json.loads(co[10] or "{}")
        pr[name] = pr.get(name,0)+1
        cur.execute("UPDATE countries SET projects=? WHERE name=?",
                    (json.dumps(pr,ensure_ascii=False), c))
        conn.commit()
        send(peer_id, f"🏗 Госпроект «{name}» запущен!"); return

    if cmd == "/вооружение":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        if len(args)<3: return send(peer_id,"📝 /вооружение <тип> <кол>\nТипы: ракета, бпла, пво, танк")
        try: col = int(args[2])
        except: return send(peer_id,"❌")
        t = args[1].lower()
        cost_map = {"ракета":50000,"бпла":30000,"пво":100000,"танк":80000}
        if t not in cost_map: return send(peer_id,"❌ Неизвестный тип")
        co = get_country(c)
        total = col * cost_map[t]
        if co[3] < total: return send(peer_id,f"❌ Нужно {fmt(total)} 💵")
        cur.execute("UPDATE countries SET treasury=treasury-? WHERE name=?",(total,c))
        if t=="ракета": upd_carmy(c,"rockets",col)
        elif t=="бпла": upd_carmy(c,"drones",col)
        elif t=="пво": upd_carmy(c,"pvo",col)
        elif t=="танк": upd_carmy(c,"troops",col*1000)
        conn.commit()
        send(peer_id, f"⚙️ Закуплено: {col} {t}"); return

    # ================= АРМИЯ =================
    if cmd == "/мобилизация":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_government(uid): return send(peer_id,"❌ Только правительство")
        upd_carmy(c,"troops",50000)
        send(peer_id, f"🪖 Мобилизация! +50 000 войск {c}"); return

    if cmd == "/демобилизация":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_government(uid): return send(peer_id,"❌ Только правительство")
        upd_carmy(c,"troops",-30000)
        send(peer_id, f"🪖 Демобилизация! -30 000 войск"); return

    if cmd in ("/пво","/установить пво"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_government(uid): return send(peer_id,"❌ Только правительство")
        co = get_country(c)
        if co[3] < 150000: return send(peer_id,"❌ Нужно 150 000 💵")
        cur.execute("UPDATE countries SET treasury=treasury-?, pvo=pvo+1 WHERE name=?",(150000,c))
        upd_carmy(c,"pvo",1)
        conn.commit()
        send(peer_id, "🎯 ПВО установлено!"); return

    if cmd == "/запуск":
        if len(args)<4: return send(peer_id,"📝 /запуск ракета|бпла <кол> <страна>")
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_government(uid): return send(peer_id,"❌ Только правительство")
        t = args[1].lower(); 
        try: col=int(args[2])
        except: return send(peer_id,"❌")
        target = " ".join(args[3:])
        if not get_country(target): return send(peer_id,"❌ Страна не найдена")
        ca = get_carmy(c)
        if t=="ракета" and ca[3] < col: return send(peer_id,"❌ Мало ракет")
        if t=="бпла" and ca[4] < col: return send(peer_id,"❌ Мало бпла")
        if t=="ракета": upd_carmy(c,"rockets",-col)
        else: upd_carmy(c,"drones",-col)
        tca = get_carmy(target)
        pvo_def = tca[2] * 10
        dmg = max(0, col - pvo_def) * 5000
        upd_carmy(target,"troops",-dmg)
        send(peer_id, f"🚀 Запуск {col} {t} по {target}\n💥 Урон: {fmt(dmg)} войск"); return

    if cmd in ("/дрон","/перехват"):
        send(peer_id, f"🛸 {cmd[1:].upper()}: выполнено"); return

    if cmd in ("/сирена","/воздухтревога"):
        send(peer_id, "🚨 ВОЗДУШНАЯ ТРЕВОГА 🚨\n\n❗ Всем в укрытие! ❗"); return

    if cmd == "/задание":
        send(peer_id, card("📋 ЗАДАНИЯ", [
            ("1️⃣","5 новобранцев → 50 000 💵"),
            ("2️⃣","3 дуэли → 30 000 💵"),
            ("3️⃣","Захват → 500 000 💵"),
        ], "/выполнитьзадание")); return

    if cmd == "/выполнитьзадание":
        r = random.randint(10000, 100000)
        upd_balance(uid, r)
        send(peer_id, f"✅ Задание выполнено! +{fmt(r)} 💵"); return

    if cmd == "/upgrade_army":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        co = get_country(c)
        if co[3] < 100000: return send(peer_id,"❌ Нужно 100 000 💵")
        cur.execute("UPDATE countries SET treasury=treasury-100000, army=army+50000 WHERE name=?",(c,))
        conn.commit()
        send(peer_id, "🎖️ Армия улучшена! +50 000"); return

    if cmd in ("/сделать","/запуск_ракеты"):
        send(peer_id, f"🪖 {cmd[1:].upper()}: ок"); return

    if cmd in ("/звание","🎖️ звание"):
        send(peer_id, card("🎖️ ЗВАНИЕ", [("👤",name_of(uid)),("🎖️",get_user(uid)[10])]))
        return

    if cmd == "/повысить":
        if not is_admin(uid): return send(peer_id,"❌ Нет прав")
        if len(args)<2: return send(peer_id,"📝 /повысить <id>")
        try: t=int(args[1])
        except: return
        ranks=["Новобранец","Рядовой","Сержант","Лейтенант","Капитан","Майор","Полковник","Генерал"]
        cur.execute("SELECT rank FROM users WHERE user_id=?",(t,))
        r=cur.fetchone()
        idx = ranks.index(r[0]) if r and r[0] in ranks else 0
        new=ranks[min(idx+1,len(ranks)-1)]
        cur.execute("UPDATE users SET rank=? WHERE user_id=?",(new,t))
        conn.commit()
        send(peer_id, f"🎖️ {name_of(t)} → {new}"); return

    # ================= ГРАНИЦЫ =================
    if cmd == "/граница":
        if len(args)<2: return send(peer_id,"📝 /граница открыть|закрыть [страна]")
        action = args[1].lower()
        c = " ".join(args[2:]) if len(args)>2 else get_country_of(uid)
        if not c or not get_country(c): return send(peer_id,"❌ Страна не найдена")
        if not is_president(uid) and not is_owner(uid): return send(peer_id,"❌ Только президент")
        val = 1 if action=="открыть" else 0
        cur.execute("UPDATE countries SET border_open=? WHERE name=?",(val,c))
        conn.commit()
        send(peer_id, f"🌉 Граница {c} {action}та"); return

    if cmd == "/виза":
        if len(args)<3: return send(peer_id,"📝 /виза выдать|забрать @user")
        action = args[1].lower()
        try: t = int(args[2].replace("@","").replace("[id","").split("|")[0].split("]")[0])
        except: return send(peer_id,"❌")
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        if action == "выдать":
            cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)",
                        (t,c,'Гражданин'))
            conn.commit()
            send(peer_id, f"📗 Виза выдана {name_of(t)}")
        else:
            cur.execute("DELETE FROM members WHERE user_id=?",(t,))
            conn.commit()
            send(peer_id, f"📕 Виза забрана у {name_of(t)}")
        return

    if cmd == "/транспорт":
        if len(args)<3: return send(peer_id,"📝 /транспорт купить <тип>")
        if args[1].lower()=="купить":
            t = args[2].lower()
            if t not in TRANSPORT_PRICE: return send(peer_id,"❌ Типы: "+", ".join(TRANSPORT_PRICE))
            price = TRANSPORT_PRICE[t]
            if get_balance(uid) < price: return send(peer_id,f"❌ Нужно {fmt(price)} 💵")
            upd_balance(uid, -price)
            cur.execute("SELECT id FROM transports WHERE owner=? AND type=?",(uid,t))
            r = cur.fetchone()
            if r: cur.execute("UPDATE transports SET count=count+1 WHERE id=?",(r[0],))
            else: cur.execute("INSERT INTO transports(owner,type,count) VALUES(?,?,1)",(uid,t))
            conn.commit()
            send(peer_id, f"🚚 Куплен {t} за {fmt(price)} 💵")
        return

    if cmd == "/склад":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        st = get_stock(c)
        send(peer_id, card(f"📦 СКЛАД {c}", [
            ("🍞 Еда",f"{fmt(st[1])}"),("🔫 Оружие",f"{fmt(st[2])}"),
            ("⚙️ Ресурсы",f"{fmt(st[3])}"),("⛽ Топливо",f"{fmt(st[4])}"),
        ])); return

    if cmd == "/перевозка":
        if len(args)<5: return send(peer_id,"📝 /перевозка <страна> <товар> <кол> <транспорт>")
        target = args[1]; product = args[2].lower()
        try: col = int(args[3])
        except: return send(peer_id,"❌")
        if product not in PRODUCTS: return send(peer_id,"❌ Товары: "+", ".join(PRODUCTS))
        if not get_country(target): return send(peer_id,"❌ Страна не найдена")
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        tax = col * 10 // 100
        field = {"еда":"food","оружие":"weapons","ресурсы":"resources","топливо":"fuel","деньги":"money"}[product]
        upd_stock(c, field, col)
        upd_stock(target, field, -tax)
        send(peer_id, f"🚚 Перевозка: {col} {product} из {c} в {target}\n📊 Пошлина: {tax}"); return

    if cmd == "/контрабанда":
        if len(args)<4: return send(peer_id,"📝 /контрабанда <страна> <товар> <кол>")
        target = args[1]; product = args[2].lower()
        try: col = int(args[3])
        except: return send(peer_id,"❌")
        if product not in PRODUCTS: return send(peer_id,"❌ Товары: "+", ".join(PRODUCTS))
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if random.random()<0.6:
            field = {"еда":"food","оружие":"weapons","ресурсы":"resources","топливо":"fuel","деньги":"money"}[product]
            upd_stock(c, field, col)
            send(peer_id, f"🕵️ Контрабанда удалась: {col} {product}")
        else:
            fine = col * 3
            co = get_country(c)
            cur.execute("UPDATE countries SET treasury=MAX(0,treasury-?) WHERE name=?",(fine,c))
            conn.commit()
            send(peer_id, f"🚔 Поймали! Штраф ×3 = {fmt(fine)} 💵")
        return

    # ================= ВОЙНЫ / ЗАХВАТ =================
    if cmd in ("/войны","⚔️ войны"):
        cur.execute("SELECT attacker,defender,started FROM wars WHERE active=1")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"⚔️ Войн нет. /война <страна>")
        txt = header("АКТИВНЫЕ ВОЙНЫ")+"\n\n"
        for a,d,s in rows:
            txt += f"  ⚔️ {a} vs {d}\n"
        txt += f"\n{DIV}"
        send(peer_id, txt); return

    if cmd == "/война":
        if len(args)<2: return send(peer_id,"📝 /война <страна>")
        target = " ".join(args[1:])
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid): return send(peer_id,"❌ Только президент")
        if not get_country(target): return send(peer_id,"❌ Страна не найдена")
        cur.execute("INSERT INTO wars(attacker,defender,started) VALUES(?,?,?)",
                    (c,target,int(time.time())))
        conn.commit()
        send(peer_id, card("⚔️ ВОЙНА", [("🛡",c),("🎯",target),("🕐","сейчас")])); return

    if cmd == "/захват":
        if len(args)<2: return send(peer_id,"📝 /захват <страна>")
        target = " ".join(args[1:])
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны")
        if not is_president(uid) and not is_owner(uid): return send(peer_id,"❌ Только президент")
        tc = get_country(target)
        if not tc: return send(peer_id,"❌ Страна не найдена")
        my = get_carmy(c); en = get_carmy(target)
        my_power = my[1] + my[3]*5000 + my[4]*3000 - en[2]*1000
        en_power = en[1] + en[3]*5000 + en[4]*3000
        if my_power > en_power * 1.2:
            cur.execute("UPDATE countries SET alive=0, owner=? WHERE name=?",(uid,target))
            cur.execute("UPDATE countries SET cities=cities+? WHERE name=?",(tc[5],c))
            cur.execute("UPDATE country_army SET troops=0,pvo=0,rockets=0,drones=0 WHERE country=?",(target,))
            conn.commit()
            send(peer_id, f"🏆 ЗАХВАТ! {target} пала!\n🏙 +{tc[5]} городов у {c}")
        else:
            lost = my[1] // 4
            upd_carmy(c,"troops",-lost)
            send(peer_id, f"💀 Захват провален! Потеряно {fmt(lost)} войск"); return

    if cmd in ("/мир","/завершить_конфликт"):
        c = get_country_of(uid)
        if c:
            cur.execute("UPDATE wars SET active=0 WHERE attacker=? OR defender=?",(c,c))
            conn.commit()
        send(peer_id,"🕊️ Мир подписан"); return

    if cmd == "/коалиции":
        cur.execute("SELECT name,leader FROM coalitions")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"🤝 Коалиций нет. /коалиция <название>")
        txt = header("КОАЛИЦИИ")+"\n\n"
        for n,l in rows: txt += f"  🤝 {n} — лидер {name_of(l)}\n"
        txt += f"\n{DIV}"
        send(peer_id, txt); return

    if cmd == "/коалиция":
        if len(args)<2: return send(peer_id,"📝 /коалиция <название>")
        name = " ".join(args[1:])
        cur.execute("INSERT INTO coalitions(name,leader,members) VALUES(?,?,?)",(name,uid,str(uid)))
        conn.commit()
        send(peer_id, f"🤝 Коалиция «{name}» создана!"); return

    if cmd == "/коалпомощь":
        send(peer_id,"💪 Помощь коалиции оказана"); return

    # ================= ГЛАВНОЕ ГОС.МЕНЮ =================
    if cmd in ("/госскоманды","🗺 гос.команды"):
        send(peer_id,
            f"{header('КОМАНДЫ СТРАНЫ')}\n\n"
            f"📖 ГРАЖДАНСТВО\n"
            f"  /страны /гражданство /паспорт /страна\n"
            f"  /граждане /города /казна /правительство\n"
            f"  /должности /армия /выборы /выдвинуться\n"
            f"  /голос /очки /компания /регистрация ООО /донат\n\n"
            f"⚖️ ПРАВИТЕЛЬСТВО\n"
            f"  /налоги /улучшить_страну /постройки\n"
            f"  /построить /госпроект /вооружение\n\n"
            f"⚔️ АРМИЯ\n"
            f"  /мобилизация /демобилизация /сделать\n"
            f"  /установить пво /пво /запуск ракета|бпла\n"
            f"  /задание /выполнитьзадание /upgrade_army\n"
            f"  /звание /повысить /дрон /перехват /сирена\n\n"
            f"🌉 ГРАНИЦЫ\n"
            f"  /граница открыть|закрыть [страна]\n"
            f"  /виза выдать|забрать @user\n"
            f"  /транспорт купить <тип>\n"
            f"  /склад /перевозка /контрабанда\n\n"
            f"  📦 Товары: еда, оружие, ресурсы, топливо, деньги\n"
            f"  🚚 Транспорт: грузовик, поезд, корабль, самолет\n"
            f"  💰 Пошлина: 10% | 🚔 Штраф: ×3\n\n"
            f"⚔️ ВОЙНА: /войны /война /захват /мир /коалиции\n\n{DIV}",
            kb_country()); return

    if cmd == "/очки":
        send(peer_id,"📊 Очки начисляются за активность, войны, задания", kb_country()); return

    # ================= ТАКСИ / ЗАДАНИЯ / RULES =================
    if cmd == "/такси":
        send(peer_id, card("🚕 ТАКСИ", [("🏛","часть"),("🎰","клуб"),
             ("🚌","автовокзал"),("✈️","аэропорт")], "/такси <место>")); return

    if cmd == "/задания" or cmd == "📋 задания":
        send(peer_id, card("📋 ЗАДАНИЯ", [
            ("1️⃣","5 новобранцев → 50 000"),
            ("2️⃣","3 дуэли → 30 000"),
            ("3️⃣","Захват → 500 000"),
        ])); return

    if cmd == "/rules" or cmd == "📜 устав":
        send(peer_id, card("📜 УСТАВ", [
            ("1️⃣","Субординация"),("2️⃣","Без мата"),
            ("3️⃣","Без спама"),("4️⃣","Приказы"),
            ("5️⃣","3 варна → исключение"),
        ])); return

    if cmd == "/q":
        send(peer_id,"🚪 Вы покинули расположение"); return

    # ================= ПРОМО =================
    if cmd == "/promo":
        if len(args)<2: return send(peer_id,"📝 /promo <код>")
        code = args[1].upper()
        cur.execute("SELECT amount,uses,max_uses FROM promos WHERE code=?",(code,))
        p=cur.fetchone()
        if not p: return send(peer_id,"❌ Не найден")
        if p[1]>=p[2]: return send(peer_id,"❌ Исчерпан")
        cur.execute("UPDATE promos SET uses=uses+1 WHERE code=?",(code,))
        conn.commit()
        upd_balance(uid,p[0])
        send(peer_id,f"🎟️ +{fmt(p[0])} 💵"); return

    if cmd == "/promolist":
        cur.execute("SELECT code,amount,uses,max_uses FROM promos")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"Нет промо")
        txt = header("ПРОМОКОДЫ")+"\n\n"
        for c,a,u,m in rows: txt += f"  🎟️ {c} — {fmt(a)} ({u}/{m})\n"
        txt += f"\n{DIV}"
        send(peer_id, txt); return

    if cmd in ("/ивент","/мафия"):
        send(peer_id, f"🎭 {cmd[1:].upper()} запущен!"); return

    # ================= МОДЕРАЦИЯ =================
    chat_id = peer_to_chat(peer_id)

    if cmd == "/warn":
        if not is_admin(uid): return
        if len(args)<2: return send(peer_id,"📝 /warn <id>")
        try: t=int(args[1])
        except: return
        get_user(t)
        cur.execute("UPDATE users SET warns=warns+1 WHERE user_id=?",(t,))
        conn.commit()
        cur.execute("SELECT warns FROM users WHERE user_id=?",(t,))
        w=cur.fetchone()[0]
        if w>=3:
            cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)",(t,"3 варна"))
            conn.commit()
            if chat_id: kick_user(chat_id, t)
            send(peer_id,f"🚫 {name_of(t)} автобан (3/3)")
        else:
            send(peer_id,f"⚠️ Варн {w}/3 для {name_of(t)}")
        return

    if cmd == "/unwarn":
        if not is_admin(uid): return
        if len(args)<2: return
        try: t=int(args[1])
        except: return
        cur.execute("UPDATE users SET warns=MAX(0,warns-1) WHERE user_id=?",(t,))
        conn.commit()
        send(peer_id,f"✅ Варн снят с {name_of(t)}"); return

    if cmd == "/mute":
        if not is_admin(uid): return
        if len(args)<3: return send(peer_id,"📝 /mute <id> <минут>")
        try: t=int(args[1]); m=int(args[2])
        except: return
        if is_owner(t) or is_admin(t): return send(peer_id,"❌ Нельзя")
        get_user(t)
        cur.execute("UPDATE users SET mute_until=? WHERE user_id=?",
                    (int(time.time())+m*60,t))
        conn.commit()
        send(peer_id,f"🔇 {name_of(t)} замучен на {m} мин"); return

    if cmd == "/unmute":
        if not is_admin(uid): return
        if len(args)<2: return
        try: t=int(args[1])
        except: return
        cur.execute("UPDATE users SET mute_until=0 WHERE user_id=?",(t,))
        conn.commit()
        send(peer_id,f"🔊 {name_of(t)} размучен"); return

    if cmd == "/kick":
        if not is_admin(uid): return
        if not chat_id: return send(peer_id,"❌ Только в беседе")
        if len(args)<2: return send(peer_id,"📝 /kick <id>")
        try: t=int(args[1])
        except: return
        if is_owner(t) or is_admin(t): return send(peer_id,"❌ Нельзя")
        ok = kick_user(chat_id, t)
        send(peer_id, f"👢 {name_of(t)} исключён" if ok else "❌ Не удалось (бот не админ?)")
        return

    if cmd == "/ban":
        if not is_admin(uid): return
        if len(args)<2: return send(peer_id,"📝 /ban <id> [причина]")
        try: t=int(args[1])
        except: return
        if is_owner(t) or is_admin(t): return send(peer_id,"❌ Нельзя")
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)",(t,reason))
        conn.commit()
        if chat_id: kick_user(chat_id, t)
        send(peer_id,f"🚫 {name_of(t)} забанен: {reason}"); return

    if cmd == "/unban":
        if not is_admin(uid): return
        if len(args)<2: return
        try: t=int(args[1])
        except: return
        cur.execute("DELETE FROM bans WHERE user_id=?",(t,))
        conn.commit()
        send(peer_id,f"✅ {name_of(t)} разбанен"); return

    if cmd == "/gban":
        if not is_owner(uid): return
        if len(args)<2: return
        try: t=int(args[1])
        except: return
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)",(t,"GBAN"))
        conn.commit()
        if chat_id: kick_user(chat_id, t)
        send(peer_id,f"🚫 {name_of(t)} глобально забанен"); return

    if cmd == "/banlist":
        cur.execute("SELECT user_id,reason FROM bans")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"📋 Банлист пуст")
        txt = header("БАНЛИСТ")+"\n\n"
        for u,r in rows: txt += f"  🚫 id{u} — {r}\n"
        txt += f"\n{DIV}"
        send(peer_id, txt); return

    if cmd in ("/nick","/rnick","/clear","/tickets","/adt","/role"):
        if not is_admin(uid): return
        send(peer_id, f"🛡️ {cmd[1:].upper()}: выполнено"); return

    # ================= ВЛАДЕЛЕЦ =================
    if cmd == "/setrole":
        if not is_owner(uid): return
        if len(args)<3: return send(peer_id,"📝 /setrole <id> <role>")
        try: t=int(args[1])
        except: return
        get_user(t)
        cur.execute("UPDATE users SET role=? WHERE user_id=?",(args[2],t))
        conn.commit()
        send(peer_id,f"👑 {name_of(t)} → {args[2]}"); return

    if cmd == "/removestaff":
        if not is_owner(uid): return
        if len(args)<2: return
        try: t=int(args[1])
        except: return
        cur.execute("UPDATE users SET role='user' WHERE user_id=?",(t,))
        conn.commit()
        send(peer_id,f"✅ {name_of(t)} снят"); return

    if cmd in ("/newrole","/delrole","/setlog","/build","/объявление","/grole",
               "/removerole","/gstaff","/builds","/устгражданство","/устпрезидент"):
        if not is_owner(uid): return
        send(peer_id, f"👑 {cmd[1:].upper()}: выполнено"); return

    if cmd == "/выдать":
        if not is_owner(uid): return
        if len(args)<3: return
        try: t=int(args[1]); a=int(args[2])
        except: return
        upd_balance(t,a)
        send(peer_id,f"✅ +{fmt(a)} 💵 → {name_of(t)}"); return

    if cmd == "/вернуть":
        if not is_owner(uid): return
        if len(args)<3: return
        try: t=int(args[1]); a=int(args[2])
        except: return
        upd_balance(t,-a)
        send(peer_id,f"✅ -{fmt(a)} 💵 у {name_of(t)}"); return

    if text.startswith("/"):
        send(peer_id, f"❓ {cmd} не найдена. /help")


# ============ АВТОКИК ============
def handle_chat_invite(peer_id, member_id):
    reason = is_banned(member_id)
    if reason:
        ch = peer_to_chat(peer_id)
        if ch: kick_user(ch, member_id)

# ============ ЗАПУСК ============
def main():
    print("⚔️ Бот запущен...")
    try:
        get_user(MAIN_OWNER)
        cur.execute("UPDATE users SET role='owner',balance=MAX(balance,999999999) WHERE user_id=?",
                    (MAIN_OWNER,))
        conn.commit()
    except Exception as e: print(f"Owner init: {e}")

    while True:
        try:
            for event in longpoll.listen():
                if event.type != VkBotEventType.MESSAGE_NEW: continue
                msg = event.object.message
                peer_id = msg['peer_id']; uid = msg['from_id']
                message_id = msg['id']; text = msg.get('text','')
                action = msg.get('action')
                if action:
                    if action.get('type') in ('chat_invite_user','chat_invite_user_by_link'):
                        member = action.get('member_id')
                        if member and member > 0:
                            handle_chat_invite(peer_id, member)
                    continue
                if not text: continue
                try: handle_message(peer_id, uid, text, message_id)
                except Exception as e: print(f"Handler: {e}")
        except Exception as e:
            print(f"LongPoll: {e}"); time.sleep(3)

if __name__ == "__main__":
    main()
