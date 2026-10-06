# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3, random, time, json, os
from datetime import datetime

# ============ НАСТРОЙКИ ============
TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", 242006213))
MAIN_OWNER = int(os.getenv("MAIN_OWNER", 889701916))
if not TOKEN: raise SystemExit("❌ Не задан VK_TOKEN!")

# ============ БАЗА ============
conn = sqlite3.connect('bot.db', check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 100, warns INTEGER DEFAULT 0,
        role TEXT DEFAULT 'user', country TEXT, citizenship TEXT, army INTEGER DEFAULT 100000,
        war INTEGER DEFAULT 1000000, mute_until INTEGER DEFAULT 0, last_bonus INTEGER DEFAULT 0,
        rank TEXT DEFAULT 'Новобранец', biz INTEGER DEFAULT 0, biz_income INTEGER DEFAULT 0,
        biz_collect INTEGER DEFAULT 0, subscription INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS countries(
        name TEXT PRIMARY KEY, owner INTEGER, president INTEGER, treasury INTEGER DEFAULT 100000,
        army INTEGER DEFAULT 100000, cities INTEGER DEFAULT 1, taxes INTEGER DEFAULT 5,
        pvo INTEGER DEFAULT 0, border_open INTEGER DEFAULT 1, buildings TEXT DEFAULT '{}',
        projects TEXT DEFAULT '{}', alive INTEGER DEFAULT 1)""")
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
    cur.execute("""CREATE TABLE IF NOT EXISTS members(user_id INTEGER PRIMARY KEY,
        country TEXT, position TEXT DEFAULT 'Гражданин')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner INTEGER, country TEXT, name TEXT, income INTEGER DEFAULT 1000, balance INTEGER DEFAULT 0,
        last_collect INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stockpile(country TEXT PRIMARY KEY,
        food INTEGER DEFAULT 0, weapons INTEGER DEFAULT 0, resources INTEGER DEFAULT 0,
        fuel INTEGER DEFAULT 0, money INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS transports(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner INTEGER, type TEXT, count INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS country_army(country TEXT PRIMARY KEY,
        troops INTEGER DEFAULT 0, pvo INTEGER DEFAULT 0, rockets INTEGER DEFAULT 0, drones INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS nicks(user_id INTEGER PRIMARY KEY, nick TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS roles(name TEXT PRIMARY KEY, level INTEGER DEFAULT 1,
        created_by INTEGER, created_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_roles(user_id INTEGER, chat_id INTEGER,
        role TEXT, PRIMARY KEY(user_id, chat_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS global_roles(user_id INTEGER PRIMARY KEY, role TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS builds(chat_id INTEGER PRIMARY KEY, peer_id INTEGER,
        title TEXT, linked_by INTEGER, linked_at INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cmd_perms(user_id INTEGER, command TEXT,
        PRIMARY KEY(user_id, command))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS chat_staff(chat_id INTEGER, user_id INTEGER,
        position TEXT, PRIMARY KEY(chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bot_disabled(peer_id INTEGER PRIMARY KEY, since INTEGER)""")
    conn.commit()
    for r, lvl in [("Глава",10),("Заместитель",8),("Модератор",5),("Хелпер",3),("Участник",1)]:
        try: cur.execute("INSERT OR IGNORE INTO roles(name,level,created_by,created_at) VALUES(?,?,?,?)",
                         (r, lvl, MAIN_OWNER, int(time.time())))
        except: pass
    conn.commit()

init_db()

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
def is_owner(uid): return uid == MAIN_OWNER

def is_admin(uid):
    if uid == MAIN_OWNER: return True
    cur.execute("SELECT role FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    return r and r[0] in ('admin','moder','owner')

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
    if msg and msg.get('reply_message'):
        return msg['reply_message']['from_id']
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

def is_government(uid):
    return get_position(uid) in ('Президент','Министр','Генерал','Губернатор')

# ============ VK ============
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

def send(peer_id, text, keyboard=None):
    try: vk.messages.send(peer_id=peer_id, message=text, random_id=get_random_id(), keyboard=keyboard)
    except Exception as e: print(f"Send: {e}")

def send_uid(user_id, text):
    try: vk.messages.send(user_id=user_id, message=text, random_id=get_random_id())
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
def kbt(label, cmd):
    return {"action":{"type":"text","label":label,"payload":json.dumps({"cmd":cmd})},"color":"primary"}
def kbc(label, cmd, color="positive"):
    return {"action":{"type":"callback","label":label,"payload":json.dumps({"cmd":cmd})},"color":color}

def kb_main(): return kb([
    [kbt("💰 Баланс","/баланс"), kbt("🏆 Топ","/топ")],
    [kbt("🎰 Клуб","/клуб"), kbt("🎲 Казино","/казино")],
    [kbt("🌍 Страна","/страна"), kbt("📘 Паспорт","/паспорт")],
    [kbt("🎁 Приз","/приз"), kbt("📋 Задания","/задания")],
    [kbt("📜 Устав","/rules"), kbt("⚔️ Войны","/войны")],
])
def kb_games(): return kb([
    [kbt("🎰 Казино","/казино"), kbt("🪙 Монетка","/монетка")],
    [kbt("🎲 Кубик","/кубик"), kbt("🍒 Слоты","/слоты")],
    [kbt("⚔️ Дуэль","/дуэль"), kbt("◀️ Меню","/меню")],
])
def kb_country(): return kb([
    [kbt("🌍 Страны","/страны"), kbt("📘 Паспорт","/паспорт")],
    [kbt("🏛 Казна","/казна"), kbt("🎖️ Армия","/армия")],
    [kbt("🗺 Гос.команды","/госскоманды"), kbt("◀️ Меню","/меню")],
])
def kb_back(): return kb([[kbt("◀️ Меню","/меню")]])
def kb_mafia_lobby(): return kb([
    [kbc("✅ Вступить","/мафия_вступить","positive")],
    [kbc("▶️ Начать","/мафия_старт","primary")],
])

TRANSPORT_PRICE = {"грузовик":50000,"поезд":250000,"корабль":500000,"самолет":1000000}
PRODUCTS = ("еда","оружие","ресурсы","топливо","деньги")
BUILDINGS = {"ферма":100000,"завод":250000,"нефтевышка":300000,"казарма":200000,"радар":150000,"госпиталь":180000}

# ============ МАФИЯ ============
MAFIA = {}

def mafia_new(peer_id, uid, chat_id):
    if chat_id in MAFIA: return send(peer_id, "🎭 Игра уже идёт!")
    MAFIA[chat_id] = {'state':'lobby','players':[],'roles':{},'alive':[],'votes':{},'day':0,'host':uid,'night':{}}
    send(peer_id, "🎭 МАФИЯ — набор игроков!\nНужно минимум 4.\n\nЖми «Вступить»", kb_mafia_lobby())

def mafia_join(peer_id, uid, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='lobby': return
    if uid in g['players']: return send(peer_id, f"❌ {mention(uid)} уже в игре")
    g['players'].append(uid)
    send(peer_id, f"✅ {mention(uid)} присоединился! Игроков: {len(g['players'])}")

def mafia_start(peer_id, uid, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='lobby': return
    if uid != g['host'] and not is_admin(uid): return send(peer_id,"❌ Только организатор")
    if len(g['players'])<4: return send(peer_id,"❌ Минимум 4 игрока")
    n = len(g['players'])
    roles = ['мафия']*max(1,n//3) + ['комиссар','доктор'] + ['мирный']*(n - max(1,n//3) - 2)
    random.shuffle(roles)
    for i,u in enumerate(g['players']):
        g['roles'][u] = roles[i]
        send_uid(u, f"🎭 Твоя роль: *{roles[i].upper()}*")
    g['alive'] = list(g['players']); g['state']='night'; g['day']=1; g['night']={}
    send(peer_id, f"{header('НОЧЬ 1')}\n\nГород засыпает...\nМафия выбирает жертву.")
    send_uid(g['host'], "💡 Мафия должна написать /мафия_убить <id>")

def mafia_kill(peer_id, uid, target):
    chat_id = peer_id - 2000000000 if peer_id >= 2000000000 else peer_id
    g = MAFIA.get(chat_id)
    if not g or g['state']!='night': return
    if g['roles'].get(uid) != 'мафия': return send(peer_id, "❌ Только мафия")
    if target not in g['alive']: return
    g['night']['kill'] = target
    send(peer_id, "🔪 Мафия сделала выбор.")

def mafia_next_day(peer_id, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='night': return
    killed = g['night'].get('kill')
    if killed and killed in g['alive']: g['alive'].remove(killed)
    g['state']='day'
    day_num = g['day']
    txt = header("ДЕНЬ " + str(day_num)) + "\n\n"
    if killed: txt += f"💀 Ночью погиб {mention(killed)}\n\n"
    txt += "Обсуждайте и голосуйте:\n/мафия_голос <id>\n\nЖивые:\n"
    for u in g['alive']: txt += f"  • {mention(u)}\n"
    send(peer_id, txt)
    g['votes'] = {}

def mafia_vote(peer_id, uid, target):
    chat_id = peer_id - 2000000000 if peer_id >= 2000000000 else peer_id
    g = MAFIA.get(chat_id)
    if not g or g['state']!='day': return
    if uid not in g['alive']: return
    if target not in g['alive']: return
    g['votes'][uid] = target
    send(peer_id, f"🗳️ {mention(uid)} проголосовал")

def mafia_resolve(peer_id, chat_id):
    g = MAFIA.get(chat_id)
    if not g or g['state']!='day': return
    if not g['votes']: return send(peer_id, "❌ Никто не голосовал")
    from collections import Counter
    cnt = Counter(g['votes'].values())
    victim, votes = cnt.most_common(1)[0]
    if victim in g['alive']: g['alive'].remove(victim)
    role = g['roles'].get(victim, '?')
    txt = f"⚖️ Изгнан {mention(victim)} — он был *{role}*\n\n"
    maf_alive = [u for u in g['alive'] if g['roles'].get(u)=='мафия']
    town_alive = [u for u in g['alive'] if g['roles'].get(u)!='мафия']
    if not maf_alive:
        txt += "🎉 ГОРОД ПОБЕДИЛ!"
        send(peer_id, txt); del MAFIA[chat_id]; return
    if len(maf_alive) >= len(town_alive):
        txt += "🔪 МАФИЯ ПОБЕДИЛА!"
        send(peer_id, txt); del MAFIA[chat_id]; return
    g['day'] += 1; g['state'] = 'night'; g['night'] = {}
    day_num = g['day']
    txt += header("НОЧЬ " + str(day_num)) + "\n\nМафия выбирает жертву."
    send(peer_id, txt)

# ============ ОСНОВНОЙ ОБРАБОТЧИК ============
def handle_message(peer_id, uid, text, message_id=None, event_msg=None):
    text = text.strip(); low = text.lower()
    args = text.split(); cmd = args[0].lower() if args else ""
    chat_id = peer_to_chat(peer_id)

    # ============ /stop ============
    if cmd == "/stop":
        if not is_owner(uid): return send(peer_id, "❌ Только главный владелец")
        cur.execute("INSERT OR REPLACE INTO bot_disabled(peer_id,since) VALUES(?,?)", (peer_id, int(time.time())))
        conn.commit()
        send(peer_id, "🛑 Бот выключен в этом чате.\nДля включения: /start")
        return

    # ============ /start ============
    if cmd == "/start":
        if is_bot_disabled(peer_id):
            if not is_owner(uid): return
            cur.execute("DELETE FROM bot_disabled WHERE peer_id=?", (peer_id,))
            conn.commit()
            send(peer_id, "✅ Бот снова активен в этом чате!")
            return
        if is_owner(uid) and chat_id:
            send(peer_id, "✅ Бот активен. Для выключения — /stop")
            return
        # обычное меню
        get_user(uid); u = get_user(uid)
        send(peer_id, f"{header('БОЕВОЙ БОТ')}\n\n  👤 {name_of(uid)}\n"
                      f"  💰 {fmt(u[1])} 💵\n  🎖️ {u[10]}\n  🌍 {u[5] or 'нет гражданства'}\n\n"
                      f"  🎯 Выберите действие\n  📖 /help — все команды", kb_main())
        return

    # Если бот выключен в этом чате — игнорируем всё
    if is_bot_disabled(peer_id):
        return

    if is_banned(uid) and not is_owner(uid):
        if chat_id: kick_user(chat_id, uid)
        return
    if is_muted(uid) > 0 and not is_admin(uid):
        if message_id: delete_message(peer_id, message_id)
        return

    # ================= МЕНЮ =================
    if low in ("начать","start","меню","◀️ меню"):
        get_user(uid); u = get_user(uid)
        send(peer_id, f"{header('БОЕВОЙ БОТ')}\n\n  👤 {name_of(uid)}\n"
                      f"  💰 {fmt(u[1])} 💵\n  🎖️ {u[10]}\n  🌍 {u[5] or 'нет гражданства'}\n\n"
                      f"  🎯 Выберите действие\n  📖 /help — все команды", kb_main())
        return

    if cmd == "/help":
        send(peer_id, f"{header('КОМАНДЫ')}\n\n"
            f"💰 /баланс /топ /приз /передать /донат\n"
            f"🎁 /раздача /взять /подписка\n"
            f"🎲 /казино /дуэль /монетка /кубик /слоты\n"
            f"🌍 /страны /гражданство /паспорт /казна\n"
            f"⚔️ /войны /война /захват /мобилизация\n"
            f"🏛 /госскоманды — все команды страны\n"
            f"🎭 /ивент /мафия — игра\n"
            f"🎭 /role /setrole /grole /staff /gstaff\n"
            f"👑 /nick /rnick /стата /cmd\n"
            f"🎟️ /promo /promolist\n"
            f"🛡️ /warn /mute /kick /ban /обнулить /вайп\n"
            f"👑 /start /stop — вкл/выкл бота (владелец)", kb_back())
        return

    # ================= ЭКОНОМИКА =================
    if cmd in ("/баланс","баланс","💰 баланс"):
        u = get_user(uid)
        send(peer_id, card("БАЛАНС", [("👤",name_of(uid)),("💰",f"{fmt(u[1])} 💵"),
            ("🎖️",u[10]),("⚠️",f"{u[2]}/3"),("🌍",u[5] or "нет")]), kb_back()); return

    if cmd in ("/топ","топ","🏆 топ"):
        cur.execute("SELECT user_id,balance FROM users ORDER BY balance DESC LIMIT 10")
        rows = cur.fetchall(); medals = ["🥇","🥈","🥉"] + ["🔹"]*7
        txt = header("ТОП-10") + "\n\n"
        for i,(u,b) in enumerate(rows): txt += f"  {medals[i]} {name_of(u)} — {fmt(b)} 💵\n"
        send(peer_id, txt + f"\n{DIV}", kb_back()); return

    if cmd in ("/приз","приз","🎁 приз"):
        u = get_user(uid); last = u[9]
        if int(time.time()) - last < 3600:
            left = 3600 - (int(time.time()) - last)
            return send(peer_id, f"⏳ Приз через {left//60}м {left%60}с", kb_back())
        amount = random.randint(100, 900000); upd_balance(uid, amount)
        cur.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (int(time.time()), uid)); conn.commit()
        send(peer_id, f"🎁 +{fmt(amount)} 💵 | Баланс: {fmt(get_balance(uid))}", kb_back()); return

    if cmd == "/передать":
        if len(args) < 3: return send(peer_id, "📝 /передать <id> <сумма>")
        try:
            t = int(args[1].replace("@","").replace("[id","").split("|")[0].split("]")[0]); a = int(args[2])
        except: return send(peer_id, "❌")
        if a <= 0 or t == uid or get_balance(uid) < a: return send(peer_id, "❌")
        upd_balance(uid, -a); upd_balance(t, a)
        send(peer_id, f"✅ {fmt(a)} 💵 → {name_of(t)}", kb_back()); return

    if cmd == "/донат":
        send(peer_id, card("💎 ДОНАТ",[("⭐","500 000"),("💎","1 000 000")], f"@id{MAIN_OWNER}"), kb_back()); return

    # ================= ПОДПИСКА =================
    if cmd == "/подписка":
        u = get_user(uid)
        if u[14]:
            return send(peer_id, "✅ Подписка уже активна!")
        try:
            r = vk.groups.isMember(group_id=GROUP_ID, user_id=uid)
            if r:
                cur.execute("UPDATE users SET subscription=1 WHERE user_id=?", (uid,))
                upd_balance(uid, 50000); conn.commit()
                send(peer_id, "🎉 Спасибо за подписку! +50 000 💵")
            else:
                send(peer_id, f"📰 Подпишись на сообщество:\nhttps://vk.com/club{GROUP_ID}\n\nЗатем напиши /подписка снова")
        except:
            send(peer_id, f"📰 Подпишись: https://vk.com/club{GROUP_ID}\nЗатем /подписка снова")
        return

    if cmd == "/buybiz":
        u = get_user(uid)
        if u[11]: return send(peer_id, "🏢 Уже есть бизнес", kb_back())
        if get_balance(uid) < 500000: return send(peer_id, "❌ 500 000 💵", kb_back())
        upd_balance(uid, -500000)
        cur.execute("UPDATE users SET biz=1,biz_income=10000,biz_collect=? WHERE user_id=?", (int(time.time()), uid)); conn.commit()
        send(peer_id, "🏢 Бизнес куплен! 10 000 💵/час", kb_back()); return

    if cmd == "/mybiz":
        u = get_user(uid)
        if not u[11]: return send(peer_id, "❌ /buybiz", kb_back())
        hrs = min((int(time.time())-u[13])//3600, 24)
        send(peer_id, card("🏢 БИЗНЕС",[("💵",f"{fmt(u[12])}/ч"),("⏳",f"{fmt(hrs*u[12])} 💵")], "/collect"), kb_back()); return

    if cmd == "/collect":
        u = get_user(uid)
        if not u[11]: return send(peer_id, "❌", kb_back())
        hrs = min((int(time.time())-u[13])//3600, 24)
        if hrs < 1: return send(peer_id, "⏳ Позже", kb_back())
        inc = hrs * u[12]; upd_balance(uid, inc)
        cur.execute("UPDATE users SET biz_collect=? WHERE user_id=?", (int(time.time()), uid)); conn.commit()
        send(peer_id, f"💼 +{fmt(inc)} 💵", kb_back()); return

    # ================= РАЗДАЧА =================
    if cmd == "/раздача":
        if not is_admin(uid): return send(peer_id, "❌")
        if len(args) < 4: return send(peer_id, "📝 /раздача <сумма> <s|m|h|d> <текст>")
        try: a = int(args[1]); unit = args[2].lower()
        except: return send(peer_id, "❌")
        mult = {"s":1,"m":60,"h":3600,"d":86400}.get(unit,60)
        cur.execute("INSERT INTO giveaways(amount,expire,text,creator) VALUES(?,?,?,?)",
                    (a, int(time.time())+mult, " ".join(args[3:]), uid)); conn.commit()
        send(peer_id, f"🎁 Раздача #{cur.lastrowid} на {fmt(a)} 💵", kb_back()); return

    if cmd == "/взять":
        cur.execute("SELECT id,amount FROM giveaways WHERE taken_by IS NULL AND expire>? ORDER BY id DESC LIMIT 1", (int(time.time()),))
        g = cur.fetchone()
        if not g: return send(peer_id, "❌ Нет", kb_back())
        cur.execute("UPDATE giveaways SET taken_by=? WHERE id=?", (uid, g[0])); conn.commit()
        upd_balance(uid, g[1]); send(peer_id, f"🎉 +{fmt(g[1])} 💵", kb_back()); return

    # ================= ИГРЫ =================
    if cmd in ("/казино","🎲 казино"):
        if len(args)<2: return send(peer_id,"📝 /казино <ставка>", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌", kb_games())
        if random.random()<0.45: upd_balance(uid,bet); send(peer_id, f"🎰 +{fmt(bet)} 💵", kb_games())
        else: upd_balance(uid,-bet); send(peer_id, f"🎰 -{fmt(bet)} 💵", kb_games())
        return

    if cmd in ("/монетка","🪙 монетка"):
        if len(args)<2: return send(peer_id,"📝 /монетка <ставка>", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌", kb_games())
        side = args[2].lower() if len(args)>2 and args[2].lower() in ("орёл","решка") else "орёл"
        res = random.choice(["орёл","решка"])
        if res==side: upd_balance(uid,bet); send(peer_id, f"🪙 {res}! +{fmt(bet)}", kb_games())
        else: upd_balance(uid,-bet); send(peer_id, f"🪙 {res}! -{fmt(bet)}", kb_games())
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
        r=[random.choice(icons) for _ in range(3)]; line=" │ ".join(r)
        if r[0]==r[1]==r[2]: upd_balance(uid,bet*5); send(peer_id, f"🎰 ║ {line} ║\n💥 JACKPOT +{fmt(bet*5)}", kb_games())
        elif r[0]==r[1] or r[1]==r[2]: upd_balance(uid,bet); send(peer_id, f"🎰 ║ {line} ║\n✅ +{fmt(bet)}", kb_games())
        else: upd_balance(uid,-bet); send(peer_id, f"🎰 ║ {line} ║\n❌ -{fmt(bet)}", kb_games())
        return

    if cmd in ("/дуэль","⚔️ дуэль"):
        if len(args)<3: return send(peer_id,"📝 /дуэль <id> <ставка>", kb_games())
        try:
            t=int(args[1].replace("@","").split("|")[0].split("]")[0]); bet=int(args[2])
        except: return send(peer_id,"❌", kb_games())
        if t==uid or get_balance(uid)<bet or get_balance(t)<bet: return send(peer_id,"❌", kb_games())
        if random.random()<0.5: upd_balance(uid,bet); upd_balance(t,-bet); send(peer_id, f"⚔️ {name_of(uid)} победил!", kb_games())
        else: upd_balance(uid,-bet); upd_balance(t,bet); send(peer_id, f"⚔️ {name_of(t)} победил!", kb_games())
        return

    game_map = {"/краш":"🚀","/дартс":"🎯","/колесо":"🎡","/рулетка":"🎰","/блэкджек":"🃏",
                "/мины":"💣","/башня":"🏗","/кейс":"🎁","/гонка":"🏎","/рыбалка":"🎣"}
    if cmd in game_map:
        if len(args)<2: return send(peer_id, f"📝 {cmd} <ставка>", kb_games())
        try: bet=int(args[1])
        except: return send(peer_id,"❌", kb_games())
        if get_balance(uid)<bet: return send(peer_id,"❌", kb_games())
        if random.random()<0.5: upd_balance(uid,bet); send(peer_id, f"{game_map[cmd]} +{fmt(bet)} 💵", kb_games())
        else: upd_balance(uid,-bet); send(peer_id, f"{game_map[cmd]} -{fmt(bet)} 💵", kb_games())
        return

    if cmd in ("/клуб","🎰 клуб"):
        send(peer_id, card("🎰 КЛУБ",[("🎲","/казино"),("🪙","/монетка"),("🍒","/слоты"),("⚔️","/дуэль")]), kb_games()); return

    if cmd == "/купитьклуб":
        if get_balance(uid)<1000000: return send(peer_id,"❌ 1 трон = 1M 💵", kb_back())
        upd_balance(uid,-1000000); send(peer_id,"💎 Клуб куплен!", kb_back()); return

    # ================= ИВЕНТ / МАФИЯ =================
    if cmd in ("/ивент","/мафия"):
        if not chat_id: return send(peer_id, "❌ Только в беседе")
        if len(args)>1 and args[1].lower()=="стоп":
            if chat_id in MAFIA: del MAFIA[chat_id]
            return send(peer_id, "🛑 Игра остановлена")
        mafia_new(peer_id, uid, chat_id); return

    if cmd == "/мафия_вступить":
        if chat_id: mafia_join(peer_id, uid, chat_id); return

    if cmd == "/мафия_старт":
        if chat_id: mafia_start(peer_id, uid, chat_id); return

    if cmd == "/мафия_убить":
        if len(args)<2: return send(peer_id, "📝 /мафия_убить <id>")
        try: t = int(args[1])
        except: return
        mafia_kill(peer_id, uid, t); return

    if cmd == "/мафия_голос":
        if len(args)<2: return send(peer_id, "📝 /мафия_голос <id>")
        try: t = int(args[1])
        except: return
        mafia_vote(peer_id, uid, t); return

    if cmd == "/мафия_итог":
        if chat_id: mafia_resolve(peer_id, chat_id); return

    # ================= РОЛИ =================
    if cmd == "/role":
        cur.execute("SELECT name,level FROM roles ORDER BY level DESC")
        rows = cur.fetchall()
        txt = header("СПИСОК РОЛЕЙ")+"\n\n"
        for n,l in rows: txt += f"  🎭 {n} — уровень {l}\n"
        send(peer_id, txt + f"\n{DIV}", kb_back()); return

    if cmd == "/newrole":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        if len(args)<3: return send(peer_id, "📝 /newrole <название> <уровень>")
        name = args[1]
        try: lvl = int(args[2])
        except: return send(peer_id, "❌ Уровень — число")
        cur.execute("INSERT OR REPLACE INTO roles(name,level,created_by,created_at) VALUES(?,?,?,?)",
                    (name, lvl, uid, int(time.time()))); conn.commit()
        send(peer_id, f"✅ Роль «{name}» (уровень {lvl}) создана"); return

    if cmd == "/setrole":
        if not is_owner(uid) and not is_admin(uid): return send(peer_id, "❌")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return send(peer_id, "📝 /setrole <юзер> <роль>")
        role = args[2]
        cur.execute("SELECT name FROM roles WHERE name=?", (role,))
        if not cur.fetchone(): return send(peer_id, "❌ Роль не найдена")
        if chat_id:
            cur.execute("INSERT OR REPLACE INTO user_roles(user_id,chat_id,role) VALUES(?,?,?)", (t, chat_id, role))
        else:
            cur.execute("INSERT OR REPLACE INTO global_roles(user_id,role) VALUES(?,?)", (t, role))
        conn.commit()
        send(peer_id, f"✅ {mention(t)} → {role}"); return

    if cmd == "/grole":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return send(peer_id, "📝 /grole <юзер> <роль>")
        cur.execute("INSERT OR REPLACE INTO global_roles(user_id,role) VALUES(?,?)", (t, args[2])); conn.commit()
        send(peer_id, f"🌐 {mention(t)} глобально → {args[2]}"); return

    if cmd == "/staff":
        if not chat_id: return send(peer_id, "❌ Только в беседе")
        cur.execute("SELECT user_id, role FROM user_roles WHERE chat_id=?", (chat_id,))
        rows = cur.fetchall()
        if not rows: return send(peer_id, "📋 Состав пуст")
        txt = header("СОСТАВ ЧАТА")+"\n\n"
        for u,r in rows: txt += f"  🎭 {mention(u)} — {r}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd == "/gstaff":
        cur.execute("""SELECT u.user_id, COALESCE(gr.role, u.role) FROM users u
                       LEFT JOIN global_roles gr ON gr.user_id=u.user_id
                       WHERE u.role IN ('admin','moder','owner') OR gr.role IS NOT NULL""")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "📋 Глобальный состав пуст")
        txt = header("ГЛОБАЛЬНЫЙ СОСТАВ")+"\n\n"
        for u,r in rows: txt += f"  🌐 {mention(u)} — {r}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    # ================= НИКИ =================
    if cmd == "/nick":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if t and (is_admin(uid) or is_owner(uid)) and t != uid:
            if len(args)<3: return send(peer_id, "📝 /nick <юзер> <ник>")
            nick = " ".join(args[2:])
        else:
            t = uid; nick = " ".join(args[1:])
            if not nick: return send(peer_id, "📝 /nick <ник>")
        cur.execute("INSERT OR REPLACE INTO nicks(user_id,nick) VALUES(?,?)", (t, nick)); conn.commit()
        send(peer_id, f"✅ Ник {mention(t)}: {nick}"); return

    if cmd == "/rnick":
        if not is_admin(uid) and not is_owner(uid): return send(peer_id, "❌")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id, "📝 /rnick <юзер>")
        cur.execute("DELETE FROM nicks WHERE user_id=?", (t,)); conn.commit()
        send(peer_id, f"✅ Ник снят с id{t}"); return

    # ================= СТАТА =================
    if cmd == "/стата":
        t = extract_uid(args[1] if len(args)>1 else None, event_msg) or uid
        u = get_user(t)
        cur.execute("SELECT COALESCE(gr.role, u.role) FROM users u LEFT JOIN global_roles gr ON gr.user_id=u.user_id WHERE u.user_id=?", (t,))
        rr = cur.fetchone(); role = rr[0] if rr else 'user'
        send(peer_id, card("СТАТИСТИКА", [
            ("👤", name_of(t)), ("🆔", f"id{t}"),
            ("💰 Баланс", f"{fmt(u[1])} 💵"),
            ("🎖️ Звание", u[10]),
            ("🌍 Страна", u[5] or "нет"),
            ("⚠️ Варны", f"{u[2]}/3"),
            ("💼 Бизнес", "да" if u[11] else "нет"),
            ("🎭 Роль", role),
            ("📰 Подписка", "✅" if u[14] else "❌"),
        ]), kb_back()); return

    # ================= CMD =================
    if cmd == "/cmd":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        if len(args)<2: return send(peer_id, "📝 /cmd <команда>")
        c = args[1]
        cur.execute("INSERT OR IGNORE INTO cmd_perms(user_id,command) VALUES(?,?)", (uid, c)); conn.commit()
        send(peer_id, f"✅ Команда {c} разрешена только тебе"); return

    # ================= ОБЪЯВЛЕНИЕ =================
    if cmd == "/объявление":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        if len(args)<2: return send(peer_id, "📝 /объявление <текст>")
        text_msg = " ".join(args[1:])
        cur.execute("SELECT peer_id FROM builds")
        rows = cur.fetchall()
        sent = 0
        for (p,) in rows:
            try:
                vk.messages.send(peer_id=p, message=f"{header('ОБЪЯВЛЕНИЕ')}\n\n{text_msg}\n\n{DIV}", random_id=get_random_id())
                sent += 1
            except: pass
        send(peer_id, f"📢 Отправлено в {sent} бесед"); return

    # ================= BUILD / BUILDS =================
    if cmd == "/builds":
        if not is_owner(uid): return send(peer_id, "❌")
        if not chat_id: return send(peer_id, "❌ Только в беседе")
        title = " ".join(args[1:]) if len(args)>1 else f"Беседа {chat_id}"
        cur.execute("INSERT OR REPLACE INTO builds(chat_id,peer_id,title,linked_by,linked_at) VALUES(?,?,?,?,?)",
                    (chat_id, peer_id, title, uid, int(time.time()))); conn.commit()
        send(peer_id, f"✅ Беседа привязана: {title}"); return

    if cmd == "/build":
        if not is_owner(uid): return send(peer_id, "❌")
        cur.execute("SELECT chat_id,title FROM builds")
        rows = cur.fetchall()
        if not rows: return send(peer_id, "📋 Нет привязанных бесед")
        txt = header("ПРИВЯЗАННЫЕ БЕСЕДЫ")+"\n\n"
        for c,t in rows: txt += f"  🏛 {t} (chat_id: {c})\n"
        send(peer_id, txt + f"\n{DIV}"); return

    # ================= СТРАНЫ =================
    if cmd in ("/страны","/страна","🌍 страна"):
        cur.execute("SELECT name,treasury,cities,army FROM countries WHERE alive=1 ORDER BY cities DESC")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"🌍 Стран нет. /гражданство <название>", kb_country())
        txt = header("СТРАНЫ МИРА")+"\n\n"
        for i,(n,t,c,a) in enumerate(rows[:15],1):
            txt += f"  {i}. 🏳️ {n}\n     💰 {fmt(t)} | 🏙 {c} | 🎖️ {fmt(a)}\n"
        send(peer_id, txt + f"\n{DIV}", kb_country()); return

    if cmd == "/гражданство":
        if len(args)<2: return send(peer_id,"📝 /гражданство <страна>", kb_country())
        country=" ".join(args[1:])
        cur.execute("SELECT name FROM countries WHERE name=?",(country,))
        if not cur.fetchone():
            cur.execute("INSERT INTO countries(name,owner,president) VALUES(?,?,?)",(country,uid,uid))
            cur.execute("INSERT INTO stockpile(country) VALUES(?)",(country,))
            cur.execute("INSERT INTO country_army(country,troops) VALUES(?,?)",(country,100000))
            cur.execute("INSERT INTO members(user_id,country,position) VALUES(?,?,?)",(uid,country,'Президент'))
            conn.commit()
            send(peer_id, f"🌍 «{country}» создана! Вы президент", kb_country())
        else:
            cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)",(uid,country,'Гражданин'))
            conn.commit()
        cur.execute("UPDATE users SET citizenship=?,country=? WHERE user_id=?",(country,country,uid)); conn.commit()
        send(peer_id, f"✅ Гражданство: {country}", kb_country()); return

    if cmd in ("/паспорт","📘 паспорт"):
        u=get_user(uid); pos = get_position(uid) or "—"
        send(peer_id, card("📘 ПАСПОРТ", [("👤",name_of(uid)),("🆔",f"id{uid}"),
            ("🌍",u[5] or "нет"),("💼",pos),("🎖️",u[10]),("💰",f"{fmt(u[1])} 💵")]), kb_country()); return

    if cmd in ("/казна","🏛 казна"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        co = get_country(c); st = get_stock(c)
        send(peer_id, card("🏛 КАЗНА", [("🏳️",c),("💰",f"{fmt(co[3])} 💵"),
            ("🍞",f"{fmt(st[1])}"),("🔫",f"{fmt(st[2])}"),("⚙️",f"{fmt(st[3])}"),
            ("⛽",f"{fmt(st[4])}"),("🏙",f"{co[5]}"),("📊",f"{co[6]}%")]), kb_country()); return

    if cmd in ("/армия","🎖️ армия"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        ca = get_carmy(c)
        send(peer_id, card("🎖️ АРМИЯ", [("🏳️",c),("🪖",f"{fmt(ca[1])}"),("🎯 ПВО",f"{fmt(ca[2])}"),
            ("🚀",f"{fmt(ca[3])}"),("🛸",f"{fmt(ca[4])}")]), kb_country()); return

    if cmd in ("/граждане","/города","/правительство","/должности","/очки"):
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌ Нет страны", kb_country())
        if cmd == "/граждане":
            cur.execute("SELECT user_id,position FROM members WHERE country=?",(c,))
            rows = cur.fetchall()
            txt = header(f"ГРАЖДАНЕ {c}")+f"\n\n  Всего: {len(rows)}\n\n"
            for u,p in rows[:20]: txt += f"  👤 {name_of(u)} — {p}\n"
            send(peer_id, txt + f"\n{DIV}", kb_country())
        elif cmd == "/правительство":
            cur.execute("SELECT user_id,position FROM members WHERE country=? AND position!='Гражданин'",(c,))
            rows = cur.fetchall()
            txt = header(f"ПРАВИТЕЛЬСТВО {c}")+"\n\n"
            for u,p in rows: txt += f"  👑 {name_of(u)} — {p}\n"
            send(peer_id, txt + f"\n{DIV}", kb_country())
        else:
            send(peer_id, f"📊 {cmd}: информация доступна", kb_country())
        return

    if cmd == "/выборы":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌", kb_country())
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1",(c,)); e = cur.fetchone()
        if not e:
            if is_president(uid):
                cur.execute("INSERT INTO elections(country,started) VALUES(?,?)",(c,int(time.time())))
                conn.commit(); return send(peer_id, f"🗳️ Выборы в {c} начались!", kb_country())
            return send(peer_id, f"🗳️ Выборов нет", kb_country())
        cur.execute("SELECT user_id,votes FROM candidates WHERE election_id=? ORDER BY votes DESC",(e[0],))
        rows = cur.fetchall()
        txt = header(f"ВЫБОРЫ {c}")+"\n\n"
        for u,v in rows: txt += f"  🗳️ {name_of(u)} — {v} голосов\n"
        send(peer_id, txt + f"\n{DIV}", kb_country()); return

    if cmd == "/выдвинуться":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌")
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1",(c,)); e = cur.fetchone()
        if not e:
            cur.execute("INSERT INTO elections(country,started) VALUES(?,?)",(c,int(time.time()))); conn.commit()
            e = (cur.lastrowid,)
        cur.execute("INSERT INTO candidates(election_id,user_id) VALUES(?,?)",(e[0],uid)); conn.commit()
        send(peer_id, f"🗳️ Вы выдвинулись в {c}!", kb_country()); return

    if cmd == "/голос":
        if len(args)<2: return send(peer_id,"📝 /голос <id>")
        try: cand = int(args[1])
        except: return
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌")
        cur.execute("SELECT id FROM elections WHERE country=? AND active=1",(c,)); e = cur.fetchone()
        if not e: return send(peer_id,"❌")
        cur.execute("SELECT id FROM votes WHERE election_id=? AND voter=?",(e[0],uid))
        if cur.fetchone(): return send(peer_id,"❌ Уже голосовали")
        cur.execute("INSERT INTO votes(election_id,voter,candidate) VALUES(?,?,?)",(e[0],uid,cand))
        cur.execute("UPDATE candidates SET votes=votes+1 WHERE election_id=? AND user_id=?",(e[0],cand))
        conn.commit(); send(peer_id, f"🗳️ Голос за {name_of(cand)}!", kb_country()); return

    if cmd == "/компания":
        send(peer_id, "📢 Кампания активна!", kb_country()); return

    if cmd == "/регистрация":
        if len(args)>=3 and args[1].lower()=="ооо":
            name = " ".join(args[2:]); c = get_country_of(uid)
            if not c: return send(peer_id,"❌ Нужна страна")
            cur.execute("INSERT INTO companies(owner,country,name) VALUES(?,?,?)",(uid,c,name)); conn.commit()
            send(peer_id, f"🏢 ООО «{name}» создано!", kb_country())
        else: send(peer_id, "📝 /регистрация ООО <название>", kb_country())
        return

    # ================= ПРАВИТЕЛЬСТВО =================
    if cmd == "/налоги":
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        if len(args)<2: return send(peer_id,"📝 /налоги <0-50>")
        try: tax = max(0, min(50, int(args[1])))
        except: return
        cur.execute("UPDATE countries SET taxes=? WHERE name=?",(tax,c)); conn.commit()
        send(peer_id, f"📊 Налог: {tax}%"); return

    if cmd in ("/улучшить_страну","/улучшитьстрану"):
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        co = get_country(c)
        if co[3] < 100000: return send(peer_id,"❌ 100 000 💵")
        cur.execute("UPDATE countries SET treasury=treasury-100000, cities=cities+1 WHERE name=?",(c,))
        conn.commit(); send(peer_id, f"🏙 Город построен! Всего: {co[5]+1}"); return

    if cmd == "/постройки":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌")
        co = get_country(c); b = json.loads(co[9] or "{}")
        txt = header(f"ПОСТРОЙКИ {c}")+"\n\n"
        for k,v in b.items(): txt += f"  🏗 {k} x{v}\n"
        txt += "\n📝 /построить <название>"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd == "/построить":
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        if len(args)<2:
            txt = header("ДОСТУПНОЕ")+"\n\n"
            for k,v in BUILDINGS.items(): txt += f"  🏗 {k} — {fmt(v)} 💵\n"
            return send(peer_id, txt + f"\n{DIV}")
        bname = args[1].lower()
        if bname not in BUILDINGS: return send(peer_id,"❌")
        co = get_country(c); cost = BUILDINGS[bname]
        if co[3] < cost: return send(peer_id,f"❌ {fmt(cost)} 💵")
        b = json.loads(co[9] or "{}"); b[bname] = b.get(bname,0)+1
        cur.execute("UPDATE countries SET treasury=treasury-?, buildings=? WHERE name=?",
                    (cost, json.dumps(b,ensure_ascii=False), c)); conn.commit()
        send(peer_id, f"🏗 {bname} x{b[bname]}"); return

    if cmd == "/госпроект":
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        if len(args)<2: return send(peer_id,"📝 /госпроект <название>")
        name = " ".join(args[1:]); co = get_country(c)
        pr = json.loads(co[10] or "{}"); pr[name] = pr.get(name,0)+1
        cur.execute("UPDATE countries SET projects=? WHERE name=?", (json.dumps(pr,ensure_ascii=False), c))
        conn.commit(); send(peer_id, f"🏗 Проект «{name}» запущен!"); return

    if cmd == "/вооружение":
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        if len(args)<3: return send(peer_id,"📝 /вооружение <тип> <кол>\nТипы: ракета, бпла, пво, танк")
        try: col = int(args[2])
        except: return
        t = args[1].lower(); cost_map = {"ракета":50000,"бпла":30000,"пво":100000,"танк":80000}
        if t not in cost_map: return send(peer_id,"❌")
        co = get_country(c); total = col * cost_map[t]
        if co[3] < total: return send(peer_id,f"❌ {fmt(total)} 💵")
        cur.execute("UPDATE countries SET treasury=treasury-? WHERE name=?",(total,c))
        if t=="ракета": upd_carmy(c,"rockets",col)
        elif t=="бпла": upd_carmy(c,"drones",col)
        elif t=="пво": upd_carmy(c,"pvo",col)
        elif t=="танк": upd_carmy(c,"troops",col*1000)
        conn.commit(); send(peer_id, f"⚙️ Закуплено: {col} {t}"); return

    # ================= АРМИЯ =================
    if cmd == "/мобилизация":
        c = get_country_of(uid)
        if not c or not is_government(uid): return send(peer_id,"❌")
        upd_carmy(c,"troops",50000); send(peer_id, f"🪖 +50 000 войск {c}"); return

    if cmd == "/демобилизация":
        c = get_country_of(uid)
        if not c or not is_government(uid): return send(peer_id,"❌")
        upd_carmy(c,"troops",-30000); send(peer_id, "🪖 -30 000 войск"); return

    if cmd in ("/пво","/установить пво","/установить_пво"):
        c = get_country_of(uid)
        if not c or not is_government(uid): return send(peer_id,"❌")
        co = get_country(c)
        if co[3] < 150000: return send(peer_id,"❌ 150 000 💵")
        cur.execute("UPDATE countries SET treasury=treasury-?, pvo=pvo+1 WHERE name=?",(150000,c))
        upd_carmy(c,"pvo",1); conn.commit()
        send(peer_id, "🎯 ПВО установлено!"); return

    if cmd == "/запуск":
        if len(args)<4: return send(peer_id,"📝 /запуск ракета|бпла <кол> <страна>")
        c = get_country_of(uid)
        if not c or not is_government(uid): return send(peer_id,"❌")
        t = args[1].lower()
        try: col=int(args[2])
        except: return
        target = " ".join(args[3:])
        if not get_country(target): return send(peer_id,"❌ Страна не найдена")
        ca = get_carmy(c)
        if t=="ракета" and ca[3] < col: return send(peer_id,"❌ Мало ракет")
        if t=="бпла" and ca[4] < col: return send(peer_id,"❌ Мало бпла")
        if t=="ракета": upd_carmy(c,"rockets",-col)
        else: upd_carmy(c,"drones",-col)
        tca = get_carmy(target); pvo_def = tca[2]*10
        dmg = max(0, col - pvo_def) * 5000
        upd_carmy(target,"troops",-dmg)
        send(peer_id, f"🚀 Запуск {col} {t} по {target}\n💥 Урон: {fmt(dmg)}"); return

    if cmd in ("/дрон","/перехват"): send(peer_id, f"🛸 {cmd[1:].upper()}: ок"); return
    if cmd in ("/сирена","/воздухтревога"): send(peer_id, "🚨 ВОЗДУШНАЯ ТРЕВОГА! 🚨"); return

    if cmd == "/задание":
        send(peer_id, card("📋 ЗАДАНИЯ", [("1️⃣","5 новобранцев → 50 000"),
            ("2️⃣","3 дуэли → 30 000"),("3️⃣","Захват → 500 000")], "/выполнитьзадание")); return

    if cmd == "/выполнитьзадание":
        r = random.randint(10000, 100000); upd_balance(uid, r)
        send(peer_id, f"✅ +{fmt(r)} 💵"); return

    if cmd == "/upgrade_army":
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        co = get_country(c)
        if co[3] < 100000: return send(peer_id,"❌")
        cur.execute("UPDATE countries SET treasury=treasury-100000, army=army+50000 WHERE name=?",(c,))
        conn.commit(); send(peer_id, "🎖️ +50 000"); return

    if cmd in ("/сделать","/запуск_ракеты"): send(peer_id, f"🪖 {cmd[1:].upper()}: ок"); return

    if cmd in ("/звание","🎖️ звание"):
        send(peer_id, card("🎖️ ЗВАНИЕ", [("👤",name_of(uid)),("🎖️",get_user(uid)[10])])); return

    if cmd == "/повысить":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id,"📝 /повысить <юзер>")
        ranks=["Новобранец","Рядовой","Сержант","Лейтенант","Капитан","Майор","Полковник","Генерал"]
        cur.execute("SELECT rank FROM users WHERE user_id=?",(t,)); r=cur.fetchone()
        idx = ranks.index(r[0]) if r and r[0] in ranks else 0
        new=ranks[min(idx+1,len(ranks)-1)]
        cur.execute("UPDATE users SET rank=? WHERE user_id=?",(new,t)); conn.commit()
        send(peer_id, f"🎖️ {mention(t)} → {new}"); return

    # ================= ГРАНИЦЫ =================
    if cmd == "/граница":
        if len(args)<2: return send(peer_id,"📝 /граница открыть|закрыть [страна]")
        action = args[1].lower()
        c = " ".join(args[2:]) if len(args)>2 else get_country_of(uid)
        if not c or not get_country(c): return send(peer_id,"❌")
        if not is_president(uid) and not is_owner(uid): return send(peer_id,"❌")
        val = 1 if action=="открыть" else 0
        cur.execute("UPDATE countries SET border_open=? WHERE name=?",(val,c)); conn.commit()
        send(peer_id, f"🌉 Граница {c} {action}та"); return

    if cmd == "/виза":
        if len(args)<3: return send(peer_id,"📝 /виза выдать|забрать <юзер>")
        action = args[1].lower()
        t = extract_uid(args[2], event_msg)
        if not t: return send(peer_id,"❌")
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        if action == "выдать":
            cur.execute("INSERT OR REPLACE INTO members(user_id,country,position) VALUES(?,?,?)",(t,c,'Гражданин'))
            conn.commit(); send(peer_id, f"📗 Виза выдана {mention(t)}")
        else:
            cur.execute("DELETE FROM members WHERE user_id=?",(t,)); conn.commit()
            send(peer_id, f"📕 Виза забрана у {mention(t)}")
        return

    if cmd == "/транспорт":
        if len(args)<3: return send(peer_id,"📝 /транспорт купить <тип>")
        if args[1].lower()=="купить":
            t = args[2].lower()
            if t not in TRANSPORT_PRICE: return send(peer_id,"❌ Типы: "+", ".join(TRANSPORT_PRICE))
            price = TRANSPORT_PRICE[t]
            if get_balance(uid) < price: return send(peer_id,f"❌ {fmt(price)} 💵")
            upd_balance(uid, -price)
            cur.execute("SELECT id FROM transports WHERE owner=? AND type=?",(uid,t)); r = cur.fetchone()
            if r: cur.execute("UPDATE transports SET count=count+1 WHERE id=?",(r[0],))
            else: cur.execute("INSERT INTO transports(owner,type,count) VALUES(?,?,1)",(uid,t))
            conn.commit(); send(peer_id, f"🚚 Куплен {t} за {fmt(price)} 💵")
        return

    if cmd == "/склад":
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌")
        st = get_stock(c)
        send(peer_id, card(f"📦 СКЛАД {c}", [("🍞",f"{fmt(st[1])}"),("🔫",f"{fmt(st[2])}"),
            ("⚙️",f"{fmt(st[3])}"),("⛽",f"{fmt(st[4])}")])); return

    if cmd == "/перевозка":
        if len(args)<5: return send(peer_id,"📝 /перевозка <страна> <товар> <кол> <транспорт>")
        target = args[1]; product = args[2].lower()
        try: col = int(args[3])
        except: return
        if product not in PRODUCTS: return send(peer_id,"❌ Товары: "+", ".join(PRODUCTS))
        if not get_country(target): return send(peer_id,"❌")
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌")
        tax = col * 10 // 100
        field = {"еда":"food","оружие":"weapons","ресурсы":"resources","топливо":"fuel","деньги":"money"}[product]
        upd_stock(c, field, col); upd_stock(target, field, -tax)
        send(peer_id, f"🚚 {col} {product}: {c} → {target}\n📊 Пошлина: {tax}"); return

    if cmd == "/контрабанда":
        if len(args)<4: return send(peer_id,"📝 /контрабанда <страна> <товар> <кол>")
        target = args[1]; product = args[2].lower()
        try: col = int(args[3])
        except: return
        if product not in PRODUCTS: return send(peer_id,"❌")
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌")
        if random.random()<0.6:
            field = {"еда":"food","оружие":"weapons","ресурсы":"resources","топливо":"fuel","деньги":"money"}[product]
            upd_stock(c, field, col)
            send(peer_id, f"🕵️ Контрабанда удалась: {col} {product}")
        else:
            fine = col * 3
            cur.execute("UPDATE countries SET treasury=MAX(0,treasury-?) WHERE name=?",(fine,c)); conn.commit()
            send(peer_id, f"🚔 Поймали! Штраф ×3 = {fmt(fine)} 💵")
        return

    # ================= ВОЙНЫ =================
    if cmd in ("/войны","⚔️ войны"):
        cur.execute("SELECT id,attacker,defender FROM wars WHERE active=1")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"⚔️ Войн нет. /война <страна>")
        txt = header("АКТИВНЫЕ ВОЙНЫ")+"\n\n"
        for i,a,d in rows: txt += f"  ⚔️ #{i} {a} vs {d}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd == "/война":
        if len(args)<2: return send(peer_id,"📝 /война <страна>")
        target = " ".join(args[1:])
        c = get_country_of(uid)
        if not c or not is_president(uid): return send(peer_id,"❌")
        if not get_country(target): return send(peer_id,"❌ Страна не найдена")
        cur.execute("INSERT INTO wars(attacker,defender,started) VALUES(?,?,?)",(c,target,int(time.time())))
        conn.commit()
        send(peer_id, card("⚔️ ВОЙНА", [("🛡",c),("🎯",target)])); return

    if cmd == "/захват":
        if len(args)<2: return send(peer_id,"📝 /захват <страна>")
        target = " ".join(args[1:])
        c = get_country_of(uid)
        if not c: return send(peer_id,"❌")
        if not is_president(uid) and not is_owner(uid): return send(peer_id,"❌")
        tc = get_country(target)
        if not tc: return send(peer_id,"❌")
        my = get_carmy(c); en = get_carmy(target)
        my_power = my[1] + my[3]*5000 + my[4]*3000 - en[2]*1000
        en_power = en[1] + en[3]*5000 + en[4]*3000
        if my_power > en_power * 1.2:
            cur.execute("UPDATE countries SET alive=0, owner=? WHERE name=?",(uid,target))
            cur.execute("UPDATE countries SET cities=cities+? WHERE name=?",(tc[5],c))
            conn.commit()
            send(peer_id, f"🏆 ЗАХВАТ! {target} пала! +{tc[5]} городов")
        else:
            lost = my[1]//4; upd_carmy(c,"troops",-lost)
            send(peer_id, f"💀 Провал! -{fmt(lost)} войск"); return

    if cmd in ("/мир","/завершить_конфликт"):
        c = get_country_of(uid)
        if c:
            cur.execute("UPDATE wars SET active=0 WHERE attacker=? OR defender=?",(c,c)); conn.commit()
        send(peer_id,"🕊️ Мир подписан"); return

    if cmd == "/коалиции":
        cur.execute("SELECT name,leader FROM coalitions")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"🤝 Коалиций нет. /коалиция <название>")
        txt = header("КОАЛИЦИИ")+"\n\n"
        for n,l in rows: txt += f"  🤝 {n} — {name_of(l)}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd == "/коалиция":
        if len(args)<2: return send(peer_id,"📝 /коалиция <название>")
        name = " ".join(args[1:])
        cur.execute("INSERT INTO coalitions(name,leader,members) VALUES(?,?,?)",(name,uid,str(uid)))
        conn.commit(); send(peer_id, f"🤝 «{name}» создана!"); return

    if cmd == "/коалпомощь": send(peer_id,"💪 Помощь оказана"); return

    # ================= ГОС.МЕНЮ =================
    if cmd in ("/госскоманды","🗺 гос.команды"):
        send(peer_id, f"{header('КОМАНДЫ СТРАНЫ')}\n\n"
            f"📖 /страны /гражданство /паспорт /страна\n"
            f"  /граждане /города /казна /правительство\n"
            f"  /должности /армия /выборы /выдвинуться\n"
            f"  /голос /очки /компания /регистрация ООО /донат\n\n"
            f"⚖️ /налоги /улучшить_страну /постройки\n"
            f"  /построить /госпроект /вооружение\n\n"
            f"⚔️ /мобилизация /демобилизация /сделать\n"
            f"  /установить пво /пво /запуск ракета|бпла\n"
            f"  /задание /выполнитьзадание /upgrade_army\n"
            f"  /звание /повысить /дрон /перехват /сирена\n\n"
            f"🌉 /граница /виза /транспорт /склад\n"
            f"  /перевозка /контрабанда\n\n"
            f"  📦 Товары: еда, оружие, ресурсы, топливо, деньги\n"
            f"  🚚 Транспорт: грузовик, поезд, корабль, самолет\n"
            f"  💰 Пошлина: 10% | 🚔 Штраф: ×3\n\n"
            f"⚔️ ВОЙНА: /войны /война /захват /мир /коалиции\n\n{DIV}", kb_country()); return

    if cmd == "/очки": send(peer_id,"📊 Очки за активность", kb_country()); return

    # ================= ТАКСИ / RULES / Q =================
    if cmd == "/такси":
        send(peer_id, card("🚕 ТАКСИ", [("🏛","часть"),("🎰","клуб"),("🚌","автовокзал"),("✈️","аэропорт")])); return

    if cmd == "/задания" or cmd == "📋 задания":
        send(peer_id, card("📋 ЗАДАНИЯ", [("1️⃣","5 новобранцев → 50 000"),
            ("2️⃣","3 дуэли → 30 000"),("3️⃣","Захват → 500 000")])); return

    if cmd == "/rules" or cmd == "📜 устав":
        send(peer_id, card("📜 УСТАВ", [("1️⃣","Субординация"),("2️⃣","Без мата"),
            ("3️⃣","Без спама"),("4️⃣","Приказы"),("5️⃣","3 варна → исключение")])); return

    if cmd == "/q": send(peer_id,"🚪 Вы покинули расположение"); return

    # ================= ПРОМО =================
    if cmd == "/promo":
        if len(args)<2: return send(peer_id,"📝 /promo <код>")
        code = args[1].upper()
        cur.execute("SELECT amount,uses,max_uses FROM promos WHERE code=?",(code,)); p=cur.fetchone()
        if not p: return send(peer_id,"❌ Не найден")
        if p[1]>=p[2]: return send(peer_id,"❌ Исчерпан")
        cur.execute("UPDATE promos SET uses=uses+1 WHERE code=?",(code,)); conn.commit()
        upd_balance(uid,p[0]); send(peer_id,f"🎟️ +{fmt(p[0])} 💵"); return

    if cmd == "/promolist":
        cur.execute("SELECT code,amount,uses,max_uses FROM promos")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"Нет промо")
        txt = header("ПРОМОКОДЫ")+"\n\n"
        for c,a,u,m in rows: txt += f"  🎟️ {c} — {fmt(a)} ({u}/{m})\n"
        send(peer_id, txt + f"\n{DIV}"); return

    # ================= МОДЕРАЦИЯ =================
    if cmd == "/warn":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id,"📝 /warn <юзер> (или ответом)")
        get_user(t); cur.execute("UPDATE users SET warns=warns+1 WHERE user_id=?",(t,)); conn.commit()
        cur.execute("SELECT warns FROM users WHERE user_id=?",(t,)); w=cur.fetchone()[0]
        if w>=3:
            cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)",(t,"3 варна")); conn.commit()
            if chat_id: kick_user(chat_id, t)
            send(peer_id,f"🚫 {mention(t)} автобан (3/3)")
        else: send(peer_id,f"⚠️ Варн {w}/3 для {mention(t)}")
        return

    if cmd == "/unwarn":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("UPDATE users SET warns=MAX(0,warns-1) WHERE user_id=?",(t,)); conn.commit()
        send(peer_id,f"✅ Варн снят с {mention(t)}"); return

    if cmd == "/mute":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id,"📝 /mute <юзер> <мин>")
        try: m = int(args[2]) if len(args)>2 else 60
        except: m = 60
        if is_owner(t) or is_admin(t): return send(peer_id,"❌")
        get_user(t); cur.execute("UPDATE users SET mute_until=? WHERE user_id=?",(int(time.time())+m*60,t)); conn.commit()
        send(peer_id,f"🔇 {mention(t)} замучен на {m} мин"); return

    if cmd == "/unmute":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("UPDATE users SET mute_until=0 WHERE user_id=?",(t,)); conn.commit()
        send(peer_id,f"🔊 {mention(t)} размучен"); return

    if cmd == "/kick":
        if not is_admin(uid): return
        if not chat_id: return send(peer_id,"❌ Только в беседе")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id,"📝 /kick <юзер> (или ответом)")
        if is_owner(t) or is_admin(t): return send(peer_id,"❌")
        ok = kick_user(chat_id, t)
        send(peer_id, f"👢 {mention(t)} исключён" if ok else "❌ Не удалось"); return

    if cmd == "/ban":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return send(peer_id,"📝 /ban <юзер> [причина]")
        if is_owner(t) or is_admin(t): return send(peer_id,"❌")
        reason = " ".join(args[2:]) if len(args)>2 else "не указана"
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)",(t,reason)); conn.commit()
        if chat_id: kick_user(chat_id, t)
        send(peer_id,f"🚫 {mention(t)} забанен: {reason}"); return

    if cmd == "/unban":
        if not is_admin(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("DELETE FROM bans WHERE user_id=?",(t,)); conn.commit()
        send(peer_id,f"✅ {mention(t)} разбанен"); return

    if cmd == "/gban":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("INSERT OR REPLACE INTO bans(user_id,reason) VALUES(?,?)",(t,"GBAN")); conn.commit()
        if chat_id: kick_user(chat_id, t)
        send(peer_id,f"🚫 {mention(t)} глобально забанен"); return

    if cmd == "/banlist":
        cur.execute("SELECT user_id,reason FROM bans")
        rows=cur.fetchall()
        if not rows: return send(peer_id,"📋 Банлист пуст")
        txt = header("БАНЛИСТ")+"\n\n"
        for u,r in rows: txt += f"  🚫 id{u} — {r}\n"
        send(peer_id, txt + f"\n{DIV}"); return

    if cmd in ("/clear","/tickets","/adt"):
        if not is_admin(uid): return
        send(peer_id, f"🛡️ {cmd[1:].upper()}: ок"); return

    # ================= ОБНУЛИТЬ / ВАЙП =================
    if cmd == "/обнулить":
        if not is_owner(uid) and not is_admin(uid): return send(peer_id, "❌")
        t = extract_uid(args[1] if len(args) > 1 else None, event_msg)
        if not t: return send(peer_id, "📝 /обнулить (ответом) или /обнулить <юзер>")
        get_user(t)
        cur.execute("""UPDATE users SET balance=0, army=0, war=0, biz=0,
                       biz_income=0, biz_collect=0, warns=0, mute_until=0 WHERE user_id=?""", (t,))
        cur.execute("DELETE FROM user_roles WHERE user_id=?", (t,))
        cur.execute("DELETE FROM global_roles WHERE user_id=?", (t,))
        cur.execute("DELETE FROM companies WHERE owner=?", (t,))
        cur.execute("DELETE FROM transports WHERE owner=?", (t,))
        conn.commit()
        send(peer_id, card("♻️ ОБНУЛЕНИЕ", [("👤",name_of(t)),("💰","0 💵"),
            ("🎖️","0"),("💼","сброшен"),("⚠️","0"),("🎭","удалены")])); return

    if cmd == "/вайп":
        if not is_owner(uid): return send(peer_id, "❌ Только главный владелец")
        t = extract_uid(args[1] if len(args) > 1 else None, event_msg)
        if not t: return send(peer_id, "📝 /вайп (ответом) или /вайп <юзер>")
        if t == MAIN_OWNER: return send(peer_id, "❌ Нельзя вайпнуть владельца")
        get_user(t); old_balance = get_balance(t)
        cur.execute("""UPDATE users SET balance=0, warns=0, role='user', country=NULL,
                       citizenship=NULL, army=0, war=0, mute_until=0, last_bonus=0,
                       rank='Новобранец', biz=0, biz_income=0, biz_collect=0, subscription=0
                       WHERE user_id=?""", (t,))
        cur.execute("DELETE FROM user_roles WHERE user_id=?", (t,))
        cur.execute("DELETE FROM global_roles WHERE user_id=?", (t,))
        cur.execute("DELETE FROM companies WHERE owner=?", (t,))
        cur.execute("DELETE FROM transports WHERE owner=?", (t,))
        cur.execute("DELETE FROM members WHERE user_id=?", (t,))
        cur.execute("DELETE FROM nicks WHERE user_id=?", (t,))
        cur.execute("DELETE FROM cmd_perms WHERE user_id=?", (t,))
        cur.execute("DELETE FROM candidates WHERE user_id=?", (t,))
        cur.execute("DELETE FROM votes WHERE voter=?", (t,))
        conn.commit()
        send(peer_id, card("💀 ВАЙП", [("👤",name_of(t)),("💰 Было",f"{fmt(old_balance)} 💵"),
            ("💰 Стало","0 💵"),("🌍","удалена"),("💼","удалён"),("🎖️","0"),
            ("🎭","удалены"),("📝","удалён")])); return

    # ================= ВЛАДЕЛЕЦ =================
    if cmd == "/removestaff":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t: return
        cur.execute("UPDATE users SET role='user' WHERE user_id=?",(t,))
        cur.execute("DELETE FROM global_roles WHERE user_id=?",(t,))
        conn.commit(); send(peer_id,f"✅ {mention(t)} снят"); return

    if cmd in ("/delrole","/setlog","/build_admin"):
        if not is_owner(uid): return
        send(peer_id, f"👑 {cmd[1:].upper()}: ок"); return

    if cmd == "/выдать":
        if not is_owner(uid): return send(peer_id, "❌ Только владелец")
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return send(peer_id, "📝 /выдать <юзер> <сумма> (или ответом)")
        try: a = int(args[2])
        except: return send(peer_id, "❌ Сумма — число")
        upd_balance(t, a); send(peer_id, f"✅ +{fmt(a)} 💵 → {mention(t)}"); return

    if cmd == "/вернуть":
        if not is_owner(uid): return
        t = extract_uid(args[1] if len(args)>1 else None, event_msg)
        if not t or len(args)<3: return send(peer_id, "📝 /вернуть <юзер> <сумма>")
        try: a = int(args[2])
        except: return
        upd_balance(t,-a); send(peer_id,f"✅ -{fmt(a)} 💵 у {mention(t)}"); return

    if text.startswith("/"):
        send(peer_id, f"❓ {cmd} не найдена. /help")

# ============ АВТОКИК ============
def handle_chat_invite(peer_id, member_id):
    if is_banned(member_id):
        ch = peer_to_chat(peer_id)
        if ch: kick_user(ch, member_id)

# ============ ЗАПУСК ============
def main():
    print("⚔️ Бот запущен...")
    try:
        get_user(MAIN_OWNER)
        cur.execute("UPDATE users SET role='owner', balance=MAX(balance,999999999) WHERE user_id=?", (MAIN_OWNER,))
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
                    except Exception as e:
                        print(f"MEv error: {e}")
                    continue

                if event.type != VkBotEventType.MESSAGE_NEW:
                    continue

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
                try:
                    handle_message(peer_id, uid, text, message_id, msg)
                except Exception as e:
                    print(f"Handler: {e}")
        except Exception as e:
            print(f"LongPoll: {e}"); time.sleep(3)

if __name__ == "__main__":
    main()
