# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3, random, time, json, os, sys, traceback, threading
from datetime import datetime
from collections import deque
import requests
import urllib.request

def log(msg):
    print(msg, flush=True); sys.stdout.flush()

# ============ НАСТРОЙКИ ============
FALLBACK_TOKEN = ""  # Вставь токен ИЛИ задай env VK_TOKEN
TOKEN = os.getenv("VK_TOKEN") or FALLBACK_TOKEN
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
STYLES = {
    "обычный": {"emoji":"⚔️","div":"▬","name":"Обычный","bonus":1.0},
    "хэллоуин": {"emoji":"🎃","div":"🎃","name":"Хэллоуин","bonus":1.5},
    "новый_год": {"emoji":"🎄","div":"❄️","name":"Новый год","bonus":1.5},
    "пасха": {"emoji":"🐣","div":"🌸","name":"Пасха","bonus":1.4},
    "1_сентября": {"emoji":"📚","div":"✏️","name":"1 сентября","bonus":1.3},
    "admin_abuse": {"emoji":"🚨","div":"🔥","name":"Admin Abuse","bonus":2.0},
}
CURRENT_STYLE = "обычный"

RAID_COST = 50000
RAID_COOLDOWN = 3600
RAID_SUCCESS_CHANCE = 0.40

MAT_ROOTS = (
    "хуй","хуя","хую","хуе","хуё","хер","хрен","пизд","пизж","пезд",
    "бля","бляд","блят","ебан","ебал","ебуч","ебат","ебет","ебёт","ебну","ебля",
    "сука","суки","сучк","мудак","мудил","мудозв","гандон","гондон",
    "долбоеб","долбоёб","залуп","шлюх","шалав","fuck","shit","bitch","cunt","dick","pussy","asshole",
)

# ============ БАЗА ДАННЫХ (В /app/data) ============
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
if not os.path.exists(DATA_DIR):
    try: os.makedirs(DATA_DIR, exist_ok=True)
    except: DATA_DIR = "."

DB_PATH = os.path.join(DATA_DIR, 'bot.db')
log(f"📁 База данных: {DB_PATH}")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 100,
        bank INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, role TEXT DEFAULT 'user', priority INTEGER DEFAULT 0,
        country TEXT, citizenship TEXT, army INTEGER DEFAULT 100000, war INTEGER DEFAULT 1000000,
        mute_until INTEGER DEFAULT 0, last_bonus INTEGER DEFAULT 0, rank TEXT DEFAULT 'Новобранец',
        biz INTEGER DEFAULT 0, biz_income INTEGER DEFAULT 0, biz_collect INTEGER DEFAULT 0,
        subscription INTEGER DEFAULT 0, points INTEGER DEFAULT 0, exp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
        work TEXT, work_last INTEGER DEFAULT 0, password TEXT, exp_last INTEGER DEFAULT 0,
        title TEXT, rep INTEGER DEFAULT 0, daily INTEGER DEFAULT 0, mute_notify INTEGER DEFAULT 0,
        married_to INTEGER DEFAULT 0, married_date INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS countries(name TEXT PRIMARY KEY, flag TEXT,
        owner INTEGER, president INTEGER, treasury INTEGER DEFAULT 100000, army INTEGER DEFAULT 100000,
        cities INTEGER DEFAULT 3, taxes INTEGER DEFAULT 5, pvo INTEGER DEFAULT 0,
        border_open INTEGER DEFAULT 1, buildings TEXT DEFAULT '{}', projects TEXT DEFAULT '{}',
        alive INTEGER DEFAULT 1, last_mob INTEGER DEFAULT 0, points INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cities(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, country TEXT, owner INTEGER, level INTEGER DEFAULT 1,
        population INTEGER DEFAULT 10000, income INTEGER DEFAULT 5000,
        defense INTEGER DEFAULT 1000, is_capital INTEGER DEFAULT 0, last_collect INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY, amount INTEGER,
        uses INTEGER, max_uses INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bans(user_id INTEGER PRIMARY KEY, reason TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS wars(id INTEGER PRIMARY KEY AUTOINCREMENT,
        attacker TEXT, defender TEXT, started INTEGER, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS members(user_id INTEGER PRIMARY KEY, country TEXT,
        position TEXT DEFAULT 'Гражданин')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner INTEGER, country TEXT, name TEXT, type TEXT, income INTEGER DEFAULT 1000)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stockpile(country TEXT PRIMARY KEY, food INTEGER DEFAULT 0,
        weapons INTEGER DEFAULT 0, resources INTEGER DEFAULT 0, fuel INTEGER DEFAULT 0, money INTEGER DEFAULT 0)""")
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
    cur.execute("""CREATE TABLE IF NOT EXISTS pr_orders(id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, tariff TEXT, price INTEGER, text TEXT, status TEXT DEFAULT 'wait_pay',
        created INTEGER, paid_at INTEGER, confirmed_by INTEGER, sent_at INTEGER,
        sent_count INTEGER DEFAULT 0, duration INTEGER DEFAULT 0, expires_at INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_stats(user_id INTEGER PRIMARY KEY,
        bans INTEGER DEFAULT 0, mutes INTEGER DEFAULT 0, warns INTEGER DEFAULT 0,
        reports INTEGER DEFAULT 0, offers INTEGER DEFAULT 0, tickets INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS case_stats(user_id INTEGER, case_key TEXT,
        count INTEGER DEFAULT 0, PRIMARY KEY(user_id, case_key))""")
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

    cur.execute("INSERT OR IGNORE INTO bot_settings(key,value) VALUES(?,?)", ("style","обычный"))
    cur.execute("INSERT OR IGNORE INTO bot_settings(key,value) VALUES(?,?)", ("drone_case_active","0"))
    cur.execute("INSERT OR IGNORE INTO bot_settings(key,value) VALUES(?,?)", ("season_active","0"))
    conn.commit()

try:
    init_db(); log("✅ БД инициализирована")
except Exception as e:
    log(f"❌ Ошибка БД: {e}"); traceback.print_exc(file=sys.stdout); raise SystemExit(1)

# ============ ЗАЩИТА ОТ ДУБЛИКАТОВ ============
_processed_ids = deque(maxlen=1000)

def is_duplicate(msg_id):
    if msg_id in _processed_ids: return True
    _processed_ids.append(msg_id)
    return False

# ============ МИГРАЦИИ ============
def _col_exists(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())
def _add_col(table, col, dfn):
    if not _col_exists(table, col):
        try: cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dfn}"); conn.commit()
        except: pass

for t, c, d in [
    ("users","priority","INTEGER DEFAULT 0"),("users","exp","INTEGER DEFAULT 0"),
    ("users","level","INTEGER DEFAULT 0"),("users","work","TEXT"),
    ("users","work_last","INTEGER DEFAULT 0"),("users","password","TEXT"),
    ("users","exp_last","INTEGER DEFAULT 0"),("users","title","TEXT"),
    ("users","rep","INTEGER DEFAULT 0"),("users","daily","INTEGER DEFAULT 0"),
    ("users","mute_notify","INTEGER DEFAULT 0"),("users","bank","INTEGER DEFAULT 0"),
    ("jobs","min_exp","INTEGER DEFAULT 0"),("roles","emoji","TEXT DEFAULT '🎭'"),
    ("builds","type","TEXT DEFAULT 'chat'"),("pr_orders","duration","INTEGER DEFAULT 0"),
    ("pr_orders","expires_at","INTEGER DEFAULT 0"),("cities","last_collect","INTEGER DEFAULT 0"),
    ("users","raid_last","INTEGER DEFAULT 0"),("users","msg_count","INTEGER DEFAULT 0"),
    ("users","mat_count","INTEGER DEFAULT 0"),("users","captures","INTEGER DEFAULT 0"),
    ("pr_orders","interval_min","INTEGER DEFAULT 0"),("pr_orders","last_resend","INTEGER DEFAULT 0"),
    ("users","married_to","INTEGER DEFAULT 0"),("users","married_date","INTEGER DEFAULT 0"),
    ("users","aevent_last","INTEGER DEFAULT 0"),("users","drone_last","INTEGER DEFAULT 0"),
    ("users","vip_until","INTEGER DEFAULT 0"),("users","drone_mult","INTEGER DEFAULT 1"),
    ("users","drone_name","TEXT"),("users","daily_case_last","INTEGER DEFAULT 0"),
]:
    _add_col(t, c, d)
    # ============ СТИЛЬ ============
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
def style_div(): return style_cfg()["div"] * 20
def style_emoji(): return style_cfg()["emoji"]
def style_bonus(): return style_cfg()["bonus"]
def style_name(): return style_cfg()["name"]

# ============ ХЕЛПЕРЫ ЮЗЕРА ============
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
def umsg_count(uid): return ufield(uid, "msg_count", 0)
def uwarns(uid): return ufield(uid, "warns", 0)
def umarried_to(uid): return ufield(uid, "married_to", 0)
def umarried_date(uid): return ufield(uid, "married_date", 0)
def udrone_mult(uid): return ufield(uid, "drone_mult", 1) or 1
def udrone_name(uid): return ufield(uid, "drone_name", None)

def is_vip(uid):
    v = ufield(uid, "vip_until", 0)
    return v and v > int(time.time())

def get_password(uid): return upassword(uid)
def set_password(uid, pw):
    get_user(uid); cur.execute("UPDATE users SET password=? WHERE user_id=?", (pw, uid)); conn.commit()
def upd_balance(uid, amount):
    get_user(uid); cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid)); conn.commit()
def upd_bank(uid, amount):
    get_user(uid); cur.execute("UPDATE users SET bank=bank+? WHERE user_id=?", (amount, uid)); conn.commit()
def get_balance(uid): return ubal(uid)
def get_bank(uid): return ubank(uid)

# ============ ПРОГРЕСС-БАР И УРОВНИ ============
def get_progress_bar(current, total, length=8):
    if total <= 0: return "▱" * length
    current = max(0, min(current, total))
    filled = int((current / total) * length)
    return "▰" * filled + "▱" * (length - filled)

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

# ============ КАРТОЧКИ НАКАЗАНИЙ ============
def punish_card(action, target, reason, mod):
    names = {"ban": "ЗАБАНЕН", "mute": "МУТ", "warn": "ВАРН", "kick": "ИСКЛЮЧЕН", "gban": "ГЛОБАЛЬНЫЙ БАН"}
    emojis = {"ban": "🚫", "mute": "🔇", "warn": "⚠️", "kick": "👢", "gban": "🌐"}
    title = f"{emojis.get(action, '')} {names.get(action, action.upper())}"
    cur.execute("SELECT nick FROM nicks WHERE user_id=?", (mod,)); r = cur.fetchone()
    mod_name = r[0] if r and r[0] else f"id{mod}"
    return (f"{style_div()}\n     {title}\n{style_div()}\n\n"
            f"  👤 Нарушитель: {mention(target)}\n\n"
            f"  📝 Причина: {reason}\n"
            f"  👮 Модератор: @id{mod} ({mod_name})\n\n"
            f"{style_div()}")

# ============ СТРАНЫ / ГОРОДА ============
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
    co = get_country(c)
    if not co: return False
    return co[3] == uid or co[2] == uid

# ============ ИГРОВОЕ СОСТОЯНИЕ / EXP ============
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

# ============ СТАТИСТИКА АДМИНОВ ============
def inc_admin_stat(uid, field):
    if field not in ("bans","mutes","warns","reports","offers","tickets"): return
    cur.execute("SELECT user_id FROM admin_stats WHERE user_id=?", (uid,))
    if not cur.fetchone():
        cur.execute("INSERT INTO admin_stats(user_id) VALUES(?)", (uid,))
    cur.execute(f"UPDATE admin_stats SET {field}={field}+1 WHERE user_id=?", (uid,))
    conn.commit()

def get_admin_stats(uid):
    cur.execute("SELECT bans,mutes,warns,reports,offers,tickets FROM admin_stats WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r: return (0,0,0,0,0,0)
    return r

# ============ МАТ-ФИЛЬТР ============
def has_mat(text):
    low = text.lower()
    return any(root in low for root in MAT_ROOTS)

# ============ VK ИНИЦИАЛИЗАЦИЯ ============
vk = None
longpoll = None

def _init_vk():
    global vk, longpoll
    try:
        log("📡 VK сессия...")
        _sess = vk_api.VkApi(token=TOKEN)
        vk = _sess.get_api()
        try:
            info = vk.groups.getById(group_id=GROUP_ID)
            log(f"✅ Группа: {info[0]['name']}")
        except Exception as e:
            log(f"❌ {type(e).__name__}: {e}"); return False
        longpoll = VkBotLongPoll(_sess, GROUP_ID)
        log("✅ Long Poll готов")
        return True
    except Exception as e:
        log(f"❌ VK: {e}"); traceback.print_exc(file=sys.stdout)
        return False

if not _init_vk():
    log("⚠️ VK не инициализирован на старте — попробуем в main()")

def send(peer_id, text, keyboard=None, attachment=None):
    try:
        kw = {"peer_id": peer_id, "message": text, "random_id": get_random_id()}
        # Клавиатура ТОЛЬКО в ЛС — в беседах VK её не принимает
        if peer_id < 2000000000 and keyboard:
            kw["keyboard"] = keyboard
        if attachment:
            kw["attachment"] = attachment
        vk.messages.send(**kw)
    except Exception as e:
        log(f"❌ Send peer={peer_id}: {e}")
        # Если упало из-за клавиатуры — пробуем без неё
        if "keyboard" in kw:
            try:
                del kw["keyboard"]
                vk.messages.send(**kw)
            except Exception as e2:
                log(f"❌ Send без kb: {e2}")

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

def get_chat_link(peer_id):
    if peer_id >= 2000000000: cid = peer_id - 2000000000
    else: cid = peer_id
    return f"https://m.vk.ru/gim{GROUP_ID}/convo/{cid}?entrypoint=list_all"

# ============ ОТПРАВКА КАРТИНКИ /СТАТА ============
def vk_upload_photo(peer_id, file_path):
    """Загружает фото. Работает и для ЛС, и для бесед."""
    try:
        server = None
        try:
            server = vk.photos.getMessagesUploadServer(peer_id=peer_id)
            log(f"📤 upload server (peer_id={peer_id}) OK")
        except Exception as e1:
            log(f"⚠️ upload с peer_id упал: {e1}, пробую без")
            try:
                server = vk.photos.getMessagesUploadServer()
                log("📤 upload server (без peer_id) OK")
            except Exception as e2:
                log(f"❌ upload без peer_id: {e2}")
                return None

        with open(file_path, "rb") as f:
            r = requests.post(server["upload_url"], files={"photo": ("stats.png", f)}, timeout=20)
        resp = r.json()
        log(f"📤 upload resp: {str(resp)[:200]}")

        if "photo" not in resp:
            log(f"❌ нет photo в ответе: {resp}")
            return None

        saved = vk.photos.saveMessagesPhoto(
            photo=resp["photo"], server=resp["server"], hash=resp["hash"]
        )
        if not saved:
            log("❌ saveMessagesPhoto вернул пусто")
            return None
        p = saved[0]
        att = f"photo{p['owner_id']}_{p['id']}"
        log(f"✅ Фото загружено: {att}")
        return att
    except Exception as e:
        log(f"❌ vk_upload_photo: {e}")
        traceback.print_exc(file=sys.stdout)
        return None

_stats_cache = {}
STATS_CACHE_TTL = 300

def build_stats_user_dict(uid, chat_id=None):
    lvl = ulevel(uid); exp = uexp(uid)
    need = (lvl + 1) * 100
    pct = int((exp / need) * 100) if need else 0
    m_to = umarried_to(uid)
    partner = name_of(m_to) if m_to else "нет"
    pos = get_position(uid) or "—"
    cur.execute("SELECT role FROM user_roles WHERE user_id=? AND chat_id=?", (uid, chat_id or 0))
    ur = cur.fetchone()
    chat_role = ur[0] if ur else "Участник"
    status = get_title(lvl)
    status_emoji = get_priority_emoji(get_priority(uid))

    # Получаем аватарку
    avatar_url = ""
    try:
        info = vk.users.get(user_ids=uid, fields="photo_200")[0]
        avatar_url = info.get("photo_200", "")
    except: pass

    return {
        "name": name_of(uid),
        "avatar_url": avatar_url,
        "title": pos, "priv": "Игрок", "vip": is_vip(uid),
        "role": chat_role, "priority": get_priority(uid), "msgs": umsg_count(uid),
        "lvl": lvl, "lvl_max": 999, "xp": exp, "xp_max": need, "xp_pct": pct,
        "warns": uwarns(uid), "marriage": partner, "rep": urep(uid),
        "nick": ufield(uid, "nick") or "не установлен", "gift": udrone_name(uid) or "—",
        "drone_mult": udrone_mult(uid),
        "status": status, "status_emoji": status_emoji,
    }

def send_stats_card(peer_id, uid, chat_id=None):
    now = int(time.time())
    cached = _stats_cache.get(uid)
    if cached and now - cached[1] < STATS_CACHE_TTL:
        try:
            vk.messages.send(peer_id=peer_id, message="", random_id=get_random_id(), attachment=cached[0])
            return True
        except Exception as e:
            log(f"⚠️ cached send упал: {e}")

    try:
        from stats_card import render_card
    except Exception as e:
        log(f"❌ stats_card НЕ загружен: {type(e).__name__}: {e}")
        return False

    try:
        from PIL import Image as _T1
        import requests as _T2
    except Exception as e:
        log(f"❌ Pillow/requests не установлены: {e}")
        return False

    try:
        u = build_stats_user_dict(uid, chat_id)
        bg_url = "https://i.postimg.cc/4x3XfLZW/ffaa3ac666ac63e26a51b9b22f83fcf8.jpg"
        
        # Передаем аватарку
        avatar_url = u.get("avatar_url", "")
        path = render_card(bg_url, u, avatar_url=avatar_url, out_path=f"stats_{uid}.png")
        
        log(f"✅ Картинка сгенерирована: {path}")
    except Exception as e:
        log(f"❌ render_card: {type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stdout)
        return False

    att = vk_upload_photo(peer_id, path)
    if not att:
        log(f"❌ Не удалось загрузить фото для peer={peer_id}")
        try: os.remove(path)
        except: pass
        return False

    try:
        vk.messages.send(peer_id=peer_id, message="", random_id=get_random_id(), attachment=att)
        _stats_cache[uid] = (att, now)
        log(f"✅ /стата отправлена (peer={peer_id}, att={att})")
        try: os.remove(path)
        except: pass
        return True
    except Exception as e:
        log(f"❌ Финальный send упал: {e}")
        try: os.remove(path)
        except: pass
        return False

# ============ КЛАВИАТУРЫ ============
def header(t):
    cfg = style_cfg(); div = cfg["div"] * 20
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
        [kbt("🌍 Страна","/страна","secondary"), kbt("🎫 Гражданство","/гражданство","positive")],
        [kbt("🏙 Города","/моигорода","secondary"), kbt("🏴 Налёт","/налёт","negative")],
        [kbt("💼 Работы","/работы"), kbt("🏢 Бизнесы","/списокбиз")],
        [kbt("🏆 Уровень","/уровень","positive"), kbt("🎖️ Титул","/мтитул","primary")],
        [kbt("📢 Пиар","/пиар","positive"), kbt("💞 Брак","/брак","positive")],
        [kbt("🎁 Кейсы","/кейс","positive"), kbt("🆘 Помощь","/help","secondary")],
        [kbt("📊 Моя стата","/стата","secondary")],
    ])

def kb_games():
    return kb([
        [kbc("🎰 Казино","/казино"), kbc("🪙 Монетка","/монетка")],
        [kbc("🎲 Кубик","/кубик"), kbc("🍒 Слоты","/слоты")],
        [kbc("🎡 Рулетка","/рулетка"), kbc("🎯 Дартс","/дартс")],
        [kbc("🚀 Краш","/краш"), kbc("🃏 Блэкджек","/блэкджек")],
        [kbc("💣 Мины","/мины"), kbc("🎁 Кейсы","/кейс")],
        [kbc("🏗 Башня","/башня"), kbc("🏎 Гонка","/гонка")],
        [kbc("🎣 Рыбалка","/рыбалка"), kbc("◀️ Меню","/меню","secondary")],
    ])

def kb_country():
    return kb([
        [kbt("🌍 Страны","/страны","primary"), kbt("🎫 Гражданство","/гражданство","positive")],
        [kbt("🏙 Мои города","/моигорода","primary"), kbt("🏴 Налёт","/налёт","negative")],
        [kbt("👑 Президент","/президент","positive")],
        [kbt("🛒 Купить город","/купитьгород","secondary"), kbt("🏛 Казна","/казна","secondary")],
        [kbt("🎖️ Армия","/армия","secondary"), kbt("👥 Граждане","/граждане","secondary")],
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
    "📊 стата":"/стата","🆘 помощь":"/help","🏙 города":"/моигорода","💞 брак":"/брак",
    "🎁 кейсы":"/кейс",
}

def promo_card(code, amount, uses, max_uses):
    left = max_uses - uses
    status = "🟢 Активен" if left > 0 else "🔴 Исчерпан"
    return (f"{style_div()}\n     {style_emoji()} 🎟️ ПРОМОКОД {style_emoji()}\n{style_div()}\n\n"
            f"  🔑 ➜ `{code}`\n  💰 ➜ {fmt(amount)} 💵\n  👥 ➜ {uses} / {max_uses} активаций\n"
            f"  📊 ➜ Осталось: {left}\n  {status}\n\n{style_div()}")
    # ============ ИГРЫ ============
def play_game(peer_id, uid, game, bet):
    if bet <= 0: return send(peer_id, "❌ Ставка > 0")
    if get_balance(uid) < bet: return send(peer_id, f"❌ Мало!\n💳 {fmt(get_balance(uid))} 💵")
    emoji, name, desc = GAMES_INFO.get(game, ("🎮","ИГРА","Играй!"))

    tbonus, title = get_title_bonus(uid)
    sbonus = style_bonus()
    vbonus = 1.5 if is_vip(uid) else 1.0
    dmult = udrone_mult(uid)
    bonus = tbonus * sbonus * vbonus * dmult

    btxt = ""
    if bonus > 1.0:
        parts = []
        if tbonus > 1.0: parts.append(f"титул ×{tbonus}")
        if sbonus > 1.0: parts.append(f"стиль ×{sbonus}")
        if vbonus > 1.0: parts.append(f"VIP ×{vbonus}")
        if dmult > 1: parts.append(f"дрон ×{dmult}")
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

# ============ НАЛЁТ ============
def do_raid(peer_id, uid, city_name):
    last = ufield(uid, "raid_last", 0) or 0
    now = int(time.time())
    left = RAID_COOLDOWN - (now - last)
    if left > 0:
        return send(peer_id, f"⏳ Повторный налёт через {time_left_fmt(left)}")

    cur.execute("SELECT id,name,country,income,owner,is_capital FROM cities WHERE LOWER(name)=LOWER(?)", (city_name,))
    c = cur.fetchone()
    if not c:
        return send(peer_id, f"❌ Город «{city_name}» не найден")
    cid, cn, cc, inc, cowner, cap = c

    if cowner == uid:
        return send(peer_id, "❌ Нельзя грабить собственный город")

    if get_balance(uid) < RAID_COST:
        return send(peer_id, f"❌ Нужно {fmt(RAID_COST)} 💵 на балансе\n💳 У тебя: {fmt(get_balance(uid))} 💵")

    upd_balance(uid, -RAID_COST)
    cur.execute("UPDATE users SET raid_last=? WHERE user_id=?", (now, uid)); conn.commit()

    cfg = style_cfg()
    cur.execute("SELECT flag FROM countries WHERE name=?", (cc,)); cf = cur.fetchone()
    flag = cf[0] if cf else "🏳️"

    success = random.random() < RAID_SUCCESS_CHANCE
    tbonus, _ = get_title_bonus(uid)
    sbonus = style_bonus()
    vbonus = 1.5 if is_vip(uid) else 1.0
    dmult = udrone_mult(uid)
    bonus = tbonus * sbonus * vbonus * dmult

    if not success:
        send(peer_id,
            f"{style_div()}\n     💥 НАЛЁТ ПРОВАЛЕН\n{style_div()}\n\n"
            f"  🏙 {flag} {cn} ({cc})\n"
            f"  💸 Затраты: -{fmt(RAID_COST)} 💵\n"
            f"  💳 Баланс: {fmt(get_balance(uid))} 💵\n\n"
            f"  🚨 Охрана отбила атаку!\n\n{style_div()}")
        if cowner:
            try:
                send_uid(cowner, f"🚨 Попытка налёта на ваш город {flag} {cn}!\n👤 Нападавший: {mention(uid)}")
            except: pass
        return

    base_loot = int(inc * 0.20)
    want_loot = int(base_loot * bonus)

    taken = 0
    if cowner:
        owner_bank = get_bank(cowner)
        if owner_bank >= want_loot:
            upd_bank(cowner, -want_loot); taken = want_loot
        else:
            upd_bank(cowner, -owner_bank); taken = max(0, owner_bank)
    else:
        taken = want_loot

    upd_balance(uid, taken)

    bt = ""
    if bonus > 1.0:
        parts = []
        if tbonus > 1.0: parts.append(f"титул ×{tbonus}")
        if sbonus > 1.0: parts.append(f"стиль ×{sbonus}")
        if vbonus > 1.0: parts.append(f"VIP ×{vbonus}")
        if dmult > 1: parts.append(f"дрон ×{dmult}")
        bt = f"\n  🎖️ Бонусы: {', '.join(parts)}"

    send(peer_id,
        f"{style_div()}\n     🏴 НАЛЁТ УСПЕШЕН\n{style_div()}\n\n"
        f"  🏙 {flag} {cn} ({cc})\n"
        f"  💰 Доход города: {fmt(inc)} 💵/24ч\n"
        f"  💸 Затраты: -{fmt(RAID_COST)} 💵\n"
        f"  🏆 Добыча: +{fmt(taken)} 💵{bt}\n"
        f"  💳 Баланс: {fmt(get_balance(uid))} 💵\n\n"
        f"  🔥 {cfg['emoji']} Город разграблен! {cfg['emoji']}\n{style_div()}")

    if cowner:
        try:
            send_uid(cowner,
                f"🏴 Ваш город {flag} {cn} ограблен!\n"
                f"👤 Нападавший: {mention(uid)}\n"
                f"💸 Потеряно: {fmt(taken)} 💵")
        except: pass

# ============ СИСТЕМА КЕЙСОВ ============
RUSSIAN_DRONES = [
    "«Молния-2»", "«Овод»", "«Князь Вандал Новгородский»", "«Герань-2»", "«Герань-5»",
    "«Ланцет»", "«КУБ»", "«СКАТ 350М»", "«Гранат-4»", "«БПЛА400Т»", "«Каракурт 2.0»",
    "«Голиаф 2.0»", "«Орлан-10»", "«Орлан-30»", "ZALA", "«Форпост»", "«Элерон-3»",
    "«С-70 Охотник»", "«Кронштадт Орион»", "«МиС-150»", "«МиС-35»", "«Буран»",
    "«Скальпель»", "«Клин»"
]

OTHER_DRONES = [
    "MQ-9 Reaper", "RQ-4 Global Hawk", "MQ-1C Gray Eagle", "MQ-1 Predator",
    "Switchblade 300", "Switchblade 600", "Wing Loong II", "CH-5 Rainbow",
    "Bayraktar TB2", "Bayraktar AKINCI", "Bayraktar TB3", "IAI Harop",
    "Hermes 900", "Hermes 450", "Shahed-136", "Shahed-131", "Mohajer-6",
    "Mohajer-10", "Ababil-5", "Black Hornet", "Watchkeeper", "Harfang"
]

BUSINESS_CASE_REWARDS = [
    ("Мини-маркет", 100_000), ("Пекарня", 150_000), ("Кафе быстрого питания", 250_000),
    ("Барбершоп", 400_000), ("Автомойка", 500_000), ("Магазин одежды", 750_000),
    ("Ресторан", 1_000_000), ("Фитнес-клуб", 2_500_000), ("Автосервис", 4_000_000),
    ("Кинотеатр", 7_500_000), ("Отель 4*", 12_000_000), ("IT-компания", 18_000_000),
    ("Торговый центр", 25_000_000), ("Завод", 40_000_000), ("Нефтяная вышка", 55_000_000),
    ("Авиакомпания", 70_000_000), ("Мегакорпорация", 85_000_000), ("Космопорт", 100_000_000),
]

CASES = {
    "daily": {
        "emoji": "🎁", "name": "Ежедневный кейс", "price": 0, "cooldown": 86400,
        "desc": "Бесплатно, раз в 24 часа",
        "rewards": [
            (0.50, "money", 10_000), (0.30, "exp", 50),
            (0.15, "money", 50_000), (0.05, "money", 500_000),
        ]
    },
    "bomzh": {
        "emoji": "🥖", "name": "Кейс Бомжа", "price": 100_000, "cooldown": 0,
        "desc": "Дёшево и сердито",
        "rewards": [
            (0.40, "money", 100_000), (0.25, "money", 200_000),
            (0.20, "exp", 500), (0.10, "money", 1_000_000), (0.05, "drone", 3),
        ]
    },
    "musor": {
        "emoji": "🗑", "name": "Кейс MusorDrop", "price": 1_000_000, "cooldown": 0,
        "desc": "Мусор или золото?",
        "rewards": [
            (0.30, "money", 500_000), (0.30, "money", 1_500_000),
            (0.20, "exp", 5_000), (0.10, "money", 5_000_000),
            (0.05, "money", 10_000_000), (0.05, "drone", 5),
        ]
    },
    "drone": {
        "emoji": "🛸", "name": "Кейс Дрон", "price": 1_000_000, "cooldown": 0,
        "desc": "Только дроны. Русские — самые редкие!",
        "rewards": [
            (0.50, "drone", 3), (0.25, "drone", 5), (0.15, "drone", 7),
            (0.07, "drone", 10), (0.02, "drone", 25), (0.01, "drone", 99),
        ]
    },
    "rich": {
        "emoji": "💎", "name": "Кейс Богач", "price": 100_000_000, "cooldown": 0,
        "desc": "Для настоящих богачей",
        "rewards": [
            (0.30, "money", 50_000_000), (0.25, "money", 150_000_000),
            (0.20, "money", 300_000_000), (0.15, "rep", 1000),
            (0.05, "drone", 25), (0.03, "drone", 50), (0.02, "drone", 99),
        ]
    },
    "biz": {
        "emoji": "🏢", "name": "Кейс Бизнес", "price": 10_000_000, "cooldown": 0,
        "desc": "Случайный бизнес с доходом до 100М",
        "rewards": [
            (0.35, "biz", (100_000, 1_000_000)),
            (0.30, "biz", (1_000_000, 10_000_000)),
            (0.20, "biz", (10_000_000, 50_000_000)),
            (0.10, "biz", (50_000_000, 80_000_000)),
            (0.05, "biz", (80_000_000, 100_000_000)),
        ]
    },
    "season_halloween": {
        "emoji": "🎃", "name": "Хэллоуин-кейс", "price": 500_000, "cooldown": 0,
        "desc": "Сезонный кейс (осень)", "season": True,
        "rewards": [
            (0.30, "money", 250_000), (0.30, "money", 750_000),
            (0.20, "exp", 2_500), (0.10, "money", 5_000_000),
            (0.07, "drone", 5), (0.03, "drone", 15),
        ]
    },
    "season_newyear": {
        "emoji": "🎄", "name": "Новогодний кейс", "price": 1_000_000, "cooldown": 0,
        "desc": "Сезонный кейс (зима)", "season": True,
        "rewards": [
            (0.25, "money", 1_000_000), (0.25, "money", 3_000_000),
            (0.20, "exp", 5_000), (0.15, "money", 10_000_000),
            (0.10, "drone", 10), (0.05, "drone", 25),
        ]
    },
    "season_easter": {
        "emoji": "🐣", "name": "Пасхальный кейс", "price": 750_000, "cooldown": 0,
        "desc": "Сезонный кейс (весна)", "season": True,
        "rewards": [
            (0.30, "money", 500_000), (0.30, "money", 1_500_000),
            (0.20, "exp", 3_000), (0.10, "money", 7_500_000),
            (0.07, "drone", 5), (0.03, "drone", 20),
        ]
    },
    "season_birthday": {
        "emoji": "🎂", "name": "Именинный кейс", "price": 5_000_000, "cooldown": 0,
        "desc": "Праздничный кейс", "season": True,
        "rewards": [
            (0.25, "money", 3_000_000), (0.25, "money", 10_000_000),
            (0.20, "exp", 15_000), (0.15, "money", 50_000_000),
            (0.10, "drone", 25), (0.05, "drone", 50),
        ]
    },
}

def roll_case_reward(case_key):
    case = CASES[case_key]
    r = random.random()
    acc = 0.0
    for chance, rtype, val in case["rewards"]:
        acc += chance
        if r <= acc: return rtype, val
    return case["rewards"][-1][1], case["rewards"][-1][2]

def add_case_stat(uid, case_key):
    cur.execute("SELECT count FROM case_stats WHERE user_id=? AND case_key=?", (uid, case_key))
    r = cur.fetchone()
    if r: cur.execute("UPDATE case_stats SET count=count+1 WHERE user_id=? AND case_key=?", (uid, case_key))
    else: cur.execute("INSERT INTO case_stats(user_id, case_key, count) VALUES(?,?,1)", (uid, case_key))
    conn.commit()

def get_case_count(uid, case_key):
    cur.execute("SELECT count FROM case_stats WHERE user_id=? AND case_key=?", (uid, case_key))
    r = cur.fetchone()
    return r[0] if r else 0

def apply_drone_reward(uid, mult):
    cur_mult = udrone_mult(uid)
    if mult == 99 or random.random() < 0.4:
        drone_name = random.choice(RUSSIAN_DRONES)
    else:
        drone_name = random.choice(OTHER_DRONES)

    if mult > cur_mult:
        cur.execute("UPDATE users SET drone_mult=?, drone_name=? WHERE user_id=?", (mult, drone_name, uid))
        conn.commit()
        return drone_name, mult, True
    else:
        comp = mult * 500_000
        upd_balance(uid, comp)
        return drone_name, mult, False

def open_case(peer_id, uid, case_key):
    if case_key not in CASES:
        return send(peer_id, "❌ Кейс не найден")
    case = CASES[case_key]

    if case_key == "drone":
        cur.execute("SELECT value FROM bot_settings WHERE key='drone_case_active'")
        r = cur.fetchone()
        if not r or r[0] != "1":
            return send(peer_id, "⛔ Кейс Дрон сейчас закрыт. Владелец должен его включить.")

    if case.get("season"):
        cur.execute("SELECT value FROM bot_settings WHERE key='season_active'")
        r = cur.fetchone()
        if not r or r[0] != "1":
            return send(peer_id, "⛔ Сезонные кейсы сейчас закрыты. Владелец должен их включить.")

    if case_key == "daily":
        last = ufield(uid, "daily_case_last", 0) or 0
        left = case["cooldown"] - (int(time.time()) - last)
        if left > 0:
            return send(peer_id, f"⏳ Ежедневный кейс будет доступен через: {time_left_fmt(left)}")

    if case["price"] > 0:
        if get_balance(uid) < case["price"]:
            return send(peer_id, f"❌ Нужно {fmt(case['price'])} 💵\n💳 У тебя: {fmt(get_balance(uid))} 💵")
        upd_balance(uid, -case["price"])

    if case_key == "daily":
        cur.execute("UPDATE users SET daily_case_last=? WHERE user_id=?", (int(time.time()), uid)); conn.commit()

    rtype, val = roll_case_reward(case_key)

    if rtype == "money":
        upd_balance(uid, val); reward = f"💰 +{fmt(val)} 💵"
    elif rtype == "exp":
        add_exp(uid, val); reward = f"⚡ +{fmt(val)} exp"
    elif rtype == "rep":
        cur.execute("UPDATE users SET rep=rep+? WHERE user_id=?", (val, uid)); conn.commit()
        reward = f"🌟 +{fmt(val)} репутации"
    elif rtype == "drone":
        drone_name, mult, upgraded = apply_drone_reward(uid, val)
        if upgraded: reward = f"🛸 Дрон: *{drone_name}*\n  📈 ×{mult} к доходу игр и бизнеса!"
        else:
            comp = mult * 500_000
            reward = f"🛸 Дрон: *{drone_name}* (×{mult})\n  ⚠️ У тебя уже лучше — компенсация +{fmt(comp)} 💵"
    elif rtype == "biz":
        low, high = val
        biz_name, biz_income = random.choice(BUSINESS_CASE_REWARDS)
        if biz_income < low: biz_income = low
        if biz_income > high: biz_income = high
        country = ucountry(uid) or "—"
        cur.execute("INSERT INTO companies(owner,country,name,type,income) VALUES(?,?,?,?,?)",
                    (uid, country, biz_name, biz_name, biz_income))
        conn.commit()
        reward = f"🏢 Бизнес: *{biz_name}*\n  💰 Доход: {fmt(biz_income)} 💵/24ч"
    else:
        reward = "❌ Ошибка"

    add_case_stat(uid, case_key)

    txt = (f"{style_div()}\n     {case['emoji']} {case['name'].upper()} {case['emoji']}\n{style_div()}\n\n"
           f"  👤 {mention(uid)} открыл кейс!\n\n  🎁 Выпало:\n  {reward}\n\n{style_div()}")
    send(peer_id, txt)

def show_cases_menu(peer_id, uid):
    cur.execute("SELECT value FROM bot_settings WHERE key='drone_case_active'")
    r = cur.fetchone(); drone_active = r and r[0] == "1"
    cur.execute("SELECT value FROM bot_settings WHERE key='season_active'")
    r = cur.fetchone(); season_active = r and r[0] == "1"

    txt = f"{header('🎁 КЕЙСЫ')}\n\n"
    for key, case in CASES.items():
        if key == "drone" and not drone_active: continue
        if case.get("season") and not season_active: continue
        price_str = "Бесплатно" if case["price"] == 0 else f"{fmt(case['price'])} 💵"
        txt += f"  {case['emoji']} *{case['name']}*\n     💰 Цена: {price_str}\n     📝 {case['desc']}\n"
        for chance, rtype, val in case["rewards"]:
            pct = int(chance * 100)
            if rtype == "money": row = f"{pct}% — 💰 {fmt(val)} 💵"
            elif rtype == "exp": row = f"{pct}% — ⚡ {fmt(val)} exp"
            elif rtype == "rep": row = f"{pct}% — 🌟 {fmt(val)} репутации"
            elif rtype == "drone": row = f"{pct}% — 🛸 Дрон ×{val}"
            elif rtype == "biz":
                low, high = val
                row = f"{pct}% — 🏢 Бизнес ({fmt(low)}–{fmt(high)} 💵)"
            else: row = f"{pct}% — ???"
            txt += f"       • {row}\n"
        txt += "\n"
    txt += f"{style_div()}\n📝 Нажми на кнопку для открытия"

    btns = []; row = []
    for key, case in CASES.items():
        if key == "drone" and not drone_active: continue
        if case.get("season") and not season_active: continue
        row.append(kbc(f"{case['emoji']} {case['name']}", f"/open_case {key}", "primary"))
        if len(row) == 2: btns.append(row); row = []
    if row: btns.append(row)
    btns.append([kbc("📊 Мои кейсы", "/моикейсы", "secondary")])
    btns.append([kbc("🏆 Топ кейсов", "/топ кейсы", "secondary")])
    btns.append([kbc("◀️ Меню", "/меню", "secondary")])
    send(peer_id, txt, kb(btns))

# ============ АДМИН-ИВЕНТ ============
def play_admin_event(peer_id, uid, chat_id):
    if get_priority(uid) < 20:
        return send(peer_id, "❌ Ивент доступен только администрации (20+)")

    now = int(time.time())
    last = ufield(uid, "aevent_last", 0) or 0
    if now - last < 86400:
        return send(peer_id, f"⏳ Ты уже открывал админ-ивент.\nСледующий через: {time_left_fmt(86400 - (now - last))}")

    cur.execute("UPDATE users SET aevent_last=? WHERE user_id=?", (now, uid)); conn.commit()

    roll = random.random()
    if roll < 0.10:
        amt = random.randint(5000000, 10000000); upd_balance(uid, amt)
        reward = f"💰 {fmt(amt)} 💵"
    elif roll < 0.40:
        amt = random.randint(1000, 3000); add_exp(uid, amt)
        reward = f"⚡ +{amt} exp"
    else:
        cur.execute("UPDATE users SET rep=rep+10 WHERE user_id=?", (uid,)); conn.commit()
        reward = "🌟 +10 Репутации"

    send(peer_id, f"{style_div()}\n     🚨 АДМИН-ИВЕНТ 🚨\n{style_div()}\n\n"
                  f"  👤 {mention(uid)} вскрыл сейф!\n\n  🎁 Выпало: {reward}\n\n{style_div()}")

# ============ ПИАР ============
def pr_auto_price(minutes):
    return 1050 - 50 * minutes

def pr_send_to_piar_chats(body):
    pr_text = f"{style_div()}\n     📢 РЕКЛАМА\n{style_div()}\n\n{body}\n\n{style_div()}"
    sent = 0
    cur.execute("SELECT peer_id FROM builds WHERE UPPER(type)='PIAR'"); chats = cur.fetchall()
    for (cp,) in chats:
        try:
            vk.messages.send(peer_id=cp, message=pr_text, random_id=get_random_id())
            sent += 1; time.sleep(0.34)
        except: pass
    return sent

def pr_resend_worker():
    time.sleep(15)
    while True:
        try:
            now = int(time.time())
            cur.execute("""SELECT id,text,interval_min,last_resend FROM pr_orders 
                           WHERE status='sent' AND interval_min>0 AND text IS NOT NULL AND text != ''""")
            rows = cur.fetchall()
            for oid, body, interval, last in rows:
                if not interval or interval <= 0: continue
                if now - (last or 0) < interval * 60: continue
                sent = pr_send_to_piar_chats(body)
                cur.execute("UPDATE pr_orders SET last_resend=?, sent_count=sent_count+? WHERE id=?", (now, sent, oid))
                conn.commit()
                log(f"🔁 Авто-пиар #{oid}: {sent} PIAR-чатов")
        except Exception as e:
            log(f"❌ pr_resend_worker: {e}")
        time.sleep(30)

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
  /дартс /краш /блэкджек /мины /башня /гонка /рыбалка

🎁 КЕЙСЫ
  /кейс — меню всех кейсов со шансами
  /моикейсы — мои активные кулдауны
  /топ кейсы — топ игроков по открытиям

💼 РАБОТА И БИЗНЕС
  /работы /устроиться /уволиться /работать
  /списокбиз /купбиз /собрать /мбиз

🏙 ГОРОДА
  /моигорода /город <название> /собрать_город <название>
  /купитьгород <название> <цена> /построить_город <название>
  /налёт <город> — грабёж чужого города (50 000 💵, 40%)

🌍 СТРАНА
  /страны /страна
  /гражданство [название] — вступить в страну
  /паспорт /казна /граждане /армия /города

💞 БРАК
  /брак <юзер> — жениться/выйти замуж
  /развод — развестись
  /топ брак — самые долгие браки

📢 СОЦИАЛЬНОЕ
  /пиар /pr_my /promo /подписка /донат
  /report /offer /ивент /мафия /ежедневно

🎟️ /promo <код> — активировать промокод
⚔️ /война <страна> — только для генералов

🏆 ТОПЫ
  /топ баланс | /топ сообщения | /топ маты
  /топ захваты | /топ уровень | /топ брак

🚪 /q
🆘 /help
{style_div()}"""

def build_help_admin():
    return f"""{header('КОМАНДЫ АДМИНА (4-79)')}

🛡️ МОДЕРАЦИЯ
  /warn /unwarn /mute /unmute /kick /ban /unban /gban /ungban /banlist

🎭 РОЛИ
  /role /setrole /staff /gstaff /nick /rnick

💬 УПРАВЛЕНИЕ
  /тишина <0-101> /назначить /повысить

📩 ТИКЕТЫ
  /tickets /adt <номер> <ответ>

🚨 /админ_ивент — открыть админ-кейс (20+)
📊 /мойстат — моя статистика
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
  /builds /build /build report /build_piar
  /выдать /вернуть /обнулить /вайп
  /removestaff /setpass

👑 ПРЕЗИДЕНТ И ДОЛЖНОСТИ
  /президент <юзер> <страна>
  /снятьпрезидента <страна>
  /должность <юзер> <страна> <позиция>

🎟️ ПРОМОКОДЫ
  /createpromo <код> <сумма> <макс>
  /promo_info <код>
  /promo_list

📢 ПИАР
  /pr_orders /pr_stats /pr_ok <id> /pr_no <id> /pr_stop <id>

🛸 ДРОН-КЕЙС
  /дрон_кейс_вкл — включить (100+)
  /дрон_кейс_выкл — выключить (100+)

🎃 СЕЗОННЫЕ КЕЙСЫ
  /сезон_вкл — включить (100+)
  /сезон_выкл — выключить (100+)

🌍 /удалитьстрану /улучшить_страну
⚔️ /война /захват /мир /запуск /дрон

📊 /мойстат — моя статистика
🔐 /adminpa
📖 /ghelp
{style_div()}"""

# ============ АВТО-РОЛИ ============
def apply_global_role_in_chat(uid, chat_id):
    cur.execute("SELECT role FROM global_roles WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if r and r[0]:
        cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)", (uid, chat_id, r[0]))
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
            cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)", (uid, cid, role))
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
        cur.execute("SELECT user_id,tariff,status,duration,interval_min FROM pr_orders WHERE id=?", (oid,))
        o = cur.fetchone()
        if o and o[2] == "confirmed":
            duration = o[3] or 0; interval = o[4] or 0
            now = int(time.time()); expires = 0 if duration == 0 else now + duration
            sent = pr_send_to_piar_chats(text)
            cur.execute("""UPDATE pr_orders SET status='sent', sent_at=?, sent_count=?,
                           expires_at=?, text=?, last_resend=? WHERE id=?""",
                        (now, sent, expires, text, now, oid))
            conn.commit()
            dtxt = "♾" if duration == 0 else time_left_fmt(duration)
            auto_txt = f"\n🔁 Авто-повтор: каждые {interval} мин" if interval else ""
            send(peer_id, f"✅ Пиар #{oid} → {sent} PIAR-чатов\n⏳ {dtxt}{auto_txt}")
            send_uid(o[0], f"✅ Пиар #{oid} разослан\n⏳ {dtxt}{auto_txt}")
        else:
            send(peer_id, "⚠️ Заказ не в статусе confirmed")
        return

    # СЧЁТЧИКИ
    if not text.startswith("/") and len(text) >= 2:
        if has_mat(text):
            cur.execute("UPDATE users SET msg_count=msg_count+1, mat_count=mat_count+1 WHERE user_id=?", (uid,))
        else:
            cur.execute("UPDATE users SET msg_count=msg_count+1 WHERE user_id=?", (uid,))
        conn.commit()

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
            send_uid(uid, f"{style_div()}\n     🔇 МУТ\n{style_div()}\n\n  ⏳ Осталось: {time_left_fmt(ml)}\n{style_div()}")
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

    # ============ КЕЙСЫ ============
    if cmd in ("/кейс", "/кейсы", "/cases"):
        return show_cases_menu(peer_id, uid)

    if cmd == "/open_case":
        if len(args) < 2: return send(peer_id, "📝 /open_case <id>")
        return open_case(peer_id, uid, args[1].lower())

    if cmd == "/моикейсы":
        now = int(time.time())
        txt = f"{header('🔕 МОИ КЕЙСЫ')}\n\n"
        last = ufield(uid, "daily_case_last", 0) or 0
        left_daily = max(0, 86400 - (now - last))
        status = "✅ Доступен" if left_daily == 0 else f"⏳ {time_left_fmt(left_daily)}"
        txt += f"  🎁 Ежедневный кейс\n     {status}\n     📊 Открыто: {get_case_count(uid, 'daily')}\n\n"

        cur.execute("SELECT value FROM bot_settings WHERE key='drone_case_active'")
        r = cur.fetchone(); drone_active = r and r[0] == "1"
        last = ufield(uid, "drone_last", 0) or 0
        left_drone = max(0, 86400 - (now - last))
        if not drone_active: status = "🔴 Кейс закрыт владельцем"
        elif left_drone == 0: status = "✅ Доступен"
        else: status = f"⏳ {time_left_fmt(left_drone)}"
        txt += f"  🛸 Кейс Дрон\n     {status}\n     📊 Открыто: {get_case_count(uid, 'drone')}\n\n"

        last = ufield(uid, "aevent_last", 0) or 0
        left_aevent = max(0, 86400 - (now - last))
        if get_priority(uid) < 20: status = "🔒 Только 20+"
        elif left_aevent == 0: status = "✅ Доступен"
        else: status = f"⏳ {time_left_fmt(left_aevent)}"
        txt += f"  🚨 Админ-ивент\n     {status}\n\n"

        cur.execute("""SELECT case_key, count FROM case_stats 
                       WHERE user_id=? AND case_key NOT IN ('daily','drone') 
                       ORDER BY count DESC""", (uid,))
        rows = cur.fetchall()
        if rows:
            txt += f"  📊 Остальные открытия:\n"
            for ck, cnt in rows:
                case_name = CASES.get(ck, {}).get("name", ck)
                txt += f"     • {case_name}: {cnt}\n"
            txt += "\n"
        cur.execute("SELECT SUM(count) FROM case_stats WHERE user_id=?", (uid,))
        r = cur.fetchone(); total = r[0] if r and r[0] else 0
        txt += f"  🎯 Всего открыто: {total}\n{style_div()}"
        return send(peer_id, txt, kb_back())

    if cmd == "/топ кейсы":
        cur.execute("""SELECT user_id, SUM(count) as total FROM case_stats 
                       GROUP BY user_id ORDER BY total DESC LIMIT 10""")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ Пока никто не открывал кейсы")
        m = ["🥇","🥈","🥉"] + ["🔹"]*7
        txt = header("🎁 ТОП-10 ПО КЕЙСАМ")+"\n\n"
        for i, (u, cnt) in enumerate(rows):
            txt += f"  {m[i]} {name_of(u)} — {cnt} кейсов\n"
        return send(peer_id, txt + f"\n{style_div()}", kb_back())

    if cmd in ("/сезон_вкл", "/сезон_выкл"):
        if get_priority(uid) < 100: return
        state = "1" if cmd == "/сезон_вкл" else "0"
        cur.execute("INSERT OR REPLACE INTO bot_settings(key,value) VALUES('season_active',?)", (state,))
        conn.commit()
        msg = "🟢 Сезонные кейсы ВКЛЮЧЕНЫ" if state == "1" else "🔴 Сезонные кейсы ВЫКЛЮЧЕНЫ"
        send(peer_id, f"{msg}"); return

    if cmd == "/админ_ивент":
        return play_admin_event(peer_id, uid, chat_id)

    if cmd in ("/дрон_кейс_вкл", "/дрон_кейс_выкл"):
        if get_priority(uid) < 100: return
        state = "1" if cmd == "/дрон_кейс_вкл" else "0"
        cur.execute("INSERT OR REPLACE INTO bot_settings(key,value) VALUES('drone_case_active',?)", (state,))
        conn.commit()
        msg = "🟢 Дрон-кейс ВКЛЮЧЕН" if state == "1" else "🔴 Дрон-кейс ВЫКЛЮЧЕН"
        send(peer_id, f"{msg}\nТеперь доступен всем игрокам."); return

    # ============ МОДЕРАЦИЯ ============
    if cmd == "/warn":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        get_user(t); cur.execute("UPDATE users SET warns=warns+1 WHERE user_id=?", (t,)); conn.commit()
        cur.execute("SELECT warns FROM users WHERE user_id=?", (t,)); w = cur.fetchone()[0]
        inc_admin_stat(uid, "warns")
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        if w >= 3:
            cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t,"3/3 варна")); conn.commit()
            if chat_id: kick_user(chat_id, t)
            inc_admin_stat(uid, "bans")
            send(peer_id, punish_card("ban", t, "3/3 варна (автобан)", uid))
            send_uid(t, f"🚫 Ты забанен (3/3 варна)")
        else:
            send(peer_id, punish_card("warn", t, reason, uid))
            send_uid(t, f"⚠️ Тебе выдан варн ({w}/3). Причина: {reason}")
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
        inc_admin_stat(uid, "mutes")
        send(peer_id, punish_card("mute", t, f"{reason} (на {time_left_fmt(m*60)})", uid))
        send_uid(t, f"🔇 Ты заглушен на {time_left_fmt(m*60)}. Причина: {reason}"); return

    if cmd == "/unmute":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t: cur.execute("UPDATE users SET mute_until=0, mute_notify=0 WHERE user_id=?", (t,)); conn.commit()
        send(peer_id, f"✅ {mention(t)} размучен"); return

    if cmd == "/kick":
        if not is_admin(uid) or not chat_id: return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        kick_user(chat_id, t)
        send(peer_id, punish_card("kick", t, reason, uid)); return

    if cmd == "/ban":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or is_owner(t) or is_admin(t): return
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t, reason)); conn.commit()
        inc_admin_stat(uid, "bans")
        if chat_id: kick_user(chat_id, t)
        send(peer_id, punish_card("ban", t, reason, uid))
        send_uid(t, f"🚫 Ты забанен. Причина: {reason}"); return

    if cmd in ("/unban", "/ungban"):
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t:
            cur.execute("DELETE FROM bans WHERE user_id=?", (t,)); conn.commit()
            send(peer_id, f"✅ {mention(t)} разбанен")
        return

    if cmd == "/gban":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or t in OWNERS: return
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)", (t, reason)); conn.commit()
        inc_admin_stat(uid, "bans")
        kicked = 0
        cur.execute("SELECT chat_id FROM builds"); chats = cur.fetchall()
        for (cid,) in chats:
            if kick_user(cid, t): kicked += 1
        if chat_id and kick_user(chat_id, t): kicked += 1
        send(peer_id, punish_card("gban", t, f"{reason}\n  🏛 Исключен из {kicked} чатов", uid))
        send_uid(t, f"🌐 Ты глобально забанен. Причина: {reason}"); return

    # ============ ВЫДАЧА ПРИВИЛЕГИЙ ============
    if cmd in ("/выдать_vip", "/vip"):
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        try: days = int(args[2]) if len(args)>2 else 30
        except: days = 30
        if not t: return
        until = int(time.time()) + days*86400
        cur.execute("UPDATE users SET vip_until=? WHERE user_id=?", (until, t)); conn.commit()
        send(peer_id, f"💠 {mention(t)} выдан VIP на {days} дней")
        send_uid(t, f"💠 Тебе выдан VIP на {days} дней!"); return

    if cmd in ("/выдать_опыт", "/exp"):
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        try: amt = int(args[2]) if len(args)>2 else 100
        except: amt = 100
        if not t: return
        add_exp(t, amt)
        send(peer_id, f"⚡ {mention(t)} выдано {amt} опыта"); return

    if cmd in ("/выдать_репу", "/rep"):
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        try: amt = int(args[2]) if len(args)>2 else 10
        except: amt = 10
        if not t: return
        cur.execute("UPDATE users SET rep=rep+? WHERE user_id=?", (amt, t)); conn.commit()
        send(peer_id, f"🌟 {mention(t)} выдано {amt} репутации"); return

    # ============ СТАТА ============
    if cmd == "/стата":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg) or uid
        
        # Пытаемся отправить картинку
        if send_stats_card(peer_id, t, chat_id):
            return
            
        # Если картинка не удалась — шлём текстом
        lvl = ulevel(t); exp = uexp(t); need = (lvl+1)*100
        prog = get_progress_bar(exp, need, 8)
        pct = int((exp/need)*100) if need > 0 else 0
        msgs = umsg_count(t); warns = uwarns(t)
        m_to = umarried_to(t); partner = name_of(m_to) if m_to else "нет"
        rep = urep(t); nick = ufield(t, "nick") or "не установлен"
        pos = get_position(t) or "—"
        cur.execute("SELECT role FROM user_roles WHERE user_id=? AND chat_id=?", (t, chat_id or 0))
        ur = cur.fetchone(); chat_role = ur[0] if ur else "Участник"
        priority = get_priority(t)
        vip = "Да" if is_vip(t) else "Нет"
        drone_name = udrone_name(t) or "Нет"
        drone_mult = udrone_mult(t)
        
        txt = (f"━━━━━━━━━━━━━━━━━━━━\n"
               f"👤  {name_of(t).upper()}\n"
               f"Monster PROFILE\n"
               f"━━━━━━━━━━━━━━━━━━━━\n\n"
               f"👑  Должность   ·  {pos}\n"
               f"🎖️  Привилегия  ·  Игрок  (стандарт)\n"
               f"💠  VIP         ·  {vip}\n"
               f"🎭  Роль в чате ·  {chat_role}  ·  приоритет {priority}\n\n"
               f"━━━━━━━━━━━━━━━━━━━━\n"
               f"📊  АКТИВНОСТЬ\n"
               f"━━━━━━━━━━━━━━━━━━━━\n\n"
               f"📝  Сообщений   ·  {fmt(msgs)}\n"
               f"⭐  Уровень     ·  {lvl} / 999\n"
               f"✨  Опыт        ·  {exp} / {need} ({pct}%) [{prog}] XP\n"
               f"⚠️  Варнов      ·  {warns} / 3\n"
               f"💞  Брак        ·  {partner}\n"
               f"🌟  Репутация   ·  {rep}\n"
               f"📛  Ник         ·  {nick}\n\n"
               f"🛸  Дрон        ·  {drone_name}\n"
               f"📈  Множитель   ·  ×{drone_mult} к играм и бизнесу\n\n"
               f"━━━━━━━━━━━━━━━━━━━━\n\n"
               f"🔥  Статус:  {get_title(lvl)}\n\n"
               f"━━━━━━━━━━━━━━━━━━━━")
        send(peer_id, txt, kb_back()); return

    # ============ БРАК ============
    if cmd == "/брак":
        if umarried_to(uid): return send(peer_id, "❌ Ты уже в браке. Используй /развод")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or t == uid: return send(peer_id, "📝 /брак @юзер")
        if umarried_to(t): return send(peer_id, "❌ Этот человек уже в браке")
        now = int(time.time())
        cur.execute("UPDATE users SET married_to=?, married_date=? WHERE user_id=?", (t, now, uid))
        cur.execute("UPDATE users SET married_to=?, married_date=? WHERE user_id=?", (uid, now, t))
        conn.commit()
        send(peer_id, f"💞 {mention(uid)} и {mention(t)} теперь в браке!\n🎉 Совет да любовь!"); return

    if cmd == "/развод":
        p = umarried_to(uid)
        if not p: return send(peer_id, "❌ Ты не в браке")
        cur.execute("UPDATE users SET married_to=0, married_date=0 WHERE user_id IN (?,?)", (uid, p))
        conn.commit()
        send(peer_id, f"💔 Брак между {mention(uid)} и {mention(p)} расторгнут."); return

    # ============ ТОПЫ ============
    if cmd in ("/топ", "топ"):
        cat = args[1].lower() if len(args) > 1 else "баланс"
        m = ["🥇","🥈","🥉"] + ["🔹"]*7
        if cat in ("баланс", "balance", "деньги", "💰"):
            cur.execute("SELECT user_id,balance+bank FROM users ORDER BY balance+bank DESC LIMIT 10")
            rows = cur.fetchall(); txt = header("💰 ТОП-10 ПО БАЛАНСУ")+"\n\n"
            for i,(u,b) in enumerate(rows): txt += f"  {m[i]} {name_of(u)} — {fmt(b)} 💵\n"
        elif cat in ("брак", "любовь", "💞"):
            cur.execute("""SELECT u1.user_id, u1.married_to, u1.married_date 
                           FROM users u1 WHERE u1.married_to > 0 AND u1.user_id < u1.married_to 
                           ORDER BY u1.married_date ASC LIMIT 10""")
            rows = cur.fetchall(); txt = header("💞 ТОП-10 САМЫХ ДОЛГИХ БРАКОВ")+"\n\n"
            for i, (u1, u2, dt) in enumerate(rows):
                days = (int(time.time()) - dt) // 86400
                txt += f"  {m[i]} {name_of(u1)} + {name_of(u2)} — {days} дн.\n"
            if not rows: txt += "  ❌ Пока нет браков\n"
        else:
            txt = f"{header('🏆 ТОПЫ')}\n\n  💰 /топ баланс\n  💞 /топ брак\n{style_div()}"
        send(peer_id, txt + f"\n{style_div()}", kb_back()); return

    # ============ БАНК ============
    if cmd == "/банк":
        send(peer_id, f"{header('🏦 БАНК')}\n\n  👤 {name_of(uid)}\n\n  💰 Баланс: {fmt(get_balance(uid))} 💵\n  🏦 Счёт: {fmt(get_bank(uid))} 💵\n  📊 Всего: {fmt(get_balance(uid)+get_bank(uid))} 💵\n\n  📈 Доход с бизнеса идёт сюда!\n\n{style_div()}\n📝 /положить | /снять", kb_bank()); return

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
        cur.execute("SELECT flag FROM countries WHERE name=?", (cc,)); cf = cur.fetchone(); flag = cf[0] if cf else "🏳️"
        send(peer_id, card(f"🏙 {cn}", [("🌍",f"{flag} {cc}"),("👑 Капитал","Да" if cap else "Нет"),("📊 Уровень",str(lv)),("👥 Население",fmt(pop)),("💰 Доход",f"{fmt(inc)} 💵/24ч"),("🛡 Оборона",fmt(df))], "/моигорода"), kb_country()); return

    if cmd == "/собрать_город":
        if len(args) < 2: return send(peer_id, "📝 /собрать_город <название>")
        name = " ".join(args[1:])
        cur.execute("SELECT id,name,country,income,last_collect FROM cities WHERE LOWER(name)=LOWER(?)", (name,))
        c = cur.fetchone()
        if not c: return send(peer_id, f"❌ Город не найден")
        cid, cn, cc, inc, lc = c
        if ucountry(uid) != cc and not is_owner(uid): return send(peer_id, "❌ Город не вашей страны")
        now = int(time.time()); left = 86400 - (now - (lc or 0))
        if left > 0: return send(peer_id, f"⏳ Через {time_left_fmt(left)}")
        treasury_share = int(inc * 0.05); bank_share = inc - treasury_share
        upd_bank(uid, bank_share)
        cur.execute("UPDATE countries SET treasury=treasury+? WHERE name=?", (treasury_share, cc))
        cur.execute("UPDATE cities SET last_collect=? WHERE id=?", (now, cid)); conn.commit()
        send(peer_id, card(f"🏙 {cn}", [("💰 Доход",f"+{fmt(inc)} 💵"),("🏦 В банк",f"{fmt(bank_share)} 💵"),("🏛 В казну",f"{fmt(treasury_share)} 💵")], "/моигорода"), kb_country()); return

    if cmd == "/купитьгород":
        if len(args) < 3: return send(peer_id, "📝 /купитьгород <название> <цена>")
        name = " ".join(args[1:-1])
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
        cur.execute("UPDATE countries SET cities=cities+1 WHERE name=?", (c,)); conn.commit()
        send(peer_id, f"🏙 Город «{name}» куплен за {fmt(price)} 💵", kb_country()); return

    if cmd == "/построить_город":
        if len(args) < 2: return send(peer_id, "📝 /построить_город <название>")
        name = " ".join(args[1:])
        cur.execute("SELECT id,level FROM cities WHERE LOWER(name)=LOWER(?)", (name,))
        c = cur.fetchone()
        if not c: return send(peer_id, "❌ Город не найден")
        cid, lv = c; cost = 50000 * lv
        if get_bank(uid) < cost: return send(peer_id, f"❌ Нужно {fmt(cost)} 💵")
        upd_bank(uid, -cost)
        cur.execute("UPDATE cities SET level=level+1, population=population+5000, income=income+2000, defense=defense+500 WHERE id=?", (cid,))
        conn.commit(); send(peer_id, f"🏗 {name} прокачан до ур. {lv+1}", kb_country()); return

    if cmd in ("/налёт","/налет"):
        if len(args) < 2:
            return send(peer_id, f"📝 /налёт <название города>\n\n  💰 Стоимость: {fmt(RAID_COST)} 💵\n  🎯 Шанс успеха: 40%\n  🏆 Добыча: 20% от дохода города\n  ⏳ Кулдаун: 1 час", kb_country())
        return do_raid(peer_id, uid, " ".join(args[1:]))

    # ============ ВОЙНА / ПРЕЗИДЕНТ ============
    if cmd == "/война":
        c = ucountry(uid)
        if not c: return send(peer_id, "❌ Ты не гражданин страны")
        position = get_position(uid)
        if position != "Генерал" and not is_owner(uid):
            return send(peer_id, f"❌ /война доступна только генералам страны\n\n  🌍 Твоя страна: {c}\n  💼 Твоя должность: {position or 'Гражданин'}")
        if len(args) < 2: return send(peer_id, "📝 /война <страна>")
        target_name = " ".join(args[1:]).strip()
        cur.execute("SELECT name,flag FROM countries WHERE LOWER(name) LIKE LOWER(?) AND alive=1", (f"%{target_name}%",))
        co = cur.fetchone()
        if not co: return send(peer_id, f"❌ Страна «{target_name}» не найдена")
        target_country, target_flag = co
        if target_country == c: return send(peer_id, "❌ Нельзя объявить войну своей стране")
        cur.execute("SELECT id FROM wars WHERE attacker=? AND defender=? AND active=1", (c, target_country))
        if cur.fetchone(): return send(peer_id, f"❌ Война уже идёт")
        cur.execute("INSERT INTO wars(attacker,defender,started,active) VALUES(?,?,?,1)", (c, target_country, int(time.time()))); conn.commit()
        cur.execute("SELECT flag FROM countries WHERE name=?", (c,)); cf = cur.fetchone(); my_flag = cf[0] if cf else "🏳️"
        txt = f"{style_div()}\n     ⚔️ ВОЙНА ОБЪЯВЛЕНА\n{style_div()}\n\n  {my_flag} {c}\n     ⚔️ ⚔️ ⚔️\n  {target_flag} {target_country}\n\n  👮 Генерал: {mention(uid)}\n  📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n{style_div()}"
        send(peer_id, txt)
        cur.execute("SELECT president, owner FROM countries WHERE name=?", (target_country,)); pres = cur.fetchone()
        if pres:
            for pid in [pres[0], pres[1]]:
                if pid:
                    try: send_uid(pid, txt)
                    except: pass
        return

    if cmd in ("/президент","/презик"):
        if not is_owner(uid): return
        if len(args) < 3: return send(peer_id, "📝 /президент <юзер> <страна>")
        t = extract_uid(args[1], event_msg)
        if not t: return send(peer_id, "❌ Не понял кого")
        cname = " ".join(args[2:]).strip()
        cur.execute("SELECT name,flag,president FROM countries WHERE LOWER(name) LIKE LOWER(?) AND alive=1", (f"%{cname}%",))
        co = cur.fetchone()
        if not co: return send(peer_id, f"❌ Страна не найдена")
        country_name, flag, old_pres = co
        old_country = ucountry(t)
        if old_country != country_name:
            if old_country: cur.execute("DELETE FROM members WHERE user_id=?", (t,))
            cur.execute("UPDATE users SET country=? WHERE user_id=?", (country_name, t))
        cur.execute("UPDATE countries SET president=? WHERE name=?", (t, country_name))
        cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)", (t, country_name, "Президент")); conn.commit()
        txt = (f"{style_div()}\n     👑 ПРЕЗИДЕНТ НАЗНАЧЕН\n{style_div()}\n\n  👤 {mention(t)}\n  🌍 {flag} {country_name}\n  👮 Назначил: {mention(uid)}\n\n{style_div()}")
        send(peer_id, txt)
        try: send_uid(t, txt)
        except: pass
        return

    if cmd in ("/должность","/назначить"):
        if not is_owner(uid): return
        if len(args) < 4: return send(peer_id, "📝 /должность <юзер> <страна> <позиция>")
        t = extract_uid(args[1], event_msg)
        if not t: return send(peer_id, "❌ Не понял кого")
        cname = args[2]; position = " ".join(args[3:])
        cur.execute("SELECT name,flag FROM countries WHERE LOWER(name) LIKE LOWER(?) AND alive=1", (f"%{cname}%",))
        co = cur.fetchone()
        if not co: return send(peer_id, f"❌ Страна не найдена")
        country_name, flag = co
        cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)", (t, country_name, position))
        cur.execute("UPDATE users SET country=? WHERE user_id=?", (country_name, t)); conn.commit()
        send(peer_id, f"✅ {mention(t)} — {position} в {flag} {country_name}")
        try: send_uid(t, f"🎖️ Ты назначен: {position}\n🌍 {flag} {country_name}")
        except: pass
        return

    # ============ ТИКЕТЫ ============
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
        cur.execute("SELECT user_id, type FROM tickets WHERE id=?", (tid,)); t = cur.fetchone()
        if not t: return
        cur.execute("UPDATE tickets SET status='closed', answer=?, answered_by=? WHERE id=?", (ans, uid, tid)); conn.commit()
        inc_admin_stat(uid, "tickets")
        if t[1] == "report": inc_admin_stat(uid, "reports")
        elif t[1] == "offer": inc_admin_stat(uid, "offers")
        send_uid(t[0], f"📩 ОТВЕТ #{tid}\n\n{ans}"); send(peer_id, "✅"); return

    # ============ ПРИВЯЗКА ЧАТОВ ============
    if cmd == "/build":
        if not is_owner(uid): return
        if len(args) >= 2 and args[1].lower() == "report":
            if not chat_id: return
            cur.execute("INSERT OR REPLACE INTO report_chats(peer_id,linked_by,linked_at) VALUES(?,?,?)", (peer_id, uid, int(time.time()))); conn.commit()
            send(peer_id, "✅ Report-чат привязан"); return
        cur.execute("SELECT chat_id,title,type FROM builds ORDER BY type DESC, chat_id"); rows = cur.fetchall()
        piar = [r for r in rows if (r[2] or "").upper() == "PIAR"]
        other = [r for r in rows if (r[2] or "").upper() != "PIAR"]
        txt = f"{header('ПРИВЯЗАННЫЕ ЧАТЫ')}\n\n  📢 PIAR ({len(piar)}):\n"
        if piar:
            for c,t,tp in piar: txt += f"     ✅ {t} (id {c})\n"
        else: txt += "     ❌ Нет\n"
        txt += f"\n  🏛 Остальные ({len(other)}):\n"
        for c,t,tp in other[:20]: txt += f"     • {t} (id {c})\n"
        txt += f"\n{style_div()}\n📝 /build_piar — пометить текущий чат как PIAR"
        send(peer_id, txt); return

    if cmd == "/builds":
        if not is_owner(uid): return
        if not chat_id: return
        title = " ".join(args[1:]) if len(args)>1 else f"Беседа {chat_id}"
        btype = "PIAR" if title.strip().upper() == "PIAR" else "chat"
        cur.execute("INSERT OR REPLACE INTO builds(chat_id,peer_id,title,type,linked_by,linked_at) VALUES(?,?,?,?,?,?)", (chat_id,peer_id,title,btype,uid,int(time.time()))); conn.commit()
        if btype == "PIAR": send(peer_id, f"✅ Чат помечен как 📢 PIAR")
        else: send(peer_id, f"✅ {title}")
        return

    if cmd == "/build_piar":
        if not is_owner(uid) or not chat_id: return
        cur.execute("INSERT OR REPLACE INTO builds(chat_id,peer_id,title,type,linked_by,linked_at) VALUES(?,?,?,?,?,?)", (chat_id, peer_id, "PIAR", "PIAR", uid, int(time.time()))); conn.commit()
        send(peer_id, "✅ Этот чат помечен как 📢 PIAR"); return

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

    # ============ ИГРЫ ============
    if cmd in GAMES_INFO:
        if len(args) < 2:
            set_game_state(uid, cmd); emoji, name, desc = GAMES_INFO[cmd]
            send(peer_id, f"{header(emoji+' '+name)}\n\n  {desc}\n\n  💰 Введите ставку\n\n  💳 {fmt(get_balance(uid))} 💵\n{style_div()}", kb_games()); return
        try: bet = int(args[1])
        except: return
        play_game(peer_id, uid, cmd, bet); return

    # ============ БАЛАНС / ПРИЗ ============
    if cmd in ("/баланс","баланс"):
        send(peer_id, card("БАЛАНС", [
            ("👤",name_of(uid)),("💰",f"{fmt(get_balance(uid))} 💵"),
            ("🏦",f"{fmt(get_bank(uid))} 💵"),
            ("🏆",f"{ulevel(uid)} {get_title(ulevel(uid))}"),("⚡",f"{uexp(uid)} exp"),
        ]), kb_back()); return

    if cmd == "/уровень":
        lv = ulevel(uid); e = uexp(uid); need = (lv+1)*100
        send(peer_id, card("УРОВЕНЬ", [("📊",str(lv)),("⚡",f"{e} exp"),("📈 До след.",f"{max(0,need-e)}")]), kb_back()); return

    if cmd in ("/приз","приз"):
        last = ulast_bonus(uid) or 0; left = 86400 - (int(time.time()) - last)
        if left > 0:
            h = left//3600; m_ = (left%3600)//60
            return send(peer_id, f"⏳ Через {h}ч {m_}мин")
        amt = int(random.randint(100, 900000) * style_bonus())
        upd_balance(uid, amt); add_exp(uid, 5)
        cur.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (int(time.time()), uid)); conn.commit()
        send(peer_id, f"🎁 +{fmt(amt)} 💵 | +5 exp\n⏰ Через 24ч"); return

    if cmd in ("/ежедневно","/daily"):
        last = udaily(uid); now = int(time.time())
        if now - (last or 0) < 86400:
            left = 86400 - (now - (last or 0)); h = left//3600; m_ = (left%3600)//60
            return send(peer_id, f"⏳ {h}ч {m_}мин")
        rw = int(50000 * style_bonus()); upd_balance(uid, rw)
        cur.execute("UPDATE users SET daily=? WHERE user_id=?", (now, uid)); conn.commit()
        add_exp(uid, 20); send(peer_id, f"🎁 +{fmt(rw)} 💵 | +20 exp"); return

    if cmd == "/передать":
        if len(args) < 3: return
        try: t = int(args[1].replace("@","").replace("[id","").split("|")[0].split("]")[0]); a = int(args[2])
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

    # ============ РАБОТЫ ============
    if cmd == "/работы":
        cur.execute("SELECT name,salary,exp,min_exp FROM jobs ORDER BY min_exp"); rows = cur.fetchall()
        e = uexp(uid); bonus = round(get_title_bonus(uid)[0] * style_bonus(), 2)
        txt = header("РАБОТЫ")+f"\n\n  ⚡ {e} exp"
        if bonus > 1.0: txt += f"  🎖️ ×{bonus}"
        txt += "\n\n"
        for n,s,ex,me in rows:
            lk = "✅" if e >= me else "🔒"
            sb = int(s * bonus) if bonus > 1.0 else s
            txt += f"  {lk} {n} — {fmt(sb)} 💵 (+{ex} exp) [нужно {me} exp]\n"
        send(peer_id, txt + f"\n{style_div()}\n📝 /устроиться <название>"); return

    if cmd == "/устроиться":
        if len(args) < 2: return send(peer_id, "📝 /устроиться <название>")
        job = " ".join(args[1:])
        cur.execute("SELECT name,salary,exp,min_exp FROM jobs WHERE LOWER(name)=LOWER(?)", (job,)); j = cur.fetchone()
        if not j: return send(peer_id, "❌ Работа не найдена")
        if uexp(uid) < j[3]: return send(peer_id, f"❌ Для этой работы нужно {j[3]} exp (у тебя {uexp(uid)})")
        cur.execute("UPDATE users SET work=?, work_last=0 WHERE user_id=?", (j[0], uid)); conn.commit()
        send(peer_id, f"💼 Ты устроен: {j[0]}", kb_back()); return

    if cmd == "/уволиться":
        cur.execute("UPDATE users SET work=NULL WHERE user_id=?", (uid,)); conn.commit()
        send(peer_id, "❌ Ты уволен"); return

    if cmd == "/работать":
        w = uwork(uid)
        if not w: return send(peer_id, "❌ Сначала устройся на работу (/работы)")
        cur.execute("SELECT salary, exp FROM jobs WHERE name=?", (w,)); j = cur.fetchone()
        if not j: return
        lw = ufield(uid, "work_last", 0); now = int(time.time())
        left = 86400 - (now - (lw or 0))
        if left > 0: return send(peer_id, f"⏳ Отдыхай ещё {time_left_fmt(left)}")
        tbonus, _ = get_title_bonus(uid); bonus = tbonus * style_bonus()
        sal = int(j[0] * bonus); ex = int(j[1] * bonus)
        upd_bank(uid, sal)
        cur.execute("UPDATE users SET work_last=? WHERE user_id=?", (now, uid))
        nlv = add_exp(uid, ex); conn.commit()
        txt = f"💼{style_div()}\n     ✅ СМЕНА ЗАВЕРШЕНА\n{style_div()}\n\n  💼 Работа: {w}\n  🏦 +{fmt(sal)} 💵 в банк\n  ⚡ +{ex} exp\n"
        if nlv: txt += f"\n🎉 Ты достиг {nlv} уровня!"
        send(peer_id, txt + f"\n{style_div()}"); return

    # ============ БИЗНЕС ============
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
        base_total = sum(r[2] for r in rows)
        dmult = udrone_mult(uid)
        total = int(base_total * dmult)
        for cid,_,_ in rows: cur.execute("DELETE FROM companies WHERE id=?", (cid,))
        upd_bank(uid, total)
        cur.execute("UPDATE users SET biz=1 WHERE user_id=?", (uid,)); conn.commit()
        msg = f"💼 Собрано {fmt(total)} 💵 в банк"
        if dmult > 1: msg += f"\n  🛸 Бонус дрона: ×{dmult} (было бы {fmt(base_total)} 💵)"
        send(peer_id, msg); return

    if cmd == "/мбиз":
        cur.execute("SELECT name,income FROM companies WHERE owner=?", (uid,)); rows = cur.fetchall()
        if not rows: return send(peer_id, "❌ Нет")
        txt = header("МОИ БИЗНЕСЫ")+"\n\n"; t = 0
        for n,i in rows: txt += f"  • {n} — {fmt(i)} 💵\n"; t += i
        send(peer_id, txt + f"\n  🏦 {fmt(t)} 💵\n{style_div()}"); return

    # ============ СТРАНЫ / ГРАЖДАНСТВО ============
    if cmd == "/гражданство":
        if len(args) < 2:
            c = ucountry(uid)
            if c:
                co = get_country(c); fl = co[1] if co else "🏳️"
                return send(peer_id, card("🌍 ВАШЕ ГРАЖДАНСТВО", [("👤", name_of(uid)), ("🌍", f"{fl} {c}"), ("💼", get_position(uid) or "Гражданин")], f"📝 Сменить: /гражданство <страна>"), kb_country())
            cur.execute("SELECT name,flag FROM countries WHERE alive=1 ORDER BY name")
            rows = cur.fetchall()
            txt = f"{header('🌍 ВЫБОР ГРАЖДАНСТВА')}\n\n  У тебя пока нет гражданства.\n\n"
            for n,f in rows: txt += f"  {f or '🏳️'} {n}\n"
            txt += f"\n{style_div()}\n📝 /гражданство <название страны>"
            return send(peer_id, txt, kb_country())
        cname = " ".join(args[1:]).strip()
        cur.execute("SELECT name,flag FROM countries WHERE LOWER(name)=LOWER(?) AND alive=1", (cname,))
        co = cur.fetchone()
        if not co:
            cur.execute("SELECT name,flag FROM countries WHERE LOWER(name) LIKE LOWER(?) AND alive=1", (f"%{cname}%",))
            co = cur.fetchone()
        if not co: return send(peer_id, f"❌ Страна «{cname}» не найдена. Список: /страна")
        target_country, flag = co[0], co[1]
        old = ucountry(uid)
        if old == target_country: return send(peer_id, f"❌ Ты уже гражданин {flag} {target_country}")
        if old: cur.execute("DELETE FROM members WHERE user_id=?", (uid,))
        cur.execute("UPDATE users SET country=? WHERE user_id=?", (target_country, uid))
        cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)", (uid, target_country, "Гражданин")); conn.commit()
        if old: send(peer_id, f"✅ Гражданство изменено: {old} → {flag} {target_country}")
        else:   send(peer_id, f"✅ Ты стал гражданином {flag} {target_country}!")
        return

    if cmd in ("/страны","/страна"):
        cur.execute("SELECT name,flag,treasury,army,cities,president FROM countries WHERE alive=1 ORDER BY cities DESC")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "🌍 Нет стран", kb_country())
        txt = header("СТРАНЫ МИРА")+"\n\n"
        for n,f,t,a,c,pr in rows[:25]:
            pn = name_of(pr) if pr else "❌"
            marker = " ⬅️" if ucountry(uid) == n else ""
            txt += f"  {f or '🏳️'} {n} | 👑 {pn} | ⚔️ {fmt(a)} | 🏙 {c}/40{marker}\n"
        txt += f"\n{style_div()}\n📝 Вступить: /гражданство <страна>"
        send(peer_id, txt, kb_country()); return

    if cmd in ("/паспорт","📘 паспорт"):
        pos = get_position(uid) or "—"; cn = ucountry(uid) or "—"
        co = get_country(cn) if cn != "—" else None; fl = co[1] if co else "—"
        send(peer_id, card("ПАСПОРТ", [("👤",name_of(uid)),("🆔",f"id{uid}"),("🌍",f"{fl} {cn}"),("💼",pos)]), kb_country()); return

    if cmd == "/казна":
        c = ucountry(uid)
        if not c: return
        co = get_country(c); st = get_stock(c)
        send(peer_id, card(f"КАЗНА {c}", [("💰",f"{fmt(co[3])} 💵"),("🍞",f"{fmt(st[1])}"),("🔫",f"{fmt(st[2])}"),("🏙",f"{co[5]}")]), kb_country()); return

    if cmd == "/армия":
        c = ucountry(uid)
        if not c: return
        ca = get_carmy(c)
        send(peer_id, card("АРМИЯ", [("🪖",f"{fmt(ca[1])}"),("🎯 ПВО",f"{fmt(ca[2])}"),("🚀",f"{fmt(ca[3])}"),("🛸",f"{fmt(ca[4])}")]), kb_country()); return

    if cmd in ("/граждане","/города","/правительство","/должности","/очки"):
        c = ucountry(uid)
        if not c: return
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

    # ============ ПИАР ============
    if cmd in ("/пиар","/pr"):
        txt = f"{header('📢 ПИАР')}\n\n  💰 Оплата через владельца\n  📢 Рассылка только в PIAR-чаты\n\n  ⏱ ВЫБЕРИТЕ ИНТЕРВАЛ:\n\n"
        btns = []; row = []
        for n in range(1, 21):
            pr = pr_auto_price(n)
            txt += f"  ⏱ {n} мин — {pr} ₽\n"
            row.append(kbc(f"{n}м | {pr}₽", f"/pr_buy_auto {n}", "primary"))
            if len(row) == 4: btns.append(row); row = []
        if row: btns.append(row)
        btns.append([kbc("📋 Мои заказы","/pr_my","secondary")])
        send(peer_id, txt + f"\n{style_div()}\n📝 @id{MAIN_OWNER}", kb(btns)); return

    if cmd == "/pr_buy_auto":
        if len(args) < 2: return
        try: n = int(args[1])
        except: return
        if n < 1 or n > 20: return
        price = pr_auto_price(n)
        cur.execute("INSERT INTO pr_orders(user_id,tariff,price,status,created,duration,interval_min) VALUES(?,?,?,?,?,?,?)",
                    (uid, f"Пиар {n} мин", price, "wait_pay", int(time.time()), 0, n))
        conn.commit(); oid = cur.lastrowid
        send(peer_id, card("📢 ЗАКАЗ ПИАРА", [("🔢",f"#{oid}"),("⏱ Интервал",f"каждые {n} мин"),("💰",f"{price} ₽"),("❓","🟡 Ожидает оплаты")], f"💳 @id{MAIN_OWNER}"))
        link = get_chat_link(peer_id)
        notif = (f"📢 НОВЫЙ ЗАКАЗ ПИАРА #{oid}\n\n  👤 Покупатель: {mention(uid)}\n  🔗 Ссылка на чат: {link}\n"
                 f"  ⏱ Интервал: каждые {n} мин\n  💰 Сумма: {price} ₽\n\n✅ /pr_ok {oid}\n❌ /pr_no {oid}")
        for ow in OWNERS: send_uid(ow, notif)
        return

    if cmd == "/pr_my":
        cur.execute("SELECT id,tariff,price,status,expires_at,interval_min FROM pr_orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
        rows = cur.fetchall()
        if not rows: return send(peer_id, "📋 Нет заказов")
        st = {"wait_pay":"🟡","paid":"🟢","confirmed":"🔵","sent":"✅","cancelled":"🔴"}
        txt = header("📋 МОИ ЗАКАЗЫ")+"\n\n"
        for oid, tn, p, s, exp, interval in rows:
            txt += f"  {st.get(s,'?')} #{oid} — {tn} — {p} ₽\n"
            if interval and interval > 0: txt += f"     🔁 каждые {interval} мин\n"
            if s == "sent" and exp and exp > int(time.time()): txt += f"     ⏳ {time_left_fmt(exp-int(time.time()))}\n"
            elif s == "sent" and exp == 0: txt += f"     ♾\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/pr_ok":
        if not (uid in OWNERS or get_priority(uid) >= 100): return
        if len(args) < 2: return
        try: oid = int(args[1])
        except: return
        cur.execute("SELECT user_id,status FROM pr_orders WHERE id=?", (oid,))
        o = cur.fetchone()
        if not o or o[1] not in ("wait_pay","paid"): return send(peer_id, "❌")
        cur.execute("UPDATE pr_orders SET status='confirmed', confirmed_by=?, paid_at=? WHERE id=?", (uid, int(time.time()), oid)); conn.commit()
        send(peer_id, f"✅ #{oid} подтверждён\n📝 Отправьте текст пиара следующим сообщением:")
        cur.execute("INSERT OR REPLACE INTO game_state(user_id,game,ts) VALUES(?,?,?)", (uid, f"pr_text:{oid}", int(time.time()))); conn.commit()
        send_uid(o[0], f"✅ Заказ #{oid} подтверждён!"); return

    if cmd == "/pr_no":
        if not (uid in OWNERS or get_priority(uid) >= 100): return
        if len(args) < 2: return
        try: oid = int(args[1])
        except: return
        cur.execute("SELECT user_id FROM pr_orders WHERE id=?", (oid,)); o = cur.fetchone()
        if not o: return
        cur.execute("UPDATE pr_orders SET status='cancelled' WHERE id=?", (oid,)); conn.commit()
        send(peer_id, f"❌ #{oid} отменён"); send_uid(o[0], f"❌ Заказ #{oid} отклонён"); return

    # ============ РОЛИ ============
    if cmd == "/role":
        cur.execute("SELECT name,priority,emoji FROM roles ORDER BY priority DESC"); rows = cur.fetchall()
        txt = header("РОЛИ")+"\n\n"
        for n,p,e in rows: txt += f"  {e} {n} — {p}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

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
        if chat_id: cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)", (t, chat_id, rn))
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

    if cmd == "/staff":
        if not chat_id: return
        cur.execute("SELECT user_id, role FROM user_roles WHERE chat_id=?", (chat_id,)); rows = cur.fetchall()
        txt = header("СОСТАВ")+"\n\n"
        if not rows: txt += "  ❌\n"
        else:
            for u,r in rows: txt += f"  🎭 {r} → {mention(u)}\n"
        send(peer_id, txt + f"\n{style_div()}"); return

    if cmd == "/gstaff":
        cur.execute("SELECT u.user_id, COALESCE(gr.role, u.role) FROM users u LEFT JOIN global_roles gr ON gr.user_id=u.user_id WHERE u.priority >= 4 OR gr.role IS NOT NULL")
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
        cur.execute("UPDATE users SET balance=0, bank=0, warns=0, role='user', country=NULL, priority=0, exp=0, level=0, work=NULL, password=NULL, title=NULL, msg_count=0, mat_count=0, captures=0, drone_mult=1, drone_name=NULL WHERE user_id=?", (t,))
        for q in ["DELETE FROM user_roles WHERE user_id=?","DELETE FROM global_roles WHERE user_id=?","DELETE FROM companies WHERE owner=?","DELETE FROM nicks WHERE user_id=?","DELETE FROM members WHERE user_id=?"]: cur.execute(q, (t,))
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

    if cmd == "/мтитул":
        bonus, _ = get_title_bonus(uid)
        send(peer_id, card("МОЙ ТИТУЛ", [("👤",name_of(uid)),("⭐",utitle(uid) or "—"),("🎰 Титул",f"×{bonus}"),("🎨 Стиль",f"×{style_bonus()}")]), kb_back()); return

    if cmd == "/promo":
        if len(args)<2: return send(peer_id, "📝 /promo <код>")
        code = args[1].upper()
        cur.execute("SELECT amount,uses,max_uses FROM promos WHERE code=?", (code,))
        p = cur.fetchone()
        if not p: return send(peer_id, f"❌ Промокод `{code}` не найден")
        amount, uses, max_uses = p
        if uses >= max_uses: return send(peer_id, f"❌ Промокод `{code}` исчерпан\n👥 {uses}/{max_uses} активаций")
        cur.execute("UPDATE promos SET uses=uses+1 WHERE code=?", (code,)); conn.commit()
        upd_balance(uid, amount)
        send(peer_id, f"✅ Промокод `{code}` активирован!\n\n  💰 +{fmt(amount)} 💵\n  👥 Активаций: {uses+1}/{max_uses}\n\n  💳 Баланс: {fmt(get_balance(uid))} 💵"); return

    if cmd == "/createpromo":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        if len(args) < 4: return send(peer_id, "📝 /createpromo <код> <сумма> <макс.активаций>")
        code = args[1].upper()
        try: a = int(args[2]); u = int(args[3])
        except: return send(peer_id, "❌ Сумма и кол-во — числа")
        if a <= 0 or u <= 0: return send(peer_id, "❌ Сумма и кол-во > 0")
        cur.execute("SELECT code FROM promos WHERE code=?", (code,))
        if cur.fetchone(): return send(peer_id, f"❌ Промокод `{code}` уже существует")
        cur.execute("INSERT OR REPLACE INTO promos(code,amount,uses,max_uses) VALUES(?,?,0,?)", (code, a, u)); conn.commit()
        send(peer_id, f"✅ Промокод создан\n\n{promo_card(code, a, 0, u)}"); return

    if cmd in ("/ивент","/мафия"):
        if chat_id: mafia_new(peer_id, uid, chat_id); return
    if cmd == "/мафия_вступить":
        if chat_id: mafia_join(peer_id, uid, chat_id); return
    if cmd == "/мафия_старт":
        if chat_id: mafia_start(peer_id, uid, chat_id); return
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

# ============ ПАГИНАЦИЯ БИЗНЕСОВ ============
def biz_page(peer_id, page):
    if page < 0: page = 0
    cur.execute("SELECT COUNT(*) FROM biz_types"); total = cur.fetchone()[0]
    pages = (total + 9) // 10
    if pages == 0: return send(peer_id, "❌ Нет бизнесов", kb_back())
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

# ============ ВХОД В ЧАТ ============
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

# ============ ДИАГНОСТИКА ============
def _startup_diagnostics():
    # Скачиваем шрифты, если их нет
    fonts = {
        "font_regular.ttf": "https://github.com/google/fonts/raw/main/ofl/roboto/Roboto-Regular.ttf",
        "font_bold.ttf": "https://github.com/google/fonts/raw/main/ofl/roboto/Roboto-Bold.ttf"
    }
    for name, url in fonts.items():
        if not os.path.exists(name):
            try:
                urllib.request.urlretrieve(url, name)
                log(f"✅ Скачан шрифт: {name}")
            except Exception as e:
                log(f"❌ Ошибка скачивания {name}: {e}")

    log("🔍 ПРОВЕРКА ОКРУЖЕНИЯ:")
    try:
        from PIL import Image
        log("   ✅ Pillow установлен")
    except Exception as e:
        log(f"   ❌ Pillow НЕ установлен: {e}")
    try:
        import requests
        log("   ✅ requests установлен")
    except Exception as e:
        log(f"   ❌ requests НЕ установлен: {e}")
    try:
        import stats_card
        log("   ✅ stats_card.py загружен")
    except Exception as e:
        log(f"   ❌ stats_card.py НЕ загружен: {e}")
    try:
        from stats_card import render_card
        test = render_card("https://i.postimg.cc/4x3XfLZW/ffaa3ac666ac63e26a51b9b22f83fcf8.jpg",
                           {"title":"Test"}, out_path="test_stats.png")
        if os.path.exists(test):
            log(f"   ✅ Тестовая карточка: {test} ({os.path.getsize(test)} байт)")
            try: os.remove(test)
            except: pass
    except Exception as e:
        log(f"   ❌ Тест render_card: {e}")

# ============ ЗАПУСК ============
def main():
    global vk, longpoll
    log("⚔️ Бот запускается...")
    if longpoll is None or vk is None:
        log("📡 Повторная инициализация VK в main()...")
        if not _init_vk():
            log("❌ Не удалось инициализировать VK"); return
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
        cur.execute("SELECT COUNT(*) FROM builds WHERE UPPER(type)='PIAR'"); pc = cur.fetchone()[0]
        log(f"🏢 Бизнесов: {bc} | 🌍 Стран: {cc} | 🏙 Городов: {ctc} | 📢 PIAR-чатов: {pc}")
        log(f"🎨 Стиль: {style_name()}")
    except Exception as e: 
        log(f"⚠️ Ошибка при инициализации данных: {e}")

    _startup_diagnostics()

    log("🎧 Слушаю события...")
    threading.Thread(target=pr_resend_worker, daemon=True).start()
    log("🔁 Авто-пиар воркер запущен")

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
                    except Exception as e: 
                        log(f"❌ Callback Error: {e}")
                    continue
                if event.type != VkBotEventType.MESSAGE_NEW: 
                    continue
                msg = event.object.message
                peer_id = msg['peer_id']; uid = msg['from_id']
                message_id = msg['id']; text = msg.get('text','')
                action = msg.get('action')

                if is_duplicate(message_id):
                    continue

                if action:
                    if action.get('type') in ('chat_invite_user','chat_invite_user_by_link'):
                        member = action.get('member_id')
                        if member and member > 0: 
                            handle_chat_invite(peer_id, member)
                    continue
                if not text: 
                    continue
                try: 
                    handle_message(peer_id, uid, text, message_id, msg)
                except Exception as e:
                    log(f"❌ Handler Error: {e}")
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            log(f"❌ LongPoll Error: {type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stdout)
            time.sleep(3)

if __name__ == "__main__":
    main()
