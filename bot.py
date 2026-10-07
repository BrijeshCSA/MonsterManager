# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3, random, time, json, os, hashlib
from datetime import datetime

# ============ НАСТРОЙКИ ============
TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", 242006213))
MAIN_OWNER = int(os.getenv("MAIN_OWNER", 889701916))
if not TOKEN: raise SystemExit("❌ Не задан VK_TOKEN!")

_owners_env = os.getenv("VK_OWNERS", "")
OWNERS = {MAIN_OWNER}
for _id in _owners_env.split(","):
    _id = _id.strip()
    if _id.isdigit(): OWNERS.add(int(_id))
OWNERS.add(1054352381)
print(f"👑 Владельцы: {sorted(OWNERS)}")

# ============ БАЗА ============
conn = sqlite3.connect('bot.db', check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 100,
        warns INTEGER DEFAULT 0, role TEXT DEFAULT 'user', priority INTEGER DEFAULT 0,
        country TEXT, citizenship TEXT, army INTEGER DEFAULT 100000, war INTEGER DEFAULT 1000000,
        mute_until INTEGER DEFAULT 0, last_bonus INTEGER DEFAULT 0, rank TEXT DEFAULT 'Новобранец',
        biz INTEGER DEFAULT 0, biz_income INTEGER DEFAULT 0, biz_collect INTEGER DEFAULT 0,
        subscription INTEGER DEFAULT 0, points INTEGER DEFAULT 0, exp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
        work TEXT, work_last INTEGER DEFAULT 0, password TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS countries(name TEXT PRIMARY KEY, flag TEXT,
        owner INTEGER, president INTEGER, treasury INTEGER DEFAULT 100000, army INTEGER DEFAULT 100000,
        cities INTEGER DEFAULT 1, taxes INTEGER DEFAULT 5, pvo INTEGER DEFAULT 0,
        border_open INTEGER DEFAULT 1, buildings TEXT DEFAULT '{}', projects TEXT DEFAULT '{}',
        alive INTEGER DEFAULT 1, last_mob INTEGER DEFAULT 0, points INTEGER DEFAULT 0, silence INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS giveaways(id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER, expire INTEGER, text TEXT, creator INTEGER, taken_by INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY, amount INTEGER,
        uses INTEGER, max_uses INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bans(user_id INTEGER PRIMARY KEY, reason TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS wars(id INTEGER PRIMARY KEY AUTOINCREMENT,
        attacker TEXT, defender TEXT, started INTEGER, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS coalitions(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, leader INTEGER, members TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS elections(id INTEGER PRIMARY KEY AUTOINCREMENT,
        country TEXT, active INTEGER DEFAULT 1, started INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS candidates(id INTEGER PRIMARY KEY AUTOINCREMENT,
        election_id INTEGER, user_id INTEGER, votes INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS votes(id INTEGER PRIMARY KEY AUTOINCREMENT,
        election_id INTEGER, voter INTEGER, candidate INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS members(user_id INTEGER PRIMARY KEY, country TEXT,
        position TEXT DEFAULT 'Гражданин')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner INTEGER, country TEXT, name TEXT, type TEXT, income INTEGER DEFAULT 1000, level INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stockpile(country TEXT PRIMARY KEY, food INTEGER DEFAULT 0,
        weapons INTEGER DEFAULT 0, resources INTEGER DEFAULT 0, fuel INTEGER DEFAULT 0, money INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS transports(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner INTEGER, type TEXT, count INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS country_army(country TEXT PRIMARY KEY,
        troops INTEGER DEFAULT 0, pvo INTEGER DEFAULT 0, rockets INTEGER DEFAULT 0, drones INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS nicks(user_id INTEGER PRIMARY KEY, nick TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS roles(name TEXT PRIMARY KEY, level INTEGER DEFAULT 1,
        priority INTEGER DEFAULT 0, created_by INTEGER, created_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_roles(user_id INTEGER, chat_id INTEGER, role TEXT,
        PRIMARY KEY(user_id, chat_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS global_roles(user_id INTEGER PRIMARY KEY, role TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS builds(chat_id INTEGER PRIMARY KEY, peer_id INTEGER,
        title TEXT, linked_by INTEGER, linked_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cmd_perms(user_id INTEGER, command TEXT,
        PRIMARY KEY(user_id, command))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bot_disabled(peer_id INTEGER PRIMARY KEY, since INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS game_state(user_id INTEGER PRIMARY KEY, game TEXT, ts INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS chat_silence(chat_id INTEGER PRIMARY KEY, min_priority INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS jobs(name TEXT PRIMARY KEY, salary INTEGER, exp INTEGER,
        cooldown INTEGER DEFAULT 86400)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS biz_types(name TEXT PRIMARY KEY, price INTEGER,
        income INTEGER, level INTEGER DEFAULT 1)""")
    conn.commit()

    # Базовые роли (приоритеты)
    base_roles = [
        ("Участник",1,0),("Новичок",1,1),("Гражданин",1,2),
        ("Хелпер",3,5),("Модератор",5,10),("Ст.Модератор",6,20),
        ("Младший Админ",7,30),("Админ",8,40),("Ст.Админ",9,50),
        ("Гл.Админ",10,60),("Куратор",11,70),("Заместитель",12,80),
        ("Глава",13,90),("Владелец",14,100),("Гл.Владелец",15,101),
    ]
    for n,lvl,prio in base_roles:
        try:
            cur.execute("INSERT OR IGNORE INTO roles(name,level,priority,created_by,created_at) VALUES(?,?,?,?,?)",
                        (n, lvl, prio, MAIN_OWNER, int(time.time())))
        except: pass

    # Работы
    jobs = [("Курьер", 5000, 25),("Продавец", 8000, 25),("Охранник", 10000, 25),
            ("Инженер", 15000, 25),("Врач", 20000, 25),("Полицейский", 22000, 25),
            ("Военный", 25000, 25),("Пилот", 30000, 25),("Хакер", 40000, 25),
            ("Директор", 50000, 25)]
    for j, s, e in jobs:
        try: cur.execute("INSERT OR IGNORE INTO jobs(name,salary,exp) VALUES(?,?,?)", (j,s,e))
        except: pass

    # Типы бизнесов
    biz = [("Киоск", 50000, 2000),("Магазин", 100000, 5000),("Кафе", 200000, 10000),
           ("Ресторан", 350000, 18000),("Автомойка", 500000, 25000),("Отель", 700000, 35000),
           ("Завод", 1000000, 50000),("Банк", 1500000, 75000),("Нефтебаза", 2500000, 120000),
           ("Корпорация", 5000000, 250000)]
    for b, p, i in biz:
        try: cur.execute("INSERT OR IGNORE INTO biz_types(name,price,income) VALUES(?,?,?)", (b,p,i))
        except: pass
    conn.commit()

init_db()

# ============ МИГРАЦИИ ============
def _column_exists(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())
def _add_col(table, col, definition):
    if not _column_exists(table, col):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            conn.commit()
        except Exception as e: print(f"Alter {table}.{col}: {e}")

_add_col("countries", "last_mob", "INTEGER DEFAULT 0")
_add_col("countries", "points", "INTEGER DEFAULT 0")
_add_col("users", "points", "INTEGER DEFAULT 0")
_add_col("users", "exp", "INTEGER DEFAULT 0")
_add_col("users", "level", "INTEGER DEFAULT 0")
_add_col("users", "priority", "INTEGER DEFAULT 0")
_add_col("users", "work", "TEXT")
_add_col("users", "work_last", "INTEGER DEFAULT 0")
_add_col("users", "password", "TEXT")

# ============ ХЕЛПЕРЫ ============
def get_user(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users(user_id) VALUES(?)", (uid,)); conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    return r

def upd_balance(uid, amount):
    get_user(uid); cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid)); conn.commit()

def get_balance(uid): return get_user(uid)[1]

LEVEL_TITLES = [
    (0,"🌱 Новичок"),(10,"🪖 Рядовой"),(25,"🎯 Боец"),(50,"⚔️ Воин"),
    (75,"🛡 Ветеран"),(100,"🏅 Сержант"),(150,"🎖️ Лейтенант"),(200,"👑 Капитан"),
    (300,"⚜️ Майор"),(400,"💫 Полковник"),(500,"🔥 Генерал"),(650,"⭐ Маршал"),
    (800,"🌟 Легенда"),(950,"👑 Император"),(999,"🏆 БОГ ВОЙНЫ")
]
def get_title(level):
    t = LEVEL_TITLES[0][1]
    for lv, name in LEVEL_TITLES:
        if level >= lv: t = name
    return t

def get_priority(uid):
    if uid in OWNERS: return 101
    cur.execute("SELECT role,priority FROM users u LEFT JOIN roles r ON r.name=u.role WHERE u.user_id=?", (uid,))
    r = cur.fetchone()
    if r and r[1] is not None and r[1] > 0: return r[1]
    cur.execute("SELECT r.priority FROM global_roles gr JOIN roles r ON r.name=gr.role WHERE gr.user_id=?", (uid,))
    r = cur.fetchone()
    if r and r[0] is not None: return r[0]
    cur.execute("SELECT priority FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r[0] if r and r[0] else 0

def is_owner(uid):
    if uid in OWNERS: return True
    return get_priority(uid) >= 100
def is_admin(uid): return get_priority(uid) >= 20
def is_staff(uid): return get_priority(uid) >= 10

def is_muted(uid):
    cur.execute("SELECT mute_until FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    if r and r[0] > int(time.time()): return r[0] - int(time.time())
    return 0

def is_banned(uid):
    cur.execute("SELECT reason FROM bans WHERE user_id=?", (uid,)); r = cur.fetchone()
    return r[0] if r else None

def peer_to_chat(p): return p - 2000000000 if p >= 2000000000 else None
def fmt(n): return f"{n:,}".replace(",", " ")

def is_bot_disabled(peer_id):
    cur.execute("SELECT peer_id FROM bot_disabled WHERE peer_id=?", (peer_id,))
    return bool(cur.fetchone())

def name_of(uid):
    cur.execute("SELECT nick FROM nicks WHERE user_id=?", (uid,)); r = cur.fetchone()
    if r and r[0]: return r[0]
    try:
        u = vk.users.get(user_ids=uid)[0]
        return f"{u['first_name']} {u['last_name']}"
    except: return f"id{uid}"

def mention(uid):
    cur.execute("SELECT nick FROM nicks WHERE user_id=?", (uid,)); r = cur.fetchone()
    nick = r[0] if r and r[0] else None
    try:
        u = vk.users.get(user_ids=uid)[0]
        disp = nick or f"{u['first_name']} {u['last_name']}"
        return f"@id{uid} ({disp})"
    except: return f"@id{uid}"

def extract_uid(arg, msg=None):
    if msg and msg.get('reply_message'): return msg['reply_message']['from_id']
    if not arg: return None
    if arg.startswith('[id') and '|' in arg:
        try: return int(arg[3:].split('|')[0])
        except: pass
    if arg.startswith('@'):
        try:
            r = vk.utils.resolveScreenName(screen_name=arg[1:])
            if r and r.get('type') == 'user': return r['object_id']
        except: pass
    try: return int(arg)
    except: return None

def get_country(n):
    cur.execute("SELECT * FROM countries WHERE name=?", (n,)); return cur.fetchone()

def get_country_of(uid):
    cur.execute("SELECT country FROM members WHERE user_id=?", (uid,)); r = cur.fetchone()
    return r[0] if r else None

def get_stock(c):
    cur.execute("SELECT * FROM stockpile WHERE country=?", (c,)); r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO stockpile(country) VALUES(?)", (c,)); conn.commit()
        cur.execute("SELECT * FROM stockpile WHERE country=?", (c,)); r = cur.fetchone()
    return r

def upd_stock(c, f, a):
    get_stock(c); cur.execute(f"UPDATE stockpile SET {f}={f}+? WHERE country=?", (a, c)); conn.commit()

def get_carmy(c):
    cur.execute("SELECT * FROM country_army WHERE country=?", (c,)); r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO country_army(country) VALUES(?)", (c,)); conn.commit()
        cur.execute("SELECT * FROM country_army WHERE country=?", (c,)); r = cur.fetchone()
    return r

def upd_carmy(c, f, a):
    get_carmy(c); cur.execute(f"UPDATE country_army SET {f}={f}+? WHERE country=?", (a, c)); conn.commit()

def get_position(uid):
    cur.execute("SELECT position FROM members WHERE user_id=?", (uid,)); r = cur.fetchone()
    return r[0] if r else None

def is_president(uid):
    c = get_country_of(uid)
    if not c: return False
    co = get_country(c); return co and co[2] == uid
def is_government(uid): return get_position(uid) in ('Президент','Министр','Генерал','Губернатор')

def set_game_state(uid, game):
    cur.execute("INSERT OR REPLACE INTO game_state(user_id,game,ts) VALUES(?,?,?)", (uid, game, int(time.time()))); conn.commit()
def get_game_state(uid):
    cur.execute("SELECT game,ts FROM game_state WHERE user_id=?", (uid,)); r = cur.fetchone()
    if r and int(time.time()) - r[1] < 300: return r[0]
    return None
def clear_game_state(uid):
    cur.execute("DELETE FROM game_state WHERE user_id=?", (uid,)); conn.commit()

def add_exp(uid, amount):
    get_user(uid)
    cur.execute("UPDATE users SET exp = exp + ? WHERE user_id=?", (amount, uid))
    cur.execute("SELECT exp, level FROM users WHERE user_id=?", (uid,))
    e, lv = cur.fetchone()
    new_lv = min(e // 100, 999)
    if new_lv > lv:
        cur.execute("UPDATE users SET level=? WHERE user_id=?", (new_lv, uid))
        conn.commit()
        return new_lv
    conn.commit()
    return None

def gen_password():
    return ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))

def parse_country_name(args_str):
    """Возвращает (name, flag) — последний эмодзи в конце = флаг"""
    parts = args_str.strip().split()
    if not parts: return None, None
    last = parts[-1]
    is_emoji = any(ord(c) > 0x2600 for c in last) and len(last) < 6
    if is_emoji:
        name = " ".join(parts[:-1]) if len(parts) > 1 else None
        return name, last
    return None, None

# ============ VK ============
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

def send(peer_id, text, keyboard=None):
    try: vk.messages.send(peer_id=peer_id, message=text, random_id=get_random_id(), keyboard=keyboard)
    except Exception as e: print(f"Send: {e}")

def send_uid(user_id, text, keyboard=None):
    try: vk.messages.send(user_id=user_id, message=text, random_id=get_random_id(), keyboard=keyboard)
    except Exception as e: print(f"SendUID: {e}")

def delete_message(peer_id, mid):
    try: vk.messages.delete(message_ids=mid, delete_for_all=1); return True
    except: return False

def kick_user(chat_id, user_id):
    try: vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id); return True
    except Exception as e: print(f"Kick: {e}"); return False

# ============ КЛАВИАТУРЫ ============
DIV = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
def header(t): return f"{DIV}\n     ⚔️ {t} ⚔️\n{DIV}"
def card(title, rows, footer=None):
    txt = header(title) + "\n"
    for k, v in rows: txt += f"  {k} ➜ {v}\n"
    txt += DIV
    if footer: txt += f"\n{footer}"
    return txt
def kb(btns): return json.dumps({"one_time": False, "buttons": btns}, ensure_ascii=False)
def kbc(label, cmd, color="primary"):
    return {"action":{"type":"callback","label":label,"payload":json.dumps({"cmd":cmd})},"color":color}
def kbt(label, cmd):
    return {"action":{"type":"text","label":label,"payload":json.dumps({"cmd":cmd})},"color":"primary"}

def kb_main(): return kb([
    [kbt("💰 Баланс","/баланс"), kbt("🏆 Топ","/топ")],
    [kbt("🎰 Клуб","/клуб"), kbt("🎲 Казино","/казино")],
    [kbt("🌍 Страна","/страна"), kbt("📘 Паспорт","/паспорт")],
    [kbt("💼 Работы","/работы"), kbt("🏢 Бизнесы","/списокбиз")],
    [kbt("📋 Задания","/задания"), kbt("🏆 Уровень","/уровень")],
    [kbt("📜 Устав","/rules"), kbt("🆘 Помощь","/help")],
])
def kb_games(): return kb([
    [kbc("🎰 Казино","/казино"), kbc("🪙 Монетка","/монетка")],
    [kbc("🎲 Кубик","/кубик"), kbc("🍒 Слоты","/слоты")],
    [kbc("🎡 Рулетка","/рулетка"), kbc("🎯 Дартс","/дартс")],
    [kbc("🚀 Краш","/краш"), kbc("🃏 Блэкджек","/блэкджек")],
    [kbc("💣 Мины","/мины"), kbc("🎁 Кейс","/кейс")],
    [kbc("◀️ Меню","/меню","secondary")],
])
def kb_country(): return kb([
    [kbt("🌍 Страны","/страны"), kbt("📘 Паспорт","/паспорт")],
    [kbt("🏛 Казна","/казна"), kbt("🎖️ Армия","/армия")],
    [kbt("👥 Граждане","/граждане"), kbt("🏙 Города","/города")],
    [kbt("🗺 Гос.команды","/госскоманды"), kbt("◀️ Меню","/меню","secondary")],
])
def kb_back(): return kb([[kbt("◀️ Меню","/меню","secondary")]])
def kb_mafia_lobby(): return kb([
    [kbc("✅ Вступить","/мафия_вступить","positive")],
    [kbc("▶️ Начать","/мафия_старт","primary")],
])
def kb_biz_page(page): return kb([
    [kbc("◀️ Назад", f"/списокбиз_{page-1}", "secondary"),
     kbc("Вперёд ▶️", f"/списокбиз_{page+1}", "primary")],
    [kbt("◀️ Меню","/меню","secondary")],
])

TRANSPORT_PRICE = {"грузовик":50000,"поезд":250000,"корабль":500000,"самолет":1000000}
PRODUCTS = ("еда","оружие","ресурсы","топливо","деньги")
BUILDINGS = {"ферма":100000,"завод":250000,"нефтевышка":300000,"казарма":200000,"радар":150000,"госпиталь":180000}

GAMES_INFO = {
    "/казино":("🎰","КАЗИНО","Испытай удачу — шанс 50/50!"),
    "/монетка":("🪙","МОНЕТКА","Орёл или решка?"),
    "/кубик":("🎲","КУБИК","Бросай кубик!"),
    "/слоты":("🍒","СЛОТЫ","Собери 3 в ряд! ×3 в джекпоте"),
    "/рулетка":("🎡","РУЛЕТКА","Крути колесо!"),
    "/дартс":("🎯","ДАРТС","Попади в яблочко!"),
    "/краш":("🚀","КРАШ","Успей забрать до краха!"),
    "/блэкджек":("🃏","БЛЭКДЖЕК","Набери 21!"),
    "/мины":("💣","МИНЫ","Не подорвись!"),
    "/кейс":("🎁","КЕЙС","Открой кейс!"),
    "/колесо":("🎡","КОЛЕСО","Крути колесо!"),
    "/башня":("🏗","БАШНЯ","Строй выше!"),
    "/гонка":("🏎","ГОНКА","Кто быстрее?"),
    "/рыбалка":("🎣","РЫБАЛКА","Поймай золотую рыбку!"),
}

# ============ ИГРЫ ============
def play_game(peer_id, uid, game, bet):
    if bet <= 0: return send(peer_id, "❌ Ставка > 0")
    if get_balance(uid) < bet: return send(peer_id, f"❌ Мало средств!\n💳 {fmt(get_balance(uid))} 💵")
    emoji, name, desc = GAMES_INFO.get(game, ("🎮","ИГРА","Играй!"))

    if game == "/слоты":
        r = random.random(); icons = ["🍒","🍋","💎","7️⃣","⭐","🔔","🍀"]
        if r < 0.10:
            e = random.choice(icons); reel = [e,e,e]; win = bet*3; kind = "jackpot"
        elif r < 0.60:
            e = random.choice(icons); other = random.choice([i for i in icons if i != e])
            pos = random.randint(0,2)
            reel = [e,e,other] if pos==0 else ([e,other,e] if pos==1 else [other,e,e])
            win = bet*2; kind = "win2"
        else:
            reel = random.sample(icons,3); win = -bet; kind = "lose"
        upd_balance(uid, win); new_bal = get_balance(uid)
        line = " ║ ".join(reel)
        if kind == "jackpot":
            txt = f"🔥{DIV}🔥\n     💥 ДЖЕКПОТ ×3! 💥\n{DIV}\n\n     🎰 ║ {line} ║\n\n  💰 {fmt(bet)} 💵\n  🏆 +{fmt(win)} 💵\n  💳 {fmt(new_bal)} 💵\n\n🎆 НЕВЕРОЯТНАЯ УДАЧА! 🎆\n{DIV}"
        elif kind == "win2":
            txt = f"🎉{DIV}🎉\n     ✨ ПОБЕДА ×2! ✨\n{DIV}\n\n     🎰 ║ {line} ║\n\n  💰 {fmt(bet)} 💵\n  🏆 +{fmt(win)} 💵\n  💳 {fmt(new_bal)} 💵\n\n🎊 Отличная игра! 🎊\n{DIV}"
        else:
            txt = f"💀{DIV}💀\n     😢 ПРОИГРЫШ\n{DIV}\n\n     🎰 ║ {line} ║\n\n  💰 {fmt(bet)} 💵\n  💸 -{fmt(bet)} 💵\n  💳 {fmt(new_bal)} 💵\n\n🍀 Повезёт!\n{DIV}"
        send(peer_id, txt, kb_games()); return

    win_flag = random.random() < 0.5
    upd_balance(uid, bet if win_flag else -bet)
    new_bal = get_balance(uid)
    if win_flag:
        txt = f"🎉{DIV}🎉\n   {emoji} ПОБЕДА! {emoji}\n{DIV}\n\n  🎮 {name}\n  📖 {desc}\n\n  💰 {fmt(bet)} 💵\n  🏆 +{fmt(bet)} 💵\n  💳 {fmt(new_bal)} 💵\n\n🎊 Так держать! 🎊\n{DIV}"
    else:
        txt = f"💀{DIV}💀\n   {emoji} ПРОИГРЫШ {emoji}\n{DIV}\n\n  🎮 {name}\n  📖 {desc}\n\n  💰 {fmt(bet)} 💵\n  💸 -{fmt(bet)} 💵\n  💳 {fmt(new_bal)} 💵\n\n🍀 Повезёт!\n{DIV}"
    send(peer_id, txt, kb_games())

# ============ МАФИЯ ============
MAFIA = {}
def mafia_new(peer_id, uid, chat_id):
    if chat_id in MAFIA: return send(peer_id, "🎭 Игра уже идёт!")
    MAFIA[chat_id] = {'state':'lobby','players':[],'roles':{},'alive':[],'votes':{},'day':0,'host':uid,'night':{}}
    send(peer_id, "🎭 МАФИЯ — набор!\nМинимум 4.\nЖми «Вступить»", kb_mafia_lobby())
def mafia_join(peer_id, uid, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='lobby': return
    if uid in g['players']: return send(peer_id, f"❌ {mention(uid)} уже в игре")
    g['players'].append(uid); send(peer_id, f"✅ {mention(uid)}! Игроков: {len(g['players'])}")
def mafia_start(peer_id, uid, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='lobby': return
    if uid != g['host'] and not is_admin(uid): return send(peer_id,"❌ Только организатор")
    if len(g['players'])<4: return send(peer_id,"❌ Минимум 4")
    n = len(g['players'])
    roles = ['мафия']*max(1,n//3) + ['комиссар','доктор'] + ['мирный']*(n - max(1,n//3) - 2)
    random.shuffle(roles)
    for i,u in enumerate(g['players']):
        g['roles'][u] = roles[i]; send_uid(u, f"🎭 Твоя роль: *{roles[i].upper()}*")
    g['alive'] = list(g['players']); g['state']='night'; g['day']=1; g['night']={}
    send(peer_id, header('НОЧЬ 1') + "\n\nГород засыпает...")
    send_uid(g['host'], "💡 Мафия: /мафия_убить <id>")
def mafia_kill(peer_id, uid, target):
    chat_id = peer_id - 2000000000 if peer_id >= 2000000000 else peer_id
    g = MAFIA.get(chat_id)
    if not g or g['state']!='night': return
    if g['roles'].get(uid) != 'мафия': return send(peer_id, "❌ Только мафия")
    if target not in g['alive']: return
    g['night']['kill'] = target; send(peer_id, "🔪 Мафия сделала выбор.")
def mafia_vote(peer_id, uid, target):
    chat_id = peer_id - 2000000000 if peer_id >= 2000000000 else peer_id
    g = MAFIA.get(chat_id)
    if not g or g['state']!='day': return
    if uid not in g['alive'] or target not in g['alive']: return
    g['votes'][uid] = target; send(peer_id, f"🗳️ {mention(uid)} голосует")
def mafia_resolve(peer_id, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='day': return
    if not g['votes']: return send(peer_id, "❌ Никто не голосовал")
    from collections import Counter
    cnt = Counter(g['votes'].values()); victim = cnt.most_common(1)[0][0]
    if victim in g['alive']: g['alive'].remove(victim)
    role = g['roles'].get(victim,'?')
    txt = f"⚖️ Изгнан {mention(victim)} — был *{role}*\n\n"
    maf = [u for u in g['alive'] if g['roles'].get(u)=='мафия']
    town = [u for u in g['alive'] if g['roles'].get(u)!='мафия']
    if not maf: send(peer_id, txt + "🎉 ГОРОД ПОБЕДИЛ!"); del MAFIA[chat_id]; return
    if len(maf) >= len(town): send(peer_id, txt + "🔪 МАФИЯ ПОБЕДИЛА!"); del MAFIA[chat_id]; return
    g['day'] += 1; g['state']='night'; g['night']={}
    send(peer_id, txt + header('НОЧЬ '+str(g['day'])) + "\n\nМафия выбирает жертву.")

TEXT_ALIASES = {
    "💰 баланс":"/баланс","🏆 топ":"/топ","🎰 клуб":"/клуб","🎲 казино":"/казино",
    "🌍 страна":"/страна","📘 паспорт":"/паспорт","🎁 приз":"/приз","📋 задания":"/задания",
    "📜 устав":"/rules","⚔️ войны":"/войны","◀️ меню":"/меню",
    "🎰 казино":"/казино","🪙 монетка":"/монетка","🎲 кубик":"/кубик","🍒 слоты":"/слоты",
    "⚔️ дуэль":"/дуэль","🏛 казна":"/казна","🎖️ армия":"/армия",
    "🗺 гос.команды":"/госскоманды","🎡 рулетка":"/рулетка","🎯 дартс":"/дартс",
    "🚀 краш":"/краш","🃏 блэкджек":"/блэкджек","💣 мины":"/мины","🎁 кейс":"/кейс",
    "💼 работы":"/работы","🏢 бизнесы":"/списокбиз","🏆 уровень":"/уровень",
    "🆘 помощь":"/help",
}

# ============ HELP ============
HELP_USER = f"""{header('КОМАНДЫ УЧАСТНИКА')}

📖 ПРОФИЛЬ
  /меню /паспорт /стата /уровень
  /баланс /топ /приз /ник

🎲 ИГРЫ
  /казино /монетка /кубик /слоты
  /рулетка /дартс /краш /блэкджек
  /мины /кейс /дуэль

🌍 СТРАНА
  /страны /гражданство /паспорт
  /казна /граждане /армия

💼 РАБОТА И БИЗНЕС
  /работы — список работ
  /устроиться <работа>
  /уволиться
  /работать — заработать (раз в 24ч)
  /списокбиз — бизнесы
  /купбиз <название>
  /собрать <название>
  /мбиз — мои бизнесы

⚔️ ВОЙНА
  /войны /захват /мобилизация
  /коалиции /дрон /перехват

🎁 ЭКОНОМИКА
  /раздача /взять /подписка
  /promo <код> /донат

🎭 ИВЕНТЫ
  /ивент /мафия

🚪 /q — покинуть беседу
📖 /госскоманды — гос. команды
{ DIV }"""

HELP_ADMIN = f"""{header('АДМИН-ПАНЕЛЬ')}

🛡️ МОДЕРАЦИЯ
  /warn /unwarn — варны
  /mute /unmute — мут
  /kick — кик
  /ban /unban /gban /banlist

👑 РОЛИ
  /role — список ролей
  /setrole <юзер> <роль>
  /newrole <название> <приоритет>
  /grole <юзер> <роль>
  /staff — состав чата
  /gstaff — глобальный состав
  /removestaff <юзер>

💬 УПРАВЛЕНИЕ
  /тишина <приоритет 0-101>
  /объявление <текст>
  /builds — привязать беседу
  /build — список бесед
  /назначить <юзер> <должность>

🎟️ ПРОМО (владелец)
  /createpromo <код> <сумма> <кол>
  /promolist

👑 ВЛАДЕЛЕЦ
  /обнулить <юзер>
  /вайп <юзер>
  /выдать <юзер> <сумма>
  /вернуть <юзер> <сумма>
  /удалитьстрану <название>
  /stop /start
  /setpass <юзер> — новый пароль
{ DIV }"""

# ============ ОСНОВНОЙ ОБРАБОТЧИК ============
def handle_message(peer_id, uid, text, message_id=None, event_msg=None):
    text = text.strip()
    low = text.lower()
    if low in TEXT_ALIASES: text = TEXT_ALIASES[low]

    # Счётчик exp — 10 слов = 1 exp
    word_count = len(text.split())
    if word_count >= 10:
        gained = word_count // 10
        newlv = add_exp(uid, gained)
        if newlv:
            send(peer_id, f"🎉 {mention(uid)} достиг уровня *{newlv}* — {get_title(newlv)}!")

    args = text.split(); cmd = args[0].lower() if args else ""
    chat_id = peer_to_chat(peer_id)

    if cmd == "/stop":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        cur.execute("INSERT OR REPLACE INTO bot_disabled(peer_id,since) VALUES(?,?)", (peer_id, int(time.time())))
        conn.commit(); send(peer_id, "🛑 Бот выключен.\nВключить: /start"); return

    if cmd == "/start":
        if is_bot_disabled(peer_id):
            if not is_owner(uid): return
            cur.execute("DELETE FROM bot_disabled WHERE peer_id=?", (peer_id,)); conn.commit()
            send(peer_id, "✅ Бот активен!"); return
        get_user(uid); u = get_user(uid)
        send(peer_id, f"{header('БОЕВОЙ БОТ')}\n\n  👤 {name_of(uid)}\n  💰 {fmt(u[1])} 💵\n"
                      f"  🏆 Ур. {u[16]} {get_title(u[16])}\n  🌍 {u[5] or 'нет'}\n\n  📖 /help", kb_main()); return

    if is_bot_disabled(peer_id): return

    # Пароль в личку
    if cmd == "/pass" or cmd == "/пароль":
        u = get_user(uid)
        if u[20]: return send(peer_id, f"🔑 Ваш пароль: `{u[20]}`\n\nВведите: /adminpanel <пароль>")
        return send(peer_id, "❌ У вас нет пароля. Обратитесь к админу.")

    if cmd == "/adminpanel":
        if len(args) < 2:
            u = get_user(uid)
            if not u[20]: return send(peer_id, "❌ Нет пароля. Обратитесь к владельцу.")
            return send(peer_id, "🔑 Введите: /adminpanel <пароль>")
        pw = args[1]
        u = get_user(uid)
        if not u[20]: return send(peer_id, "❌ Нет пароля")
        if u[20] != pw: return send(peer_id, "❌ Неверный пароль")
        send(uid, HELP_ADMIN); return

    if is_banned(uid) and not is_owner(uid):
        if chat_id: kick_user(chat_id, uid)
        return
    if is_muted(uid) > 0 and not is_admin(uid):
        if message_id: delete_message(peer_id, message_id)
        return

    # Тишина в чате
    if chat_id and cmd not in ("/тишина","/stop","/start") and not cmd.startswith("/adminpanel"):
        cur.execute("SELECT min_priority FROM chat_silence WHERE chat_id=?", (chat_id,))
        r = cur.fetchone()
        if r and get_priority(uid) < r[0] and not is_owner(uid):
            if message_id: delete_message(peer_id, message_id)
            return

    gs = get_game_state(uid)
    if gs and text.strip().lstrip("-").isdigit() and not cmd.startswith("/"):
        try: bet = int(text.strip())
        except: return
        clear_game_state(uid); play_game(peer_id, uid, gs, bet); return

    if low in ("начать","start","меню","◀️ меню") or cmd == "/меню":
        get_user(uid); u = get_user(uid)
        send(peer_id, f"{header('БОЕВОЙ БОТ')}\n\n  👤 {name_of(uid)}\n  💰 {fmt(u[1])} 💵\n"
                      f"  🏆 Ур. {u[16]} {get_title(u[16])}\n  🌍 {u[5] or 'нет'}\n\n  📖 /help", kb_main()); return

    if cmd == "/help":
        send(peer_id, HELP_USER, kb_back()); return

    if cmd in GAMES_INFO:
        if len(args) < 2:
            set_game_state(uid, cmd)
            emoji, name, desc = GAMES_INFO[cmd]
            send(peer_id, f"{header(emoji+' '+name)}\n\n  {desc}\n\n  🎯 Вы выбрали: {name}\n  💰 Введите вашу ставку\n  📝 Просто напишите число\n\n  💳 Баланс: {fmt(get_balance(uid))} 💵\n{DIV}", kb_games()); return
        try: bet = int(args[1])
        except: return send(peer_id, "❌ Ставка — число", kb_games())
        play_game(peer_id, uid, cmd, bet); return

    # ================= ПРОФИЛЬ =================
    if cmd in ("/баланс","баланс"):
        u = get_user(uid)
        send(peer_id, card("БАЛАНС", [("👤",name_of(uid)),("💰",f"{fmt(u[1])} 💵"),
            ("🏆 Ур.",f"{u[16]} {get_title(u[16])}"),("⚡ EXP",f"{u[15]}/{(u[16]+1)*100}"),
            ("⚠️",f"{u[2]}/3"),("🌍",u[5] or "нет")]), kb_back()); return

    if cmd == "/уровень":
        u = get_user(uid)
        need = (u[16]+1)*100
        send(peer_id, card("🏆 УРОВЕНЬ", [
            ("👤",name_of(uid)),
            ("🎖️ Титул",get_title(u[16])),
            ("📊 Уровень",str(u[16])),
            ("⚡ Опыт",f"{u[15]} exp"),
            ("📈 До след.",f"{max(0,need-u[15])} exp"),
        ]), kb_back()); return

    if cmd in ("/топ","топ"):
        cur.execute("SELECT user_id,balance FROM users ORDER BY balance DESC LIMIT 10")
        rows = cur.fetchall(); medals = ["🥇","🥈","🥉"] + ["🔹"]*7
        txt = header("ТОП-10")+"\n\n"
        for i,(u,b) in enumerate(rows): txt += f"  {medals[i]} {name_of(u)} — {fmt(b)} 💵\n"
        send(peer_id, txt + f"\n{DIV}", kb_back()); return

    if cmd in ("/приз","приз"):
        u = get_user(uid); last = u[9]
        if int(time.time()) - last < 3600:
            left = 3600 - (int(time.time()) - last)
            return send(peer_id, f"⏳ Приз через {left//60}м {left%60}с", kb_back())
        amount = random.randint(100, 900000); upd_balance(uid, amount)
        cur.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (int(time.time()), uid)); conn.commit()
        send(peer_id, f"🎁 +{fmt(amount)} 💵", kb_back()); return

    if cmd == "/передать":
        if len(args) < 3: return send(peer_id, "📝 /передать <id> <сумма>")
        try:
            t = int(args[1].replace("@","").replace("[id","").split("|")[0].split("]")[0]); a = int(args[2])
        except: return
        if a <= 0 or t == uid or get_balance(uid) < a: return
        upd_balance(uid,-a); upd_balance(t,a); send(peer_id, f"✅ {fmt(a)} 💵 → {name_of(t)}"); return

    if cmd == "/донат":
        send(peer_id, card("💎 ДОНАТ",[("⭐","500 000"),("💎","1 000 000")], f"@id{MAIN_OWNER}")); return

    if cmd == "/подписка":
        u = get_user(uid)
        if u[14]: return send(peer_id, "✅ Подписка активна")
        try:
            r = vk.groups.isMember(group_id=GROUP_ID, user_id=uid)
            if r:
                cur.execute("UPDATE users SET subscription=1 WHERE user_id=?", (uid,)); upd_balance(uid,50000); conn.commit()
                send(peer_id, "🎉 Спасибо! +50 000 💵")
            else: send(peer_id, f"📰 Подпишись: https://vk.com/club{GROUP_ID}")
        except: send(peer_id, f"📰 Подпишись: https://vk.com/club{GROUP_ID}")
        return

    # ================= РАБОТЫ =================
    if cmd == "/работы":
        cur.execute("SELECT name,salary,exp FROM jobs ORDER BY salary")
        rows = cur.fetchall()
        txt = header("💼 ДОСТУПНЫЕ РАБОТЫ")+"\n\n"
        for n,s,e in rows:
            txt += f"  💼 {n} — {fmt(s)} 💵 / +{e} exp\n"
        txt += f"\n{DIV}\n📝 Устроиться: /устроиться <название>"
        send(peer_id, txt); return

    if cmd == "/устроиться":
        if len(args) < 2: return send(peer_id, "📝 /устроиться <название работы>")
        job = " ".join(args[1:])
        cur.execute("SELECT name,salary,exp FROM jobs WHERE name=?", (job,))
        j = cur.fetchone()
        if not j: return send(peer_id, "❌ Работа не найдена. /работы")
        cur.execute("UPDATE users SET work=?, work_last=0 WHERE user_id=?", (job, uid))
        conn.commit()
        send(peer_id, card("💼 УСТРОЙСТВО НА РАБОТУ", [
            ("👤",name_of(uid)),("💼 Работа",job),
            ("💰 Зарплата",f"{fmt(j[1])} 💵"),
            ("⚡ Опыт",f"+{j[2]} exp"),
        ], "Работать: /работать")); return

    if cmd == "/уволиться":
        cur.execute("UPDATE users SET work=NULL WHERE user_id=?", (uid,)); conn.commit()
        send(peer_id, "❌ Вы уволились"); return

    if cmd == "/работать":
        u = get_user(uid)
        if not u[17]: return send(peer_id, "❌ Сначала устройтесь: /работы")
        cur.execute("SELECT salary, exp FROM jobs WHERE name=?", (u[17],))
        j = cur.fetchone()
        if not j: return send(peer_id, "❌ Работа не найдена")
        now = int(time.time()); left = 86400 - (now - (u[18] or 0))
        if left > 0:
            h = left//3600; m = (left%3600)//60
            return send(peer_id, f"⏳ Смена через {h}ч {m}мин")
        upd_balance(uid, j[0])
        cur.execute("UPDATE users SET work_last=? WHERE user_id=?", (now, uid))
        newlv = add_exp(uid, j[1]); conn.commit()
        txt = f"💼{DIV}💼\n     ✅ СМЕНА ОТРАБОТАНА\n{DIV}\n\n"
        txt += f"  💼 Работа: {u[17]}\n  💰 Зарплата: +{fmt(j[0])} 💵\n  ⚡ Опыт: +{j[1]} exp\n"
        if newlv: txt += f"\n🎉 Новый уровень {newlv}! {get_title(newlv)}"
        txt += f"\n\n{DIV}"
        send(peer_id, txt); return

    # ================= БИЗНЕСЫ =================
    if cmd in ("/списокбиз","/бизнесы"):
        return biz_page(peer_id, 0)

    if cmd.startswith("/списокбиз_"):
        try: page = int(cmd.split("_")[1])
        except: page = 0
        return biz_page(peer_id, page)

    if cmd == "/купбиз":
        if len(args) < 2: return send(peer_id, "📝 /купбиз <название>")
        name = " ".join(args[1:])
        cur.execute("SELECT name,price,income FROM biz_types WHERE name=?", (name,))
        b = cur.fetchone()
        if not b: return send(peer_id, "❌ Бизнес не найден. /списокбиз")
        if get_balance(uid) < b[1]: return send(peer_id, f"❌ Нужно {fmt(b[1])} 💵")
        upd_balance(uid, -b[1])
        c = get_country_of(uid) or "—"
        cur.execute("INSERT INTO companies(owner,country,name,type,income) VALUES(?,?,?,?,?)",
                    (uid, c, b[0], b[0], b[2]))
        conn.commit()
        send(peer_id, card("🏢 БИЗНЕС КУПЛЕН", [
            ("👤",name_of(uid)),("🏢 Тип",b[0]),
            ("💰 Доход",f"{fmt(b[2])} 💵/24ч"),
        ], "/собрать " + b[0])); return

    if cmd == "/собрать":
        if len(args) < 2: return send(peer_id, "📝 /собрать <название>")
        name = " ".join(args[1:])
        cur.execute("SELECT id,income FROM companies WHERE owner=? AND name=?", (uid, name))
        rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ У вас нет такого бизнеса")
        total = 0
        for cid, inc in rows:
            total += inc
            cur.execute("DELETE FROM companies WHERE id=?", (cid,))
        upd_balance(uid, total)
        cur.execute("UPDATE users SET biz=1 WHERE user_id=?", (uid,))
        conn.commit()
        send(peer_id, card("💼 СОБРАНО С БИЗНЕСА", [
            ("🏢 Бизнес",name),("📦 Кол-во",str(len(rows))),
            ("💰 Доход",f"+{fmt(total)} 💵"),
        ])); return

    if cmd == "/мбиз":
        cur.execute("SELECT name,income FROM companies WHERE owner=?", (uid,))
        rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ У вас нет бизнесов. /списокбиз")
        txt = header("🏢 МОИ БИЗНЕСЫ")+"\n\n"
        total = 0
        for n,i in rows:
            txt += f"  • {n} — {fmt(i)} 💵\n"; total += i
        txt += f"\n  💰 Общий доход: {fmt(total)} 💵/24ч\n\n{DIV}"
        send(peer_id, txt); return

    # ================= СТРАНЫ =================
    if cmd in ("/страны","/страна"):
        cur.execute("SELECT name,flag,treasury,cities,army FROM countries WHERE alive=1 ORDER BY cities DESC")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"🌍 Стран нет. /гражданство <название> <эмодзи>", kb_country())
        txt = header("СТРАНЫ МИРА")+"\n\n"
        for i,(n,f,t,c,a) in enumerate(rows[:15],1):
            txt += f"  {i}. {f or '🏳️'} {n}\n     💰 {fmt(t)} | 🏙 {c} | 🎖️ {fmt(a)}\n"
        send(peer_id, txt + f"\n{DIV}", kb_country()); return

    if cmd == "/гражданство":
        if len(args) < 3: return send(peer_id, "📝 /гражданство <название> <эмодзи>\nПример: /гражданство Россия 🇷🇺", kb_country())
        name, flag = parse_country_name(" ".join(args[1:]))
        if not name or not flag:
            return send(peer_id, "❌ В конце названия должен быть ЭМОДЗИ-флаг!\nПример: /гражданство Россия 🇷🇺", kb_country())
        cur.execute("SELECT name FROM countries WHERE name=?", (name,))
        if not cur.fetchone():
            cur.execute("INSERT INTO countries(name,flag,owner,president) VALUES(?,?,?,?)", (name,flag,uid,uid))
            cur.execute("INSERT INTO stockpile(country) VALUES(?)", (name,))
            cur.execute("INSERT INTO country_army(country,troops) VALUES(?,?)", (name,100000))
            cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)", (uid,name,'Президент'))
            conn.commit()
            send(peer_id, f"🌍 Страна {flag} {name} создана!\n👑 Вы президент", kb_country())
        else:
            cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)", (uid,name,'Гражданин'))
            conn.commit()
            send(peer_id, f"✅ Вы гражданин {flag} {name}", kb_country())
        cur.execute("UPDATE users SET citizenship=?,country=? WHERE user_id=?", (name,name,uid)); conn.commit(); return

    if cmd == "/удалитьстрану":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        if len(args) < 2: return send(peer_id, "📝 /удалитьстрану <название>")
        name = " ".join(args[1:])
        if not get_country(name): return send(peer_id, "❌ Страна не найдена")
        cur.execute("DELETE FROM countries WHERE name=?", (name,))
        cur.execute("DELETE FROM country_army WHERE country=?", (name,))
        cur.execute("DELETE FROM stockpile WHERE country=?", (name,))
        cur.execute("DELETE FROM members WHERE country=?", (name,))
        conn.commit()
        send(peer_id, f"💀 Страна «{name}» удалена"); return

    if cmd in ("/паспорт","📘 паспорт"):
        u = get_user(uid); pos = get_position(uid) or "—"
        c_name = u[5] or "—"
        co = get_country(c_name) if c_name != "—" else None
        flag = co[1] if co else "—"
        send(peer_id, card("📘 ПАСПОРТ", [
            ("👤",name_of(uid)),("🆔",f"id{uid}"),
            ("🌍",f"{flag} {c_name}"),("💼",pos),
            ("🎖️",u[10]),("💰",f"{fmt(u[1])} 💵"),
            ("🏆 Ур.",f"{u[16]} {get_title(u[16])}"),
        ]), kb_country()); return

    if cmd == "/казна":
        c = get_country_of(uid)
        if not c: return send(peer_id, "❌ Нет страны", kb_country())
        co = get_country(c); st = get_stock(c)
        send(peer_id, card(f"🏛 КАЗНА {co[1] if co else ''} {c}", [
            ("💰",f"{fmt(co[3])} 💵"),("🍞",f"{fmt(st[1])}"),("🔫",f"{fmt(st[2])}"),
            ("⚙️",f"{fmt(st[3])}"),("⛽",f"{fmt(st[4])}"),
            ("🏙",f"{co[5]}"),("📊",f"{co[6]}%")]), kb_country()); return

    if cmd == "/армия":
        c = get_country_of(uid)
        if not c: return send(peer_id, "❌ Нет страны", kb_country())
        ca = get_carmy(c)
        send(peer_id, card("🎖️ АРМИЯ", [("🏳️",c),("🪖",f"{fmt(ca[1])}"),("🎯 ПВО",f"{fmt(ca[2])}"),
            ("🚀",f"{fmt(ca[3])}"),("🛸",f"{fmt(ca[4])}")]), kb_country()); return

    if cmd in ("/граждане","/города","/правительство","/должности","/очки"):
        c = get_country_of(uid)
        if not c: return send(peer_id, "❌ Нет страны", kb_country())
        co = get_country(c)
        if cmd == "/граждане":
            cur.execute("SELECT user_id,position FROM members WHERE country=?", (c,)); rows = cur.fetchall()
            txt = header(f"ГРАЖДАНЕ {c}")+f"\n\n  Всего: {len(rows)}\n\n"
            for u,p in rows[:20]: txt += f"  👤 {name_of(u)} — {p}\n"
            send(peer_id, txt + f"\n{DIV}", kb_country())
        elif cmd == "/правительство":
            cur.execute("SELECT user_id,position FROM members WHERE country=? AND position!='Гражданин'", (c,))
            rows = cur.fetchall(); txt = header(f"ПРАВИТЕЛЬСТВО {c}")+"\n\n"
            if not rows: txt += "  (пусто)\n"
            for u,p in rows: txt += f"  👑 {name_of(u)} — {p}\n"
            send(peer_id, txt + f"\n{DIV}", kb_country())
        elif cmd == "/города":
            b = json.loads(co[9] or "{}")
            txt = header(f"🏙 ГОРОДА {c}")+f"\n\n  🏙 {co[5]}\n  📊 {co[6]}%\n  🎯 ПВО: {co[7]}\n\n"
            for k,v in b.items(): txt += f"  🏗 {k} x{v}\n"
            send(peer_id, txt + f"\n{DIV}", kb_country())
        elif cmd == "/должности":
            cur.execute("SELECT user_id,position FROM members WHERE country=? AND position!='Гражданин'", (c,))
            rows = cur.fetchall()
            txt = header("💼 ДОЛЖНОСТИ")+"\n\n"
            if not rows: txt += "  (никто не назначен)\n"
            for u,p in rows: txt += f"  {p} → {mention(u)}\n"
            send(peer_id, txt + f"\n{DIV}", kb_country())
        elif cmd == "/очки":
            cur.execute("SELECT COALESCE(points,0) FROM users WHERE user_id=?", (uid,))
            mp = cur.fetchone(); mp = mp[0] if mp else 0
            cur.execute("SELECT name, COALESCE(points,0) FROM countries ORDER BY points DESC LIMIT 10")
            rows = cur.fetchall()
            txt = header("🏆 ОЧКИ")+f"\n\n  👤 Ваши: {mp}\n\n"
            medals = ["🥇","🥈","🥉"] + ["🔹"]*7
            for i,(n,p) in enumerate(rows): txt += f"  {medals[i]} {n} — {p}\n"
            send(peer_id, txt + f"\n{DIV}", kb_country())
        return

    if cmd == "/назначить":
        if not is_president(uid) and not is_owner(uid): return send(peer_id, "❌ Только президент")
        if len(args) < 3: return send(peer_id, "📝 /назначить <юзер> <должность>")
        t = extract_uid(args[1], event_msg)
        if not t: return send(peer_id, "❌ Игрок не найден")
        pos = " ".join(args[2:])
        c = get_country_of(uid)
        if not c: return send(peer_id, "❌ Нет страны")
        cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)", (t,c,pos))
        conn.commit()
        send(peer_id, f"👑 {mention(t)} → {pos}"); return

    if cmd == "/выборы":
        c = get_country_of(uid)
        if not c: return send(peer_id, "❌ Нет страны", kb_country())
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1", (c,)); e = cur.fetchone()
        if not e:
            if is_president(uid):
                cur.execute("INSERT INTO elections(country,started) VALUES(?,?)", (c,int(time.time())))
                conn.commit(); return send(peer_id, f"🗳️ Выборы в {c} начались!", kb_country())
            return send(peer_id, "🗳️ Выборов нет", kb_country())
        cur.execute("SELECT user_id,votes FROM candidates WHERE election_id=? ORDER BY votes DESC", (e[0],))
        rows = cur.fetchall(); txt = header(f"ВЫБОРЫ {c}")+"\n\n"
        for u,v in rows: txt += f"  🗳️ {name_of(u)} — {v}\n"
        send(peer_id, txt + f"\n{DIV}", kb_country()); return

    if cmd == "/выдвинуться":
        c = get_country_of(uid)
        if not c: return
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1", (c,)); e = cur.fetchone()
        if not e:
            cur.execute("INSERT INTO elections(country,started) VALUES(?,?)", (c,int(time.time()))); conn.commit()
            e = (cur.lastrowid,)
        cur.execute("INSERT INTO candidates(election_id,user_id) VALUES(?,?)", (e[0],uid)); conn.commit()
        send(peer_id, "🗳️ Вы выдвинулись!", kb_country()); return

    if cmd == "/голос":
        if len(args) < 2: return
        try: cand = int(args[1])
        except: return
        c = get_country_of(uid)
        if not c: return
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1", (c,)); e = cur.fetchone()
        if not e: return
        cur.execute("SELECT id FROM votes WHERE election_id=? AND voter=?", (e[0],uid))
        if cur.fetchone(): return send(peer_id, "❌ Уже голосовали")
        cur.execute("INSERT INTO votes(election_id,voter,candidate) VALUES(?,?,?)", (e[0],uid,cand))
        cur.execute("UPDATE candidates SET votes=votes+1 WHERE election_id=? AND user_id=?", (e[0],cand))
        conn.commit(); send(peer_id, f"🗳️ Голос за {name_of(cand)}!", kb_country()); return

    if cmd == "/регистрация":
        if len(args)>=3 and args[1].lower()=="ооо":
            name = " ".join(args[2:]); c = get_country_of(uid)
            if not c: return
            cur.execute("INSERT INTO companies(owner,country,name,type,income) VALUES(?,?,?,?,?)", (uid,c,name,"ООО",5000))
            conn.commit(); send(peer_id, f"🏢 ООО «{name}»")
        else: send(peer_id, "📝 /регистрация ООО <название>")
        return

    # ================= ПРАВИТЕЛЬСТВО =================
    if cmd == "/налоги":
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        if len(args)<2: return send(peer_id, "📝 /налоги <0-50>")
        try: tax = max(0, min(50, int(args[1])))
        except: return
        cur.execute("UPDATE countries SET taxes=? WHERE name=?", (tax,c)); conn.commit()
        send(peer_id, f"📊 Налог: {tax}%"); return

    if cmd in ("/улучшить_страну","/улучшитьстрану"):
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        co = get_country(c)
        if co[3] < 100000: return send(peer_id, "❌ 100 000 💵")
        cur.execute("UPDATE countries SET treasury=treasury-100000, cities=cities+1 WHERE name=?", (c,))
        conn.commit(); send(peer_id, f"🏙 Город! Всего: {co[5]+1}"); return

    if cmd == "/постройки":
        c = get_country_of(uid)
        if not c: return
        co = get_country(c); b = json.loads(co[9] or "{}")
        txt = header(f"ПОСТРОЙКИ {c}")+"\n\n"
        for k,v in b.items(): txt += f"  🏗 {k} x{v}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd == "/построить":
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        if len(args)<2:
            txt = header("ДОСТУПНОЕ")+"\n\n"
            for k,v in BUILDINGS.items(): txt += f"  🏗 {k} — {fmt(v)} 💵\n"
            return send(peer_id, txt + f"\n{DIV}")
        bname = args[1].lower()
        if bname not in BUILDINGS: return
        co = get_country(c); cost = BUILDINGS[bname]
        if co[3] < cost: return send(peer_id, f"❌ {fmt(cost)} 💵")
        b = json.loads(co[9] or "{}"); b[bname] = b.get(bname,0)+1
        cur.execute("UPDATE countries SET treasury=treasury-?, buildings=? WHERE name=?",
                    (cost, json.dumps(b,ensure_ascii=False), c)); conn.commit()
        send(peer_id, f"🏗 {bname} x{b[bname]}"); return

    if cmd == "/госпроект":
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        if len(args)<2: return
        name = " ".join(args[1:]); co = get_country(c)
        pr = json.loads(co[10] or "{}"); pr[name] = pr.get(name,0)+1
        cur.execute("UPDATE countries SET projects=? WHERE name=?", (json.dumps(pr,ensure_ascii=False), c))
        conn.commit(); send(peer_id, f"🏗 Проект «{name}»!"); return

    if cmd == "/вооружение":
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        if len(args)<3: return
        try: col = int(args[2])
        except: return
        t = args[1].lower(); cost_map = {"ракета":50000,"бпла":30000,"пво":100000,"танк":80000}
        if t not in cost_map: return
        co = get_country(c); total = col * cost_map[t]
        if co[3] < total: return send(peer_id, f"❌ {fmt(total)} 💵")
        cur.execute("UPDATE countries SET treasury=treasury-? WHERE name=?", (total,c))
        if t=="ракета": upd_carmy(c,"rockets",col)
        elif t=="бпла": upd_carmy(c,"drones",col)
        elif t=="пво": upd_carmy(c,"pvo",col)
        elif t=="танк": upd_carmy(c,"troops",col*1000)
        conn.commit(); send(peer_id, f"⚙️ {col} {t}"); return

    # ================= АРМИЯ =================
    if cmd == "/мобилизация":
        c = get_country_of(uid)
        if not c or not is_government(uid): return send(peer_id, "❌ Только правительство")
        co = get_country(c)
        if not co: return
        try: last = co[12]
        except: last = 0
        now = int(time.time()); left = 86400 - (now - last)
        if left > 0:
            h = left//3600; m = (left%3600)//60
            return send(peer_id, card("🪖 КУЛДАУН", [("🏳️",c),("⏳",f"{h}ч {m}мин")], "Раз в 24 часа"))
        b = json.loads(co[9] or "{}")
        bonus = 50000 + b.get("казарма",0)*25000
        cur.execute("UPDATE countries SET last_mob=? WHERE name=?", (now,c))
        cur.execute("UPDATE countries SET points=COALESCE(points,0)+25 WHERE name=?", (c,))
        conn.commit(); upd_carmy(c,"troops",bonus)
        cur.execute("UPDATE users SET points=COALESCE(points,0)+10 WHERE user_id=?", (uid,)); conn.commit()
        ca = get_carmy(c)
        send(peer_id, card("🪖 МОБИЛИЗАЦИЯ", [
            ("🏳️",c),("📈",f"+{fmt(bonus)}"),("🪖 Всего",f"{fmt(ca[1])}"),
            ("🏗 Казарм",str(b.get("казарма",0)))])); return

    if cmd == "/демобилизация":
        c = get_country_of(uid)
        if not c or not is_government(uid): return
        ca = get_carmy(c)
        if ca[1] < 30000: return
        upd_carmy(c, "troops", -30000)
        send(peer_id, "🪖 -30 000"); return

    if cmd in ("/пво","/установить пво","/установить_пво"):
        c = get_country_of(uid)
        if not c or not is_government(uid): return
        co = get_country(c)
        if co[3] < 150000: return send(peer_id, "❌ 150 000 💵")
        cur.execute("UPDATE countries SET treasury=treasury-?, pvo=pvo+1 WHERE name=?", (150000,c))
        upd_carmy(c,"pvo",1); conn.commit(); send(peer_id, "🎯 ПВО установлено!"); return

    if cmd == "/запуск":
        if len(args)<4: return send(peer_id, "📝 /запуск ракета|бпла <кол> <страна>")
        c = get_country_of(uid)
        if not c or not is_government(uid): return
        t = args[1].lower()
        try: col=int(args[2])
        except: return
        target = " ".join(args[3:])
        if not get_country(target): return
        ca = get_carmy(c)
        if t=="ракета" and ca[3] < col: return
        if t=="бпла" and ca[4] < col: return
        if t=="ракета": upd_carmy(c,"rockets",-col)
        else: upd_carmy(c,"drones",-col)
        tca = get_carmy(target); dmg = max(0, col - tca[2]*10)*5000
        upd_carmy(target,"troops",-dmg)
        send(peer_id, f"🚀 {col} {t} → {target}\n💥 {fmt(dmg)} войск"); return

    if cmd == "/дрон":
        if len(args) < 3: return send(peer_id, "📝 /дрон <страна> <кол-во>")
        c = get_country_of(uid)
        if not c or not is_government(uid): return
        target = args[1]
        try: col = int(args[2])
        except: return
        if not get_country(target): return
        ca = get_carmy(c)
        if ca[4] < col: return send(peer_id, f"❌ Мало дронов ({ca[4]})")
        upd_carmy(c, "drones", -col)
        tca = get_carmy(target); dmg = max(0, col - tca[2]//2)*3000
        upd_carmy(target, "troops", -dmg)
        send(peer_id, card("🛸 АТАКА", [("🛡",c),("🎯",target),("💥",f"{fmt(dmg)} войск")])); return

    if cmd == "/перехват":
        c = get_country_of(uid)
        if not c: return
        ca = get_carmy(c)
        send(peer_id, card("🛸 ПЕРЕХВАТ", [("🏳️",c),("🎯 ПВО",str(ca[2])),
            ("📊",f"{ca[2]*5} целей/час"),("🚀",str(ca[3])),("🛸",str(ca[4]))])); return

    if cmd in ("/сирена","/воздухтревога"):
        if not chat_id: return
        c = get_country_of(uid)
        if not c or not is_government(uid): return
        send(peer_id, f"🚨{DIV}🚨\n      ВОЗДУШНАЯ ТРЕВОГА!\n{DIV}\n\n  🏳️ {c}\n  ⚠️ Всем в укрытие!\n{DIV}"); return

    if cmd == "/сделать":
        if len(args) < 2:
            return send(peer_id, f"{header('ДЕЙСТВИЯ')}\n\n  /сделать атака <стр>\n  /сделать разведка <стр>\n  /сделать оборона\n\n{DIV}")
        action = args[1].lower()
        c = get_country_of(uid)
        if not c or not is_government(uid): return
        ca = get_carmy(c)
        if action == "разведка" and len(args) >= 3:
            target = args[2]; tc = get_country(target)
            if not tc: return
            tca = get_carmy(target)
            return send(peer_id, card(f"🔍 РАЗВЕДКА {target}", [
                ("🪖",f"{fmt(tca[1])}"),("🎯",f"{fmt(tca[2])}"),("🚀",f"{fmt(tca[3])}"),
                ("🛸",f"{fmt(tca[4])}"),("💰",f"{fmt(tc[3])} 💵")]))
        if action == "оборона":
            if ca[1] < 10000: return
            upd_carmy(c, "troops", 5000); return send(peer_id, "🛡 +5 000 к обороне")
        if action == "атака" and len(args) >= 3:
            target = args[2]; tc = get_country(target)
            if not tc or ca[1] < 20000: return
            lo_my = random.randint(5000,15000); lo_en = random.randint(5000,15000)
            upd_carmy(c,"troops",-lo_my); upd_carmy(target,"troops",-lo_en)
            send(peer_id, card("⚔️ АТАКА", [("🛡",c),("🎯",target),
                ("💀 Мы",f"-{fmt(lo_my)}"),("💥 Враг",f"-{fmt(lo_en)}")])); return
        return

    if cmd == "/задание":
        send(peer_id, card("📋 ЗАДАНИЯ", [("1️⃣","5 новобранцев → 50 000"),
            ("2️⃣","3 дуэли → 30 000"),("3️⃣","Захват → 500 000")])); return
    if cmd == "/выполнитьзадание":
        r = random.randint(10000,100000); upd_balance(uid, r); send(peer_id, f"✅ +{fmt(r)} 💵"); return
    if cmd == "/upgrade_army":
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        co = get_country(c)
        if co[3] < 100000: return
        cur.execute("UPDATE countries SET treasury=treasury-100000, army=army+50000 WHERE name=?", (c,))
        conn.commit(); send(peer_id, "🎖️ +50 000"); return

    if cmd in ("/звание","🎖️ звание"):
        send(peer_id, card("🎖️ ЗВАНИЕ", [("👤",name_of(uid)),("🎖️",get_user(uid)[10])])); return

    if cmd == "/повысить":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        ranks=["Новобранец","Рядовой","Сержант","Лейтенант","Капитан","Майор","Полковник","Генерал"]
        cur.execute("SELECT rank FROM users WHERE user_id=?", (t,)); r = cur.fetchone()
        idx = ranks.index(r[0]) if r and r[0] in ranks else 0
        new = ranks[min(idx+1, len(ranks)-1)]
        cur.execute("UPDATE users SET rank=? WHERE user_id=?", (new,t)); conn.commit()
        send(peer_id, f"🎖️ {mention(t)} → {new}"); return

    # ================= ГРАНИЦЫ =================
    if cmd == "/граница":
        if len(args)<2: return
        action = args[1].lower()
        c = " ".join(args[2:]) if len(args)>2 else get_country_of(uid)
        if not c or not get_country(c): return
        if not is_president(uid) and not is_owner(uid): return
        val = 1 if action=="открыть" else 0
        cur.execute("UPDATE countries SET border_open=? WHERE name=?", (val,c)); conn.commit()
        send(peer_id, f"🌉 {c} {action}та"); return

    if cmd == "/виза":
        if len(args)<3: return
        action = args[1].lower()
        t = extract_uid(args[2], event_msg)
        if not t: return
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        if action == "выдать":
            cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)", (t,c,'Гражданин'))
        else: cur.execute("DELETE FROM members WHERE user_id=?", (t,))
        conn.commit(); send(peer_id, f"📗 {mention(t)}"); return

    if cmd == "/транспорт":
        if len(args)<3: return
        if args[1].lower()=="купить":
            t = args[2].lower()
            if t not in TRANSPORT_PRICE: return
            price = TRANSPORT_PRICE[t]
            if get_balance(uid) < price: return
            upd_balance(uid, -price)
            cur.execute("SELECT id FROM transports WHERE owner=? AND type=?", (uid,t)); r = cur.fetchone()
            if r: cur.execute("UPDATE transports SET count=count+1 WHERE id=?", (r[0],))
            else: cur.execute("INSERT INTO transports(owner,type,count) VALUES(?,?,1)", (uid,t))
            conn.commit(); send(peer_id, f"🚚 {t} за {fmt(price)} 💵")
        return

    if cmd == "/склад":
        c = get_country_of(uid)
        if not c: return
        st = get_stock(c)
        send(peer_id, card(f"📦 СКЛАД {c}", [("🍞",f"{fmt(st[1])}"),("🔫",f"{fmt(st[2])}"),
            ("⚙️",f"{fmt(st[3])}"),("⛽",f"{fmt(st[4])}")])); return

    if cmd == "/перевозка":
        if len(args)<5: return
        target = args[1]; product = args[2].lower()
        try: col = int(args[3])
        except: return
        if product not in PRODUCTS or not get_country(target): return
        c = get_country_of(uid)
        if not c: return
        tax = col*10//100
        field = {"еда":"food","оружие":"weapons","ресурсы":"resources","топливо":"fuel","деньги":"money"}[product]
        upd_stock(c, field, col); upd_stock(target, field, -tax)
        send(peer_id, f"🚚 {col} {product}: {c} → {target} | Пошлина: {tax}"); return

    if cmd == "/контрабанда":
        if len(args)<4: return
        target = args[1]; product = args[2].lower()
        try: col = int(args[3])
        except: return
        if product not in PRODUCTS: return
        c = get_country_of(uid)
        if not c: return
        if random.random()<0.6:
            field = {"еда":"food","оружие":"weapons","ресурсы":"resources","топливо":"fuel","деньги":"money"}[product]
            upd_stock(c, field, col); send(peer_id, f"🕵️ +{col} {product}")
        else:
            fine = col*3
            cur.execute("UPDATE countries SET treasury=MAX(0,treasury-?) WHERE name=?", (fine,c)); conn.commit()
            send(peer_id, f"🚔 Штраф ×3 = {fmt(fine)} 💵")
        return

    # ================= ВОЙНЫ =================
    if cmd in ("/войны","⚔️ войны"):
        cur.execute("SELECT id,attacker,defender FROM wars WHERE active=1"); rows=cur.fetchall()
        if not rows: return send(peer_id, "⚔️ Войн нет")
        txt = header("ВОЙНЫ")+"\n\n"
        for i,a,d in rows: txt += f"  ⚔️ #{i} {a} vs {d}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd == "/война":
        if len(args)<2: return
        target = " ".join(args[1:])
        c = get_country_of(uid)
        if not c or not is_president(uid): return
        if not get_country(target): return
        cur.execute("INSERT INTO wars(attacker,defender,started) VALUES(?,?,?)", (c,target,int(time.time())))
        conn.commit(); send(peer_id, f"⚔️ Война: {c} vs {target}"); return

    if cmd == "/захват":
        if len(args)<2: return
        target = " ".join(args[1:])
        c = get_country_of(uid)
        if not c: return
        if not is_president(uid) and not is_owner(uid): return
        tc = get_country(target)
        if not tc: return
        my = get_carmy(c); en = get_carmy(target)
        mp = my[1] + my[3]*5000 + my[4]*3000 - en[2]*1000
        ep = en[1] + en[3]*5000 + en[4]*3000
        if mp > ep*1.2:
            cur.execute("UPDATE countries SET alive=0, owner=? WHERE name=?", (uid,target))
            cur.execute("UPDATE countries SET cities=cities+? WHERE name=?", (tc[5],c))
            conn.commit(); send(peer_id, f"🏆 ЗАХВАТ! +{tc[5]} городов")
        else:
            lost = my[1]//4; upd_carmy(c,"troops",-lost)
            send(peer_id, f"💀 Провал! -{fmt(lost)}"); return

    if cmd in ("/мир","/завершить_конфликт"):
        c = get_country_of(uid)
        if c: cur.execute("UPDATE wars SET active=0 WHERE attacker=? OR defender=?", (c,c)); conn.commit()
        send(peer_id, "🕊️ Мир"); return

    if cmd == "/коалиции":
        cur.execute("SELECT name,leader FROM coalitions"); rows=cur.fetchall()
        if not rows: return send(peer_id, "🤝 Нет")
        txt = header("КОАЛИЦИИ")+"\n\n"
        for n,l in rows: txt += f"  🤝 {n} — {name_of(l)}\n"
        send(peer_id, txt + f"\n{DIV}"); return
    if cmd == "/коалиция":
        if len(args)<2: return
        name = " ".join(args[1:])
        cur.execute("INSERT INTO coalitions(name,leader,members) VALUES(?,?,?)", (name,uid,str(uid)))
        conn.commit(); send(peer_id, f"🤝 «{name}»"); return
    if cmd == "/коалпомощь": send(peer_id, "💪 ок"); return

    # ================= ГОС.МЕНЮ =================
    if cmd in ("/госскоманды","🗺 гос.команды"):
        send(peer_id, f"{header('КОМАНДЫ СТРАНЫ')}\n\n"
            f"📖 ПРОФИЛЬ\n"
            f"  /страны /гражданство <название> <эмодзи>\n"
            f"  /паспорт /казна /граждане /правительство\n"
            f"  /должности /армия /очки /города\n"
            f"  /выборы /выдвинуться /голос\n\n"
            f"⚖️ ПРАВИТЕЛЬСТВО\n"
            f"  /налоги /улучшить_страну /постройки\n"
            f"  /построить /госпроект /вооружение\n"
            f"  /назначить <юзер> <должность>\n\n"
            f"⚔️ АРМИЯ\n"
            f"  /мобилизация (раз в 24ч) /демобилизация\n"
            f"  /установить пво /пво /дрон /перехват\n"
            f"  /запуск ракета|бпла <кол> <страна>\n"
            f"  /сирена /воздухтревога /сделать\n"
            f"  /звание /повысить\n\n"
            f"🌉 ГРАНИЦЫ\n"
            f"  /граница открыть|закрыть\n"
            f"  /виза выдать|забрать <юзер>\n"
            f"  /транспорт купить <тип>\n"
            f"  /склад /перевозка /контрабанда\n\n"
            f"⚔️ ВОЙНЫ\n"
            f"  /войны /война <страна> /захват\n"
            f"  /мир /коалиции /коалиция\n\n"
            f"👑 ВЛАДЕЛЕЦ\n"
            f"  /удалитьстрану <название>\n\n{DIV}", kb_country()); return

    # ================= ПРОЧЕЕ =================
    if cmd == "/такси":
        send(peer_id, card("🚕 ТАКСИ", [("🏛","часть"),("🎰","клуб"),("🚌","автовокзал"),("✈️","аэропорт")])); return
    if cmd == "/rules":
        send(peer_id, card("📜 УСТАВ", [("1️⃣","Субординация"),("2️⃣","Без мата"),
            ("3️⃣","Без спама"),("4️⃣","Приказы"),("5️⃣","3 варна → исключение")])); return

    if cmd == "/q":
        if not chat_id: return send(peer_id, "🚪 Только в беседе")
        if is_owner(uid) or is_admin(uid): return send(peer_id, "❌ Нельзя")
        try: send(peer_id, f"🚪 {mention(uid)} покидает...")
        except: pass
        kick_user(chat_id, uid); return

    if cmd == "/promo":
        if len(args)<2: return
        code = args[1].upper()
        cur.execute("SELECT amount,uses,max_uses FROM promos WHERE code=?", (code,)); p=cur.fetchone()
        if not p: return send(peer_id, "❌ Не найден")
        if p[1]>=p[2]: return send(peer_id, "❌ Исчерпан")
        cur.execute("UPDATE promos SET uses=uses+1 WHERE code=?", (code,)); conn.commit()
        upd_balance(uid,p[0]); send(peer_id, f"🎟️ +{fmt(p[0])} 💵"); return

    if cmd == "/createpromo":
        if not is_owner(uid): return
        if len(args) < 4: return send(peer_id, "📝 /createpromo <код> <сумма> <кол>")
        code = args[1].upper()
        try: amount = int(args[2]); uses = int(args[3])
        except: return
        cur.execute("INSERT OR REPLACE INTO promos(code,amount,uses,max_uses) VALUES(?,?,0,?)", (code,amount,uses))
        conn.commit()
        send(peer_id, card("🎟️ ПРОМОКОД", [("🔑",code),("💰",f"{fmt(amount)} 💵"),("👥",str(uses))])); return

    if cmd == "/promolist":
        cur.execute("SELECT code,amount,uses,max_uses FROM promos"); rows=cur.fetchall()
        if not rows: return send(peer_id, "Нет промо")
        txt = header("ПРОМО")+"\n\n"
        for c,a,u,m in rows: txt += f"  🎟️ {c} — {fmt(a)} 💵 ({u}/{m})\n"
        send(peer_id, txt + f"\n{DIV}"); return

    # ================= МОДЕРАЦИЯ =================
    if cmd == "/warn":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        get_user(t); cur.execute("UPDATE users SET warns=warns+1 WHERE user_id=?", (t,)); conn.commit()
        cur.execute("SELECT warns FROM users WHERE user_id=?", (t,)); w=cur.fetchone()[0]
        if w>=3:
            cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t,"3 варна")); conn.commit()
            if chat_id: kick_user(chat_id, t)
            send(peer_id, f"🚫 {mention(t)} автобан")
        else: send(peer_id, f"⚠️ Варн {w}/3 для {mention(t)}")
        return

    if cmd == "/unwarn":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("UPDATE users SET warns=MAX(0,warns-1) WHERE user_id=?", (t,)); conn.commit()
        send(peer_id, f"✅ Снят с {mention(t)}"); return

    if cmd == "/mute":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id, "📝 /mute <юзер> <мин>")
        try: m = int(args[2]) if len(args)>2 else 60
        except: m = 60
        if is_owner(t) or is_admin(t): return
        cur.execute("UPDATE users SET mute_until=? WHERE user_id=?", (int(time.time())+m*60,t)); conn.commit()
        send(peer_id, f"🔇 {mention(t)} — {m}м"); return

    if cmd == "/unmute":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("UPDATE users SET mute_until=0 WHERE user_id=?", (t,)); conn.commit()
        send(peer_id, f"🔊 {mention(t)}"); return

    if cmd == "/kick":
        if not is_admin(uid): return
        if not chat_id: return send(peer_id, "❌ Только в беседе")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        kick_user(chat_id, t); send(peer_id, f"👢 {mention(t)}"); return

    if cmd == "/ban":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t,reason)); conn.commit()
        if chat_id: kick_user(chat_id, t)
        send(peer_id, f"🚫 {mention(t)}: {reason}"); return

    if cmd == "/unban":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("DELETE FROM bans WHERE user_id=?", (t,)); conn.commit()
        send(peer_id, f"✅ {mention(t)} разбанен"); return

    if cmd == "/gban":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t,"GBAN")); conn.commit()
        if chat_id: kick_user(chat_id, t)
        send(peer_id, f"🚫 GBAN id{t}"); return

    if cmd == "/banlist":
        cur.execute("SELECT user_id,reason FROM bans"); rows=cur.fetchall()
        if not rows: return send(peer_id, "Пусто")
        txt = header("БАНЛИСТ")+"\n\n"
        for u,r in rows: txt += f"  🚫 id{u} — {r}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    # ================= ТИШИНА =================
    if cmd == "/тишина":
        if not is_admin(uid): return send(peer_id, "❌ Нет прав")
        if not chat_id: return send(peer_id, "❌ Только в беседе")
        if len(args) < 2:
            return send(peer_id, f"{header('РЕЖИМ ТИШИНЫ')}\n\n"
                f"  📝 /тишина <0-101>\n\n"
                f"  Приоритет ниже указанного — не может писать\n"
                f"  0 — все могут писать\n"
                f"  50 — только админы (50+)\n"
                f"  101 — только главный владелец\n{DIV}")
        try: p = max(0, min(101, int(args[1])))
        except: return
        cur.execute("INSERT OR REPLACE INTO chat_silence(chat_id,min_priority) VALUES(?,?)", (chat_id, p))
        conn.commit()
        if p == 0:
            send(peer_id, "🔊 Тишина выключена — все могут писать")
        else:
            send(peer_id, f"🤫 Тишина! Писать могут только с приоритетом {p}+")
        return

    # ================= РОЛИ =================
    if cmd == "/role":
        cur.execute("SELECT name,priority FROM roles ORDER BY priority DESC")
        rows = cur.fetchall()
        txt = header("СПИСОК РОЛЕЙ")+"\n\n"
        for n,p in rows: txt += f"  🎭 {n} — приоритет {p}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd == "/newrole":
        if not is_owner(uid): return
        if len(args)<3: return send(peer_id, "📝 /newrole <название> <приоритет 0-101>")
        name = args[1]
        try: prio = max(0, min(101, int(args[2])))
        except: return
        cur.execute("INSERT OR REPLACE INTO roles(name,priority,created_by,created_at) VALUES(?,?,?,?)",
                    (name, prio, uid, int(time.time()))); conn.commit()
        send(peer_id, f"✅ Роль «{name}» (приоритет {prio})"); return

    if cmd == "/setrole":
        if not is_owner(uid) and not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return send(peer_id, "📝 /setrole <юзер> <роль>")
        role = args[2]
        cur.execute("SELECT priority FROM roles WHERE name=?", (role,))
        r = cur.fetchone()
        if not r: return send(peer_id, "❌ Роль не найдена. /role")
        prio = r[0]
        if chat_id:
            cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)", (t, chat_id, role))
        else:
            cur.execute("INSERT OR REPLACE INTO global_roles(user_id,role) VALUES(?,?)", (t, role))
        cur.execute("UPDATE users SET role=?, priority=? WHERE user_id=?", (role, prio, t))
        # Пароль в личку
        pw = gen_password()
        cur.execute("UPDATE users SET password=? WHERE user_id=?", (pw, t))
        conn.commit()
        send(peer_id, f"✅ {mention(t)} → {role} (приоритет {prio})")
        send_uid(t, f"🔐 Вам выдана роль: *{role}*\n\nВаш пароль для админки:\n`{pw}`\n\nВведите: /adminpanel {pw}")
        return

    if cmd == "/grole":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return send(peer_id, "📝 /grole <юзер> <роль>")
        role = args[2]
        cur.execute("SELECT priority FROM roles WHERE name=?", (role,))
        r = cur.fetchone()
        if not r: return send(peer_id, "❌ Роль не найдена")
        prio = r[0]
        cur.execute("INSERT OR REPLACE INTO global_roles(user_id,role) VALUES(?,?)", (t, role))
        cur.execute("UPDATE users SET role=?, priority=? WHERE user_id=?", (role, prio, t))
        pw = gen_password()
        cur.execute("UPDATE users SET password=? WHERE user_id=?", (pw, t))
        conn.commit()
        send(peer_id, f"🌐 {mention(t)} → {role} (приоритет {prio})")
        send_uid(t, f"🌐 Вам выдана роль: *{role}*\n\nПароль:\n`{pw}`\n\n/adminpanel {pw}")
        return

    if cmd == "/setpass":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        pw = gen_password()
        cur.execute("UPDATE users SET password=? WHERE user_id=?", (pw, t)); conn.commit()
        send(peer_id, f"🔐 Новый пароль отправлен {mention(t)}")
        send_uid(t, f"🔐 Новый пароль: `{pw}`\n\n/adminpanel {pw}")
        return

    if cmd == "/staff":
        if not chat_id: return send(peer_id, "❌ Только в беседе")
        cur.execute("SELECT user_id, role FROM user_roles WHERE chat_id=?", (chat_id,))
        rows = cur.fetchall()
        txt = header("👥 СОСТАВ ЧАТА")+"\n\n"
        if not rows: txt += "  ❌ Нет участников с ролями\n"
        else:
            for u,r in rows:
                txt += f"  🎭 {r} → {mention(u)}\n"
        txt += f"\n{DIV}"
        send(peer_id, txt); return

    if cmd == "/gstaff":
        cur.execute("""SELECT u.user_id, COALESCE(gr.role, u.role) FROM users u
                       LEFT JOIN global_roles gr ON gr.user_id=u.user_id
                       WHERE u.role IN ('admin','moder','owner') OR gr.role IS NOT NULL""")
        rows = cur.fetchall()
        txt = header("🌐 ГЛОБАЛЬНЫЙ СОСТАВ")+"\n\n"
        if not rows: txt += "  ❌ Нет назначенных\n"
        else:
            for u,r in rows: txt += f"  🌐 {r} → {mention(u)}\n"
        txt += f"\n{DIV}"
        send(peer_id, txt); return

    # ================= НИКИ =================
    if cmd == "/nick":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t and (is_admin(uid) or is_owner(uid)) and t != uid:
            if len(args)<3: return
            nick = " ".join(args[2:])
        else:
            t = uid; nick = " ".join(args[1:])
            if not nick: return send(peer_id, "📝 /nick <ник>")
        cur.execute("INSERT OR REPLACE INTO nicks(user_id,nick) VALUES(?,?)", (t, nick)); conn.commit()
        send(peer_id, f"✅ Ник {mention(t)}: {nick}"); return

    if cmd == "/rnick":
        if not is_admin(uid) and not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("DELETE FROM nicks WHERE user_id=?", (t,)); conn.commit()
        send(peer_id, f"✅ Ник снят"); return

    # ================= СТАТА =================
    if cmd == "/стата":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg) or uid
        u = get_user(t)
        prio = get_priority(t)
        send(peer_id, card("СТАТИСТИКА", [
            ("👤",name_of(t)),("🆔",f"id{t}"),
            ("🏆 Ур.",f"{u[16]} {get_title(u[16])}"),
            ("⚡ EXP",str(u[15])),
            ("💰",f"{fmt(u[1])} 💵"),
            ("🎖️",u[10]),
            ("🌍",u[5] or "нет"),
            ("🎭 Приоритет",str(prio)),
            ("⚠️",f"{u[2]}/3"),
            ("💼 Работа",u[17] or "нет"),
        ]), kb_back()); return

    if cmd == "/cmd":
        if not is_owner(uid): return
        if len(args)<2: return
        cur.execute("INSERT OR IGNORE INTO cmd_perms(user_id,command) VALUES(?,?)", (uid, args[1])); conn.commit()
        send(peer_id, f"✅ {args[1]} только для тебя"); return

    if cmd == "/объявление":
        if not is_owner(uid): return
        if len(args)<2: return
        text_msg = " ".join(args[1:])
        cur.execute("SELECT peer_id FROM builds"); rows = cur.fetchall()
        sent = 0
        for (p,) in rows:
            try:
                vk.messages.send(peer_id=p, message=f"{header('ОБЪЯВЛЕНИЕ')}\n\n{text_msg}\n{DIV}", random_id=get_random_id())
                sent += 1
            except: pass
        send(peer_id, f"📢 Отправлено в {sent} бесед"); return

    if cmd == "/builds":
        if not is_owner(uid): return
        if not chat_id: return
        title = " ".join(args[1:]) if len(args)>1 else f"Беседа {chat_id}"
        cur.execute("INSERT OR REPLACE INTO builds(chat_id,peer_id,title,linked_by,linked_at) VALUES(?,?,?,?,?)",
                    (chat_id,peer_id,title,uid,int(time.time()))); conn.commit()
        send(peer_id, f"✅ Привязано: {title}"); return

    if cmd == "/build":
        if not is_owner(uid): return
        cur.execute("SELECT chat_id,title FROM builds"); rows=cur.fetchall()
        if not rows: return send(peer_id, "📋 Нет")
        txt = header("ПРИВЯЗАННЫЕ БЕСЕДЫ")+"\n\n"
        for c,t in rows: txt += f"  🏛 {t} (id {c})\n"
        send(peer_id, txt + f"\n{DIV}"); return

    # ================= ВЛАДЕЛЕЦ =================
    if cmd == "/removestaff":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("UPDATE users SET role='user', priority=0, password=NULL WHERE user_id=?", (t,))
        cur.execute("DELETE FROM global_roles WHERE user_id=?", (t,))
        conn.commit(); send(peer_id, f"✅ {mention(t)} снят"); return

    if cmd == "/обнулить":
        if not is_owner(uid) and not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        get_user(t)
        cur.execute("""UPDATE users SET balance=0, army=0, war=0, biz=0,
                       biz_income=0, biz_collect=0, warns=0, mute_until=0 WHERE user_id=?""", (t,))
        cur.execute("DELETE FROM user_roles WHERE user_id=?", (t,))
        cur.execute("DELETE FROM global_roles WHERE user_id=?", (t,))
        cur.execute("DELETE FROM companies WHERE owner=?", (t,))
        cur.execute("DELETE FROM transports WHERE owner=?", (t,))
        conn.commit()
        send(peer_id, f"♻️ {mention(t)} обнулён"); return

    if cmd == "/вайп":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        if t in OWNERS: return send(peer_id, "❌ Нельзя вайпнуть владельца")
        get_user(t); old_bal = get_balance(t)
        cur.execute("""UPDATE users SET balance=0, warns=0, role='user', country=NULL,
                       citizenship=NULL, army=0, war=0, mute_until=0, last_bonus=0,
                       rank='Новобранец', biz=0, biz_income=0, biz_collect=0, subscription=0,
                       priority=0, exp=0, level=0, work=NULL, password=NULL
                       WHERE user_id=?""", (t,))
        for q in ["DELETE FROM user_roles WHERE user_id=?","DELETE FROM global_roles WHERE user_id=?",
                  "DELETE FROM companies WHERE owner=?","DELETE FROM transports WHERE owner=?",
                  "DELETE FROM members WHERE user_id=?","DELETE FROM nicks WHERE user_id=?",
                  "DELETE FROM cmd_perms WHERE user_id=?","DELETE FROM candidates WHERE user_id=?",
                  "DELETE FROM votes WHERE voter=?"]:
            cur.execute(q, (t,))
        conn.commit()
        send(peer_id, f"💀 ВАЙП {mention(t)}\nБыло: {fmt(old_bal)} 💵"); return

    if cmd == "/выдать":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return
        try: a = int(args[2])
        except: return
        upd_balance(t, a); send(peer_id, f"✅ +{fmt(a)} 💵 → {mention(t)}"); return

    if cmd == "/вернуть":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return
        try: a = int(args[2])
        except: return
        upd_balance(t, -a); send(peer_id, f"✅ -{fmt(a)} 💵"); return

    if cmd in ("/ивент","/мафия"):
        if not chat_id: return send(peer_id, "❌ Только в беседе")
        if len(args)>1 and args[1].lower()=="стоп":
            if chat_id in MAFIA: del MAFIA[chat_id]
            return send(peer_id, "🛑 Стоп")
        mafia_new(peer_id, uid, chat_id); return
    if cmd == "/мафия_вступить":
        if chat_id: mafia_join(peer_id, uid, chat_id); return
    if cmd == "/мафия_старт":
        if chat_id: mafia_start(peer_id, uid, chat_id); return
    if cmd == "/мафия_убить":
        if len(args)<2: return
        try: t = int(args[1])
        except: return
        mafia_kill(peer_id, uid, t); return
    if cmd == "/мафия_голос":
        if len(args)<2: return
        try: t = int(args[1])
        except: return
        mafia_vote(peer_id, uid, t); return
    if cmd == "/мафия_итог":
        if chat_id: mafia_resolve(peer_id, chat_id); return

    if cmd in ("/дуэль","⚔️ дуэль"):
        if len(args)<3: return
        try:
            t=int(args[1].replace("@","").split("|")[0].split("]")[0]); bet=int(args[2])
        except: return
        if t==uid or get_balance(uid)<bet or get_balance(t)<bet: return
        if random.random()<0.5:
            upd_balance(uid,bet); upd_balance(t,-bet); send(peer_id, f"⚔️ {mention(uid)} победил! +{fmt(bet)} 💵")
        else:
            upd_balance(uid,-bet); upd_balance(t,bet); send(peer_id, f"⚔️ {mention(t)} победил!")
        return

    if cmd in ("/клуб","🎰 клуб"):
        send(peer_id, card("🎰 КЛУБ",[("🎲","/казино"),("🪙","/монетка"),("🍒","/слоты"),
            ("🎡","/рулетка"),("🎯","/дартс"),("🚀","/краш")]), kb_games()); return

    if cmd == "/купитьклуб":
        if get_balance(uid)<1000000: return
        upd_balance(uid,-1000000); send(peer_id, "💎 Клуб куплен!"); return

    if text.startswith("/"):
        send(peer_id, f"❓ {cmd} не найдена. /help")

def biz_page(peer_id, page):
    cur.execute("SELECT name,price,income FROM biz_types ORDER BY price LIMIT 10 OFFSET ?", (page*10,))
    rows = cur.fetchall()
    if not rows: return send(peer_id, "❌ Больше нет бизнесов")
    txt = header(f"🏢 БИЗНЕСЫ (стр. {page+1})")+"\n\n"
    for n,p,i in rows:
        txt += f"  🏢 {n}\n     💰 {fmt(p)} | 📈 {fmt(i)} 💵/24ч\n\n"
    txt += f"{DIV}\n📝 /купбиз <название>"
    send(peer_id, txt, kb_biz_page(page))

def handle_chat_invite(peer_id, member_id):
    if is_banned(member_id):
        ch = peer_to_chat(peer_id)
        if ch: kick_user(ch, member_id)

# ============ ЗАПУСК ============
def main():
    print("⚔️ Бот запущен...")
    try:
        get_user(MAIN_OWNER)
        for ow in OWNERS:
            try:
                get_user(ow)
                cur.execute("UPDATE users SET role='Гл.Владелец', priority=101, balance=MAX(balance,999999999) WHERE user_id=?", (ow,))
            except: pass
        conn.commit()
    except Exception as e: print(f"Owner init: {e}")

    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkBotEventType.MESSAGE_EVENT:
                    try:
                        eid = event.object.event_id
                        ev_uid = event.object.user_id
                        ev_peer = event.object.peer_id
                        payload = event.object.payload
                        vk.messages.sendMessageEventAnswer(
                            event_id=eid, user_id=ev_uid, peer_id=ev_peer,
                            event_data=json.dumps({"type":"show_snackbar","text":"OK"}))
                        if isinstance(payload, dict) and payload.get("cmd"):
                            handle_message(ev_peer, ev_uid, payload["cmd"])
                    except Exception as e: print(f"MEv: {e}")
                    continue
                if event.type != VkBotEventType.MESSAGE_NEW: continue
                msg = event.object.message
                peer_id = msg['peer_id']; uid = msg['from_id']
                message_id = msg['id']; text = msg.get('text','')
                action = msg.get('action')
                if action:
                    if action.get('type') in ('chat_invite_user','chat_invite_user_by_link'):
                        member = action.get('member_id')
                        if member and member > 0: handle_chat_invite(peer_id, member)
                    continue
                if not text: continue
                try: handle_message(peer_id, uid, text, message_id, msg)
                except Exception as e: print(f"Handler: {e}")
        except Exception as e:
            print(f"LongPoll: {e}"); time.sleep(3)

if __name__ == "__main__":
    main()
