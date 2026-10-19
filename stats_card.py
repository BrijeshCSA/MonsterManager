# -*- coding: utf-8 -*-
import os, re, io, requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1080

# Ищем локальные шрифты (бот их скачает при старте)
FONT_PATH  = "font_regular.ttf"
FONT_BOLD  = "font_bold.ttf"

PURPLE = (200, 150, 255)
SEP    = (168, 132, 230)
WHITE  = (245, 243, 250)
GREY   = (190, 190, 205)
DIM    = (150, 150, 165)
GREEN  = (140, 230, 160)

SEP_LINE = "━━━━━━━━━━━━━━━━━━━━"

def _font(size, bold=False):
    path = FONT_BOLD if bold else FONT_PATH
    if not os.path.exists(path):
        try: return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
        except: return ImageFont.load_default()
    return ImageFont.truetype(path, size)

def _xp_bar(cur, mx, cells=10):
    filled = round(cells * cur / mx) if mx else 0
    return "[" + "▰" * filled + "▱" * (cells - filled) + "]"

def get_avatar(uid):
    url = f"https://vk.com/photo{uid}_" # Заглушка
    return None

def render_card(bg_source, u, avatar_url="", out_path="stats.png"):
    # 1. Фон
    bg = None
    if bg_source.startswith("http"):
        try:
            bg = Image.open(io.BytesIO(requests.get(bg_source, timeout=10).content)).convert("RGB")
        except: pass
    if bg is None:
        bg = Image.new("RGB", (W, H), (12, 8, 25))
    else:
        scale = max(W / bg.width, H / bg.height)
        bg = bg.resize((round(bg.width * scale), round(bg.height * scale)))
        x = (bg.width - W) // 2
        y = (bg.height - H) // 2
        bg = bg.crop((x, y, x + W, y + H))

    card = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 5, 20, 100)))
    draw = ImageDraw.Draw(card)

    # 2. Аватарка
    av_size = 180
    av_x = (W - av_size) // 2
    av_y = 60
    if avatar_url:
        try:
            av_img = Image.open(io.BytesIO(requests.get(avatar_url, timeout=10).content)).convert("RGBA")
            av_img = ImageOps.fit(av_img, (av_size, av_size), Image.Resampling.LANCZOS)
            mask = Image.new('L', (av_size, av_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
            card.paste(av_img, (av_x, av_y), mask)
            draw.ellipse((av_x, av_y, av_x+av_size, av_y+av_size), outline=PURPLE, width=4)
        except Exception as e:
            print(f"Ошибка аватарки: {e}")
            draw.ellipse((av_x, av_y, av_x+av_size, av_y+av_size), fill=(50,50,50), outline=PURPLE, width=4)
    else:
        draw.ellipse((av_x, av_y, av_x+av_size, av_y+av_size), fill=(50,50,50), outline=PURPLE, width=4)

    # 3. Текст
    y_offset = av_y + av_size + 30
    def draw_center(text, size, bold, color, y):
        f = _font(size, bold)
        w = draw.textbbox((0, 0), text, font=f)[2]
        draw.text(((W - w) // 2, y), text, font=f, fill=color)

    # Имя
    draw_center(u.get("name", "Игрок").upper(), 50, True, WHITE, y_offset)
    y_offset += 70
    # Заголовок
    draw_center("MONSTER PROFILE", 36, True, PURPLE, y_offset)
    y_offset += 60

    # Линия
    sep_f = _font(30, False)
    sep_w = draw.textbbox((0, 0), SEP_LINE, font=sep_f)[2]
    draw.text(((W - sep_w) // 2, y_offset), SEP_LINE, font=sep_f, fill=SEP)
    y_offset += 50

    # Колонки
    label_x = 200
    value_x = 480
    start_y = y_offset

    def draw_row(label, value, extra=""):
        nonlocal start_y
        f_lbl = _font(38, True)
        f_val = _font(38, False)
        f_ext = _font(30, False)
        
        draw.text((label_x, start_y), label, font=f_lbl, fill=WHITE)
        draw.text((label_x + 350, start_y), "·", font=f_lbl, fill=DIM)
        
        draw.text((value_x, start_y), value, font=f_val, fill=GREY)
        if extra:
            w_val = draw.textbbox((0,0), value, font=f_val)[2]
            draw.text((value_x + w_val + 15, start_y + 5), extra, font=f_ext, fill=DIM)
        start_y += 55

    draw_row("Должность",   u.get("title", "—"))
    draw_row("Привилегия",  u.get("priv", "Игрок"))
    draw_row("VIP",         "Да" if u.get("vip") else "Нет")
    draw_row("Роль в чате", u.get("role", "Участник"), f"· пр. {u.get('priority', 0)}")

    start_y += 20
    draw.text(((W - sep_w) // 2, start_y), SEP_LINE, font=sep_f, fill=SEP)
    start_y += 40
    draw_center("АКТИВНОСТЬ", 36, True, PURPLE, start_y)
    start_y += 60

    draw_row("Сообщений", str(u.get("msgs", 0)))
    draw_row("Уровень",   f"{u.get('lvl', 0)} / 999")
    
    # Опыт с прогресс-баром
    f_lbl = _font(38, True); f_val = _font(38, False)
    draw.text((label_x, start_y), "Опыт", font=f_lbl, fill=WHITE)
    draw.text((label_x + 350, start_y), "·", font=f_lbl, fill=DIM)
    xp_str = f"{u.get('xp', 0)} / {u.get('xp_max', 100)} ({u.get('xp_pct', 0)}%)"
    draw.text((value_x, start_y), xp_str, font=f_val, fill=GREY)
    start_y += 40
    # Бар
    bar_str = _xp_bar(u.get('xp', 0), u.get('xp_max', 100))
    draw.text((value_x, start_y), bar_str, font=f_val, fill=GREEN)
    start_y += 55

    draw_row("Варнов",    f"{u.get('warns', 0)} / 3")
    draw_row("Брак",      u.get("marriage", "нет"))
    draw_row("Репутация", str(u.get("rep", 0)))
    draw_row("Ник",       u.get("nick", "не установлен"))
    draw_row("Дрон",      u.get("gift", "—"), f"×{u.get('drone_mult', 1)}")

    start_y += 20
    draw.text(((W - sep_w) // 2, start_y), SEP_LINE, font=sep_f, fill=SEP)
    start_y += 50

    draw_center(f"🔥 Статус: {u.get('status', 'Новичок')}", 40, True, GREEN, start_y)

    card.convert("RGB").save(out_path)
    return out_path
