# -*- coding: utf-8 -*-
import os, re, io, requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1080

FONT_PATH  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_BOLD  = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

HAS_FONTS = os.path.exists(FONT_PATH) and os.path.exists(FONT_BOLD)
HAS_EMOJI = os.path.exists(EMOJI_FONT)

PURPLE = (200, 150, 255)
SEP    = (168, 132, 230)
WHITE  = (245, 243, 250)
GREY   = (190, 190, 205)
DIM    = (150, 150, 165)
GREEN  = (140, 230, 160)

SEP_LINE = "━━━━━━━━━━━━━━━━━━━━"

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\uFE0F\u200D]+"
)

def _font(size, bold=False):
    path = FONT_BOLD if bold else FONT_PATH
    if not os.path.exists(path):
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)

def _emoji_font(size):
    if HAS_EMOJI:
        return ImageFont.truetype(EMOJI_FONT, 109), size / 109
    return None, 1.0

def _segments(text, size, bold, color):
    segs, pos = [], 0
    for m in EMOJI_RE.finditer(text):
        if m.start() > pos:
            segs.append(("text", text[pos:m.start()], _font(size, bold), color, 1.0))
        f, k = _emoji_font(size)
        if f is not None:
            segs.append(("emoji", m.group(), f, color, k))
        else:
            segs.append(("text", m.group(), _font(size, bold), color, 1.0))
        pos = m.end()
    if pos < len(text):
        segs.append(("text", text[pos:], _font(size, bold), color, 1.0))
    return segs

def _xp_bar(cur, mx, cells=8):
    filled = round(cells * cur / mx) if mx else 0
    return "[" + "▰" * filled + "▱" * (cells - filled) + "]"

def build_lines(u):
    L = []
    def sep():  L.append(_segments(SEP_LINE, 30, False, SEP))
    def gap():  L.append([])
    def title(t, size): L.append(_segments(t, size, True, PURPLE))
    def row3(label, value, extra=""):
        pad = 13
        parts = [
            _segments(label.ljust(pad), 34, True, WHITE),
            _segments("·  ", 34, False, DIM),
            _segments(value, 34, False, GREY),
        ]
        if extra:
            parts.append(_segments("  " + extra, 26, False, DIM))
        L.append([s for p in parts for s in p])

    sep(); title("MONSTER · PROFILE", 44); sep(); gap()
    row3("Должность",   u.get("title", "—"))
    row3("Привилегия",  u.get("priv", "Игрок"), "(стандарт)")
    row3("VIP",         "Да" if u.get("vip") else "Нет")
    row3("Роль в чате", u.get("role", "Участник"), f"· приоритет {u.get('priority', 101)}")

    gap(); sep(); title("АКТИВНОСТЬ", 42); sep(); gap()
    row3("Сообщений", str(u.get("msgs", 0)))
    row3("Уровень",   f"{u.get('lvl', 0)} / {u.get('lvl_max', 999)}")
    row3("Опыт", f"{u.get('xp', 0)} / {u.get('xp_max', 100)} ({u.get('xp_pct', 0)}%)",
         f"{_xp_bar(u.get('xp', 0), u.get('xp_max', 100))} XP")
    row3("Варнов",    f"{u.get('warns', 0)} / 3")
    row3("Брак",      u.get("marriage", "нет"))
    row3("Репутация", str(u.get("rep", 0)))
    row3("Ник",       u.get("nick", "не установлен"))
    row3("Сувенир",   u.get("gift", "—"))

    gap(); sep(); gap()
    L.append(_segments("Статус:", 36, True, WHITE)
           + _segments("   ", 36, False, DIM)
           + _segments(f"{u.get('status_emoji', '🌱')} {u.get('status', 'Новичок')}",
                       36, False, GREEN))
    gap(); sep()
    return L

def render_card(bg_source, u, out_path="stats.png"):
    lines = build_lines(u)

    # Поддержка ссылки и локального файла
    bg = None
    if bg_source.startswith("http://") or bg_source.startswith("https://"):
        try:
            resp = requests.get(bg_source, timeout=10)
            bg = Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            print(f"Ошибка скачивания фона: {e}")
    elif os.path.exists(bg_source):
        bg = Image.open(bg_source).convert("RGB")

    # Если фон не загрузился — рисуем на чёрном
    if bg is None:
        bg = Image.new("RGB", (W, H), (12, 8, 25))
    else:
        # Обрезаем под квадрат 1080x1080
        scale = max(W / bg.width, H / bg.height)
        bg = bg.resize((round(bg.width * scale), round(bg.height * scale)))
        x = (bg.width - W) // 2
        y = (bg.height - H) // 2
        bg = bg.crop((x, y, x + W, y + H))

    card = Image.alpha_composite(bg.convert("RGBA"), Image.new("RGBA", (W, H), (8, 5, 20, 70)))

    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    LH, GAP = 58, 30
    heights = []
    for line in lines:
        if not line:
            heights.append(GAP); continue
        h = LH
        for kind, text, font, color, k in line:
            bb = probe.textbbox((0, 0), text, font=font)
            h = max(h, int((bb[3] - bb[1]) * k) + 8)
        heights.append(h)

    yy = (H - sum(heights)) // 2
    draw = ImageDraw.Draw(card)
    for line, lh in zip(lines, heights):
        if not line:
            yy += lh; continue
        w = sum(probe.textbbox((0, 0), t, font=f)[2] for _, t, f, _, _ in line)
        cx = (W - w) // 2
        ty = yy + (lh - LH) // 2
        for kind, text, font, color, k in line:
            draw.text((cx + 2, ty + 2), text, font=font, fill=(0, 0, 0))
            if kind == "emoji":
                draw.text((cx, ty), text, font=font, fill=color, embedded_color=True)
            else:
                draw.text((cx, ty), text, font=font, fill=color)
            cx += probe.textbbox((0, 0), text, font=font)[2]
        yy += lh

    card.convert("RGB").save(out_path)
    return out_path
