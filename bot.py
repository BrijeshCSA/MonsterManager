# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3, random, time, json, os, sys, traceback, threading
from datetime import datetime

def log(msg):
    print(msg, flush=True); sys.stdout.flush()

# ============ НАСТРОЙКИ ============
FALLBACK_TOKEN = ""  # Токен лучше держать в переменной окружения VK_TOKEN на Bothost
TOKEN = os.getenv("VK_TOKEN") or FALLBACK_TOKEN
GROUP_ID = int(os.getenv("GROUP_ID", 242006213))
MAIN_OWNER = int(os.getenv("MAIN_OWNER", 889701916))
if not TOKEN:
    log("❌ Нет VK_TOKEN (ни в env, ни в FALLBACK_TOKEN)"); raise SystemExit(1)

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
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_stats(user_id INTEGER PRIMARY KEY,
        bans INTEGER DEFAULT 0, mutes INTEGER DEFAULT 0, warns INTEGER DEFAULT 0,
        reports INTEGER DEFAULT 0, offers INTEGER DEFAULT 0, tickets INTEGER DEFAULT 0)""")
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

    conn.commit()
    cur.execute("INSERT OR IGNORE INTO bot_settings(key,value) VALUES(?,?)", ("style","обычный"))
    cur.execute("INSERT OR IGNORE INTO bot_settings(key,value) VALUES(?,?)", ("drone_case_active","0"))
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
    ("users","raid_last","INTEGER DEFAULT 0"),
    ("users","msg_count","INTEGER DEFAULT 0"),
    ("users","mat_count","INTEGER DEFAULT 0"),
    ("users","captures","INTEGER DEFAULT 0"),
    ("pr_orders","interval_min","INTEGER DEFAULT 0"),
    ("pr_orders","last_resend","INTEGER DEFAULT 0"),
    ("users","married_to","INTEGER DEFAULT 0"),
    ("users","married_date","INTEGER DEFAULT 0"),
    ("users","aevent_last","INTEGER DEFAULT 0"),
    ("users","drone_last","INTEGER DEFAULT 0"),
    ("users","vip_until","INTEGER DEFAULT 0"),
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

# ============ НАКАЗАНИЯ (КАРТОЧКИ) ============
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

def get_chat_link(peer_id):
    if peer_id >= 2000000000: cid = peer_id - 2000000000
    else: cid = peer_id
    return f"https://m.vk.ru/gim{GROUP_ID}/convo/{cid}?entrypoint=list_all"

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
        [kbt("🆘 Помощь","/help","secondary")],
        [kbt("📊 Моя стата","/стата","secondary")],
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
    "📊 стата":"/стата","🆘 помощь":"/help","🏙 города":"/моигорода","💞 брак":"/брак",
}

# ============ ПРОМОКОД-КАРТОЧКА ============
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
    
    # Бонусы: титул, стиль и VIP
    tbonus, title = get_title_bonus(uid)
    sbonus = style_bonus()
    vbonus = 1.5 if is_vip(uid) else 1.0
    bonus = tbonus * sbonus * vbonus
    
    btxt = ""
    if bonus > 1.0:
        parts = []
        if tbonus > 1.0: parts.append(f"титул ×{tbonus}")
        if sbonus > 1.0: parts.append(f"стиль ×{sbonus}")
        if vbonus > 1.0: parts.append(f"VIP ×{vbonus}")
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

# ============ АДМИН-ИВЕНТ И ДРОН-КЕЙС ============
DRONE_PRIZES = [
    "«Молния-2»", "«Овод»", "«Князь Вандал Новгородский»", "«Герань-2»", "«Герань-5»", "«Ланцет»", 
    "«КУБ»", "«СКАТ 350М»", "«Гранат-4»", "«БПЛА400Т»", "«Каракурт 2.0»", "«Голиаф 2.0»", 
    "«Орлан-10»", "«Орлан-30»", "ZALA", "«Форпост»", "«Элерон-3»", "«С-70 Охотник»", 
    "«Кронштадт Орион»", "«МиС-150»", "«МиС-35»", "«Буран»", "«Скальпель»", "«Клин»",
    "«Галка»", "Skyriper Minotaur", "«Гор Элкс»", "«Бешкет»", "Shturm", "Bababoom", "Zorro", "Blinc", 
    "«Оптослон»", "«Чумак»", "«Сокол»", "Hydra", "«Крук»", "«Дзига»", "«Харьок»", "«Буран»", 
    "«Белый Волк»", "«Сичень»", "«Бабака»", "Anubis", "Seth-X", "KOLIBRI", "Thyra", "«Рута»", 
    "FP-1", "Magura V5", "«Лелека-100»", "«Фурия»", "PD-2", "UJ-22 Airborne",
    "MQ-9 Reaper", "RQ-4 Global Hawk", "MQ-1C Gray Eagle", "MQ-1 Predator", "Switchblade 300", 
    "Switchblade 600", "RQ-1 Predator", "MQ-4C Triton",
    "Wing Loong II", "CH-5 Rainbow", "GJ-3A", "WZ-10", "WZ-7", "WZ-8", "GJ-2", "GJ-1", "CH-3", 
    "AV500W", "WJ-700", "TB-001", "GJ-11", "FH-97A", "BZK-005E", "FL-60A", "CY-8", 
    "«暗剑»", "«九天»", "«彩虹七号»", "«云影»-25V", "«云影»-550T",
    "Bayraktar TB2", "TAI Anka", "Bayraktar AKINCI", "Bayraktar TB3", "«Kızılelma»", 
    "K2", "Sivrisinek", "Mizrak", "TAI Gözcü", "Mini-Bayraktar",
    "IAI Harop", "Hermes 900", "Hermes 450", "IAI Eitan (Heron TP)", "IAI Heron",
    "Shahed-136", "Shahed-131", "Shahed-129", "Shahed-149 (Gaza)", "Shahed-101", "Shahed-107", 
    "Shahed-141", "Shahed-161", "Mohajer-6", "Mohajer-10", "Arash-2", "Ababil-4", "Ababil-5", 
    "Pelican", "Homa", "Chamroosh", "Jubin", "Bavar-5", "Hadid-110",
    "DRDO Abhyas", "DRDO AURA", "DRDO Fluffy", "DRDO Imperial Eagle", "DRDO Kapothaka", 
    "DRDO Lakshya", "DRDO Netra", "Gagan UAV",
    "Ababeel", "Border Eagle", "Burraq", "Explorer", "Flamingo", "GIDS Huma", "GIDS Uqab",
    "Saetbyol-4", "Saetbyol-9", "разведывательно-ударные БПЛА", "барражирующие боеприпасы",
    "小型无人机", "中高空无人机", "集群无人机",
    "MQ-9B Sky Guardian", "Harfang", "Euro Hawk", "Watchkeeper", "Sperwer A", "KZO", 
    "Luna", "Luna NG", "Aladin", "Spy Ranger", "Camcopter", "Helsing HX-2", "Stark Virtus",
    "RQ-5A/MQ-5B Hunter", "Black Hornet"
]

def play_admin_event(peer_id, uid, chat_id):
    if get_priority(uid) < 20:
        return send(peer_id, "❌ Ивент доступен только администрации (20+)")
    
    now = int(time.time())
    last = ufield(uid, "aevent_last", 0) or 0
    cooldown = 86400
    
    if now - last < cooldown:
        left = cooldown - (now - last)
        return send(peer_id, f"⏳ Ты уже открывал админ-ивент.\nСледующий через: {time_left_fmt(left)}")
        
    cur.execute("UPDATE users SET aevent_last=? WHERE user_id=?", (now, uid)); conn.commit()
    
    roll = random.random()
    if roll < 0.10:
        amt = random.randint(5000000, 10000000)
        upd_balance(uid, amt)
        reward = f"💰 {fmt(amt)} 💵"
    elif roll < 0.40:
        amt = random.randint(1000, 3000)
        add_exp(uid, amt)
        reward = f"⚡ +{amt} exp"
    else:
        cur.execute("UPDATE users SET rep=rep+10 WHERE user_id=?", (uid,))
        conn.commit()
        reward = "🌟 +10 Репутации"
        
    send(peer_id, f"{style_div()}\n     🚨 АДМИН-ИВЕНТ 🚨\n{style_div()}\n\n"
                  f"  👤 {mention(uid)} вскрыл сейф!\n\n"
                  f"  🎁 Выпало: {reward}\n\n{style_div()}")

def play_drone_case(peer_id, uid):
    cur.execute("SELECT value FROM bot_settings WHERE key='drone_case_active'")
    r = cur.fetchone()
    if not r or r[0] != "1":
        return send(peer_id, "⛔ Дрон-кейс сейчас закрыт. Владелец (100+) должен его включить.")
        
    now = int(time.time())
    last = ufield(uid, "drone_last", 0) or 0
    cooldown = 86400
    
    if now - last < cooldown:
        left = cooldown - (now - last)
        return send(peer_id, f"⏳ Следующее открытие Дрон-кейса через: {time_left_fmt(left)}")
        
    cur.execute("UPDATE users SET drone_last=? WHERE user_id=?", (now, uid)); conn.commit()
    
    drone = random.choice(DRONE_PRIZES)
    title_name = f"🛸 {drone}"
    
    cur.execute("INSERT OR IGNORE INTO custom_titles(name,emoji,level,created_by,created_at) VALUES(?,?,?,?,?)",
                (title_name, "🛸", 5, MAIN_OWNER, now))
    cur.execute("UPDATE users SET title=? WHERE user_id=?", (title_name, uid))
    conn.commit()
    
    txt = (f"{style_div()}\n"
           f"     🛸 DRONE КЕЙС 🛸\n"
           f"{style_div()}\n\n"
           f"  👤 {mention(uid)} открыл кейс!\n\n"
           f"  🎁 Выпал сувенир:\n"
           f"  🎖️ *{title_name}*\n\n"
           f"  📈 Бонус к доходу увеличен!\n"
           f"  📊 Смотри в /стата\n\n"
           f"{style_div()}")
    send(peer_id, txt)

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
  /налёт <город> — грабёж чужого города (50 000 💵, 40%)

🌍 СТРАНА
  /страны /страна
  /гражданство [название] — вступить в страну
  /паспорт /казна /граждане /армия /города

💞 БРАК
  /брак <юзер> — жениться/выйти замуж
  /развод — развестись
  /топ брак — самые долгие браки

🛸 DRONE КЕЙС
  /дрон_кейс — открыть (если включен)

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
    bonus = tbonus * sbonus * vbonus

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
            cur.execute("""SELECT id,text,interval_min,last_resend
                           FROM pr_orders
                           WHERE status='sent' AND interval_min>0
                             AND text IS NOT NULL AND text != ''""")
            rows = cur.fetchall()
            for oid, body, interval, last in rows:
                if not interval or interval <= 0: continue
                if now - (last or 0) < interval * 60: continue
                sent = pr_send_to_piar_chats(body)
                cur.execute("UPDATE pr_orders SET last_resend=?, sent_count=sent_count+? WHERE id=?",
                            (now, sent, oid))
                conn.commit()
                log(f"🔁 Авто-пиар #{oid}: {sent} PIAR-чатов")
        except Exception as e:
            log(f"❌ pr_resend_worker: {e}")
        time.sleep(30)
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

    # СЧЁТЧИКИ СООБЩЕНИЙ И МАТА
    if not text.startswith("/") and len(text) >= 2:
        if has_mat(text):
            cur.execute("UPDATE users SET msg_count=msg_count+1, mat_count=mat_count+1 WHERE user_id=?", (uid,))
        else:
            cur.execute("UPDATE users SET msg_count=msg_count+1 WHERE user_id=?", (uid,))
        conn.commit()

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

    # ПРОВЕРКИ БАНА И МУТА
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
        send_uid(t, f"🔇 Ты заглушен на {time_left_fmt(m*60)}. Причина: {reason}")
        return

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
        send_uid(t, f"🚫 Ты забанен. Причина: {reason}")
        return

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
        send_uid(t, f"🌐 Ты глобально забанен. Причина: {reason}")
        return

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
        send_uid(t, f"💠 Тебе выдан VIP на {days} дней!")
        return

    if cmd in ("/выдать_опыт", "/exp"):
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        try: amt = int(args[2]) if len(args)>2 else 100
        except: amt = 100
        if not t: return
        add_exp(t, amt)
        send(peer_id, f"⚡ {mention(t)} выдано {amt} опыта")
        return

    if cmd in ("/выдать_репу", "/rep"):
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        try: amt = int(args[2]) if len(args)>2 else 10
        except: amt = 10
        if not t: return
        cur.execute("UPDATE users SET rep=rep+? WHERE user_id=?", (amt, t)); conn.commit()
        send(peer_id, f"🌟 {mention(t)} выдано {amt} репутации")
        return

    # ============ ДРОН-КЕЙС И АДМИН-ИВЕНТ ============
    if cmd == "/админ_ивент":
        return play_admin_event(peer_id, uid, chat_id)

    if cmd == "/дрон_кейс":
        return play_drone_case(peer_id, uid)

    if cmd in ("/дрон_кейс_вкл", "/дрон_кейс_выкл"):
        if get_priority(uid) < 100: return
        state = "1" if cmd == "/дрон_кейс_вкл" else "0"
        cur.execute("INSERT OR REPLACE INTO bot_settings(key,value) VALUES('drone_case_active',?)", (state,))
        conn.commit()
        msg = "🟢 Дрон-кейс ВКЛЮЧЕН" if state == "1" else "🔴 Дрон-кейс ВЫКЛЮЧЕН"
        send(peer_id, f"{msg}\nТеперь доступен всем игрокам.")
        return

    # ============ СТАТА / ПРОФИЛЬ ============
    if cmd == "/стата":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg) or uid
        lvl = ulevel(t); exp = uexp(t); need = (lvl+1)*100
        prog = get_progress_bar(exp, need, 8)
        pct = int((exp/need)*100) if need > 0 else 0
        msgs = umsg_count(t); warns = uwarns(t)
        m_to = umarried_to(t)
        partner = name_of(m_to) if m_to else "нет"
        rep = urep(t); nick = ufield(t, "nick") or "не установлен"
        pos = get_position(t) or "—"
        
        cur.execute("SELECT role FROM user_roles WHERE user_id=? AND chat_id=?", (t, chat_id or 0))
        ur = cur.fetchone()
        chat_role = ur[0] if ur else "Участник"
        priority = get_priority(t)
        vip = "Да" if is_vip(t) else "Нет"
        
        # Титулы (сувениры)
        title_display = utitle(t) if utitle(t) else "Нет"
        
        txt = (f"━━━━━━━━━━━━━━━━━━━━\n"
               f"👤  {name_of(t).upper()}\n"
               f"NEXUS · PROFILE\n"
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
               f"📛  Ник         ·  {nick}\n"
               f"🛸  Сувенир     ·  {title_display}\n\n"
               f"━━━━━━━━━━━━━━━━━━━━\n\n"
               f"🔥  Статус:  {get_title(lvl)}\n\n"
               f"━━━━━━━━━━━━━━━━━━━━")
        send(peer_id, txt, kb_back()); return

    # ============ БРАК ============
    if cmd == "/брак":
        if umarried_to(uid):
            return send(peer_id, "❌ Ты уже в браке. Используй /развод")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or t == uid: return send(peer_id, "📝 /брак @юзер")
        if umarried_to(t): return send(peer_id, "❌ Этот человек уже в браке")
        now = int(time.time())
        cur.execute("UPDATE users SET married_to=?, married_date=? WHERE user_id=?", (t, now, uid))
        cur.execute("UPDATE users SET married_to=?, married_date=? WHERE user_id=?", (uid, now, t))
        conn.commit()
        send(peer_id, f"💞 {mention(uid)} и {mention(t)} теперь в браке!\n🎉 Совет да любовь!")
        return

    if cmd == "/развод":
        p = umarried_to(uid)
        if not p: return send(peer_id, "❌ Ты не в браке")
        cur.execute("UPDATE users SET married_to=0, married_date=0 WHERE user_id IN (?,?)", (uid, p))
        conn.commit()
        send(peer_id, f"💔 Брак между {mention(uid)} и {mention(p)} расторгнут.")
        return

    # ============ ТОПЫ ============
    if cmd in ("/топ", "топ"):
        cat = args[1].lower() if len(args) > 1 else "баланс"
        m = ["🥇","🥈","🥉"] + ["🔹"]*7
        if cat in ("баланс", "balance", "деньги", "💰"):
            cur.execute("SELECT user_id,balance+bank FROM users ORDER BY balance+bank DESC LIMIT 10")
            rows = cur.fetchall()
            txt = header("💰 ТОП-10 ПО БАЛАНСУ")+"\n\n"
            for i,(u,b) in enumerate(rows): txt += f"  {m[i]} {name_of(u)} — {fmt(b)} 💵\n"
        elif cat in ("брак", "любовь", "💞"):
            cur.execute("""SELECT u1.user_id, u1.married_to, u1.married_date 
                           FROM users u1 
                           WHERE u1.married_to > 0 AND u1.user_id < u1.married_to 
                           ORDER BY u1.married_date ASC LIMIT 10""")
            rows = cur.fetchall()
            txt = header("💞 ТОП-10 САМЫХ ДОЛГИХ БРАКОВ")+"\n\n"
            for i, (u1, u2, dt) in enumerate(rows):
                days = (int(time.time()) - dt) // 86400
                txt += f"  {m[i]} {name_of(u1)} + {name_of(u2)} — {days} дн.\n"
            if not rows: txt += "  ❌ Пока нет браков\n"
        else:
            txt = f"{header('🏆 ТОПЫ')}\n\n  💰 /топ баланс\n  💞 /топ брак\n{style_div()}"
        send(peer_id, txt + f"\n{style_div()}", kb_back()); return
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


# ============ ЗАПУСК ============
def main():
    global vk, longpoll
    log("⚔️ Бот запускается...")
    
    # Защита: если longpoll не создан при импорте — создаём здесь
    if longpoll is None or vk is None:
        log("📡 Повторная инициализация VK в main()...")
        if not _init_vk():
            log("❌ Не удалось инициализировать VK"); return

    try:
        # Выдаём права создателю и владельцам
        get_user(MAIN_OWNER)
        for ow in OWNERS:
            try:
                get_user(ow)
                cur.execute("UPDATE users SET role='Гл.Владелец', priority=101, balance=MAX(balance,999999999) WHERE user_id=?", (ow,))
            except: pass
        conn.commit()
        
        # Вывод статистики при старте
        cur.execute("SELECT COUNT(*) FROM biz_types"); bc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM countries"); cc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cities"); ctc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM builds WHERE UPPER(type)='PIAR'"); pc = cur.fetchone()[0]
        log(f"🏢 Бизнесов: {bc} | 🌍 Стран: {cc} | 🏙 Городов: {ctc} | 📢 PIAR-чатов: {pc}")
        log(f"🎨 Стиль: {style_name()}")
    except Exception as e: 
        log(f"⚠️ Ошибка при инициализации данных: {e}")

    log("🎧 Слушаю события...")
    
    # Запускаем фоновый поток авто-пиара
    threading.Thread(target=pr_resend_worker, daemon=True).start()
    log("🔁 Авто-пиар воркер запущен")

    while True:
        try:
            for event in longpoll.listen():
                # Обработка нажатий на кнопки (Callback API)
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
                
                # Обработка новых сообщений
                if event.type != VkBotEventType.MESSAGE_NEW: 
                    continue
                    
                msg = event.object.message
                peer_id = msg['peer_id']; uid = msg['from_id']
                message_id = msg['id']; text = msg.get('text','')
                action = msg.get('action')
                
                # Обработка вступления в чат
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
