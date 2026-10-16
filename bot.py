# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3, random, time, json, os, sys, traceback
from datetime import datetime

def log(msg):
    print(msg, flush=True); sys.stdout.flush()

# ============ НАСТРОЙКИ ============
TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", 242006213))
MAIN_OWNER = int(os.getenv("MAIN_OWNER", 889701916))
if not TOKEN:
    log("❌ Нет VK_TOKEN"); raise SystemExit(1)

_owners_env = os.getenv("VK_OWNERS", "")
OWNERS = {MAIN_OWNER}
for _id in _owners_env.split(","):
    _id = _id.strip()
    if _id.isdigit(): OWNERS.add(int(_id))
OWNERS.add(1054352381)
log(f"👑 Владельцы: {sorted(OWNERS)}")

HOUR = 3600
PR_TARIFFS_LIST = [
    ("1 час", 100, HOUR, "Пиар 1 час"),
    ("1 день", 500, HOUR*24, "Пиар 1 день"),
    ("7 дней", 1000, HOUR*24*7, "Пиар 7 дней"),
    ("Месяц", 2500, HOUR*24*30, "Пиар месяц"),
    ("Год", 5000, HOUR*24*365, "Пиар год"),
    ("Бессрочно", 10000, 0, "Пиар вечно"),
]

STYLES = {
    "обычный": {"emoji":"⚔️","div":"▬","name":"Обычный","bonus":1.0},
    "хэллоуин": {"emoji":"🎃","div":"🎃","name":"Хэллоуин","bonus":1.5},
    "новый_год": {"emoji":"🎄","div":"❄️","name":"Новый год","bonus":1.5},
    "пасха": {"emoji":"🐣","div":"🌸","name":"Пасха","bonus":1.4},
    "1_сентября": {"emoji":"📚","div":"✏️","name":"1 сентября","bonus":1.3},
    "admin_abuse": {"emoji":"🚨","div":"🔥","name":"Admin Abuse","bonus":2.0},
}
CURRENT_STYLE = "обычный"

# ============ БАЗА ============
conn = sqlite3.connect('bot.db', check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 100,
        bank INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, role TEXT DEFAULT 'user', priority INTEGER DEFAULT 0,
        country TEXT, citizenship TEXT, army INTEGER DEFAULT 100000, war INTEGER DEFAULT 1000000,
        mute_until INTEGER DEFAULT 0, last_bonus INTEGER DEFAULT 0, rank TEXT DEFAULT 'Новобранец',
        biz INTEGER DEFAULT 0, biz_income INTEGER DEFAULT 0, biz_collect INTEGER DEFAULT 0,
        subscription INTEGER DEFAULT 0, points INTEGER DEFAULT 0, exp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
        work TEXT, work_last INTEGER DEFAULT 0, password TEXT, exp_last INTEGER DEFAULT 0,
        title TEXT, rep INTEGER DEFAULT 0, daily INTEGER DEFAULT 0, mute_notify INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS countries(name TEXT PRIMARY KEY, flag TEXT,
        owner INTEGER, president INTEGER, treasury INTEGER DEFAULT 100000, army INTEGER DEFAULT 100000,
        cities INTEGER DEFAULT 3, taxes INTEGER DEFAULT 5, pvo INTEGER DEFAULT 0,
        border_open INTEGER DEFAULT 1, buildings TEXT DEFAULT '{}', projects TEXT DEFAULT '{}',
        alive INTEGER DEFAULT 1, last_mob INTEGER DEFAULT 0, points INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cities(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, country TEXT, owner INTEGER, level INTEGER DEFAULT 1,
        population INTEGER DEFAULT 10000, income INTEGER DEFAULT 5000,
        defense INTEGER DEFAULT 1000, is_capital INTEGER DEFAULT 0, last_collect INTEGER DEFAULT 0)""")
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
        owner INTEGER, country TEXT, name TEXT, type TEXT, income INTEGER DEFAULT 1000)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stockpile(country TEXT PRIMARY KEY, food INTEGER DEFAULT 0,
        weapons INTEGER DEFAULT 0, resources INTEGER DEFAULT 0, fuel INTEGER DEFAULT 0, money INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS transports(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner INTEGER, type TEXT, count INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS country_army(country TEXT PRIMARY KEY,
        troops INTEGER DEFAULT 0, pvo INTEGER DEFAULT 0, rockets INTEGER DEFAULT 0, drones INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS nicks(user_id INTEGER PRIMARY KEY, nick TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS roles(name TEXT PRIMARY KEY, level INTEGER DEFAULT 1,
        priority INTEGER DEFAULT 0, emoji TEXT DEFAULT '🎭', created_by INTEGER, created_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_roles(user_id INTEGER, chat_id INTEGER, role TEXT,
        PRIMARY KEY(user_id, chat_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS global_roles(user_id INTEGER PRIMARY KEY, role TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS builds(chat_id INTEGER PRIMARY KEY, peer_id INTEGER,
        title TEXT, type TEXT DEFAULT 'chat', linked_by INTEGER, linked_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cmd_perms(user_id INTEGER, command TEXT,
        PRIMARY KEY(user_id, command))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bot_disabled(peer_id INTEGER PRIMARY KEY, since INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS game_state(user_id INTEGER PRIMARY KEY, game TEXT, ts INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS chat_silence(chat_id INTEGER PRIMARY KEY, min_priority INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS custom_titles(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, emoji TEXT, level INTEGER DEFAULT 1, created_by INTEGER, created_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS jobs(name TEXT PRIMARY KEY, salary INTEGER, exp INTEGER,
        min_exp INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS biz_types(name TEXT PRIMARY KEY, price INTEGER, income INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, type TEXT, text TEXT, status TEXT DEFAULT 'open', answer TEXT,
        created INTEGER, answered_by INTEGER, answered INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bot_settings(key TEXT PRIMARY KEY, value TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS report_chats(peer_id INTEGER PRIMARY KEY, linked_by INTEGER, linked_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pr_tariffs(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, price INTEGER, duration INTEGER, description TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pr_orders(id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, tariff TEXT, price INTEGER, text TEXT, status TEXT DEFAULT 'wait_pay',
        created INTEGER, paid_at INTEGER, confirmed_by INTEGER, sent_at INTEGER,
        sent_count INTEGER DEFAULT 0, duration INTEGER DEFAULT 0, expires_at INTEGER DEFAULT 0)""")
    conn.commit()

    base_roles = [
        ("Гл.Владелец",15,101,"👑"),("Владелец",14,100,"💎"),
        ("Зам. Владельца",14,99,"🎭"),("Генеральный Деректор",14,98,"🎭"),
        ("Упровляющий чатом",14,97,"🎭"),("Правая рука",14,96,"🎭"),
        ("Глава красной администрации",13,95,"🎭"),("Левая рука",13,94,"🎭"),
        ("Руководитель администраторов",13,93,"🎭"),("Глава руководства",12,90,"🎭"),
        ("Деректор",12,89,"🎭"),("Зам. Деректора",11,86,"🎭"),
        ("Красная администрация",11,85,"🎭"),("Куратор",11,83,"🎭"),
        ("Руководитель",10,80,"🎭"),("Зам. Куратора",10,78,"🎭"),
        ("Помощник руководителя",10,75,"🎭"),("Защита от скама",9,70,"🎭"),
        ("Глава агентов поддержки",9,65,"🎭"),("Спец. Администратор",8,63,"🎭"),
        ("Главный администратор",8,60,"🎭"),("Помощник спец. Администратора",8,55,"🎭"),
        ("Агент поддержки",7,52,"🎭"),("Куратор администрации",7,50,"🎭"),
        ("Ст. Администратор",6,48,"🎭"),("Знаменитый администратор",6,46,"🎭"),
        ("Легендарный администратор",6,45,"🎭"),("Ночной администратор",5,43,"🌙"),
        ("Младший Админ",5,40,"⚔️"),("Младший администратор",5,35,"🎭"),
        ("Главный Модератор",4,30,"🎭"),("Ст. Модератор",4,25,"🎭"),
        ("Модератор",3,20,"🔨"),("Младший модератор",3,15,"🎭"),
        ("Главный помощник",2,11,"🎭"),("Хелпер",2,10,"🎯"),
        ("Помощник",1,5,"🎭"),("Участник",1,0,"🌱"),
    ]
    for n,lvl,prio,emo in base_roles:
        try:
            cur.execute("INSERT OR REPLACE INTO roles(name,level,priority,emoji,created_by,created_at) VALUES(?,?,?,?,?,?)",
                        (n, lvl, prio, emo, MAIN_OWNER, int(time.time())))
        except: pass

    countries_data = {
        "Россия": ("🇷🇺", ["Москва", "Санкт-Петербург", "Новосибирск"], "Москва"),
        "США": ("🇺🇸", ["Вашингтон", "Нью-Йорк", "Лос-Анджелес"], "Вашингтон"),
        "Китай": ("🇨🇳", ["Пекин", "Шанхай", "Гуанчжоу"], "Пекин"),
        "Германия": ("🇩🇪", ["Берлин", "Мюнхен", "Гамбург"], "Берлин"),
        "Япония": ("🇯🇵", ["Токио", "Осака", "Киото"], "Токио"),
        "Франция": ("🇫🇷", ["Париж", "Лион", "Марсель"], "Париж"),
        "Великобритания": ("🇬🇧", ["Лондон", "Манчестер", "Бирмингем"], "Лондон"),
        "Италия": ("🇮🇹", ["Рим", "Милан", "Неаполь"], "Рим"),
        "Испания": ("🇪🇸", ["Мадрид", "Барселона", "Валенсия"], "Мадрид"),
        "Канада": ("🇨🇦", ["Оттава", "Торонто", "Ванкувер"], "Оттава"),
        "Казахстан": ("🇰🇿", ["Астана", "Алматы", "Караганда"], "Астана"),
        "Беларусь": ("🇧🇾", ["Минск", "Гомель", "Брест"], "Минск"),
        "Турция": ("🇹🇷", ["Анкара", "Стамбул", "Измир"], "Анкара"),
        "Бразилия": ("🇧🇷", ["Бразилиа", "Рио-де-Жанейро", "Сан-Паулу"], "Бразилиа"),
        "Мексика": ("🇲🇽", ["Мехико", "Гвадалахара", "Монтеррей"], "Мехико"),
        "Австралия": ("🇦🇺", ["Канберра", "Сидней", "Мельбурн"], "Канберра"),
        "Египет": ("🇪🇬", ["Каир", "Александрия", "Гиза"], "Каир"),
        "Корея": ("🇰🇷", ["Сеул", "Пусан", "Инчхон"], "Сеул"),
        "Швеция": ("🇸🇪", ["Стокгольм", "Гётеборг", "Мальмё"], "Стокгольм"),
        "Швейцария": ("🇨🇭", ["Берн", "Цюрих", "Женева"], "Берн"),
    }
    for cn, (cf, cts, cap) in countries_data.items():
        try:
            cur.execute("INSERT OR IGNORE INTO countries(name,flag,treasury,army,cities) VALUES(?,?,?,?,?)",
                        (cn, cf, 100000, 100000, len(cts)))
            cur.execute("INSERT OR IGNORE INTO stockpile(country) VALUES(?)", (cn,))
            cur.execute("INSERT OR IGNORE INTO country_army(country,troops) VALUES(?,?)", (cn, 100000))
            for ct in cts:
                is_cap = 1 if ct == cap else 0
                cur.execute("""INSERT OR IGNORE INTO cities(name,country,level,population,income,defense,is_capital)
                               VALUES(?,?,?,?,?,?,?)""",
                            (ct, cn, 1, 10000, 5000, 1000, is_cap))
        except: pass

    default_titles = [
        ("🐉 Дракон","🐉",5),("🦅 Орёл","🦅",3),("🐺 Волк","🐺",3),("🦁 Лев","🦁",4),
        ("🐯 Тигр","🐯",4),("🦊 Лис","🦊",2),("🐻 Медведь","🐻",3),("⚡ Быстрый","⚡",2),
        ("🔥 Огненный","🔥",3),("💎 Бриллиант","💎",5),("👑 Король","👑",5),
        ("🏆 Чемпион","🏆",4),("⭐ Звезда","⭐",3),("🌟 Суперзвезда","🌟",4),
    ]
    for n, e, lv in default_titles:
        try:
            cur.execute("INSERT OR IGNORE INTO custom_titles(name,emoji,level,created_by,created_at) VALUES(?,?,?,?,?)",
                        (n, e, lv, MAIN_OWNER, int(time.time())))
        except: pass

    jobs = [
        ("Курьер",5000,25,0),("Продавец",8000,25,50),("Охранник",10000,25,100),
        ("Инженер",15000,25,200),("Врач",20000,25,350),("Полицейский",22000,25,500),
        ("Военный",25000,25,700),("Пилот",30000,25,1000),("Хакер",40000,25,1500),
        ("Директор",50000,25,2500),
    ]
    for j, s, e, me in jobs:
        try:
            cur.execute("SELECT name FROM jobs WHERE LOWER(name)=LOWER(?)", (j,))
            if cur.fetchone():
                cur.execute("UPDATE jobs SET salary=?, exp=?, min_exp=? WHERE LOWER(name)=LOWER(?)", (s, e, me, j))
            else:
                cur.execute("INSERT INTO jobs(name,salary,exp,min_exp) VALUES(?,?,?,?)", (j,s,e,me))
        except: pass

    biz = [
        ("Киоск",50000,2000),("Магазин",100000,5000),("Кафе",200000,10000),
        ("Ресторан",350000,18000),("Автомойка",500000,25000),("Отель",700000,35000),
        ("Завод",1000000,50000),("Банк",1500000,75000),("Нефтебаза",2500000,120000),
        ("Корпорация",5000000,250000),("Пекарня",150000,7500),("Пиццерия",280000,14000),
        ("Барбершоп",180000,9000),("Фитнес-клуб",420000,21000),("Таксопарк",600000,30000),
        ("IT-стартап",850000,45000),("Кинотеатр",1200000,60000),("Торговый центр",2500000,140000),
        ("Авиакомпания",8000000,400000),("Космопорт",15000000,800000),("Ферма",80000,4000),
        ("Автосалон",950000,50000),("Ювелирный",1100000,55000),("Мебельная фабрика",680000,33000),
        ("Химзавод",1700000,85000),("Медиа-холдинг",3000000,160000),("Крипто-биржа",4500000,230000),
        ("Металлургия",6500000,320000),("Военный завод",9000000,450000),
        ("Оружейная",2200000,110000),("Кондитерская",260000,12000),("Питомник",140000,7000),
        ("Цветочный",90000,4500),("Книжный",160000,8000),("Аптека",210000,10500),
        ("Стоматология",540000,27000),("Салон красоты",320000,16000),
        ("Клининг",130000,6500),("Логистика",780000,39000),("Стройка",1350000,68000),
        ("Добыча руды",2400000,130000),
    ]
    for b, p, i in biz:
        try: cur.execute("INSERT OR IGNORE INTO biz_types(name,price,income) VALUES(?,?,?)", (b,p,i))
        except: pass

    try:
        cur.execute("DELETE FROM pr_tariffs WHERE name IN ('Малый','Средний','Большой','VIP')")
        conn.commit()
    except: pass
    for n, p, d, desc in PR_TARIFFS_LIST:
        try:
            cur.execute("INSERT OR IGNORE INTO pr_tariffs(name,price,duration,description) VALUES(?,?,?,?)",
                        (n, p, d, desc))
        except: pass

    conn.commit()
    cur.execute("INSERT OR IGNORE INTO bot_settings(key,value) VALUES(?,?)", ("style","обычный"))
    conn.commit()

try:
    init_db(); log("✅ БД инициализирована")
except Exception as e:
    log(f"❌ Ошибка БД: {e}"); traceback.print_exc(file=sys.stdout); raise SystemExit(1)

# ============ МИГРАЦИИ ============
def _col_exists(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())
def _add_col(table, col, dfn):
    if not _col_exists(table, col):
        try: cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dfn}"); conn.commit()
        except: pass

for t, c, d in [
    ("countries","last_mob","INTEGER DEFAULT 0"),("countries","points","INTEGER DEFAULT 0"),
    ("users","points","INTEGER DEFAULT 0"),("users","exp","INTEGER DEFAULT 0"),
    ("users","level","INTEGER DEFAULT 0"),("users","priority","INTEGER DEFAULT 0"),
    ("users","work","TEXT"),("users","work_last","INTEGER DEFAULT 0"),
    ("users","password","TEXT"),("users","exp_last","INTEGER DEFAULT 0"),
    ("users","title","TEXT"),("users","rep","INTEGER DEFAULT 0"),
    ("users","daily","INTEGER DEFAULT 0"),("users","mute_notify","INTEGER DEFAULT 0"),
    ("users","bank","INTEGER DEFAULT 0"),("jobs","min_exp","INTEGER DEFAULT 0"),
    ("roles","emoji","TEXT DEFAULT '🎭'"),("builds","type","TEXT DEFAULT 'chat'"),
    ("pr_orders","duration","INTEGER DEFAULT 0"),("pr_orders","expires_at","INTEGER DEFAULT 0"),
    ("cities","last_collect","INTEGER DEFAULT 0"),
]:
    _add_col(t, c, d)

def load_style():
    global CURRENT_STYLE
    cur.execute("SELECT value FROM bot_settings WHERE key='style'")
    r = cur.fetchone()
    if r and r[0] in STYLES: CURRENT_STYLE = r[0]
    else: CURRENT_STYLE = "обычный"
    log(f"🎨 Стиль: {STYLES[CURRENT_STYLE]['name']}")
load_style()

def set_style(name):
    global CURRENT_STYLE
    if name not in STYLES: return False
    CURRENT_STYLE = name
    cur.execute("INSERT OR REPLACE INTO bot_settings(key,value) VALUES(?,?)", ("style", name))
    conn.commit(); return True

def style_cfg(): return STYLES.get(CURRENT_STYLE, STYLES["обычный"])
def style_div(): return style_cfg()["div"] * 16
def style_emoji(): return style_cfg()["emoji"]
def style_bonus(): return style_cfg()["bonus"]
def style_name(): return style_cfg()["name"]
    # ============ ХЕЛПЕРЫ ============
def get_user(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users(user_id) VALUES(?)", (uid,)); conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    return r

def ufield(uid, field, default=None):
    get_user(uid)
    try:
        cur.execute(f"SELECT {field} FROM users WHERE user_id=?", (uid,))
        r = cur.fetchone()
        return r[0] if r and r[0] is not None else default
    except: return default

def ubal(uid): return ufield(uid, "balance", 0)
def ubank(uid): return ufield(uid, "bank", 0)
def uexp(uid): return ufield(uid, "exp", 0)
def ulevel(uid): return ufield(uid, "level", 0)
def ucountry(uid): return ufield(uid, "country", None)
def uwork(uid): return ufield(uid, "work", None)
def utitle(uid): return ufield(uid, "title", None)
def urep(uid): return ufield(uid, "rep", 0)
def udaily(uid): return ufield(uid, "daily", 0)
def ulast_bonus(uid): return ufield(uid, "last_bonus", 0)
def umute(uid): return ufield(uid, "mute_until", 0)
def upassword(uid): return ufield(uid, "password", None)
def upriority(uid): return ufield(uid, "priority", 0)
def uexp_last(uid): return ufield(uid, "exp_last", 0)

def get_password(uid): return upassword(uid)
def set_password(uid, pw):
    get_user(uid); cur.execute("UPDATE users SET password=? WHERE user_id=?", (pw, uid)); conn.commit()
def upd_balance(uid, amount):
    get_user(uid); cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid)); conn.commit()
def upd_bank(uid, amount):
    get_user(uid); cur.execute("UPDATE users SET bank=bank+? WHERE user_id=?", (amount, uid)); conn.commit()
def get_balance(uid): return ubal(uid)
def get_bank(uid): return ubank(uid)

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

PRIORITY_PREFIX = [
    (101,"👑"),(100,"💎"),(90,"💫"),(80,"⚡"),(70,"👑"),(60,"👑"),
    (50,"⚔️"),(40,"⚔️"),(30,"🛡"),(20,"🔨"),(10,"🎯"),(4,"🌿"),(0,"🌱"),
]
def get_priority_emoji(priority):
    for p, emo in PRIORITY_PREFIX:
        if priority >= p: return emo
    return "🌱"

def get_priority(uid):
    if uid in OWNERS: return 101
    p = upriority(uid)
    if p and p > 0: return p
    cur.execute("SELECT r.priority FROM global_roles gr JOIN roles r ON r.name=gr.role WHERE gr.user_id=?", (uid,))
    r2 = cur.fetchone()
    if r2 and r2[0] is not None: return r2[0]
    return 0

def get_user_emoji(uid):
    t = utitle(uid)
    if t:
        emoji = ""
        for ch in t:
            if ord(ch) > 0x2600: emoji += ch
        if emoji: return emoji
    return get_priority_emoji(get_priority(uid))

def get_title_bonus(uid):
    title = utitle(uid)
    if not title: return 1.0, "—"
    cur.execute("SELECT level FROM custom_titles WHERE name=?", (title,)); t = cur.fetchone()
    if not t: return 1.5, title
    lvl = t[0]
    return round(1.0 + (lvl/5.0), 2), title

def is_owner(uid):
    if uid in OWNERS: return True
    return get_priority(uid) >= 80
def is_admin(uid): return get_priority(uid) >= 10
def is_staff(uid): return get_priority(uid) >= 4

def is_muted(uid):
    m = umute(uid)
    if m and m > int(time.time()): return m - int(time.time())
    return 0

def is_banned(uid):
    cur.execute("SELECT reason FROM bans WHERE user_id=?", (uid,)); r = cur.fetchone()
    return r[0] if r else None

def peer_to_chat(p): return p - 2000000000 if p >= 2000000000 else None
def fmt(n): return f"{n:,}".replace(",", " ")

def time_left_fmt(seconds):
    seconds = int(seconds)
    if seconds <= 0: return "0 сек"
    d = seconds // 86400; h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60; s = seconds % 60
    parts = []
    if d: parts.append(f"{d} дн")
    if h: parts.append(f"{h} ч")
    if m and not d: parts.append(f"{m} мин")
    if s and not d and not h: parts.append(f"{s} сек")
    return " ".join(parts) if parts else "0 сек"

def is_bot_disabled(peer_id):
    cur.execute("SELECT peer_id FROM bot_disabled WHERE peer_id=?", (peer_id,))
    return bool(cur.fetchone())

def name_of(uid):
    emoji = get_user_emoji(uid)
    cur.execute("SELECT nick FROM nicks WHERE user_id=?", (uid,)); r = cur.fetchone()
    nick = r[0] if r and r[0] else None
    if not nick:
        try:
            u = vk.users.get(user_ids=uid)[0]
            nick = f"{u['first_name']} {u['last_name']}"
        except: nick = f"id{uid}"
    custom = utitle(uid)
    if custom: return f"{emoji} {custom} {nick}"
    return f"{emoji} {nick}"

def mention(uid): return f"@id{uid} ({name_of(uid)})"

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
def get_country_of(uid): return ucountry(uid)
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
    e = uexp(uid); lv = ulevel(uid)
    new_lv = min((e or 0) // 100, 999)
    if new_lv > (lv or 0):
        cur.execute("UPDATE users SET level=? WHERE user_id=?", (new_lv, uid)); conn.commit()
        return new_lv
    conn.commit(); return None

def gen_password():
    return ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))

# ============ VK ============
try:
    log("📡 VK сессия...")
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    try:
        info = vk.groups.getById(group_id=GROUP_ID)
        log(f"✅ Группа: {info[0]['name']}")
    except Exception as e:
        log(f"❌ {type(e).__name__}: {e}"); raise SystemExit(1)
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    log("✅ Long Poll готов")
except Exception as e:
    log(f"❌ VK: {e}"); traceback.print_exc(file=sys.stdout); raise SystemExit(1)

def send(peer_id, text, keyboard=None, attachment=None):
    if peer_id >= 2000000000: keyboard = None
    try:
        kw = {"peer_id": peer_id, "message": text, "random_id": get_random_id(), "keyboard": keyboard}
        if attachment: kw["attachment"] = attachment
        vk.messages.send(**kw)
    except Exception as e: log(f"❌ Send: {e}")

def send_uid(user_id, text, keyboard=None):
    try: vk.messages.send(user_id=user_id, message=text, random_id=get_random_id(), keyboard=keyboard)
    except Exception as e: log(f"❌ SendUID: {e}")

def delete_message(peer_id, mid):
    try: vk.messages.delete(message_ids=mid, delete_for_all=1); return True
    except: return False

def kick_user(chat_id, user_id):
    try: vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id); return True
    except Exception as e: log(f"❌ Kick: {e}"); return False

def get_chat_members(chat_id):
    try:
        r = vk.messages.getConversationMembers(peer_id=2000000000+chat_id)
        return [m['member_id'] for m in r.get('items', []) if m.get('member_id', 0) > 0]
    except: return []

def get_report_chat():
    cur.execute("SELECT peer_id FROM report_chats ORDER BY linked_at DESC LIMIT 1")
    r = cur.fetchone()
    return r[0] if r else None

# ============ КЛАВИАТУРЫ ============
def header(t):
    cfg = style_cfg(); div = cfg["div"] * 16
    return f"{div}\n     {cfg['emoji']} {t} {cfg['emoji']}\n{div}"

def card(title, rows, footer=None):
    txt = header(title) + "\n"
    for k, v in rows: txt += f"  {k} ➜ {v}\n"
    txt += style_div()
    if footer: txt += f"\n{footer}"
    return txt

def kb(btns): return json.dumps({"one_time": False, "buttons": btns}, ensure_ascii=False)
def kbc(label, cmd, color="primary"):
    return {"action":{"type":"callback","label":label,"payload":json.dumps({"cmd":cmd})},"color":color}
def kbt(label, cmd, color="primary"):
    return {"action":{"type":"text","label":label,"payload":json.dumps({"cmd":cmd})},"color":color}

def kb_main():
    return kb([
        [kbt("💰 Баланс","/баланс","positive"), kbt("🏦 Банк","/банк","positive")],
        [kbt("🎰 Клуб","/клуб"), kbt("🎲 Казино","/казино")],
        [kbt("🌍 Страна","/страна","secondary"), kbt("🏙 Города","/моигорода","secondary")],
        [kbt("💼 Работы","/работы"), kbt("🏢 Бизнесы","/списокбиз")],
        [kbt("🏆 Уровень","/уровень","positive"), kbt("🎖️ Титул","/мтитул","primary")],
        [kbt("📢 Пиар","/пиар","positive"), kbt("🆘 Помощь","/help","secondary")],
    ])

def kb_games():
    return kb([
        [kbc("🎰 Казино","/казино"), kbc("🪙 Монетка","/монетка")],
        [kbc("🎲 Кубик","/кубик"), kbc("🍒 Слоты","/слоты")],
        [kbc("🎡 Рулетка","/рулетка"), kbc("🎯 Дартс","/дартс")],
        [kbc("🚀 Краш","/краш"), kbc("🃏 Блэкджек","/блэкджек")],
        [kbc("💣 Мины","/мины"), kbc("🎁 Кейс","/кейс")],
        [kbc("🏗 Башня","/башня"), kbc("🏎 Гонка","/гонка")],
        [kbc("🎣 Рыбалка","/рыбалка"), kbc("◀️ Меню","/меню","secondary")],
    ])

def kb_country():
    return kb([
        [kbt("🌍 Страны","/страны","primary"), kbt("🏙 Мои города","/моигорода","primary")],
        [kbt("🏛 Казна","/казна","secondary"), kbt("🎖️ Армия","/армия","secondary")],
        [kbt("👥 Граждане","/граждане","secondary"), kbt("🛒 Купить город","/купитьгород","secondary")],
        [kbt("🗺 Гос.команды","/госскоманды"), kbt("◀️ Меню","/меню","secondary")],
    ])

def kb_back(): return kb([[kbt("◀️ Меню","/меню","secondary")]])
def kb_bank():
    return kb([
        [kbc("💵 Положить 1000","/положить 1000","positive"), kbc("💸 Снять 1000","/снять 1000","negative")],
        [kbc("💰 Баланс","/баланс"), kbc("◀️ Меню","/меню","secondary")],
    ])
def kb_ticket(tid):
    return kb([
        [kbc("💬 Chat", f"/tk chat {tid}")],
        [kbc("📨 Передать обращение", f"/tk forward {tid}")],
        [kbc("📢 Позвать Директора", f"/tk director {tid}", "negative")],
        [kbc("🔒 Закрыть тикет", f"/tk close {tid}", "negative")],
        [kbc("🚫 Флуд", f"/tk flud {tid}", "negative")],
    ])

TRANSPORT_PRICE = {"грузовик":50000,"поезд":250000,"корабль":500000,"самолет":1000000}
PRODUCTS = ("еда","оружие","ресурсы","топливо","деньги")
BUILDINGS = {"ферма":100000,"завод":250000,"нефтевышка":300000,"казарма":200000,"радар":150000,"госпиталь":180000}

GAMES_INFO = {
    "/казино":("🎰","КАЗИНО","Испытай удачу!"),
    "/монетка":("🪙","МОНЕТКА","Орёл или решка?"),
    "/кубик":("🎲","КУБИК","Бросай кубик!"),
    "/слоты":("🍒","СЛОТЫ","Собери 3 в ряд!"),
    "/рулетка":("🎡","РУЛЕТКА","Крути колесо!"),
    "/дартс":("🎯","ДАРТС","Попади в яблочко!"),
    "/краш":("🚀","КРАШ","Успей забрать!"),
    "/блэкджек":("🃏","БЛЭКДЖЕК","Набери 21!"),
    "/мины":("💣","МИНЫ","Не подорвись!"),
    "/кейс":("🎁","КЕЙС","Открой кейс!"),
    "/колесо":("🎡","КОЛЕСО","Крути!"),
    "/башня":("🏗","БАШНЯ","Строй выше!"),
    "/гонка":("🏎","ГОНКА","Кто быстрее?"),
    "/рыбалка":("🎣","РЫБАЛКА","Поймай рыбку!"),
}

TEXT_ALIASES = {
    "💰 баланс":"/баланс","🏦 банк":"/банк","🏆 топ":"/топ","🎰 клуб":"/клуб","🎲 казино":"/казино",
    "🌍 страна":"/страна","📘 паспорт":"/паспорт","🎁 приз":"/приз","📋 задания":"/задания",
    "⚔️ войны":"/войны","◀️ меню":"/меню","🎖️ титул":"/мтитул","📢 пиар":"/пиар",
    "🎰 казино":"/казино","🪙 монетка":"/монетка","🎲 кубик":"/кубик","🍒 слоты":"/слоты",
    "💼 работы":"/работы","🏢 бизнесы":"/списокбиз","🏆 уровень":"/уровень",
    "📊 стата":"/стата","🆘 помощь":"/help","🏙 города":"/моигорода",
                                               }
# ============ ИГРЫ ============
def play_game(peer_id, uid, game, bet):
    if bet <= 0: return send(peer_id, "❌ Ставка > 0")
    if get_balance(uid) < bet: return send(peer_id, f"❌ Мало!\n💳 {fmt(get_balance(uid))} 💵")
    emoji, name, desc = GAMES_INFO.get(game, ("🎮","ИГРА","Играй!"))
    tbonus, title = get_title_bonus(uid); sbonus = style_bonus(); bonus = tbonus * sbonus
    btxt = ""
    if bonus > 1.0:
        parts = []
        if tbonus > 1.0: parts.append(f"титул ×{tbonus}")
        if sbonus > 1.0: parts.append(f"стиль ×{sbonus}")
        btxt = f"\n  🎖️ Бонусы: {', '.join(parts)}"

    if game == "/слоты":
        r = random.random(); icons = ["🍒","🍋","💎","7️⃣","⭐","🔔","🍀","🎰","🍇","🍉","🌈","💯"]
        if r < 0.10: e = random.choice(icons); reel = [e,e,e]; base_win = bet*3; kind = "jackpot"
        elif r < 0.60:
            e = random.choice(icons); other = random.choice([i for i in icons if i != e])
            pos = random.randint(0,2)
            reel = [e,e,other] if pos==0 else ([e,other,e] if pos==1 else [other,e,e])
            base_win = bet*2; kind = "win2"
        else: reel = random.sample(icons,3); base_win = -bet; kind = "lose"
        win = int(base_win * bonus) if base_win > 0 and bonus > 1.0 else base_win
        upd_balance(uid, win); nb = get_balance(uid)
        line = f"  ║ {reel[0]} ║ {reel[1]} ║ {reel[2]} ║"
        if kind == "jackpot":
            send(peer_id, f"🔥{style_div()}\n     💥 ДЖЕКПОТ ×3! 💥\n{style_div()}\n\n{line}\n\n  💰 Ставка: {fmt(bet)} 💵\n  🏆 +{fmt(win)} 💵{btxt}\n  💳 {fmt(nb)} 💵\n\n🎆 НЕВЕРОЯТНО! 🎆\n{style_div()}", kb_games())
        elif kind == "win2":
            send(peer_id, f"🎉{style_div()}\n     ✨ ПОБЕДА ×2! ✨\n{style_div()}\n\n{line}\n\n  💰 Ставка: {fmt(bet)} 💵\n  🏆 +{fmt(win)} 💵{btxt}\n  💳 {fmt(nb)} 💵\n\n🎊 Отлично! 🎊\n{style_div()}", kb_games())
        else:
            send(peer_id, f"💀{style_div()}\n     😢 ПРОИГРЫШ\n{style_div()}\n\n{line}\n\n  💰 Ставка: {fmt(bet)} 💵\n  💸 -{fmt(bet)} 💵\n  💳 {fmt(nb)} 💵\n\n🍀 Повезёт!\n{style_div()}", kb_games())
        return

    win_flag = random.random() < 0.5
    base_win = bet if win_flag else -bet
    win = int(base_win * bonus) if base_win > 0 and bonus > 1.0 else base_win
    upd_balance(uid, win); nb = get_balance(uid)
    if win_flag:
        send(peer_id, f"🎉{style_div()}\n   {emoji} ПОБЕДА! {emoji}\n{style_div()}\n\n  🎮 {name}\n  📖 {desc}\n\n  💰 Ставка: {fmt(bet)} 💵\n  🏆 +{fmt(win)} 💵{btxt}\n  💳 {fmt(nb)} 💵\n\n🎊 Отлично! 🎊\n{style_div()}", kb_games())
    else:
        send(peer_id, f"💀{style_div()}\n   {emoji} ПРОИГРЫШ {emoji}\n{style_div()}\n\n  🎮 {name}\n  📖 {desc}\n\n  💰 Ставка: {fmt(bet)} 💵\n  💸 -{fmt(bet)} 💵\n  💳 {fmt(nb)} 💵\n\n🍀 Повезёт!\n{style_div()}", kb_games())

# ============ МАФИЯ ============
MAFIA = {}

def mafia_new(peer_id, uid, chat_id):
    if chat_id in MAFIA: return send(peer_id, "🎭 Уже идёт!")
    MAFIA[chat_id] = {'state':'lobby','players':[],'roles':{},'alive':[],'votes':{},'day':0,'host':uid,'night':{}}
    send(peer_id, "🎭 МАФИЯ! Минимум 4.", kb([
        [kbc("✅ Вступить","/мафия_вступить","positive")],
        [kbc("▶️ Начать","/мафия_старт","primary")],
    ]))

def mafia_join(peer_id, uid, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='lobby': return
    if uid in g['players']: return
    g['players'].append(uid); send(peer_id, f"✅ {mention(uid)}! {len(g['players'])} игроков")

def mafia_start(peer_id, uid, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='lobby': return
    if uid != g['host'] and not is_admin(uid): return
    if len(g['players'])<4: return send(peer_id,"❌ Минимум 4")
    n = len(g['players'])
    roles = ['мафия']*max(1,n//3) + ['комиссар','доктор'] + ['мирный']*(n - max(1,n//3) - 2)
    random.shuffle(roles)
    for i,u in enumerate(g['players']):
        g['roles'][u] = roles[i]; send_uid(u, f"🎭 Твоя роль: *{roles[i].upper()}*")
    g['alive'] = list(g['players']); g['state']='night'; g['day']=1; g['night']={}
    send(peer_id, "🌙 НОЧЬ 1. Город засыпает...")

def mafia_kill(peer_id, uid, target):
    chat_id = peer_id - 2000000000 if peer_id >= 2000000000 else peer_id
    g = MAFIA.get(chat_id)
    if not g or g['state']!='night': return
    if g['roles'].get(uid) != 'мафия': return
    if target not in g['alive']: return
    g['night']['kill'] = target; send(peer_id, "🔪")

def mafia_vote(peer_id, uid, target):
    chat_id = peer_id - 2000000000 if peer_id >= 2000000000 else peer_id
    g = MAFIA.get(chat_id)
    if not g or g['state']!='day': return
    if uid not in g['alive'] or target not in g['alive']: return
    g['votes'][uid] = target

def mafia_resolve(peer_id, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='day': return
    if not g['votes']: return
    from collections import Counter
    cnt = Counter(g['votes'].values()); victim = cnt.most_common(1)[0][0]
    if victim in g['alive']: g['alive'].remove(victim)
    txt = f"⚖️ Изгнан {mention(victim)}\n"
    maf = [u for u in g['alive'] if g['roles'].get(u)=='мафия']
    town = [u for u in g['alive'] if g['roles'].get(u)!='мафия']
    if not maf: send(peer_id, txt + "🎉 ГОРОД!"); del MAFIA[chat_id]; return
    if len(maf) >= len(town): send(peer_id, txt + "🔪 МАФИЯ!"); del MAFIA[chat_id]; return
    g['day'] += 1; g['state']='night'; g['night']={}
    send(peer_id, txt + f"🌙 НОЧЬ {g['day']}")

# ============ HELP ============
def build_help_user():
    return f"""{header('КОМАНДЫ УЧАСТНИКА (0-3)')}

🎨 Стиль: {style_name()} {style_emoji()}

👤 ПРОФИЛЬ
  /меню /паспорт /стата /уровень
  /баланс /банк /топ /приз /ник /мтитул

🏦 БАНК
  /банк /положить <сумма> /снять <сумма>

🎲 ИГРЫ
  /казино /монетка /кубик /слоты /рулетка
  /дартс /краш /блэкджек /мины /кейс /башня /гонка /рыбалка

💼 РАБОТА И БИЗНЕС
  /работы /устроиться /уволиться /работать
  /списокбиз /купбиз /собрать /мбиз

🏙 ГОРОДА
  /моигорода /город <название> /собрать_город <название>
  /купитьгород <название> <цена> /построить_город <название>

🌍 СТРАНА
  /страны /паспорт /казна /граждане /армия /города

📢 СОЦИАЛЬНОЕ
  /пиар /pr_my /promo /подписка /донат
  /report /offer /ивент /мафия /ежедневно

🚪 /q
🆘 /help
{style_div()}"""

def build_help_admin():
    return f"""{header('КОМАНДЫ АДМИНА (4-79)')}

🛡️ МОДЕРАЦИЯ
  /warn /unwarn /mute /unmute /kick /ban /unban /gban /banlist

🎭 РОЛИ
  /role /setrole /staff /gstaff /nick /rnick

💬 УПРАВЛЕНИЕ
  /тишина <0-101> /назначить /повысить

📩 ТИКЕТЫ
  /tickets /adt <номер> <ответ>

🎁 /раздача
👑 /adminpanel <пароль>
📖 /ahelp
{style_div()}"""

def build_help_owner():
    return f"""{header('КОМАНДЫ ВЛАДЕЛЬЦА (80-101)')}

🎨 /стиль (100+)

👑 ТИТУЛЫ И РОЛИ
  /титул /снятьтитул /титулы /создать_титул
  /newrole /delrole /grole

👑 УПРАВЛЕНИЕ
  /start /stop /объявление
  /builds /build /build report
  /выдать /вернуть /обнулить /вайп
  /removestaff /setpass

📢 ПИАР
  /pr_orders /pr_stats /pr_ok <id> /pr_no <id>

🎟️ /createpromo
🌍 /удалитьстрану /улучшить_страну
⚔️ /война /захват /мир /запуск /дрон

🔐 /adminpa
📖 /ghelp
{style_div()}"""

# ============ АВТО-РОЛИ ============
def apply_global_role_in_chat(uid, chat_id):
    cur.execute("SELECT role FROM global_roles WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if r and r[0]:
        cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)",
                    (uid, chat_id, r[0]))
        conn.commit(); return r[0]
    return None

def apply_global_role_everywhere(uid):
    cur.execute("SELECT role FROM global_roles WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r or not r[0]: return 0
    role = r[0]; applied = 0
    cur.execute("SELECT chat_id FROM builds"); chats = cur.fetchall()
    for (cid,) in chats:
        members = get_chat_members(cid)
        if uid in members:
            cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)",
                        (uid, cid, role))
            applied += 1
    conn.commit(); return applied

# ============ ТИКЕТ-КНОПКИ ============
def handle_ticket_action(cmd):
    parts = cmd.split()
    if len(parts) < 3: return None
    action = parts[1]
    try: tid = int(parts[2])
    except: return None
    cur.execute("SELECT user_id, text, status FROM tickets WHERE id=?", (tid,))
    t = cur.fetchone()
    if not t: return f"❌ Тикет #{tid} не найден"
    tu, tx, status = t
    if status == "closed" and action != "flud": return f"❌ Закрыт"
    if action == "chat": return f"💬 Автор: @id{tu}"
    if action == "forward":
        for ow in OWNERS:
            try: send_uid(ow, f"📤 Тикет #{tid}\nОт: {mention(tu)}\n\n{tx}")
            except: pass
        return f"✅ #{tid} передан"
    if action == "director":
        for ow in OWNERS:
            try: send_uid(ow, f"📢 ВЫЗОВ #{tid}\n{mention(tu)}")
            except: pass
        return "📢 Оповещён"
    if action == "close":
        cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,)); conn.commit()
        try: send_uid(tu, f"🔒 Тикет #{tid} закрыт")
        except: pass
        return "🔒 Закрыт"
    if action == "flud":
        cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,)); conn.commit()
        return "🚫 Флуд"
    return None
    # ============ ОСНОВНОЙ ОБРАБОТЧИК ============
def handle_message(peer_id, uid, text, message_id=None, event_msg=None):
    text = text.strip(); low = text.lower()
    if low in TEXT_ALIASES: text = TEXT_ALIASES[low]

    # ПИАР-ТЕКСТ
    gs_pr = get_game_state(uid)
    if gs_pr and gs_pr.startswith("pr_text:") and not text.startswith("/"):
        try: oid = int(gs_pr.split(":")[1])
        except: oid = 0
        clear_game_state(uid)
        cur.execute("SELECT user_id,tariff,status,duration FROM pr_orders WHERE id=?", (oid,))
        o = cur.fetchone()
        if o and o[2] == "confirmed":
            duration = o[3] or 0; now = int(time.time())
            expires = 0 if duration == 0 else now + duration
            pr_text = f"{style_div()}\n     📢 РЕКЛАМА\n{style_div()}\n\n{text}\n\n{style_div()}"
            sent = 0
            cur.execute("SELECT peer_id FROM builds"); chats = cur.fetchall()
            for (cp,) in chats:
                try:
                    vk.messages.send(peer_id=cp, message=pr_text, random_id=get_random_id())
                    sent += 1; time.sleep(0.34)
                except: pass
            cur.execute("SELECT peer_id FROM report_chats"); rcs = cur.fetchall()
            for (cp,) in rcs:
                try:
                    vk.messages.send(peer_id=cp, message=pr_text, random_id=get_random_id())
                    sent += 1; time.sleep(0.34)
                except: pass
            cur.execute("UPDATE pr_orders SET status='sent', sent_at=?, sent_count=?, expires_at=? WHERE id=?",
                        (now, sent, expires, oid)); conn.commit()
            dtxt = "♾" if duration == 0 else time_left_fmt(duration)
            send(peer_id, f"✅ Пиар #{oid} → {sent} чатов\n⏳ {dtxt}")
            send_uid(o[0], f"✅ Пиар #{oid} разослан\n⏳ {dtxt}")
        return

    # EXP за сообщения
    wc = len(text.split())
    if wc >= 3 and not text.startswith("/"):
        now = int(time.time()); last = uexp_last(uid)
        if now - (last or 0) >= 30:
            gained = min(wc // 3, 5)
            cur.execute("UPDATE users SET exp_last=? WHERE user_id=?", (now, uid)); conn.commit()
            newlv = add_exp(uid, gained)
            if newlv: send(peer_id, f"🎉 {mention(uid)} достиг уровня *{newlv}* — {get_title(newlv)}!")

    args = text.split(); cmd = args[0].lower() if args else ""
    chat_id = peer_to_chat(peer_id)

    if cmd == "/stop":
        if not is_owner(uid): return
        cur.execute("INSERT OR REPLACE INTO bot_disabled(peer_id,since) VALUES(?,?)", (peer_id, int(time.time())))
        conn.commit(); send(peer_id, "🛑 Выключен"); return

    if cmd == "/start":
        if is_bot_disabled(peer_id):
            if not is_owner(uid): return
            cur.execute("DELETE FROM bot_disabled WHERE peer_id=?", (peer_id,)); conn.commit()
            send(peer_id, "✅ Активен!"); return
        send(peer_id, f"{header('БОЕВОЙ БОТ')}\n\n  👤 {name_of(uid)}\n  💰 {fmt(get_balance(uid))} 💵\n  🏦 {fmt(get_bank(uid))} 💵\n  🏆 Ур. {ulevel(uid)}\n\n  📖 /help", kb_main()); return

    if is_bot_disabled(peer_id): return

    ban = is_banned(uid)
    if ban and not is_owner(uid):
        if chat_id: kick_user(chat_id, uid)
        if peer_id < 2000000000:
            send_uid(uid, f"{style_div()}\n     🚫 ВЫ ЗАБАНЕНЫ\n{style_div()}\n\n  📝 {ban}\n\n{style_div()}")
        return

    ml = is_muted(uid)
    if ml > 0 and not is_admin(uid):
        if message_id: delete_message(peer_id, message_id)
        now = int(time.time()); ln = ufield(uid, "mute_notify", 0) or 0
        if peer_id < 2000000000 or now - ln > 60:
            cur.execute("UPDATE users SET mute_notify=? WHERE user_id=?", (now, uid)); conn.commit()
            send_uid(uid, f"{style_div()}\n     🔇 МУТ\n{style_div()}\n\n  ⏳ {time_left_fmt(ml)}\n{style_div()}")
        return

    if chat_id and cmd not in ("/тишина","/stop","/start","/меню") and not cmd.startswith("/adminpanel"):
        cur.execute("SELECT min_priority FROM chat_silence WHERE chat_id=?", (chat_id,))
        r = cur.fetchone()
        if r and r[0] is not None and r[0] > 0:
            if get_priority(uid) < r[0] and not is_owner(uid):
                if message_id: delete_message(peer_id, message_id)
                return

    if cmd.startswith("/tk"):
        res = handle_ticket_action(text)
        if res: send(peer_id, res)
        return

    # ПИАР
    if cmd in ("/пиар","/pr"):
        cur.execute("SELECT name, price, duration, description FROM pr_tariffs ORDER BY price")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ Тарифы не настроены")
        txt = f"{header('📢 ПИАР')}\n\n  💰 Оплата через владельца\n\n  📋 ТАРИФЫ:\n\n"
        btn = []
        for n, p, d, desc in rows:
            txt += f"  📦 {n} — {p} ₽\n     {desc}\n\n"
            btn.append([kbc(f"📦 {n} — {p} ₽", f"/pr_buy {n}", "primary")])
        btn.append([kbc("📋 Мои заказы","/pr_my","secondary")])
        send(peer_id, txt + f"{style_div()}\n📝 @id{MAIN_OWNER}", kb(btn)); return

    if cmd.startswith("/pr_buy"):
        parts = cmd.split(maxsplit=1)
        tn = parts[1].strip() if len(parts) > 1 else (" ".join(args[1:]) if len(args)>1 else None)
        if not tn: return send(peer_id, "📝 /pr_buy <тариф>")
        cur.execute("SELECT name, price, duration, description FROM pr_tariffs WHERE name=?", (tn,))
        t = cur.fetchone()
        if not t: return send(peer_id, f"❌ Тариф «{tn}» не найден")
        cur.execute("INSERT INTO pr_orders(user_id,tariff,price,status,created,duration) VALUES(?,?,?,?,?,?)",
                    (uid, t[0], t[1], "wait_pay", int(time.time()), t[2]))
        conn.commit(); oid = cur.lastrowid
        send(peer_id, card("📢 ЗАКАЗ ПИАРА", [
            ("🔢",f"#{oid}"),("📦",t[0]),("💰",f"{t[1]} ₽"),("❓","🟡 Ожидает оплаты")
        ], f"💳 @id{MAIN_OWNER}"))
        for ow in OWNERS:
            send_uid(ow, f"📢 ЗАКАЗ #{oid}\n👤 {mention(uid)}\n📦 {t[0]}\n💰 {t[1]} ₽\n\n✅ /pr_ok {oid}\n❌ /pr_no {oid}")
        return

    if cmd == "/pr_my":
        cur.execute("SELECT id,tariff,price,status,expires_at FROM pr_orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
        rows = cur.fetchall()
        if not rows: return send(peer_id, "📋 Нет заказов")
        st = {"wait_pay":"🟡","paid":"🟢","confirmed":"🔵","sent":"✅","cancelled":"🔴"}
        txt = header("📋 МОИ ЗАКАЗЫ")+"\n\n"
        for oid, tn, p, s, exp in rows:
            txt += f"  {st.get(s,'?')} #{oid} — {tn} — {p} ₽\n"
            if s == "sent" and exp and exp > int(time.time()):
                txt += f"     ⏳ {time_left_fmt(exp-int(time.time()))}\n"
            elif s == "sent" and exp == 0:
                txt += f"     ♾\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/pr_ok":
        if not is_owner(uid): return
        if len(args) < 2: return
        try: oid = int(args[1])
        except: return
        cur.execute("SELECT user_id,status FROM pr_orders WHERE id=?", (oid,))
        o = cur.fetchone()
        if not o or o[1] not in ("wait_pay","paid"): return send(peer_id, "❌")
        cur.execute("UPDATE pr_orders SET status='confirmed', confirmed_by=?, paid_at=? WHERE id=?",
                    (uid, int(time.time()), oid)); conn.commit()
        send(peer_id, f"✅ #{oid} подтверждён\n📝 Отправьте текст пиара следующим сообщением:")
        cur.execute("INSERT OR REPLACE INTO game_state(user_id,game,ts) VALUES(?,?,?)",
                    (uid, f"pr_text:{oid}", int(time.time()))); conn.commit()
        send_uid(o[0], f"✅ Заказ #{oid} подтверждён!"); return

    if cmd == "/pr_no":
        if not is_owner(uid): return
        if len(args) < 2: return
        try: oid = int(args[1])
        except: return
        cur.execute("SELECT user_id FROM pr_orders WHERE id=?", (oid,)); o = cur.fetchone()
        if not o: return
        cur.execute("UPDATE pr_orders SET status='cancelled' WHERE id=?", (oid,)); conn.commit()
        send(peer_id, f"❌ #{oid} отменён")
        send_uid(o[0], f"❌ Заказ #{oid} отклонён"); return

    if cmd == "/pr_orders":
        if not is_owner(uid): return
        cur.execute("SELECT id,user_id,tariff,price,status FROM pr_orders ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "📋 Пусто")
        st = {"wait_pay":"🟡","paid":"🟢","confirmed":"🔵","sent":"✅","cancelled":"🔴"}
        txt = header("ЗАКАЗЫ")+"\n\n"
        for oid,u,tn,p,s in rows: txt += f"  {st.get(s,'?')} #{oid} {tn} {p}₽ {name_of(u)}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/pr_stats":
        if not is_owner(uid): return
        cur.execute("SELECT COUNT(*), SUM(price) FROM pr_orders WHERE status='sent'")
        r = cur.fetchone()
        send(peer_id, card("📊 ПИАР", [("📢",str(r[0] or 0)),("💰",f"{fmt(r[1] or 0)} ₽")])); return

    # ПАРОЛЬ
    if cmd in ("/pass","/пароль"):
        pw = get_password(uid)
        return send(peer_id, f"🔑 `{pw}`\n/adminpanel {pw}" if pw else "❌ Нет пароля")

    if cmd == "/adminpanel":
        if len(args) < 2: return
        pw = args[1]; pdb = get_password(uid)
        if not pdb: return
        if pdb != pw: return send(peer_id, "❌ Неверный пароль")
        p = get_priority(uid)
        cur.execute("SELECT COUNT(*) FROM tickets WHERE answered_by=?", (uid,)); ta = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM tickets WHERE answered_by=? AND status='closed'", (uid,)); tc = cur.fetchone()[0] or 0
        if p >= 80: cmds = build_help_owner(); rk = "👑"
        elif p >= 40: cmds = build_help_admin(); rk = "🛡"
        elif p >= 10: cmds = build_help_admin(); rk = "🔨"
        elif p >= 4: cmds = build_help_admin(); rk = "🎯"
        else: return send(peer_id, "❌ Нет прав")
        st = f"{header('АДМИН-ПАНЕЛЬ')}\n\n  👤 {name_of(uid)}\n  🎭 {rk}\n  📊 {p}/101\n  🎨 {style_name()}\n\n  📩 {tc}/{ta}\n\n  ⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n{style_div()}\n\n"
        send(uid, st + cmds)
        send(peer_id, "✅ В личке!"); return

    if cmd == "/adminpa":
        if uid != MAIN_OWNER: return
        cur.execute("SELECT user_id,priority,password FROM users WHERE password IS NOT NULL AND priority>=1 ORDER BY priority DESC LIMIT 50")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ Пусто")
        txt = header("ПАРОЛИ")+f"\n\n  Всего: {len(rows)}\n\n"
        for tu,pr,pw in rows: txt += f"  🎭 {name_of(tu)}\n     🆔 id{tu}\n     📊 {pr}\n     🔑 `{pw}`\n\n"
        send(peer_id, txt + f"{style_div()}"); return

    # СТИЛЬ
    if cmd in ("/стиль","/style"):
        if len(args) < 2:
            txt = f"{header('🎨 СТИЛИ')}\n\n  🎯 {style_name()} {style_emoji()}\n  🎁 ×{style_bonus()}\n\n"
            for k,v in STYLES.items():
                m = "✅" if k == CURRENT_STYLE else "▫️"
                txt += f"  {m} {v['emoji']} `{k}` — {v['name']} (×{v['bonus']})\n"
            return send(peer_id, txt + f"\n{style_div()}\n📝 /стиль <название> (100+)", kb_back())
        if get_priority(uid) < 100: return send(peer_id, "❌ Только 100+")
        ns = args[1].lower().replace(" ","_")
        if ns not in STYLES:
            for k in STYLES:
                if ns in k or args[1].lower() in STYLES[k]["name"].lower(): ns = k; break
            else: return send(peer_id, "❌ Не найден")
        set_style(ns); cfg = STYLES[ns]
        send(peer_id, f"{style_div()}\n     {cfg['emoji']} СТИЛЬ ИЗМЕНЁН\n{style_div()}\n\n  🎨 {cfg['name']}\n  🎁 ×{cfg['bonus']}\n  👤 {mention(uid)}\n\n{style_div()}"); return

    # БАНК
    if cmd == "/банк":
        bank = get_bank(uid); bal = get_balance(uid)
        send(peer_id, f"{header('🏦 БАНК')}\n\n  👤 {name_of(uid)}\n\n  💰 Баланс: {fmt(bal)} 💵\n  🏦 Счёт: {fmt(bank)} 💵\n  📊 Всего: {fmt(bal+bank)} 💵\n\n  📈 Доход с бизнеса идёт сюда!\n\n{style_div()}\n📝 /положить | /снять", kb_bank()); return

    if cmd == "/положить":
        if len(args) < 2: return
        try: a = int(args[1])
        except: return
        if a <= 0 or get_balance(uid) < a: return send(peer_id, "❌")
        upd_balance(uid, -a); upd_bank(uid, a)
        send(peer_id, f"✅ +{fmt(a)} 💵 в банк\n🏦 {fmt(get_bank(uid))}", kb_bank()); return

    if cmd == "/снять":
        if len(args) < 2: return
        try: a = int(args[1])
        except: return
        if a <= 0 or get_bank(uid) < a: return send(peer_id, "❌")
        upd_bank(uid, -a); upd_balance(uid, a)
        send(peer_id, f"✅ -{fmt(a)} из банка\n💰 {fmt(get_balance(uid))}", kb_bank()); return

    # ============ ГОРОДА ============
    if cmd == "/моигорода":
        c = ucountry(uid)
        if not c: return send(peer_id, "❌ Нет страны", kb_country())
        cur.execute("SELECT id,name,level,population,income,is_capital FROM cities WHERE country=? ORDER BY is_capital DESC, level DESC", (c,))
        rows = cur.fetchall()
        if not rows: return send(peer_id, f"🏙 В стране {c} нет городов", kb_country())
        txt = header(f"🏙 ГОРОДА {c}")+f"\n\n  Всего: {len(rows)}\n\n"
        for cid, n, lv, pop, inc, is_cap in rows:
            cap = "👑 " if is_cap else ""
            txt += f"  {cap}🏙 {n} (ур. {lv})\n     👥 {fmt(pop)} | 💰 {fmt(inc)}/24ч\n\n"
        txt += f"{style_div()}\n📝 /город <название> | /собрать_город <название>"
        send(peer_id, txt, kb_country()); return

    if cmd == "/город":
        if len(args) < 2: return send(peer_id, "📝 /город <название>")
        name = " ".join(args[1:])
        cur.execute("SELECT id,name,country,level,population,income,defense,is_capital FROM cities WHERE LOWER(name)=LOWER(?)", (name,))
        c = cur.fetchone()
        if not c: return send(peer_id, f"❌ Город «{name}» не найден")
        cid, cn, cc, lv, pop, inc, df, cap = c
        cur.execute("SELECT flag FROM countries WHERE name=?", (cc,)); cf = cur.fetchone()
        flag = cf[0] if cf else "🏳️"
        send(peer_id, card(f"🏙 {cn}", [
            ("🌍",f"{flag} {cc}"),
            ("👑 Капитал","Да" if cap else "Нет"),
            ("📊 Уровень",str(lv)),
            ("👥 Население",fmt(pop)),
            ("💰 Доход",f"{fmt(inc)} 💵/24ч"),
            ("🛡 Оборона",fmt(df)),
        ], "/моигорода"), kb_country()); return

    if cmd == "/собрать_город":
        if len(args) < 2: return send(peer_id, "📝 /собрать_город <название>")
        name = " ".join(args[1:])
        cur.execute("SELECT id,name,country,income,last_collect FROM cities WHERE LOWER(name)=LOWER(?)", (name,))
        c = cur.fetchone()
        if not c: return send(peer_id, f"❌ Город не найден")
        cid, cn, cc, inc, lc = c
        if ucountry(uid) != cc and not is_owner(uid):
            return send(peer_id, "❌ Город не вашей страны")
        now = int(time.time()); left = 86400 - (now - (lc or 0))
        if left > 0:
            return send(peer_id, f"⏳ Через {time_left_fmt(left)}")
        # 5% идёт в казну страны, 95% в банк
        treasury_share = int(inc * 0.05)
        bank_share = inc - treasury_share
        upd_bank(uid, bank_share)
        cur.execute("UPDATE countries SET treasury=treasury+? WHERE name=?", (treasury_share, cc))
        cur.execute("UPDATE cities SET last_collect=? WHERE id=?", (now, cid))
        conn.commit()
        send(peer_id, card(f"🏙 {cn}", [
            ("💰 Доход",f"+{fmt(inc)} 💵"),
            ("🏦 В банк",f"{fmt(bank_share)} 💵"),
            ("🏛 В казну",f"{fmt(treasury_share)} 💵"),
        ], "/моигорода"), kb_country()); return

    if cmd == "/купитьгород":
        if len(args) < 3: return send(peer_id, "📝 /купитьгород <название> <цена>")
        name = " ".join(args[1:-1]); 
        try: price = int(args[-1])
        except: return
        if price < 1000: return send(peer_id, "❌ Мин. цена 1000")
        c = ucountry(uid)
        if not c: return send(peer_id, "❌ Нет страны")
        if get_bank(uid) < price: return send(peer_id, f"❌ Нужно {fmt(price)} 💵 в банке")
        cur.execute("SELECT id FROM cities WHERE LOWER(name)=LOWER(?)", (name,))
        if cur.fetchone(): return send(peer_id, "❌ Город уже есть")
        upd_bank(uid, -price)
        cur.execute("INSERT INTO cities(name,country,owner,is_capital) VALUES(?,?,?,0)", (name, c, uid))
        cur.execute("UPDATE countries SET cities=cities+1 WHERE name=?", (c,))
        conn.commit()
        send(peer_id, f"🏙 Город «{name}» куплен за {fmt(price)} 💵", kb_country()); return

    if cmd == "/построить_город":
        if len(args) < 2: return send(peer_id, "📝 /построить_город <название>")
        name = " ".join(args[1:])
        cur.execute("SELECT id,level FROM cities WHERE LOWER(name)=LOWER(?)", (name,))
        c = cur.fetchone()
        if not c: return send(peer_id, "❌ Город не найден")
        cid, lv = c
        cost = 50000 * lv
        if get_bank(uid) < cost: return send(peer_id, f"❌ Нужно {fmt(cost)} 💵")
        upd_bank(uid, -cost)
        cur.execute("UPDATE cities SET level=level+1, population=population+5000, income=income+2000, defense=defense+500 WHERE id=?", (cid,))
        conn.commit()
        send(peer_id, f"🏗 {name} прокачан до ур. {lv+1}", kb_country()); return
        
    # REPORT/OFFER
    if cmd == "/report":
        if len(args) < 2: return send(peer_id, "📝 /report <текст>")
        tm = " ".join(args[1:])
        cur.execute("INSERT INTO tickets(user_id,type,text,created) VALUES(?,?,?,?)", (uid,"report",tm,int(time.time())))
        conn.commit(); tid = cur.lastrowid
        send(peer_id, f"✅ #{tid} отправлено!")
        ttxt = f"📩 ТИКЕТ #{tid}\n👤 {mention(uid)}\n\n{tm}"
        rc = get_report_chat()
        if rc:
            try: send(rc, ttxt, kb_ticket(tid))
            except: pass
        for ow in OWNERS: send_uid(ow, ttxt)
        return

    if cmd == "/offer":
        if len(args) < 2: return send(peer_id, "📝 /offer <текст>")
        tm = " ".join(args[1:])
        cur.execute("INSERT INTO tickets(user_id,type,text,created) VALUES(?,?,?,?)", (uid,"offer",tm,int(time.time())))
        conn.commit(); tid = cur.lastrowid
        send(peer_id, f"✅ Идея #{tid}!")
        ttxt = f"💡 ИДЕЯ #{tid}\n👤 {mention(uid)}\n\n{tm}"
        rc = get_report_chat()
        if rc:
            try: send(rc, ttxt, kb_ticket(tid))
            except: pass
        for ow in OWNERS: send_uid(ow, ttxt)
        return

    if cmd == "/tickets":
        if not is_admin(uid): return
        cur.execute("SELECT id,user_id,text FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "✅ Нет")
        txt = header("ТИКЕТЫ")+"\n\n"
        for tid,tu,tx in rows: txt += f"  #{tid} {name_of(tu)}: {tx[:40]}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/adt":
        if not is_admin(uid): return
        if len(args) < 3: return
        try: tid = int(args[1])
        except: return
        ans = " ".join(args[2:])
        cur.execute("SELECT user_id FROM tickets WHERE id=?", (tid,)); t = cur.fetchone()
        if not t: return
        cur.execute("UPDATE tickets SET status='closed', answer=?, answered_by=? WHERE id=?",
                    (ans, uid, tid)); conn.commit()
        send_uid(t[0], f"📩 ОТВЕТ #{tid}\n\n{ans}"); send(peer_id, "✅"); return

    if cmd == "/build":
        if not is_owner(uid): return
        if len(args) >= 2 and args[1].lower() == "report":
            if not chat_id: return
            cur.execute("INSERT OR REPLACE INTO report_chats(peer_id,linked_by,linked_at) VALUES(?,?,?)",
                        (peer_id, uid, int(time.time()))); conn.commit()
            send(peer_id, "✅ Report-чат привязан"); return
        cur.execute("SELECT chat_id,title,type FROM builds"); rows = cur.fetchall()
        txt = header("ПРИВЯЗАННЫЕ")+"\n\n"
        for c,t,tp in rows: txt += f"  🏛 {t} ({tp}, id {c})\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/builds":
        if not is_owner(uid): return
        if not chat_id: return
        title = " ".join(args[1:]) if len(args)>1 else f"Беседа {chat_id}"
        cur.execute("INSERT OR REPLACE INTO builds(chat_id,peer_id,title,type,linked_by,linked_at) VALUES(?,?,?,?,?,?)",
                    (chat_id,peer_id,title,"chat",uid,int(time.time()))); conn.commit()
        send(peer_id, f"✅ {title}"); return

    # ТИШИНА
    if cmd == "/тишина":
        if not is_admin(uid) or not chat_id: return
        if len(args) < 2: return send(peer_id, "📝 /тишина <0-101|выкл>")
        if args[1].lower() in ("выкл","off","0"):
            cur.execute("DELETE FROM chat_silence WHERE chat_id=?", (chat_id,)); conn.commit()
            return send(peer_id, "🔊 Выкл")
        try: p = max(0, min(101, int(args[1])))
        except: return
        cur.execute("INSERT OR REPLACE INTO chat_silence(chat_id,min_priority) VALUES(?,?)", (chat_id, p)); conn.commit()
        send(peer_id, f"🤫 {p}+"); return

    # ИГРЫ
    if cmd in GAMES_INFO:
        if len(args) < 2:
            set_game_state(uid, cmd); emoji, name, desc = GAMES_INFO[cmd]
            send(peer_id, f"{header(emoji+' '+name)}\n\n  {desc}\n\n  💰 Введите ставку\n\n  💳 {fmt(get_balance(uid))} 💵\n{style_div()}", kb_games()); return
        try: bet = int(args[1])
        except: return
        play_game(peer_id, uid, cmd, bet); return

    if cmd in ("/баланс","баланс"):
        send(peer_id, card("БАЛАНС", [
            ("👤",name_of(uid)),("💰",f"{fmt(get_balance(uid))} 💵"),
            ("🏦",f"{fmt(get_bank(uid))} 💵"),
            ("🏆",f"{ulevel(uid)} {get_title(ulevel(uid))}"),("⚡",f"{uexp(uid)} exp"),
        ]), kb_back()); return

    if cmd == "/уровень":
        lv = ulevel(uid); e = uexp(uid); need = (lv+1)*100
        send(peer_id, card("УРОВЕНЬ", [("📊",str(lv)),("⚡",f"{e} exp"),("📈 До след.",f"{max(0,need-e)}")]), kb_back()); return

    if cmd in ("/топ","топ"):
        cur.execute("SELECT user_id,balance+bank FROM users ORDER BY balance+bank DESC LIMIT 10")
        rows = cur.fetchall(); m = ["🥇","🥈","🥉"] + ["🔹"]*7
        txt = header("ТОП-10")+"\n\n"
        for i,(u,b) in enumerate(rows): txt += f"  {m[i]} {name_of(u)} — {fmt(b)} 💵\n"
        send(peer_id, txt + f"\n{style_div()}", kb_back()); return

    if cmd in ("/приз","приз"):
        last = ulast_bonus(uid) or 0
        left = 86400 - (int(time.time()) - last)
        if left > 0:
            h = left//3600; m_ = (left%3600)//60
            return send(peer_id, f"⏳ Через {h}ч {m_}мин")
        amt = int(random.randint(100, 900000) * style_bonus())
        upd_balance(uid, amt); add_exp(uid, 5)
        cur.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (int(time.time()), uid)); conn.commit()
        send(peer_id, f"🎁 +{fmt(amt)} 💵 | +5 exp\n⏰ Через 24ч"); return

    if cmd == "/ежедневно" or cmd == "/daily":
        last = udaily(uid); now = int(time.time())
        if now - (last or 0) < 86400:
            left = 86400 - (now - (last or 0)); h = left//3600; m_ = (left%3600)//60
            return send(peer_id, f"⏳ {h}ч {m_}мин")
        rw = int(50000 * style_bonus()); upd_balance(uid, rw)
        cur.execute("UPDATE users SET daily=? WHERE user_id=?", (now, uid)); conn.commit()
        add_exp(uid, 20); send(peer_id, f"🎁 +{fmt(rw)} 💵 | +20 exp"); return

    if cmd == "/передать":
        if len(args) < 3: return
        try:
            t = int(args[1].replace("@","").replace("[id","").split("|")[0].split("]")[0]); a = int(args[2])
        except: return
        if a <= 0 or t == uid or get_balance(uid) < a: return
        upd_balance(uid,-a); upd_balance(t,a); send(peer_id, f"✅ {fmt(a)} 💵 → {name_of(t)}"); return

    if cmd == "/донат":
        send(peer_id, card("ДОНАТ",[("⭐","500 000"),("💎","1 000 000")], f"@id{MAIN_OWNER}")); return

    if cmd == "/подписка":
        if ufield(uid, "subscription", 0): return send(peer_id, "✅ Активна")
        try:
            r = vk.groups.isMember(group_id=GROUP_ID, user_id=uid)
            if r:
                cur.execute("UPDATE users SET subscription=1 WHERE user_id=?", (uid,)); upd_balance(uid,50000); conn.commit()
                send(peer_id, "🎉 +50 000 💵")
            else: send(peer_id, f"📰 https://vk.com/club{GROUP_ID}")
        except: send(peer_id, f"📰 https://vk.com/club{GROUP_ID}")
        return

    # РАБОТЫ
    if cmd == "/работы":
        cur.execute("SELECT name,salary,exp,min_exp FROM jobs ORDER BY min_exp"); rows = cur.fetchall()
        e = uexp(uid); bonus = round(get_title_bonus(uid)[0] * style_bonus(), 2)
        txt = header("РАБОТЫ")+f"\n\n  ⚡ {e} exp"
        if bonus > 1.0: txt += f"  🎖️ ×{bonus}"
        txt += "\n\n"
        for n,s,ex,me in rows:
            lk = "✅" if e >= me else "🔒"
            sb = int(s * bonus) if bonus > 1.0 else s
            txt += f"  {lk} {n} — {fmt(sb)} 💵 (+{ex} exp)\n"
        send(peer_id, txt + f"\n{style_div()}\n📝 /устроиться <название>"); return

    if cmd == "/устроиться":
        if len(args) < 2: return
        job = " ".join(args[1:])
        cur.execute("SELECT name,salary,exp,min_exp FROM jobs WHERE LOWER(name)=LOWER(?)", (job,)); j = cur.fetchone()
        if not j: return send(peer_id, "❌ Не найдена")
        if uexp(uid) < j[3]: return send(peer_id, f"❌ Нужно {j[3]} exp")
        cur.execute("UPDATE users SET work=?, work_last=0 WHERE user_id=?", (j[0], uid)); conn.commit()
        send(peer_id, f"💼 Устроены: {j[0]}", kb_back()); return

    if cmd == "/уволиться":
        cur.execute("UPDATE users SET work=NULL WHERE user_id=?", (uid,)); conn.commit()
        send(peer_id, "❌ Уволены"); return

    if cmd == "/работать":
        w = uwork(uid)
        if not w: return send(peer_id, "❌ /работы")
        cur.execute("SELECT salary, exp FROM jobs WHERE name=?", (w,)); j = cur.fetchone()
        if not j: return
        lw = ufield(uid, "work_last", 0); now = int(time.time())
        left = 86400 - (now - (lw or 0))
        if left > 0: return send(peer_id, f"⏳ {time_left_fmt(left)}")
        tbonus, _ = get_title_bonus(uid); bonus = tbonus * style_bonus()
        sal = int(j[0] * bonus); ex = int(j[1] * bonus)
        upd_bank(uid, sal)
        cur.execute("UPDATE users SET work_last=? WHERE user_id=?", (now, uid))
        nlv = add_exp(uid, ex); conn.commit()
        txt = f"💼{style_div()}\n     ✅ СМЕНА\n{style_div()}\n\n  💼 {w}\n  🏦 +{fmt(sal)} 💵 в банк\n  ⚡ +{ex} exp\n"
        if nlv: txt += f"\n🎉 Ур. {nlv}!"
        send(peer_id, txt + f"\n{style_div()}"); return

    # БИЗНЕС
    if cmd in ("/списокбиз","/бизнесы","/биз"):
        p = 0
        if len(args) >= 2:
            try: p = max(0, int(args[1]) - 1)
            except: pass
        return biz_page(peer_id, p)

    if cmd.startswith("/списокбиз_"):
        try: return biz_page(peer_id, max(0, int(cmd.split("_")[1])))
        except: return biz_page(peer_id, 0)

    if cmd == "/купбиз":
        if len(args) < 2: return
        name = " ".join(args[1:])
        cur.execute("SELECT name,price,income FROM biz_types WHERE LOWER(name)=LOWER(?)", (name,)); b = cur.fetchone()
        if not b: return send(peer_id, "❌ Не найден")
        if get_balance(uid) < b[1] and get_bank(uid) < b[1]: return send(peer_id, f"❌ {fmt(b[1])} 💵")
        if get_balance(uid) >= b[1]: upd_balance(uid, -b[1])
        else: upd_bank(uid, -b[1])
        c = ucountry(uid) or "—"
        ib = int(b[2] * style_bonus())
        cur.execute("INSERT INTO companies(owner,country,name,type,income) VALUES(?,?,?,?,?)", (uid, c, b[0], b[0], ib)); conn.commit()
        send(peer_id, f"🏢 {b[0]} куплен за {fmt(b[1])} 💵\n💰 {fmt(ib)}/24ч в банк"); return

    if cmd == "/собрать":
        cur.execute("SELECT id,name,income FROM companies WHERE owner=?", (uid,)); rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ Нет бизнесов")
        total = sum(r[2] for r in rows)
        for cid,_,_ in rows: cur.execute("DELETE FROM companies WHERE id=?", (cid,))
        upd_bank(uid, total)
        cur.execute("UPDATE users SET biz=1 WHERE user_id=?", (uid,)); conn.commit()
        send(peer_id, f"💼 Собрано {fmt(total)} 💵 в банк"); return

    if cmd == "/мбиз":
        cur.execute("SELECT name,income FROM companies WHERE owner=?", (uid,)); rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ Нет")
        txt = header("МОИ БИЗНЕСЫ")+"\n\n"; t = 0
        for n,i in rows: txt += f"  • {n} — {fmt(i)} 💵\n"; t += i
        send(peer_id, txt + f"\n  🏦 {fmt(t)} 💵\n{style_div()}"); return

    # СТРАНЫ
    if cmd in ("/страны","/страна"):
        cur.execute("SELECT name,flag,treasury,army,cities,president FROM countries WHERE alive=1 ORDER BY cities DESC")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "🌍 Нет стран", kb_country())
        txt = header("СТРАНЫ МИРА")+"\n\n"
        for n,f,t,a,c,pr in rows[:25]:
            pn = name_of(pr) if pr else "❌"
            txt += f"  {f or '🏳️'} {n} | 👑 {pn} | ⚔️ {fmt(a)} | 🏙 {c}/40\n"
        send(peer_id, txt + f"\n{style_div()}", kb_country()); return

    if cmd in ("/паспорт","📘 паспорт"):
        pos = get_position(uid) or "—"; cn = ucountry(uid) or "—"
        co = get_country(cn) if cn != "—" else None; fl = co[1] if co else "—"
        send(peer_id, card("ПАСПОРТ", [
            ("👤",name_of(uid)),("🆔",f"id{uid}"),
            ("🌍",f"{fl} {cn}"),("💼",pos),
        ]), kb_country()); return

    if cmd == "/казна":
        c = ucountry(uid)
        if not c: return
        co = get_country(c); st = get_stock(c)
        send(peer_id, card(f"КАЗНА {c}", [
            ("💰",f"{fmt(co[3])} 💵"),("🍞",f"{fmt(st[1])}"),("🔫",f"{fmt(st[2])}"),
            ("🏙",f"{co[5]}"),
        ]), kb_country()); return

    if cmd == "/армия":
        c = ucountry(uid)
        if not c: return
        ca = get_carmy(c)
        send(peer_id, card("АРМИЯ", [("🪖",f"{fmt(ca[1])}"),("🎯 ПВО",f"{fmt(ca[2])}"),
            ("🚀",f"{fmt(ca[3])}"),("🛸",f"{fmt(ca[4])}")]), kb_country()); return

    if cmd in ("/граждане","/города","/правительство","/должности","/очки"):
        c = ucountry(uid)
        if not c: return
        co = get_country(c)
        if cmd == "/граждане":
            cur.execute("SELECT user_id,position FROM members WHERE country=?", (c,)); rows = cur.fetchall()
            txt = header(f"ГРАЖДАНЕ {c}")+f"\n\n"
            for u,p in rows[:20]: txt += f"  👤 {name_of(u)} — {p}\n"
            send(peer_id, txt + f"\n{style_div()}", kb_country())
        elif cmd == "/правительство":
            cur.execute("SELECT user_id,position FROM members WHERE country=? AND position!='Гражданин'", (c,))
            rows = cur.fetchall()
            txt = header(f"ПРАВИТЕЛЬСТВО {c}")+"\n\n"
            for u,p in rows: txt += f"  👑 {name_of(u)} — {p}\n"
            send(peer_id, txt + f"\n{style_div()}", kb_country())
        elif cmd == "/города":
            cur.execute("SELECT name,level,is_capital FROM cities WHERE country=?", (c,)); rows = cur.fetchall()
            txt = header(f"ГОРОДА {c}")+f"\n\n"
            for n,l,cap in rows: txt += f"  {'👑 ' if cap else '🏙 '}{n} (ур. {l})\n"
            send(peer_id, txt + f"\n{style_div()}", kb_country())
        else: send(peer_id, f"📊 {cmd}: доступно", kb_country())
        return

    # МОДЕРАЦИЯ
    if cmd == "/warn":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        get_user(t); cur.execute("UPDATE users SET warns=warns+1 WHERE user_id=?", (t,)); conn.commit()
        cur.execute("SELECT warns FROM users WHERE user_id=?", (t,)); w = cur.fetchone()[0]
        if w >= 3:
            cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t,"3 варна")); conn.commit()
            if chat_id: kick_user(chat_id, t)
            send(peer_id, f"🚫 {mention(t)} автобан")
        else: send(peer_id, f"⚠️ {w}/3 для {mention(t)}")
        return

    if cmd == "/unwarn":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t: cur.execute("UPDATE users SET warns=MAX(0,warns-1) WHERE user_id=?", (t,)); conn.commit()
        return

    if cmd == "/mute":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id, "📝 /mute <юзер> <мин> [причина]")
        try: m = int(args[2]) if len(args)>2 else 60
        except: m = 60
        if is_owner(t) or is_admin(t): return
        reason = " ".join(args[3:]) if len(args) > 3 else "не указана"
        get_user(t); until = int(time.time()) + m*60
        cur.execute("UPDATE users SET mute_until=? WHERE user_id=?", (until, t)); conn.commit()
        dt = datetime.fromtimestamp(until).strftime("%d.%m.%Y %H:%M")
        cur.execute("SELECT nick FROM nicks WHERE user_id=?", (uid,)); ar = cur.fetchone()
        an = ar[0] if ar and ar[0] else f"id{uid}"
        txt = (f"{style_div()}\n     🔇 МУТ ВЫДАН\n{style_div()}\n\n"
               f"  ✅ Кому: {mention(t)}\n  ⏳ Срок: {time_left_fmt(m*60)} (до {dt})\n"
               f"  📝 Причина: {reason}\n  👮 Модератор: @id{uid} ({an})\n\n{style_div()}")
        send(peer_id, txt)
        send_uid(t, txt + "\n\n🚫 Писать запрещено")
        return

    if cmd == "/unmute":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t: cur.execute("UPDATE users SET mute_until=0, mute_notify=0 WHERE user_id=?", (t,)); conn.commit()
        return

    if cmd == "/kick":
        if not is_admin(uid) or not chat_id: return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        kick_user(chat_id, t); send(peer_id, f"👢 {mention(t)}"); return

    if cmd == "/ban":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t, reason)); conn.commit()
        if chat_id: kick_user(chat_id, t)
        cur.execute("SELECT nick FROM nicks WHERE user_id=?", (uid,)); ar = cur.fetchone()
        an = ar[0] if ar and ar[0] else f"id{uid}"
        txt = (f"{style_div()}\n     🚫 БАН\n{style_div()}\n\n"
               f"  ✅ Кому: {mention(t)}\n  📝 Причина: {reason}\n  👮 @id{uid} ({an})\n\n{style_div()}")
        send(peer_id, txt); send_uid(t, txt); return

    if cmd == "/unban":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t: cur.execute("DELETE FROM bans WHERE user_id=?", (t,)); conn.commit()
        return

    if cmd == "/gban":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or t in OWNERS: return
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t, reason)); conn.commit()
        kicked = 0
        cur.execute("SELECT chat_id FROM builds"); chats = cur.fetchall()
        for (cid,) in chats:
            try: vk.messages.removeChatUser(chat_id=cid, user_id=t); kicked += 1
            except: pass
        if chat_id:
            if kick_user(chat_id, t): kicked += 1
        send(peer_id, f"🚫 GBAN {mention(t)}\n🏛 Из {kicked} чатов\n📝 {reason}")
        send_uid(t, f"🚫 Глобальный бан: {reason}"); return

    if cmd == "/banlist":
        cur.execute("SELECT user_id,reason FROM bans"); rows = cur.fetchall()
        if not rows: return send(peer_id, "Пусто")
        txt = header("БАНЛИСТ")+"\n\n"
        for u,r in rows: txt += f"  🚫 id{u} — {r}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    # РОЛИ
    if cmd == "/role":
        cur.execute("SELECT name,priority,emoji FROM roles ORDER BY priority DESC"); rows = cur.fetchall()
        txt = header("РОЛИ")+"\n\n"
        for n,p,e in rows: txt += f"  {e} {n} — {p}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/newrole":
        if not is_owner(uid): return
        if len(args) < 3: return
        last = args[-1]
        he = any(ord(c) > 0x2600 for c in last) and len(last) < 6
        if he:
            emoji = last
            try: prio = max(0, min(101, int(args[-2])))
            except: return
            name = " ".join(args[1:-2])
        else:
            emoji = "🎭"
            try: prio = max(0, min(101, int(args[-1])))
            except: return
            name = " ".join(args[1:-1])
        if not name: return
        cur.execute("INSERT OR REPLACE INTO roles(name,priority,emoji,created_by,created_at) VALUES(?,?,?,?,?)",
                    (name, prio, emoji, uid, int(time.time()))); conn.commit()
        send(peer_id, f"✅ {name} {emoji} — {prio}"); return

    if cmd == "/setrole":
        if not is_owner(uid) and not is_admin(uid): return
        if len(args) < 3: return
        t = extract_uid(args[1], event_msg)
        if not t: return
        get_user(t)
        try: prio = max(0, min(101, int(args[2])))
        except: return
        cur.execute("SELECT name FROM roles WHERE priority=?", (prio,)); rr = cur.fetchone()
        rn = rr[0] if rr else f"Приоритет {prio}"
        if chat_id:
            cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)", (t, chat_id, rn))
        cur.execute("UPDATE users SET role=?, priority=? WHERE user_id=?", (rn, prio, t))
        pw = gen_password(); set_password(t, pw)
        send(peer_id, f"✅ {mention(t)} → {rn} ({prio})")
        send_uid(t, f"🎭 Приоритет *{prio}*\n🔐 `{pw}`\n/adminpanel {pw}"); return

    if cmd == "/grole":
        if not is_owner(uid): return
        if len(args) < 3: return
        t = extract_uid(args[1], event_msg)
        if not t: return
        get_user(t)
        try: prio = max(0, min(101, int(args[2])))
        except: return
        cur.execute("SELECT name FROM roles WHERE priority=?", (prio,)); rr = cur.fetchone()
        rn = rr[0] if rr else f"Приоритет {prio}"
        cur.execute("INSERT OR REPLACE INTO global_roles(user_id,role) VALUES(?,?)", (t, rn))
        cur.execute("UPDATE users SET role=?, priority=? WHERE user_id=?", (rn, prio, t))
        pw = gen_password(); set_password(t, pw); conn.commit()
        ap = apply_global_role_everywhere(t)
        send(peer_id, f"🌐 {mention(t)} → {rn} ({prio})\n🏛 {ap} чатов")
        send_uid(t, f"🌐 Глобально *{prio}*\n🔐 `{pw}`\n/adminpanel {pw}"); return

    if cmd == "/setpass":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        pw = gen_password(); set_password(t, pw)
        send(peer_id, f"🔐 → {mention(t)}")
        send_uid(t, f"🔐 `{pw}`"); return

    if cmd == "/staff":
        if not chat_id: return
        cur.execute("SELECT user_id, role FROM user_roles WHERE chat_id=?", (chat_id,)); rows = cur.fetchall()
        txt = header("СОСТАВ")+"\n\n"
        if not rows: txt += "  ❌\n"
        else:
            for u,r in rows: txt += f"  🎭 {r} → {mention(u)}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/gstaff":
        cur.execute("""SELECT u.user_id, COALESCE(gr.role, u.role) FROM users u
                       LEFT JOIN global_roles gr ON gr.user_id=u.user_id
                       WHERE u.priority >= 4 OR gr.role IS NOT NULL""")
        rows = cur.fetchall()
        txt = header("ГЛОБАЛЬНЫЙ СОСТАВ")+"\n\n"
        for u,r in rows: txt += f"  🌐 {r} → {mention(u)}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/nick":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t and (is_admin(uid) or is_owner(uid)) and t != uid:
            if len(args)<3: return
            nick = " ".join(args[2:])
        else:
            t = uid; nick = " ".join(args[1:])
            if not nick: return
        cur.execute("INSERT OR REPLACE INTO nicks(user_id,nick) VALUES(?,?)", (t, nick)); conn.commit()
        send(peer_id, f"✅ {mention(t)}: {nick}"); return

    if cmd == "/rnick":
        if not is_admin(uid) and not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t: cur.execute("DELETE FROM nicks WHERE user_id=?", (t,)); conn.commit()
        return

    if cmd == "/стата":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg) or uid
        send(peer_id, card("СТАТА", [
            ("👤",name_of(t)),("🎭",f"Приоритет {get_priority(t)}"),
            ("🏆",f"{ulevel(t)} {get_title(ulevel(t))}"),
            ("💰",f"{fmt(get_balance(t))} 💵"),("🏦",f"{fmt(get_bank(t))} 💵"),
        ]), kb_back()); return

    if cmd == "/объявление":
        if not is_owner(uid): return
        if len(args)<2: return
        tm = " ".join(args[1:])
        cur.execute("SELECT peer_id FROM builds"); rows = cur.fetchall()
        s = 0
        for (p,) in rows:
            try:
                vk.messages.send(peer_id=p, message=f"{header('ОБЪЯВЛЕНИЕ')}\n\n{tm}\n{style_div()}", random_id=get_random_id())
                s += 1
            except: pass
        send(peer_id, f"📢 в {s}"); return

    # ВЛАДЕЛЕЦ
    if cmd == "/обнулить":
        if not is_owner(uid) and not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("UPDATE users SET balance=0, bank=0, warns=0 WHERE user_id=?", (t,)); conn.commit()
        send(peer_id, f"♻️ {mention(t)}"); return

    if cmd == "/вайп":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or t in OWNERS: return
        cur.execute("""UPDATE users SET balance=0, bank=0, warns=0, role='user', country=NULL,
                       priority=0, exp=0, level=0, work=NULL, password=NULL, title=NULL WHERE user_id=?""", (t,))
        for q in ["DELETE FROM user_roles WHERE user_id=?","DELETE FROM global_roles WHERE user_id=?",
                  "DELETE FROM companies WHERE owner=?","DELETE FROM nicks WHERE user_id=?",
                  "DELETE FROM members WHERE user_id=?"]:
            cur.execute(q, (t,))
        conn.commit(); send(peer_id, f"💀 {mention(t)}"); return

    if cmd == "/выдать":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return
        try: a = int(args[2])
        except: return
        upd_balance(t, a); send(peer_id, f"✅ +{fmt(a)} 💵"); return

    if cmd == "/вернуть":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return
        try: a = int(args[2])
        except: return
        upd_balance(t, -a); send(peer_id, f"✅ -{fmt(a)} 💵"); return

    # ТИТУЛЫ
    if cmd == "/мтитул":
        bonus, _ = get_title_bonus(uid)
        send(peer_id, card("МОЙ ТИТУЛ", [
            ("👤",name_of(uid)),("⭐",utitle(uid) or "—"),
            ("🎰 Титул",f"×{bonus}"),("🎨 Стиль",f"×{style_bonus()}"),
        ]), kb_back()); return

    if cmd == "/титул":
        if uid != MAIN_OWNER: return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return
        title = " ".join(args[2:])
        cur.execute("UPDATE users SET title=? WHERE user_id=?", (title, t)); conn.commit()
        send(peer_id, f"✅ {mention(t)}: {title}"); return

    # ПРОМО
    if cmd == "/promo":
        if len(args)<2: return
        code = args[1].upper()
        cur.execute("SELECT amount,uses,max_uses FROM promos WHERE code=?", (code,)); p = cur.fetchone()
        if not p or p[1]>=p[2]: return send(peer_id, "❌")
        cur.execute("UPDATE promos SET uses=uses+1 WHERE code=?", (code,)); conn.commit()
        upd_balance(uid,p[0]); send(peer_id, f"🎟️ +{fmt(p[0])} 💵"); return

    if cmd == "/createpromo":
        if not is_owner(uid): return
        if len(args)<4: return
        code = args[1].upper()
        try: a = int(args[2]); u = int(args[3])
        except: return
        cur.execute("INSERT OR REPLACE INTO promos(code,amount,uses,max_uses) VALUES(?,?,0,?)", (code,a,u)); conn.commit()
        send(peer_id, f"🎟️ {code} создан"); return

    # МАФИЯ
    if cmd in ("/ивент","/мафия"):
        if chat_id: mafia_new(peer_id, uid, chat_id); return
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

    if cmd == "/q":
        if not chat_id: return
        if is_owner(uid) or is_admin(uid): return
        kick_user(chat_id, uid); return

    if cmd == "/меню" or low in ("начать","start","меню","◀️ меню"):
        send(peer_id, f"{header('БОЕВОЙ БОТ')}\n\n  👤 {name_of(uid)}\n  💰 {fmt(get_balance(uid))} 💵\n  🏦 {fmt(get_bank(uid))} 💵\n  🏆 Ур. {ulevel(uid)}\n\n  📖 /help", kb_main()); return

    if cmd == "/help": send(peer_id, build_help_user(), kb_back()); return
    if cmd == "/ahelp":
        if get_priority(uid) < 4: return
        send(peer_id, build_help_admin(), kb_back()); return
    if cmd == "/ghelp":
        if not is_owner(uid): return
        send(peer_id, build_help_owner(), kb_back()); return


def biz_page(peer_id, page):
    if page < 0: page = 0
    cur.execute("SELECT COUNT(*) FROM biz_types"); total = cur.fetchone()[0]
    pages = (total + 9) // 10
    if page >= pages: page = pages - 1
    cur.execute("SELECT name,price,income FROM biz_types ORDER BY price LIMIT 10 OFFSET ?", (page*10,))
    rows = cur.fetchall()
    if not rows: return send(peer_id, "❌ Нет", kb_back())
    txt = header(f"БИЗНЕСЫ ({page+1}/{pages})")+f"\n\n"
    for n,p,i in rows:
        ib = int(i * style_bonus())
        txt += f"  🏢 {n}\n     💰 {fmt(p)} | 🏦 {fmt(ib)}/24ч\n\n"
    txt += f"{style_div()}\n📝 /купбиз <название>"
    send(peer_id, txt, kb([
        [kbc("◀️ Назад", f"/списокбиз_{page-1}", "secondary"),
         kbc("Вперёд ▶️", f"/списокбиз_{page+1}", "primary")],
        [kbt("◀️ Меню","/меню","secondary")],
    ]))


def handle_chat_invite(peer_id, member_id):
    if is_banned(member_id):
        ch = peer_to_chat(peer_id)
        if ch: kick_user(ch, member_id)
        return
    chat_id = peer_to_chat(peer_id)
    if chat_id:
        role = apply_global_role_in_chat(member_id, chat_id)
        if role:
            try: send(peer_id, f"🎭 {mention(member_id)} — *{role}*")
            except: pass


# ============ ЗАПУСК ============
def main():
    log("⚔️ Бот запускается...")
    try:
        get_user(MAIN_OWNER)
        for ow in OWNERS:
            try:
                get_user(ow)
                cur.execute("UPDATE users SET role='Гл.Владелец', priority=101, balance=MAX(balance,999999999) WHERE user_id=?", (ow,))
            except: pass
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM biz_types"); bc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM countries"); cc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cities"); ctc = cur.fetchone()[0]
        log(f"🏢 Бизнесов: {bc} | 🌍 Стран: {cc} | 🏙 Городов: {ctc}")
        log(f"🎨 Стиль: {style_name()}")
    except Exception as e: log(f"⚠️ {e}")

    log("🎧 Слушаю события...")
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
                    except Exception as e: log(f"MEv: {e}")
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
                except Exception as e:
                    log(f"❌ Handler: {e}")
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            log(f"❌ LongPoll: {type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stdout)
            time.sleep(3)


if __name__ == "__main__":
    main()
    
