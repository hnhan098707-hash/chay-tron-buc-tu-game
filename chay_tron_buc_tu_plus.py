"""
CHẠY TRỐN BỨC TỬ  v3 - game cuộn ngang pixel art bằng Python (pygame)

Cài đặt:   pip install pygame
Chạy:      python chay_tron_buc_tu.py

Điều khiển mặc định (đổi được trong CÀI ĐẶT):
  SPACE / W / MŨI TÊN LÊN : nhảy  (nhấn thêm lần nữa trên không = NHẢY ĐÔI)
  J / CHUỘT TRÁI          : bắn (giữ để bắn liên tục)
  P / ESC                 : tạm dừng
  R                       : chơi lại (khi đã chết)
  F11                     : bật/tắt toàn màn hình
  F6                      : (thử nghiệm) nhảy sang địa hình kế tiếp

Chọn chế độ SINH TỒN, THỬ THÁCH 90 GIÂY hoặc SĂN QUÁI trong menu.
Quái có nhiều hành vi; hạ quái có thể rơi khiên, tăng tốc, bắn nhanh hoặc tim.
Cài đặt được lưu vào file cai_dat.json cạnh file game.
"""
import array
import json
import math
import os
import random
import sys

import pygame

W, H = 384, 216          # độ phân giải pixel thật
GROUND = 180             # y của mặt đất
FPS = 60
PLAYER_SPEED = 1.9
SETTINGS_VERSION = 4

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "cai_dat.json")

# (giây, nhãn): chu kỳ đổi địa hình + đổi ngày/đêm
STAGE_OPTIONS = [(600, "10 PHÚT"), (300, "5 PHÚT"), (120, "2 PHÚT"),
                 (30, "30 GIÂY (thử)")]

# ----------------------------------------------------------------------
# 3 ĐỘ KHÓ - KHÁC NHAU HOÀN TOÀN VỀ LUẬT CHƠI
# ----------------------------------------------------------------------
DIFFS = [
    dict(   # DỄ: sống sót lâu, nhiều tim, nhiều lần nhảy, đạn xuyên, hồi máu
        name="DỄ", color=(110, 230, 130),
        desc="5 tim · nhảy 3 lần · tường chậm · đạn xuyên 2 quái · "
             "rơi tim & tự hồi máu",
        hp=5, jumps=3, jump2=-4.7,
        wall_base=1.0, wall_accel=1 / 9000, wall_cap=2.05, maxgap=230,
        push=24, stun=25, stun_speed=0.6, invuln=100,
        fire_cd=8, pierce=2, hp_mult={"slime": 1, "bat": 1, "ghost": 1},
        drop=0.22, heal_every=12,
        spawn_lo=62, spawn_min=46, spawn_spread=60, group=0.0,
        enemy_fire=False, overheat=False, surge=False, score=0.7),
    dict(   # THƯỜNG: cân bằng
        name="THƯỜNG", color=(255, 225, 90),
        desc="3 tim · nhảy đôi · tường tăng tốc · choáng 0.8 giây · "
             "thỉnh thoảng rơi tim",
        hp=3, jumps=2, jump2=-4.4,
        wall_base=1.25, wall_accel=1 / 7000, wall_cap=2.4, maxgap=190,
        push=14, stun=50, stun_speed=0.35, invuln=70,
        fire_cd=11, pierce=1, hp_mult={"slime": 2, "bat": 1, "ghost": 2},
        drop=0.12, heal_every=0,
        spawn_lo=90, spawn_min=36, spawn_spread=55, group=0.12,
        enemy_fire=False, overheat=False, surge=False, score=1.0),
    dict(   # KHÓ: sinh tồn khắc nghiệt
        name="KHÓ", color=(255, 90, 90),
        desc="2 tim · nhảy đôi yếu · tường lao nhanh · quái bắn trả · "
             "súng quá nhiệt · choáng 1.5 giây · điểm x2",
        hp=2, jumps=2, jump2=-3.5,
        wall_base=1.55, wall_accel=1 / 5000, wall_cap=3.0, maxgap=150,
        push=8, stun=90, stun_speed=0.2, invuln=60,
        fire_cd=13, pierce=1, hp_mult={"slime": 3, "bat": 2, "ghost": 3},
        drop=0.04, heal_every=0,
        spawn_lo=64, spawn_min=24, spawn_spread=40, group=0.35,
        enemy_fire=True, overheat=True, surge=True, score=2.0),
]

DEFAULTS = {
    "version": SETTINGS_VERSION,
    "difficulty": 1,
    "stage_idx": 0,           # chỉ số trong STAGE_OPTIONS
    "volume": 7,              # 0..10
    "shake": True,
    "fullscreen": False,
    "scale": 3,               # hệ số phóng cửa sổ
    "lighting": 2,            # cường độ hiệu ứng ánh sáng, 0..3
    "particles": True,        # hạt môi trường và hiệu ứng
    "mode": 0,                # chế độ chơi
    "key_jump": pygame.K_SPACE,
    "key_shoot": pygame.K_j,
    "best": [0, 0, 0],        # kỷ lục theo từng độ khó
}

WHITE = (255, 255, 255)
YELLOW = (255, 225, 90)
RED = (255, 70, 70)
GRAY = (190, 190, 205)
LBLUE = (180, 220, 255)


# ---------------------------------------------------------------- TIỆN ÍCH
def mix(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def shade(c, f):
    return (max(0, min(255, int(c[0] * f))),
            max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))))


def night_tint(c):
    return (int(c[0] * 0.20), int(c[1] * 0.26), min(255, int(c[2] * 0.40) + 28))


def pickup_color(kind):
    return {
        "heart": (255, 90, 130),
        "shield": (80, 205, 255),
        "haste": (255, 220, 70),
        "rapid": (255, 145, 55),
    }.get(kind, WHITE)


def hsh(n):
    n = (n * 374761393 + 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFFFF


# ---------------------------------------------------------------- SETTINGS
def load_settings():
    s = json.loads(json.dumps(DEFAULTS))
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("version") not in (3, SETTINGS_VERSION):
            return s                          # file cũ -> dùng mặc định
        for k, v in d.items():
            if k in s and type(v) == type(s[k]):
                s[k] = v
        s["version"] = SETTINGS_VERSION
        s["difficulty"] = max(0, min(2, s["difficulty"]))
        s["stage_idx"] = max(0, min(len(STAGE_OPTIONS) - 1, s["stage_idx"]))
        s["volume"] = max(0, min(10, s["volume"]))
        if s["scale"] not in (1, 2, 3, 4, 5, 6):
            s["scale"] = 3
        s["lighting"] = max(0, min(3, s["lighting"]))
        s["mode"] = max(0, min(2, s["mode"]))
        if len(s["best"]) != 3 or not all(isinstance(x, int) for x in s["best"]):
            s["best"] = [0, 0, 0]
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def key_name(k):
    n = pygame.key.name(k).upper()
    return n if n else str(k)


# ---------------------------------------------------------------- AUDIO
def tone(f0, f1, dur, vol=0.35, noise=False):
    """Âm thanh 8-bit tạo bằng code (sóng vuông / nhiễu), không cần file ngoài."""
    freq, fmt, ch = pygame.mixer.get_init()
    if fmt != -16:
        raise RuntimeError("định dạng âm thanh không hỗ trợ")
    n = int(freq * dur)
    buf = array.array("h")
    phase = 0.0
    for i in range(n):
        t = i / n
        phase += (f0 + (f1 - f0) * t) / freq
        if noise:
            v = random.uniform(-1, 1)
        else:
            v = 1.0 if (phase % 1.0) < 0.5 else -1.0
        val = int(v * vol * ((1 - t) ** 1.5) * 32767)
        for _ in range(ch):
            buf.append(val)
    return pygame.mixer.Sound(buffer=buf.tobytes())


class Audio:
    def __init__(self, settings):
        self.s = settings
        self.snd = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.snd = {
                "jump": tone(280, 620, 0.12),
                "jump2": tone(480, 900, 0.10),
                "shoot": tone(900, 300, 0.07, 0.25),
                "hit": tone(200, 120, 0.06, 0.3, True),
                "kill": tone(500, 1100, 0.16, 0.35),
                "hurt": tone(220, 70, 0.28, 0.4, True),
                "die": tone(400, 40, 0.8, 0.45, True),
                "move": tone(600, 600, 0.04, 0.2),
                "ok": tone(500, 900, 0.09, 0.3),
                "pickup": tone(700, 1500, 0.14, 0.3),
                "warn": tone(160, 160, 0.18, 0.35),
                "stage": tone(260, 820, 0.45, 0.3),
                "hot": tone(130, 70, 0.3, 0.3, True),
            }
        except Exception:
            self.snd = {}

    def play(self, name):
        snd = self.snd.get(name)
        v = self.s["volume"] / 10
        if snd is None or v <= 0:
            return
        snd.set_volume(v)
        snd.play()


# ---------------------------------------------------------------- SPRITES
PAL = {
    "o": (25, 20, 35), "r": (210, 55, 60), "R": (255, 120, 110),
    "s": (255, 208, 165), "K": (25, 25, 40), "b": (60, 115, 225),
    "B": (115, 175, 255), "p": (45, 55, 120), "k": (30, 30, 45),
    "m": (120, 125, 140), "M": (195, 200, 215), "n": (125, 85, 45),
}

PLAYER_TOP = [
    "...oooooo...",
    "..orrrrrro..",
    ".orrrRrrrro.",
    ".orrrrrrrooo",
    ".osssssssso.",
    ".ossKsssKso.",
    "..osssssso..",
    "..obbbbbbo..",
    ".obbBbbbbomm",
    ".sobbbbbbomM",
    "..obbbbbbo..",
    "..onnnnnno..",
]
LEGS_A = ["..oppo.oppo.", "..okko.okko.", "..oooo.oooo."]
LEGS_B = ["...oppppo...", "...okkkko...", "...oooooo..."]
LEGS_JUMP = [".oppo..oppo.", ".okko..okko.", ".oooo..oooo."]

SLIME_A = [
    "....OOOOOO....",
    "..OOGGGGGGOO..",
    ".OGGLLGGGGGGO.",
    ".OGLLGGGGGGGO.",
    "OGGGGGGGGGGGGO",
    "OGGwKGGGGwKGGO",
    "OGGKKGGGGKKGGO",
    "OGGGGGGGGGGGGO",
    "ODGGGGGGGGGGDO",
    ".ODDDDDDDDDDO.",
]
SLIME_B = [
    "..............",
    "...OOOOOOOO...",
    "..OGGLLGGGGO..",
    ".OGGLGGGGGGGO.",
    "OGGGGGGGGGGGGO",
    "OGwKGGGGGGwKGO",
    "OGKKGGGGGGKKGO",
    "OGGGGGGGGGGGGO",
    "ODGGGGGGGGGGDO",
    "ODDDDDDDDDDDDO",
]
BAT_A = [
    "O............O",
    "OO....OO....OO",
    "OOOO.OLLO.OOOO",
    "OOOOOOGGOOOOOO",
    ".OOOGYGGYGGOO.",
    "..OOOGGGGGOO..",
    "....OGGGGO....",
    ".....OOOO.....",
]
BAT_B = [
    "..............",
    "..............",
    "O....OOOO....O",
    "OOO.OYGGYO.OOO",
    "OOOOOGGGGOOOOO",
    ".OOOOGGGGOOOO.",
    "..OOOOGGOOOO..",
    "....OOOOOO....",
]
GHOST = [
    "...WWWWWW...",
    "..WWWWWWWW..",
    ".WWWWWWWWWW.",
    ".WWKKWWKKWW.",
    ".WWKKWWKKWW.",
    ".WWWWMMWWWW.",
    ".WWWWMMWWWW.",
    ".WWWWWWWWWW.",
    ".WWWWWWWWWW.",
    "WWWWWWWWWWWW",
    "WWW.WWWW.WWW",
    "W....WW....W",
]
HEART = [
    ".RR.RR.",
    "RwRRRRR",
    "RRRRRRR",
    ".RRRRR.",
    "..RRR..",
    "...R...",
]

PLAYER_W, PLAYER_H = 8, 15      # hitbox khớp sprite (sprite 12x15)
SPRITE_OFFSET_X = 2


def make_sprite(rows, pal):
    w = max(len(r) for r in rows)
    surf = pygame.Surface((w, len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            col = pal.get(ch)
            if col is not None:
                surf.set_at((x, y), col)
    return surf


def monster_pal(c):
    return {"G": c, "D": shade(c, 0.62), "L": mix(c, (255, 255, 255), 0.5),
            "O": shade(c, 0.22), "w": (255, 255, 255), "K": (20, 20, 30),
            "Y": (255, 70, 70)}


SPR = {}
STAR_LIST = []


# ---------------------------------------------------------------- THEMES
THEMES = [
    {"name": "ĐỒNG CỎ", "sky": ((92, 160, 235), (196, 228, 250)),
     "far": (120, 150, 205), "near": (84, 140, 120), "ridge": "hills",
     "g_top": (92, 190, 84), "g_mid": (118, 80, 52), "g_dark": (84, 56, 38),
     "ground": "grass", "deco": "tree", "dc1": (48, 150, 70),
     "dc2": (110, 210, 110), "cloud": (255, 255, 255), "weather": "leaf",
     "mon": (70, 205, 95), "spike": "metal", "sun": (255, 240, 170),
     "space": False},
    {"name": "SA MẠC", "sky": ((236, 150, 80), (253, 224, 150)),
     "far": (222, 170, 120), "near": (200, 145, 95), "ridge": "dunes",
     "g_top": (238, 205, 125), "g_mid": (208, 164, 98), "g_dark": (176, 130, 74),
     "ground": "sand", "deco": "cactus", "dc1": (70, 155, 80),
     "dc2": (130, 210, 120), "cloud": (255, 240, 215), "weather": "sand",
     "mon": (235, 195, 60), "spike": "cactus", "sun": (255, 225, 150),
     "space": False},
    {"name": "RỪNG TUYẾT", "sky": ((120, 160, 210), (228, 240, 252)),
     "far": (165, 185, 220), "near": (125, 150, 190), "ridge": "peaks",
     "g_top": (242, 249, 255), "g_mid": (160, 185, 215),
     "g_dark": (120, 146, 182),
     "ground": "snow", "deco": "pine", "dc1": (42, 110, 96),
     "dc2": (240, 248, 255), "cloud": (250, 252, 255), "weather": "snow",
     "mon": (95, 205, 245), "spike": "ice", "sun": (255, 255, 240),
     "space": False},
    {"name": "NÚI LỬA", "sky": ((70, 22, 30), (238, 112, 52)),
     "far": (110, 44, 44), "near": (66, 30, 34), "ridge": "cones",
     "g_top": (80, 66, 72), "g_mid": (56, 44, 50), "g_dark": (38, 30, 36),
     "ground": "lava", "deco": "rock", "dc1": (44, 34, 40),
     "dc2": (255, 130, 40), "cloud": (70, 52, 56), "weather": "ember",
     "mon": (245, 105, 50), "spike": "obsidian", "sun": (255, 110, 50),
     "space": False},
    {"name": "TINH THỂ", "sky": ((14, 10, 52), (96, 54, 150)),
     "far": (78, 56, 140), "near": (54, 38, 108), "ridge": "spires",
     "g_top": (140, 100, 230), "g_mid": (74, 52, 136), "g_dark": (46, 34, 92),
     "ground": "tech", "deco": "crystal", "dc1": (120, 80, 220),
     "dc2": (110, 235, 255), "cloud": (120, 90, 190), "weather": "mote",
     "mon": (205, 95, 245), "spike": "crystal", "sun": (190, 150, 255),
     "space": True},
]


def build_sprites():
    SPR["p_a"] = make_sprite(PLAYER_TOP + LEGS_A, PAL)
    SPR["p_b"] = make_sprite(PLAYER_TOP + LEGS_B, PAL)
    SPR["p_j"] = make_sprite(PLAYER_TOP + LEGS_JUMP, PAL)
    SPR["slime"], SPR["bat"] = [], []
    for th in THEMES:
        pal = monster_pal(th["mon"])
        SPR["slime"].append((make_sprite(SLIME_A, pal), make_sprite(SLIME_B, pal)))
        SPR["bat"].append((make_sprite(BAT_A, pal), make_sprite(BAT_B, pal)))
    SPR["ghost"] = make_sprite(
        GHOST, {"W": (225, 235, 255), "K": (30, 30, 60), "M": (90, 90, 140)})
    SPR["ghost"].set_alpha(205)
    SPR["heart"] = make_sprite(HEART, {"R": (240, 50, 75), "w": (255, 205, 215)})
    SPR["heart_e"] = make_sprite(HEART, {"R": (55, 55, 78), "w": (78, 78, 100)})
    sh = pygame.Surface((14, 4), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 255), (0, 0, 14, 4))
    SPR["shadow"] = sh
    # ánh sáng cộng (additive) cho đạn
    g = pygame.Surface((16, 16))
    for r in range(8, 0, -1):
        v = int(150 * (1 - r / 8) ** 0.8) + 25
        pygame.draw.circle(g, (v, int(v * 0.6), int(v * 0.2)), (8, 8), r)
    SPR["glow"] = g
    # viền đỏ khi nguy hiểm
    vg = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(22):
        a = int(210 * (1 - i / 22) ** 2)
        pygame.draw.rect(vg, (210, 10, 10, a), (i, i, W - 2 * i, H - 2 * i), 1)
    SPR["vignette"] = vg
    # quầng sáng đỏ phía trước bức tường (additive)
    wa = pygame.Surface((34, H))
    for i in range(34):
        v = int(120 * (1 - i / 34) ** 2)
        pygame.draw.line(wa, (v, v // 5, v // 8), (i, 0), (i, H))
    SPR["wall_aura"] = wa
    fl = pygame.Surface((W, H))
    fl.fill((255, 255, 255))
    SPR["flash"] = fl
    rnd = random.Random(3)
    STAR_LIST[:] = [(rnd.randint(0, W - 1), rnd.randint(0, GROUND - 70),
                     rnd.random() * 6.28) for _ in range(70)]


GLOWS = {}


def night_glow(R):
    s = GLOWS.get(R)
    if s is None:
        s = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
        s.fill((8, 10, 36, 255))
        for r in range(R, 0, -2):
            a = int(255 * (r / R) ** 1.7)
            pygame.draw.circle(s, (8, 10, 36, a), (R, R), r)
        GLOWS[R] = s
    return s


# ---------------------------------------------------------------- NỀN / MÔI TRƯỜNG
SKY_CACHE = {}


def sky_surface(theme_i, night):
    key = (theme_i, night)
    s = SKY_CACHE.get(key)
    if s is None:
        s = pygame.Surface((W, GROUND))
        top, bot = THEMES[theme_i]["sky"]
        if night:
            top, bot = night_tint(top), night_tint(bot)
        for y in range(0, GROUND, 3):
            pygame.draw.rect(s, mix(top, bot, y / GROUND), (0, y, W, 3))
        SKY_CACHE[key] = s
    return s


def ridge(kind, wx):
    if kind == "hills":
        return 0.5 + 0.28 * math.sin(wx * 0.016) + 0.18 * math.sin(wx * 0.05 + 1.3)
    if kind == "dunes":
        return 0.5 + 0.4 * math.sin(wx * 0.009 + math.sin(wx * 0.004) * 2)
    if kind == "peaks":
        tri = abs(((wx * 0.018) % 2) - 1)
        return 0.2 + 0.8 * (1 - tri) ** 1.2 * (0.7 + 0.3 * math.sin(wx * 0.004))
    if kind == "cones":
        tri = abs(((wx * 0.012) % 2) - 1)
        return max(0.15, 1.0 - tri * 1.35)
    n = int(wx // 7)                         # spires: tinh thể dạng khối
    return 0.2 + 0.8 * ((hsh(n) % 100) / 100) ** 1.5


def draw_deco(surf, th, c, cam):
    spacing = 70
    k = 0.62
    first = int((cam * k) // spacing) - 1
    col1, col2 = c(th["dc1"]), c(th["dc2"])
    kind = th["deco"]
    base = GROUND
    for i in range(first, first + W // spacing + 4):
        r = hsh(i * 31 + 7)
        if r % 5 == 0:
            continue
        sx = int(i * spacing + (r % 40) - cam * k)
        if sx < -30 or sx > W + 30:
            continue
        s = 0.7 + (r % 40) / 100.0
        if kind == "tree":
            th_ = int(16 * s)
            pygame.draw.rect(surf, c((90, 60, 40)), (sx - 2, base - th_, 4, th_))
            pygame.draw.circle(surf, col1, (sx - 6, base - int(19 * s)), int(8 * s))
            pygame.draw.circle(surf, col1, (sx + 6, base - int(19 * s)), int(8 * s))
            pygame.draw.circle(surf, col1, (sx, base - int(24 * s)), int(11 * s))
            pygame.draw.circle(surf, col2, (sx - 3, base - int(28 * s)), int(4 * s))
        elif kind == "cactus":
            hh = int(24 * s)
            pygame.draw.rect(surf, col1, (sx - 2, base - hh, 5, hh))
            pygame.draw.rect(surf, col1, (sx - 8, base - int(14 * s), 6, 3))
            pygame.draw.rect(surf, col1, (sx - 8, base - int(19 * s), 3, int(8 * s)))
            pygame.draw.rect(surf, col1, (sx + 3, base - int(10 * s), 6, 3))
            pygame.draw.rect(surf, col1, (sx + 6, base - int(15 * s), 3, int(8 * s)))
            pygame.draw.rect(surf, col2, (sx - 1, base - hh, 1, hh - 2))
        elif kind == "pine":
            pygame.draw.rect(surf, c((80, 56, 44)), (sx - 1, base - int(8 * s), 3, int(8 * s)))
            for j in range(3):
                yb = base - int(6 * s) - j * int(9 * s)
                hw = int((11 - j * 2.5) * s)
                hgt = int(14 * s)
                pygame.draw.polygon(surf, col1,
                                    [(sx - hw, yb), (sx + hw, yb), (sx, yb - hgt)])
                pygame.draw.polygon(surf, col2,
                                    [(sx - hw // 2, yb - hgt // 2),
                                     (sx + hw // 2, yb - hgt // 2),
                                     (sx, yb - hgt)])
        elif kind == "rock":
            pts = [(sx - int(8 * s), base), (sx - int(4 * s), base - int(14 * s)),
                   (sx + int(2 * s), base - int(18 * s)),
                   (sx + int(9 * s), base - int(6 * s)), (sx + int(10 * s), base)]
            pygame.draw.polygon(surf, col1, pts)
            pygame.draw.line(surf, col2, (sx - 1, base - int(16 * s)),
                             (sx + 1, base - int(6 * s)))
        else:  # crystal
            pts = [(sx - int(5 * s), base), (sx - int(3 * s), base - int(22 * s)),
                   (sx, base - int(30 * s)), (sx + int(3 * s), base - int(22 * s)),
                   (sx + int(5 * s), base)]
            pygame.draw.polygon(surf, col1, pts)
            pygame.draw.polygon(surf, mix(col1, col2, 0.5),
                                [(sx, base), (sx, base - int(30 * s)),
                                 (sx + int(3 * s), base - int(22 * s)),
                                 (sx + int(5 * s), base)])
            pygame.draw.rect(surf, col2, (sx - 1, base - int(31 * s), 2, 2))


def draw_ground(surf, th, c, cam, t):
    g_top, g_mid, g_dark = c(th["g_top"]), c(th["g_mid"]), c(th["g_dark"])
    pygame.draw.rect(surf, g_mid, (0, GROUND, W, H - GROUND))
    pygame.draw.rect(surf, g_top, (0, GROUND, W, 5))
    pygame.draw.rect(surf, shade(g_top, 1.25), (0, GROUND, W, 1))
    pygame.draw.rect(surf, g_dark, (0, GROUND + 5, W, 2))
    icam = int(cam)
    for row in range(3):
        y = GROUND + 10 + row * 9
        off = (row % 2) * 10
        x0 = -((icam + off) % 20)
        for x in range(x0 - 20, W + 20, 20):
            pygame.draw.rect(surf, g_dark, (x, y, 12, 4))
            pygame.draw.rect(surf, shade(g_mid, 1.15), (x, y, 12, 1))
    kind = th["ground"]
    if kind == "grass":
        for gx in range((icam // 5) * 5, icam + W + 10, 5):
            r = hsh(gx)
            sx = gx - icam
            if r % 3 == 0:
                pygame.draw.line(surf, shade(g_top, 1.3), (sx, GROUND),
                                 (sx, GROUND - 2 - r % 4))
            if r % 23 == 0:
                pygame.draw.rect(surf, c((255, 230, 90)), (sx, GROUND - 5, 2, 2))
    elif kind == "sand":
        for gx in range((icam // 8) * 8, icam + W + 16, 8):
            r = hsh(gx)
            sx = gx - icam
            if r % 3 == 0:
                pygame.draw.line(surf, shade(g_top, 0.9), (sx, GROUND + 2),
                                 (sx + 5, GROUND + 2))
            if r % 17 == 0:
                pygame.draw.rect(surf, g_dark, (sx, GROUND - 2, 4, 2))
    elif kind == "snow":
        for gx in range((icam // 6) * 6, icam + W + 12, 6):
            r = hsh(gx)
            sx = gx - icam
            if r % 11 == 0:
                pygame.draw.rect(surf, g_top, (sx, GROUND - 2, 7, 2))
            if r % 19 == 0 and ((t // 8 + gx) % 3 == 0):
                surf.set_at((sx, GROUND + 2), (255, 255, 255))
    elif kind == "lava":
        for gx in range((icam // 40) * 40, icam + W + 40, 40):
            if hsh(gx) % 2 == 0:
                sx = gx - icam
                col = (255, 120 + int(60 * math.sin(t * 0.1 + gx)), 40)
                pts = [(sx, GROUND + 10), (sx + 4, GROUND + 14),
                       (sx + 2, GROUND + 19), (sx + 7, GROUND + 25)]
                pygame.draw.lines(surf, col, False, pts, 1)
                pygame.draw.rect(surf, col, (sx, GROUND, 8, 1))
    else:  # tech
        for gx in range((icam // 24) * 24, icam + W + 24, 24):
            sx = gx - icam
            pygame.draw.line(surf, shade(g_top, 1.15), (sx, GROUND + 5),
                             (sx, H))
            if (t // 20 + gx // 24) % 2 == 0:
                pygame.draw.rect(surf, (80, 240, 255), (sx + 8, GROUND + 2, 2, 2))


def draw_bg(surf, theme_i, night, cam, t):
    th = THEMES[theme_i]

    def c(x):
        return night_tint(x) if night else x

    surf.blit(sky_surface(theme_i, night), (0, 0))
    # sao
    if night or th["space"]:
        for sx0, sy, ph in STAR_LIST:
            x = int((sx0 - cam * 0.03) % W)
            b = 150 + int(105 * math.sin(t * 0.05 + ph))
            col = (b, b, min(255, b + 25))
            surf.set_at((x, sy), col)
            if ph > 5.2:
                surf.set_at((x + 1, sy), col)
                surf.set_at((x - 1, sy), col)
                surf.set_at((x, sy + 1), col)
                surf.set_at((x, sy - 1), col)
    # thiên thể
    cx, cy = 310, 46
    if th["space"]:
        pygame.draw.circle(surf, (140, 95, 225), (cx, cy + 4), 20)
        pygame.draw.circle(surf, (105, 70, 190), (cx + 6, cy + 8), 15)
        pygame.draw.ellipse(surf, (220, 190, 255), (cx - 36, cy - 2, 72, 14), 2)
        pygame.draw.circle(surf, (225, 225, 240), (cx - 60, cy + 24), 5)
    elif night:
        top = night_tint(th["sky"][0])
        pygame.draw.circle(surf, mix(top, (255, 255, 255), 0.14), (cx, cy), 19)
        pygame.draw.circle(surf, (235, 235, 215), (cx, cy), 14)
        for (ox, oy, r) in ((-4, -3, 3), (6, 4, 2), (2, -8, 2)):
            pygame.draw.circle(surf, (205, 205, 188), (cx + ox, cy + oy), r)
    else:
        bot = th["sky"][1]
        sun = th["sun"]
        pygame.draw.circle(surf, mix(bot, sun, 0.25), (cx, cy), 25)
        pygame.draw.circle(surf, mix(bot, sun, 0.55), (cx, cy), 20)
        pygame.draw.circle(surf, sun, (cx, cy), 15)
    # mây
    if not th["space"]:
        cc = c(th["cloud"])
        for i in range(6):
            x = int((i * 83 - cam * 0.07 - t * 0.12) % (W + 120)) - 60
            y = 18 + ((i * 37) % 52)
            pygame.draw.ellipse(surf, cc, (x, y, 38, 11))
            pygame.draw.ellipse(surf, cc, (x + 10, y - 5, 26, 12))
            pygame.draw.ellipse(surf, shade(cc, 0.86), (x + 4, y + 6, 30, 5))
    # núi / đụn cát / đỉnh băng / nón lửa / tinh thể (parallax)
    kind = th["ridge"]
    for (k, base, amp, key, off) in ((0.12, GROUND - 50, 56, "far", 0),
                                      (0.30, GROUND - 18, 34, "near", 977)):
        col = c(th[key])
        rim = shade(col, 1.3)
        for x in range(0, W, 2):
            h = ridge(kind, x + cam * k + off) * amp
            top = int(base - h)
            pygame.draw.rect(surf, col, (x, top, 2, GROUND - top))
            pygame.draw.rect(surf, rim, (x, top, 2, 1))
            if kind == "cones" and key == "far" and h > amp * 0.88:
                pygame.draw.rect(surf, (255, 140, 60), (x, top, 2, 2))
    draw_deco(surf, th, c, cam)
    draw_ground(surf, th, c, cam, t)


def draw_spike(surf, sx, sy, theme_i):
    kind = THEMES[theme_i]["spike"]
    if kind == "cactus":
        col, hl = (60, 160, 70), (120, 215, 120)
        pygame.draw.rect(surf, col, (sx + 3, sy, 5, 9))
        pygame.draw.rect(surf, col, (sx, sy + 3, 3, 2))
        pygame.draw.rect(surf, col, (sx, sy + 1, 2, 4))
        pygame.draw.rect(surf, col, (sx + 8, sy + 4, 3, 2))
        pygame.draw.rect(surf, col, (sx + 9, sy + 2, 2, 4))
        pygame.draw.rect(surf, hl, (sx + 4, sy, 1, 9))
        for (px_, py_) in ((2, 2), (9, 3), (5, 3), (6, 6)):
            surf.set_at((sx + px_, sy + py_), (240, 240, 200))
        return
    if kind == "ice":
        col, edge = (150, 225, 255), (235, 250, 255)
    elif kind == "obsidian":
        col, edge = (40, 30, 48), (255, 120, 40)
    elif kind == "crystal":
        col, edge = (215, 90, 250), (250, 190, 255)
    else:
        col, edge = (185, 190, 205), (240, 242, 250)
    for (a, b, hgt) in ((0, 6, 7), (3, 8, 9), (7, 11, 6)):
        pts = [(sx + a, sy + 9), (sx + (a + b) // 2, sy + 9 - hgt), (sx + b, sy + 9)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.line(surf, edge, pts[0], pts[1])


CRACKS = [
    [(-10, 20), (-16, 34), (-12, 48), (-20, 60)],
    [(-30, 90), (-24, 104), (-34, 120)],
    [(-8, 150), (-18, 162), (-12, 176), (-22, 190)],
]


def draw_wall(surf, wx, frame):
    """Bức tường tử thần: đá, vết nứt dung nham, mắt đỏ, răng nhọn."""
    if wx <= 0:
        return
    wx = min(wx, W + 100)
    pygame.draw.rect(surf, (52, 6, 14), (0, 0, wx, H))
    for i in range(0, min(wx, 64), 4):
        f = 1.0 - i / 64
        col = (int(52 + 60 * f), int(6 + 10 * f), int(14 + 14 * f))
        pygame.draw.rect(surf, col, (wx - i - 4, 0, 4, H))
    mort = (26, 2, 8)
    for y in range(0, H, 12):
        pygame.draw.line(surf, mort, (0, y), (wx, y))
        x = wx - (y // 12) % 2 * 12 - 1
        while x > 0:
            pygame.draw.line(surf, mort, (x, y), (x, y + 11))
            x -= 24
    glow = int(40 * math.sin(frame * 0.1))
    for pts in CRACKS:
        pp = [(wx + dx, y) for dx, y in pts]
        pygame.draw.lines(surf, (255, 110 + glow, 40), False, pp, 2)
    for ey in (58, 126):
        ex = wx - 40
        if ex + 16 > 0:
            pygame.draw.rect(surf, (255, 215, 60), (ex, ey, 16, 9))
            pygame.draw.rect(surf, (255, 255, 200), (ex + 2, ey + 1, 12, 3))
            pxx = ex + 6 + int(math.sin(frame * 0.05) * 2)
            pygame.draw.rect(surf, (130, 0, 0), (pxx, ey + 2, 4, 7))
            pygame.draw.polygon(surf, (20, 0, 6),
                                [(ex - 4, ey - 8), (ex + 18, ey - 1),
                                 (ex + 18, ey + 2), (ex - 4, ey - 4)])
    pygame.draw.rect(surf, (150, 20, 30), (wx - 6, 0, 3, H))
    for y in range(0, H, 12):
        tl = 9 + int(4 * math.sin(frame * 0.2 + y * 0.5))
        pts = [(wx - 3, y), (wx + tl, y + 6), (wx - 3, y + 12)]
        pygame.draw.polygon(surf, (236, 226, 200), pts)
        pygame.draw.polygon(surf, (120, 20, 20), pts, 1)
    surf.blit(SPR["wall_aura"], (wx, 0), special_flags=pygame.BLEND_RGB_ADD)


def draw_shadow(surf, cx, above, size=1.0):
    sh = SPR["shadow"]
    sh.set_alpha(max(25, int(120 - above * 0.9)))
    surf.blit(sh, (int(cx - 7), GROUND - 2))


# ---------------------------------------------------------------- QUÁI
class Monster:
    def __init__(self, kind, x, hp, theme):
        self.kind = kind
        self.x = float(x)
        self.hp = hp
        self.theme = theme
        self.t = random.random() * 6
        self.flash = 0
        self.fire = random.randint(60, 130)
        if kind == "slime":
            self.w, self.h = 12, 9
            self.y = float(GROUND - 9)
            self.vx = -0.4
        elif kind == "bat":
            self.w, self.h = 12, 6
            self.base = random.randint(108, 150)
            self.y = float(self.base)
            self.vx = -0.9
        elif kind == "ghost":
            self.w, self.h = 10, 13
            self.base = random.randint(115, 155)
            self.y = float(self.base)
            self.vx = -1.15
        elif kind == "wisp":
            self.w, self.h = 10, 12
            self.base = random.randint(80, 145)
            self.y = float(self.base)
            self.vx = -1.35
        elif kind == "spitter":
            self.w, self.h = 12, 10
            self.base = random.randint(105, 145)
            self.y = float(self.base)
            self.vx = -0.4
        elif kind == "runner":
            self.w, self.h = 12, 10
            self.y = float(GROUND - self.h)
            self.vx = -1.45
        elif kind == "golem":
            self.w, self.h = 14, 13
            self.y = float(GROUND - self.h)
            self.vx = -0.35
        else:  # spike
            self.w, self.h = 11, 9
            self.y = float(GROUND - 9)
            self.vx = 0.0

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update(self):
        self.t += 0.12
        self.x += self.vx
        if self.kind == "bat":
            self.y = self.base + math.sin(self.t) * 12
        elif self.kind == "ghost":
            self.y = self.base + math.sin(self.t * 0.7) * 18
        elif self.kind == "slime":
            self.y = GROUND - self.h - abs(math.sin(self.t * 0.8)) * 5
        elif self.kind == "runner":
            self.y = GROUND - self.h - abs(math.sin(self.t * 1.8)) * 2
        elif self.kind == "wisp":
            self.y = self.base + math.sin(self.t * 1.2) * 14
        elif self.kind == "spitter":
            self.y = self.base + math.sin(self.t * 0.8) * 3
        if self.flash > 0:
            self.flash -= 1

    def draw(self, surf, cam):
        sx, sy = int(self.x - cam), int(self.y)
        if sx < -20 or sx > W + 20:
            return
        if self.kind == "spike":
            draw_spike(surf, sx, sy, self.theme)
            return
        draw_shadow(surf, sx + self.w / 2, GROUND - (self.y + self.h))
        if self.kind == "runner":
            body = THEMES[self.theme]["mon"]
            bob = int(abs(math.sin(self.t * 1.8)) * 2)
            pygame.draw.ellipse(surf, shade(body, 0.55),
                                (sx + 1, sy + 3 + bob, 10, 7))
            pygame.draw.rect(surf, body, (sx + 2, sy + bob, 9, 7))
            pygame.draw.rect(surf, (255, 245, 210), (sx + 7, sy + 2 + bob, 2, 2))
            pygame.draw.rect(surf, (25, 20, 35), (sx + 8, sy + 2 + bob, 1, 1))
            leg = int(self.t * 3) % 2
            pygame.draw.line(surf, shade(body, 0.65), (sx + 4, sy + 6 + bob),
                             (sx + (2 if leg else 5), sy + 10), 2)
            pygame.draw.line(surf, shade(body, 0.65), (sx + 9, sy + 6 + bob),
                             (sx + (11 if leg else 8), sy + 10), 2)
            return
        if self.kind == "golem":
            body = THEMES[self.theme]["dc1"]
            pygame.draw.rect(surf, shade(body, 0.55), (sx + 1, sy + 3, 12, 10))
            pygame.draw.rect(surf, body, (sx + 2, sy + 1, 10, 10))
            pygame.draw.rect(surf, shade(body, 1.3), (sx + 4, sy + 2, 5, 2))
            pygame.draw.rect(surf, (255, 100, 65), (sx + 4, sy + 5, 2, 2))
            pygame.draw.rect(surf, (255, 100, 65), (sx + 9, sy + 5, 2, 2))
            return
        if self.kind == "wisp":
            glow = (110, 235, 255)
            pulse = int(35 + 20 * (1 + math.sin(self.t * 2)))
            pygame.draw.circle(surf, (pulse, pulse, 255), (sx + 5, sy + 6), 7)
            pygame.draw.circle(surf, glow, (sx + 5, sy + 5), 4)
            pygame.draw.circle(surf, WHITE, (sx + 4, sy + 4), 1)
            return
        if self.kind == "spitter":
            body = THEMES[self.theme]["mon"]
            pygame.draw.ellipse(surf, shade(body, 0.55), (sx, sy + 3, 12, 7))
            pygame.draw.ellipse(surf, body, (sx + 1, sy, 10, 8))
            pygame.draw.circle(surf, (80, 255, 110), (sx + 8, sy + 4), 2)
            pygame.draw.circle(surf, WHITE, (sx + 8, sy + 3), 1)
            return
        if self.kind == "slime":
            a, b = SPR["slime"][self.theme]
            img = a if abs(math.sin(self.t * 0.8)) > 0.35 else b
            pos = (sx - 1, sy - 1)
        elif self.kind == "bat":
            a, b = SPR["bat"][self.theme]
            img = a if int(self.t * 2) % 2 == 0 else b
            pos = (sx - 1, sy - 1)
        else:
            img = SPR["ghost"]
            pos = (sx - 1, sy)
        if self.flash:
            img = img.copy()
            img.fill((255, 255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(img, pos)


# ---------------------------------------------------------------- GAME
CAM_NORMAL, CAM_NEAR, CAM_STUN = 108.0, 150.0, 215.0
GAME_MODES = ("SINH TỒN", "THỬ THÁCH 90 GIÂY", "SĂN QUÁI")


class Game:
    def __init__(self, settings, play=None, on_death=None):
        self.s = settings
        self.play = play or (lambda name: None)
        self.on_death = on_death or (lambda: None)
        self.bg_tmp = pygame.Surface((W, H))
        self.night_overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        self.reset()

    def reset(self):
        self.diff_i = self.s["difficulty"]
        self.cfg = DIFFS[self.diff_i]
        cfg = self.cfg
        self.mode_i = max(0, min(len(GAME_MODES) - 1, self.s.get("mode", 0)))
        self.mode_name = GAME_MODES[self.mode_i]
        self.time_left = 90 * FPS
        self.kill_goal = 15
        self.won = False
        self.px = 100.0
        self.pw, self.ph = PLAYER_W, PLAYER_H
        self.py = float(GROUND - self.ph)
        self.vy = 0.0
        self.on_ground = True
        self.jumps_left = cfg["jumps"]
        self.jump_prev = False
        self.jump_buf = 0
        self.hp = cfg["hp"]
        self.invuln = 0
        self.stun = 0
        self.heat = 0.0
        self.overheated = False
        self.wall = self.px - (500 if self.mode_i in (1, 2) else 70)
        self.frame = 0
        self.kills = 0
        self.dist = 0.0
        self.bullets = []      # [x, y, pierce, set(id quái đã trúng)]
        self.monsters = []
        self.eshots = []       # [x, y, vx, vy]
        self.pickups = []      # [x, y, vy, life]
        self.particles = []    # [x, y, vx, vy, life, color, size]
        self.weather = []      # [x, y, vx, vy, color, size]
        self.buffs = {"shield": 0, "haste": 0, "rapid": 0}
        self.debuffs = {"slow": 0, "poison": 0}
        self.status_msg = ""
        self.status_t = 0
        self.shoot_anim = 0
        self.shoot_cd = 0
        self.spawn_timer = 70
        self.shake = 0
        self.flash = 0
        self.dead = False
        self.new_record = False
        self.death_cause = ""
        self.cam_off = CAM_NORMAL
        self.stage = 0
        self.theme = 0
        self.night = False
        self.prev_theme = 0
        self.prev_night = False
        self.blend = 1.0
        self.banner = ""
        self.banner_t = 0
        self.surge_warn = False
        self.surge_on = False
        for _ in range(40):
            self.spawn_weather(True)

    # ---------------- địa hình / ngày đêm
    def advance_stage(self):
        self.stage += 1
        self.prev_theme, self.prev_night = self.theme, self.night
        pool = min(self.stage + 1, len(THEMES))
        cands = [i for i in range(pool) if i != self.theme]
        if (pool - 1) != self.theme and random.random() < 0.7:
            new = pool - 1                      # ưu tiên biom mới mở khóa
        else:
            new = random.choice(cands)
        self.theme = new
        self.night = (self.stage % 2 == 1)
        self.blend = 0.0
        self.banner = ("ĐÊM" if self.night else "NGÀY") + " · " + THEMES[new]["name"]
        self.banner_t = 240
        self.play("stage")

    # ---------------- hạt / thời tiết
    def burst(self, x, y, color, n=10, size=1):
        if not self.s.get("particles", True):
            return
        for _ in range(n):
            a = random.random() * math.tau
            s = random.random() * 2 + 0.5
            self.particles.append(
                [x, y, math.cos(a) * s, math.sin(a) * s - 0.5,
                 random.randint(15, 30), color, size])

    def spawn_weather(self, initial=False):
        kind = THEMES[self.theme]["weather"]
        x = random.uniform(0, W + 30) if initial else W + random.uniform(0, 30)
        if kind == "leaf":
            p = [x, random.uniform(0, GROUND - 20), random.uniform(-1.4, -0.7),
                 random.uniform(0.15, 0.5),
                 random.choice([(120, 200, 90), (230, 170, 60), (90, 170, 80)]), 1]
        elif kind == "sand":
            p = [x, random.uniform(GROUND - 70, GROUND - 2),
                 random.uniform(-3.2, -2.0), 0.0, (240, 215, 150), 2]
        elif kind == "snow":
            p = [random.uniform(0, W + 30), -4 if not initial else random.uniform(0, GROUND),
                 random.uniform(-0.7, -0.2), random.uniform(0.5, 1.1),
                 (255, 255, 255), random.choice([1, 1, 2])]
        elif kind == "ember":
            p = [x, random.uniform(GROUND - 40, GROUND) if not initial
                 else random.uniform(40, GROUND),
                 random.uniform(-0.6, -0.1), random.uniform(-0.7, -0.25),
                 random.choice([(255, 150, 40), (255, 210, 80), (255, 90, 40)]), 1]
        else:  # mote
            p = [x, random.uniform(10, GROUND - 10), random.uniform(-0.5, -0.1),
                 random.uniform(-0.15, 0.15),
                 random.choice([(110, 235, 255), (230, 140, 255)]), 1]
        self.weather.append(p)

    def update_weather(self):
        if not self.s.get("particles", True):
            self.weather.clear()
            return
        for p in self.weather:
            p[0] += p[2]
            p[1] += p[3]
            p[0] += math.sin(self.frame * 0.05 + p[1] * 0.1) * 0.15
        self.weather = [p for p in self.weather
                        if -12 < p[0] < W + 40 and -10 < p[1] < H]
        if len(self.weather) < 44 and random.random() < 0.6:
            self.spawn_weather()

    def update_particles(self):
        if not self.s.get("particles", True):
            self.particles.clear()
            return
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.08
            p[4] -= 1
        self.particles = [p for p in self.particles if p[4] > 0]

    def update_ambient(self):
        """Phần cập nhật luôn chạy (cả khi menu / đã chết)."""
        if self.blend < 1:
            self.blend = min(1.0, self.blend + 1 / 300)
        if self.banner_t > 0:
            self.banner_t -= 1
        gap = self.px - self.wall
        if self.stun > 0:
            target = CAM_STUN          # bị choáng: kéo camera lùi để thấy tường
        elif gap < 55:
            target = CAM_NEAR
        else:
            target = CAM_NORMAL
        self.cam_off += (target - self.cam_off) * 0.06
        self.update_weather()
        self.update_particles()
        if gap < 260 and random.random() < 0.6:       # tia lửa từ tường
            self.particles.append(
                [self.wall + random.randint(2, 10), random.randint(0, GROUND),
                 random.random() * 1.2 + 0.3, -random.random() * 0.8,
                 random.randint(14, 30), (255, random.randint(100, 200), 40), 1])
        if self.shake > 0:
            self.shake -= 1
        if self.flash > 0:
            self.flash -= 1

    # ---------------- tiện ích
    def player_rect(self):
        return pygame.Rect(int(self.px), int(self.py), self.pw, self.ph)

    def score(self):
        return int((self.dist / 8 + self.kills * 10) * self.cfg["score"])

    # ---------------- cập nhật chính
    def update(self, jump, shoot):
        self.update_ambient()
        if self.dead:
            return
        cfg = self.cfg
        self.frame += 1
        if self.status_t > 0:
            self.status_t -= 1
        if self.shoot_anim > 0:
            self.shoot_anim -= 1
        for effects in (self.buffs, self.debuffs):
            for name in effects:
                effects[name] = max(0, effects[name] - 1)
        if self.debuffs["poison"] and self.frame % (2 * FPS) == 0:
            self.hp -= 1
            self.flash = 3
            self.burst(self.px + 4, self.py + 7, (115, 245, 95), 7)
            if self.hp <= 0:
                self.die("BỊ TRÚNG ĐỘC!")
                return

        if self.mode_i == 1:
            self.time_left -= 1
            if self.time_left <= 0:
                self.finish("HOÀN THÀNH THỬ THÁCH 90 GIÂY!")
                return

        # đổi địa hình / ngày đêm theo thời gian
        period = STAGE_OPTIONS[self.s["stage_idx"]][0]
        if self.frame // (60 * period) > self.stage:
            self.advance_stage()

        # ---- tốc độ
        speed = PLAYER_SPEED
        if self.stun > 0:
            self.stun -= 1
            speed *= cfg["stun_speed"]
        if self.buffs["haste"]:
            speed *= 1.45
        if self.debuffs["slow"]:
            speed *= 0.72
        if self.invuln > 0:
            self.invuln -= 1
        self.px += speed
        self.dist += speed

        # ---- bức tường
        ws = min(cfg["wall_base"] + self.frame * cfg["wall_accel"], cfg["wall_cap"])
        was_warn = self.surge_warn
        self.surge_warn = self.surge_on = False
        if cfg["surge"]:
            ph = self.frame % 1800
            if 1500 <= ph < 1620:
                self.surge_warn = True
                if not was_warn:
                    self.play("warn")
            elif ph >= 1620:
                self.surge_on = True
        if self.surge_on:
            ws *= 1.35
            if self.frame % 4 == 0:
                self.shake = max(self.shake, 2)
        if self.mode_i in (1, 2):
            self.wall = self.px - 500
        else:
            self.wall += ws
            self.wall = max(self.wall, self.px - cfg["maxgap"])

        # ---- nhảy / nhảy đôi
        if jump and not self.jump_prev:
            self.jump_buf = 7
        self.jump_prev = jump
        if self.jump_buf > 0:
            self.jump_buf -= 1
            if self.on_ground:
                self.vy = -5.0
                self.on_ground = False
                self.jumps_left = cfg["jumps"] - 1
                self.jump_buf = 0
                self.burst(self.px + 3, GROUND, (190, 170, 130), 5)
                self.play("jump")
            elif self.jumps_left > 0:
                self.vy = cfg["jump2"]
                self.jumps_left -= 1
                self.jump_buf = 0
                for i in range(8):                      # vòng khói khi nhảy đôi
                    a = math.pi * (0.1 + 0.8 * i / 7)
                    self.particles.append(
                        [self.px + 4, self.py + self.ph, math.cos(a) * 1.4,
                         math.sin(a) * 0.5, 16, (230, 240, 255), 1])
                self.play("jump2")
        if not jump and self.vy < -1.8:                 # nhả sớm -> nhảy thấp
            self.vy = -1.8
        self.vy += 0.26
        self.py += self.vy
        if self.vy >= 0 and self.py + self.ph >= GROUND:
            if not self.on_ground and self.vy > 2.5:
                self.burst(self.px + 3, GROUND, (190, 170, 130), 4)
            self.py = float(GROUND - self.ph)
            self.vy = 0.0
            self.on_ground = True
            self.jumps_left = cfg["jumps"]

        # ---- bắn (+ quá nhiệt ở mức KHÓ)
        if self.shoot_cd > 0:
            self.shoot_cd -= 1
        if cfg["overheat"]:
            if self.overheated:
                self.heat = max(0.0, self.heat - 0.9)
                if self.heat <= 35:
                    self.overheated = False
            else:
                self.heat = max(0.0, self.heat - 0.5)
        if shoot and self.shoot_cd == 0 and not self.overheated:
            self.bullets.append([self.px + 10, self.py + 9, cfg["pierce"], set()])
            self.shoot_cd = max(3, cfg["fire_cd"] // 2) if self.buffs["rapid"] else cfg["fire_cd"]
            self.shoot_anim = 5
            self.burst(self.px + 11, self.py + 9, (255, 230, 100), 2)
            self.play("shoot")
            if cfg["overheat"]:
                self.heat += 17
                if self.heat >= 100:
                    self.heat = 100.0
                    self.overheated = True
                    self.play("hot")
        for b in self.bullets:
            b[0] += 5.5
            if self.frame % 2 == 0:
                self.particles.append([b[0] - 2, b[1], -0.3, 0, 8, (255, 170, 60), 1])
        self.bullets = [b for b in self.bullets
                        if b[0] < self.px + 300 and b[2] > 0]

        # ---- sinh quái
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.spawn()
            lo = max(cfg["spawn_min"], cfg["spawn_lo"] - self.frame // 60)
            interval = random.randint(lo, lo + cfg["spawn_spread"])
            if self.mode_i == 1:
                interval = int(interval * 0.72)
            elif self.mode_i == 2:
                interval = int(interval * 0.82)
            self.spawn_timer = max(24, interval)

        # ---- quái
        pr = self.player_rect()
        for m in self.monsters:
            m.update()
            if m.kind in ("bat", "spitter") and cfg["enemy_fire"]:
                m.fire -= 1
                if m.fire <= 0 and self.px + 40 < m.x < self.px + W - 40:
                    dx = (self.px + 4) - (m.x + 6)
                    dy = (self.py + 7) - (m.y + 3)
                    d = max(1.0, math.hypot(dx, dy))
                    self.eshots.append([m.x + 6, m.y + 4, dx / d * 1.7,
                                        dy / d * 1.7, m.kind == "spitter"])
                    m.fire = random.randint(110, 170)
            mr = m.rect()
            if m.kind != "spike":
                for b in self.bullets:
                    if b[2] <= 0 or id(m) in b[3]:
                        continue
                    if mr.collidepoint(b[0] + 3, b[1]):
                        b[3].add(id(m))
                        b[2] -= 1
                        m.hp -= 1
                        m.flash = 4
                        self.burst(b[0], b[1], (255, 255, 255), 3)
                        if m.hp <= 0:
                            self.kill_monster(m)
                            if self.dead:
                                return
                            break
                        self.play("hit")
            if m.hp > 0 and self.invuln == 0 and pr.colliderect(mr):
                self.burst(m.x + 5, m.y + 4, (255, 80, 80), 14)
                m.hp = 0
                self.hurt("BỊ QUÁI HẠ GỤC!")
                if m.kind == "wisp":
                    self.apply_debuff("slow", "BỊ LÀN SƯƠNG LÀM CHẬM!")
                if self.dead:
                    return
        self.monsters = [m for m in self.monsters
                         if m.hp > 0 and m.x > self.wall - 20 and m.x > self.px - 220]

        # ---- đạn của quái
        for e in self.eshots:
            e[0] += e[2]
            e[1] += e[3]
            if self.invuln == 0 and pr.colliderect(pygame.Rect(int(e[0]) - 2, int(e[1]) - 2, 4, 4)):
                e[0] = -9999
                self.burst(self.px + 4, self.py + 6, (255, 140, 60), 10)
                if len(e) > 4 and e[4]:
                    self.apply_debuff("poison", "BỊ ĐỘC TỐ!")
                else:
                    self.hurt("BỊ ĐẠN QUÁI HẠ GỤC!")
                if self.dead:
                    return
        self.eshots = [e for e in self.eshots
                       if self.px - 120 < e[0] < self.px + W and -20 < e[1] < GROUND]

        # ---- tim hồi máu
        for p in self.pickups:
            p[3] -= 1
            if p[1] < GROUND - 9:
                p[2] += 0.15
                p[1] = min(GROUND - 9.0, p[1] + p[2])
            else:
                p[2] = 0
            if pr.inflate(10, 10).colliderect(pygame.Rect(int(p[0]), int(p[1]), 7, 6)):
                kind = p[4] if len(p) > 4 else "heart"
                if kind == "heart" and self.hp < cfg["hp"]:
                    self.hp += 1
                    self.play("pickup")
                    self.burst(p[0] + 3, p[1] + 3, (255, 120, 150), 12)
                    p[3] = 0
                elif kind != "heart":
                    durations = {"shield": 8 * FPS, "haste": 7 * FPS, "rapid": 7 * FPS}
                    self.buffs[kind] = durations[kind]
                    self.status_msg = {
                        "shield": "KHIÊN NĂNG LƯỢNG!",
                        "haste": "TĂNG TỐC!",
                        "rapid": "BẮN NHANH!",
                    }[kind]
                    self.status_t = 100
                    self.play("pickup")
                    self.burst(p[0] + 3, p[1] + 3, pickup_color(kind), 14)
                    p[3] = 0
        self.pickups = [p for p in self.pickups if p[3] > 0 and p[0] > self.wall]

        # ---- CHẠM TƯỜNG = CHẾT
        if self.mode_i == 0 and self.px < self.wall + 3:
            self.die("BỊ BỨC TƯỜNG NUỐT CHỬNG!")

    def spawn(self):
        kinds = ["slime", "bat", "spike"]
        w = [40, 28, 26]
        kinds.extend(["runner", "spitter"])
        w.extend([18, 12])
        if self.night:
            kinds.append("ghost")
            w.append(24)
            kinds.append("wisp")
            w.append(18)
        if self.theme == 3:
            kinds.append("golem")
            w.append(22)
        kind = random.choices(kinds, w)[0]
        self.add_monster(kind, self.px + W + 20)
        if random.random() < self.cfg["group"]:
            self.add_monster(random.choice(["slime", "bat", "spike", "runner"]),
                             self.px + W + 20 + random.randint(26, 60))

    def add_monster(self, kind, x):
        hp = 999 if kind == "spike" else self.cfg["hp_mult"].get(
            kind, 2 if kind == "golem" else 1)
        self.monsters.append(Monster(kind, x, hp, self.theme))

    def hurt(self, cause):
        if self.buffs.get("shield", 0):
            self.status_msg = "KHIÊN ĐÃ CHẶN ĐÒN!"
            self.status_t = 70
            self.burst(self.px + 4, self.py + 7, (100, 220, 255), 12)
            self.play("hit")
            return
        cfg = self.cfg
        self.hp -= 1
        self.invuln = cfg["invuln"]
        self.stun = cfg["stun"]
        self.shake = 10
        self.flash = 4
        self.play("hurt")
        if self.hp <= 0:
            self.die(cause)

    def die(self, cause):
        self.dead = True
        self.death_cause = cause
        self.shake = 24
        self.flash = 6
        self.burst(self.px + 4, self.py + 7, (255, 60, 60), 40, 2)
        self.play("die")
        self.on_death()

    def finish(self, message):
        self.won = True
        self.dead = True
        self.death_cause = message
        self.play("stage")
        self.on_death()

    def apply_debuff(self, kind, message):
        if self.buffs.get("shield", 0):
            return
        self.debuffs[kind] = max(self.debuffs[kind], 5 * FPS)
        self.status_msg = message
        self.status_t = 100

    def kill_monster(self, m):
        cfg = self.cfg
        self.kills += 1
        self.wall -= cfg["push"]                     # đẩy tường lùi lại
        self.burst(m.x + 5, m.y + 4, (255, 220, 80), 16, 2)
        self.shake = max(self.shake, 3)
        self.play("kill")
        drop = random.random()
        if drop < cfg["drop"]:
            self.pickups.append([m.x + 2, min(m.y, GROUND - 12), 0.0, 700, "heart"])
        elif drop < cfg["drop"] + 0.17:
            kind = random.choice(("shield", "haste", "rapid"))
            self.pickups.append([m.x + 2, min(m.y, GROUND - 12), 0.0, 700, kind])
        if cfg["heal_every"] and self.kills % cfg["heal_every"] == 0 \
                and self.hp < cfg["hp"]:
            self.hp += 1
            self.play("pickup")
        if self.mode_i == 2 and self.kills >= self.kill_goal:
            self.finish("ĐÃ HẠ GỤC ĐỦ QUÁI!")

    # ---------------- vẽ
    def draw(self, canvas, hud=True):
        """Vẽ lên canvas W x H. Trả về độ lệch rung (ox, oy)."""
        cam = self.px - self.cam_off
        t = self.frame

        draw_bg(canvas, self.theme, self.night, cam, t)
        if self.blend < 1:
            draw_bg(self.bg_tmp, self.prev_theme, self.prev_night, cam, t)
            self.bg_tmp.set_alpha(int(255 * (1 - self.blend)))
            canvas.blit(self.bg_tmp, (0, 0))

        for m in self.monsters:
            m.draw(canvas, cam)

        for p in self.pickups:
            sx = int(p[0] - cam)
            bob = int(math.sin(t * 0.15 + p[0]) * 1.5)
            kind = p[4] if len(p) > 4 else "heart"
            canvas.blit(SPR["glow"], (sx - 5, int(p[1]) - 5 + bob),
                        special_flags=pygame.BLEND_RGB_ADD)
            if kind == "heart":
                canvas.blit(SPR["heart"], (sx, int(p[1]) + bob))
            else:
                col = pickup_color(kind)
                pygame.draw.circle(canvas, shade(col, 0.4), (sx + 3, int(p[1]) + 3 + bob), 5)
                pygame.draw.circle(canvas, col, (sx + 3, int(p[1]) + 3 + bob), 3)
                pygame.draw.circle(canvas, WHITE, (sx + 2, int(p[1]) + 2 + bob), 1)

        for b in self.bullets:                           # đạn
            bx, by = int(b[0] - cam), int(b[1])
            canvas.blit(SPR["glow"], (bx - 6, by - 7), special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.rect(canvas, (255, 245, 150), (bx, by, 5, 2))
            pygame.draw.rect(canvas, (255, 150, 40), (bx - 2, by, 2, 2))

        for e in self.eshots:                            # đạn quái
            ex, ey = int(e[0] - cam), int(e[1])
            pygame.draw.circle(canvas, (255, 90, 60), (ex, ey), 3)
            pygame.draw.circle(canvas, (255, 220, 120), (ex, ey), 1)

        # người chơi
        if not self.dead:
            draw_shadow(canvas, self.px - cam + 4, GROUND - (self.py + self.ph))
            if not self.on_ground:
                img = SPR["p_j"]
            else:
                img = SPR["p_a"] if (self.frame // 6) % 2 == 0 else SPR["p_b"]
            player_y = int(self.py + (1 if self.shoot_anim and self.on_ground else 0))
            if self.invuln > 0 and (self.frame // 3) % 2 == 0:
                img = img.copy()
                img.fill((150, 40, 40, 255), special_flags=pygame.BLEND_RGB_ADD)
            player_x = int(self.px - cam) - SPRITE_OFFSET_X
            canvas.blit(img, (player_x, player_y))
            if self.shoot_anim:
                pygame.draw.rect(canvas, (255, 245, 175),
                                 (player_x + 12, player_y + 8, 5, 2))
                pygame.draw.circle(canvas, (255, 170, 55),
                                   (player_x + 17, player_y + 9), 3)
            if self.buffs["shield"]:
                pygame.draw.ellipse(canvas, (90, 220, 255),
                                    (player_x - 2, player_y - 2, 15, 20), 1)
            elif self.buffs["haste"] and self.s.get("particles", True):
                pygame.draw.line(canvas, (255, 220, 90),
                                 (player_x - 4, player_y + 7),
                                 (player_x - 1, player_y + 7), 1)

        # hạt
        if self.s.get("particles", True):
            for p in self.particles:
                x, y = int(p[0] - cam), int(p[1])
                if 0 <= x < W and 0 <= y < H:
                    if p[6] > 1:
                        pygame.draw.rect(canvas, p[5], (x, y, p[6], p[6]))
                    else:
                        canvas.set_at((x, y), p[5])

        # bức tường
        wx = int(self.wall - cam)
        draw_wall(canvas, wx, t)

        # thời tiết (trước mặt)
        streak = THEMES[self.theme]["weather"] == "sand"
        if self.s.get("particles", True):
            for p in self.weather:
                x, y = int(p[0]), int(p[1])
                if 0 <= x < W and 0 <= y < H:
                    if streak:
                        pygame.draw.rect(canvas, p[4], (x, y, 4, 1))
                    elif p[5] > 1:
                        pygame.draw.rect(canvas, p[4], (x, y, p[5], p[5]))
                    else:
                        canvas.set_at((x, y), p[4])

        # ánh sáng ban đêm: tối dần, chỉ sáng quanh người / đạn / tường
        n_str = ((1.0 if self.prev_night else 0.0) * (1 - self.blend)
                 + (1.0 if self.night else 0.0) * self.blend)
        n_str *= self.s.get("lighting", 2) / 3
        if n_str > 0.02:
            ov = self.night_overlay
            ov.fill((8, 10, 36, int(165 * n_str)))
            if not self.dead:
                pcx, pcy = int(self.px - cam) + 4, int(self.py) + 7
                ov.blit(night_glow(46), (pcx - 46, pcy - 46),
                        special_flags=pygame.BLEND_RGBA_MIN)
            for b in self.bullets:
                bx, by = int(b[0] - cam), int(b[1])
                ov.blit(night_glow(16), (bx - 16, by - 16),
                        special_flags=pygame.BLEND_RGBA_MIN)
            if wx > -60:
                ov.blit(night_glow(70), (wx - 70, H // 2 - 70),
                        special_flags=pygame.BLEND_RGBA_MIN)
                ov.blit(night_glow(70), (wx - 70, 20 - 70),
                        special_flags=pygame.BLEND_RGBA_MIN)
                ov.blit(night_glow(70), (wx - 70, H - 20 - 70),
                        special_flags=pygame.BLEND_RGBA_MIN)
            for p in self.pickups:
                ov.blit(night_glow(14), (int(p[0] - cam) - 7, int(p[1]) - 7),
                        special_flags=pygame.BLEND_RGBA_MIN)
            canvas.blit(ov, (0, 0))

        # viền đỏ khi nguy hiểm / bị choáng
        gap = self.px - self.wall
        danger = 0.0
        if not self.dead:
            if self.stun > 0:
                danger = 0.9
            elif gap < 45:
                danger = 0.35 + 0.35 * (((self.frame // 5) % 2))
            elif self.surge_on or (self.surge_warn and (self.frame // 8) % 2 == 0):
                danger = 0.5
        if danger > 0:
            SPR["vignette"].set_alpha(int(255 * danger))
            canvas.blit(SPR["vignette"], (0, 0))
        if self.flash > 0:
            SPR["flash"].set_alpha(40 * self.flash)
            canvas.blit(SPR["flash"], (0, 0))

        if hud:
            self.draw_hud_pixels(canvas, gap)

        if self.shake:
            return random.randint(-1, 1), random.randint(-1, 1)
        return 0, 0

    def draw_hud_pixels(self, canvas, gap):
        cfg = self.cfg
        for i in range(cfg["hp"]):
            canvas.blit(SPR["heart"] if i < self.hp else SPR["heart_e"], (6 + i * 9, 6))
        for i in range(cfg["jumps"]):
            cx = 9 + i * 8
            if i < self.jumps_left:
                pygame.draw.circle(canvas, (255, 255, 255), (cx, 18), 3)
            else:
                pygame.draw.circle(canvas, (90, 90, 115), (cx, 18), 3, 1)
        if cfg["overheat"]:
            pygame.draw.rect(canvas, (0, 0, 0), (5, 24, 48, 7))
            frac = self.heat / 100
            if self.overheated:
                col = (255, 40, 40) if (self.frame // 4) % 2 == 0 else (120, 20, 20)
            else:
                col = mix((255, 210, 60), (255, 60, 40), frac)
            pygame.draw.rect(canvas, col, (6, 25, int(46 * frac), 5))
        if self.buffs["shield"]:
            pygame.draw.rect(canvas, (80, 205, 255), (6, 32, 3, 3))
        if self.buffs["haste"]:
            pygame.draw.rect(canvas, (255, 220, 70), (12, 32, 3, 3))
        if self.buffs["rapid"]:
            pygame.draw.rect(canvas, (255, 145, 55), (18, 32, 3, 3))
        if self.debuffs["slow"]:
            pygame.draw.rect(canvas, (160, 120, 255), (24, 32, 3, 3))
        if self.debuffs["poison"]:
            pygame.draw.rect(canvas, (105, 235, 90), (30, 32, 3, 3))
        # thanh khoảng cách tới tường
        bw = 120
        bx = (W - bw) // 2
        g = max(0.0, min(self.px - self.wall, 160.0)) / 160.0
        pygame.draw.rect(canvas, (0, 0, 0), (bx - 1, 5, bw + 2, 9))
        col = (80, 220, 90) if g > 0.45 else (240, 200, 50) if g > 0.22 else (240, 50, 50)
        pygame.draw.rect(canvas, col, (bx, 6, int(bw * g), 7))
        pygame.draw.rect(canvas, (190, 30, 40), (bx - 9, 4, 6, 10))
        pygame.draw.rect(canvas, (60, 115, 225), (bx + bw + 4, 4, 6, 10))
        if self.surge_warn and (self.frame // 8) % 2 == 0:
            pygame.draw.rect(canvas, (255, 0, 0), (0, 0, W, 2))
            pygame.draw.rect(canvas, (255, 0, 0), (0, H - 2, W, 2))


# ---------------------------------------------------------------- APP
MENUS = ("menu", "settings", "paused")
SCALES = [1, 2, 3, 4, 5, 6]


class App:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        build_sprites()
        self.s = load_settings()
        self.audio = Audio(self.s)
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((W, H))
        self.fonts = {}
        self.screen = None
        self.apply_display()
        self.game = None
        self.demo = Game(self.s)
        self.demo.px = 400.0
        self.state = "menu"
        self.prev = "menu"
        self.sel = 0
        self.rebind_key = None
        self.overlay_cache = None
        self.layout()

    # ---------------- cài đặt / hiển thị
    def save(self):
        save_settings(self.s)

    def apply_display(self):
        if self.s["fullscreen"]:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            sc = self.s["scale"]
            try:                       # không để cửa sổ to hơn màn hình
                dw, dh = pygame.display.get_desktop_sizes()[0]
                sc = min(sc, max(1, min((dw - 60) // W, (dh - 120) // H)))
            except Exception:
                pass
            self.screen = pygame.display.set_mode((W * sc, H * sc))
        pygame.display.set_caption("CHẠY TRỐN BỨC TỬ")
        self.overlay_cache = None

    def layout(self):
        sw, sh = self.screen.get_size()
        self.scale = max(1, min(sw // W, sh // H))
        self.rw, self.rh = W * self.scale, H * self.scale
        self.ox, self.oy = (sw - self.rw) // 2, (sh - self.rh) // 2
        self.k = self.rw / 1280          # hệ số UI (toạ độ ảo 1280x720)

    # ---------------- chữ (có dấu tiếng Việt)
    def font(self, size):
        key = max(8, int(size * self.k))
        f = self.fonts.get(key)
        if f is None:
            f = pygame.font.SysFont(
                "segoeui,arial,tahoma,dejavusans,liberationsans,freesans",
                key, bold=True)
            self.fonts[key] = f
        return f

    def text(self, s, vx, vy, size=28, color=WHITE, align="c", alpha=255):
        f = self.font(size)
        img = f.render(s, True, color)
        sh = f.render(s, True, (0, 0, 0))
        if alpha < 255:
            img.set_alpha(alpha)
            sh.set_alpha(alpha)
        r = img.get_rect()
        X = self.ox + vx * self.k
        Y = self.oy + vy * self.k
        if align == "c":
            r.center = (X, Y)
        elif align == "l":
            r.midleft = (X, Y)
        else:
            r.midright = (X, Y)
        d = max(2, int(2 * self.k))
        self.screen.blit(sh, (r.x + d, r.y + d))
        self.screen.blit(img, r)

    def dim(self, alpha):
        size = self.screen.get_size()
        if self.overlay_cache is None or self.overlay_cache.get_size() != size:
            self.overlay_cache = pygame.Surface(size, pygame.SRCALPHA)
        self.overlay_cache.fill((0, 0, 20, alpha))
        self.screen.blit(self.overlay_cache, (0, 0))

    # ---------------- hành động menu
    def goto(self, state, sel=0):
        self.state = state
        self.sel = sel

    def start_game(self):
        self.game = Game(self.s, self.audio.play, self.on_death)
        self.goto("playing")

    def on_death(self):
        sc = self.game.score()
        d = self.game.diff_i
        if sc > self.s["best"][d]:
            self.s["best"][d] = sc
            self.game.new_record = True
            self.save()

    def open_settings(self):
        self.prev = self.state
        self.goto("settings")

    def back(self):
        if self.state == "settings":
            self.goto(self.prev)
        elif self.state == "paused":
            self.goto("playing")

    def quit(self):
        self.save()
        pygame.quit()
        sys.exit()

    def chg_diff(self, d):
        self.s["difficulty"] = (self.s["difficulty"] + d) % len(DIFFS)
        self.save()

    def chg_stage(self, d):
        self.s["stage_idx"] = (self.s["stage_idx"] + d) % len(STAGE_OPTIONS)
        self.save()

    def chg_mode(self, d):
        self.s["mode"] = (self.s["mode"] + d) % len(GAME_MODES)
        self.save()

    def chg_vol(self, d):
        self.s["volume"] = max(0, min(10, self.s["volume"] + d))
        self.save()
        self.audio.play("ok")

    def chg_shake(self, d):
        self.s["shake"] = not self.s["shake"]
        self.save()

    def chg_lighting(self, d):
        self.s["lighting"] = (self.s["lighting"] + d) % 4
        self.save()

    def chg_particles(self, d):
        self.s["particles"] = not self.s["particles"]
        self.save()

    def chg_full(self, d):
        self.s["fullscreen"] = not self.s["fullscreen"]
        self.apply_display()
        self.save()

    def chg_scale(self, d):
        i = SCALES.index(self.s["scale"])
        self.s["scale"] = SCALES[(i + d) % len(SCALES)]
        if not self.s["fullscreen"]:
            self.apply_display()
        self.save()

    def start_rebind(self, key):
        self.rebind_key = key
        self.state = "rebind"

    def reset_defaults(self):
        best = self.s["best"]
        self.s.update(json.loads(json.dumps(DEFAULTS)))
        self.s["best"] = best
        self.apply_display()
        self.save()

    def items(self):
        """Danh sách mục: (nhãn, hàm khi Enter, hàm đổi giá trị hoặc None)."""
        st, s = self.state, self.s

        def opt(label, val, fn):
            return (f"{label}:   <  {val}  >", lambda: fn(1), fn)

        if st == "menu":
            return [("CHƠI NGAY", self.start_game, None),
                    opt("ĐỘ KHÓ", DIFFS[s["difficulty"]]["name"], self.chg_diff),
                    opt("CHẾ ĐỘ", GAME_MODES[s["mode"]], self.chg_mode),
                    ("CÀI ĐẶT", self.open_settings, None),
                    ("THOÁT", self.quit, None)]
        if st == "paused":
            return [("TIẾP TỤC", lambda: self.goto("playing"), None),
                    ("CHƠI LẠI", self.start_game, None),
                    ("CÀI ĐẶT", self.open_settings, None),
                    ("VỀ MENU CHÍNH", lambda: self.goto("menu"), None)]
        return [
            opt("Độ khó", DIFFS[s["difficulty"]]["name"], self.chg_diff),
            opt("Đổi địa hình mỗi", STAGE_OPTIONS[s["stage_idx"]][1], self.chg_stage),
            opt("Âm lượng", f"{s['volume']}/10", self.chg_vol),
            opt("Rung màn hình", "BẬT" if s["shake"] else "TẮT", self.chg_shake),
            opt("Toàn màn hình", "BẬT" if s["fullscreen"] else "TẮT", self.chg_full),
            opt("Độ phân giải cửa sổ", f"{W * s['scale']}x{H * s['scale']}", self.chg_scale),
            opt("Ánh sáng ban đêm", ("TẮT", "THẤP", "VỪA", "CAO")[s["lighting"]],
                lambda d: self.chg_lighting(d)),
            opt("Hạt & thời tiết", "BẬT" if s["particles"] else "TẮT",
                lambda d: self.chg_particles(d)),
            (f"Phím nhảy:   [ {key_name(s['key_jump'])} ]",
             lambda: self.start_rebind("key_jump"), None),
            (f"Phím bắn:   [ {key_name(s['key_shoot'])} ]",
             lambda: self.start_rebind("key_shoot"), None),
            ("KHÔI PHỤC MẶC ĐỊNH", self.reset_defaults, None),
            ("QUAY LẠI", self.back, None),
        ]

    def item_ys(self, n):
        sp = 62 if n <= 4 else 52 if n <= 8 else 40
        y0 = 425 - (n - 1) * sp / 2
        return [y0 + i * sp for i in range(n)], sp

    # ---------------- sự kiện
    def activate(self):
        items = self.items()
        if 0 <= self.sel < len(items):
            self.audio.play("ok")
            items[self.sel][1]()

    def change(self, d):
        items = self.items()
        if 0 <= self.sel < len(items) and items[self.sel][2]:
            self.audio.play("move")
            items[self.sel][2](d)

    def hover(self, pos):
        items = self.items()
        ys, sp = self.item_ys(len(items))
        vx = (pos[0] - self.ox) / self.k
        vy = (pos[1] - self.oy) / self.k
        for i, y in enumerate(ys):
            if abs(vy - y) < sp / 2 and abs(vx - 640) < 380:
                if self.sel != i:
                    self.sel = i
                    self.audio.play("move")
                return True
        return False

    def on_key(self, k):
        if k == pygame.K_F11:
            self.chg_full(1)
            return
        st = self.state
        if st == "rebind":
            if k != pygame.K_ESCAPE:
                self.s[self.rebind_key] = k
                self.save()
            self.state = "settings"
            return
        if st in MENUS:
            n = len(self.items())
            if k in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % n
                self.audio.play("move")
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % n
                self.audio.play("move")
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.activate()
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.change(-1)
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.change(1)
            elif k == pygame.K_ESCAPE:
                self.back()
        elif st == "playing":
            if k in (pygame.K_ESCAPE, pygame.K_p):
                if self.game.dead:
                    self.goto("menu")
                else:
                    self.goto("paused")
            elif k in (pygame.K_r, pygame.K_RETURN) and self.game.dead:
                self.start_game()
            elif k == pygame.K_F6 and not self.game.dead:
                self.game.advance_stage()          # chức năng thử nghiệm

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.quit()
            elif e.type == pygame.KEYDOWN:
                self.on_key(e.key)
            elif e.type == pygame.MOUSEMOTION and self.state in MENUS:
                self.hover(e.pos)
            elif (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                  and self.state in MENUS):
                if self.hover(e.pos):
                    self.activate()

    # ---------------- cập nhật
    def in_pause_bg(self):
        return self.state == "paused" or (
            self.state in ("settings", "rebind") and self.prev == "paused")

    def update(self):
        if self.state == "playing":
            keys = pygame.key.get_pressed()
            jump = (keys[self.s["key_jump"]] or keys[pygame.K_UP]
                    or keys[pygame.K_w])
            shoot = keys[self.s["key_shoot"]] or pygame.mouse.get_pressed()[0]
            self.game.update(jump, shoot)
        elif not self.in_pause_bg():
            d = self.demo                     # nền menu: tự chạy, đổi biome liên tục
            d.frame += 1
            d.px += PLAYER_SPEED
            d.dist += PLAYER_SPEED
            d.wall = d.px - 500
            if d.frame % 480 == 0:
                d.advance_stage()
            d.update_ambient()

    # ---------------- vẽ
    def draw_menu(self, title, subtitle=None):
        items = self.items()
        ys, sp = self.item_ys(len(items))
        self.text(title, 640, 95, 76 if self.state == "menu" else 56, RED)
        if subtitle:
            self.text(subtitle, 640, 160, 26, GRAY)
        for i, (label, _, _) in enumerate(items):
            sel = (i == self.sel)
            if sel:
                w, h = int(760 * self.k), int((sp - 8) * self.k)
                box = pygame.Surface((w, h), pygame.SRCALPHA)
                box.fill((255, 255, 255, 38))
                r = box.get_rect(center=(self.ox + 640 * self.k,
                                         self.oy + ys[i] * self.k))
                self.screen.blit(box, r)
                pygame.draw.rect(self.screen, YELLOW, r, max(2, int(3 * self.k)))
            self.text(label, 640, ys[i], 34, YELLOW if sel else WHITE)

    def draw_hud(self):
        g = self.game
        cfg = g.cfg
        best = self.s["best"][g.diff_i]
        self.text(f"ĐIỂM: {g.score()}", 1256, 30, 32, WHITE, "r")
        self.text(f"KỶ LỤC ({cfg['name']}): {best}", 1256, 66, 24, LBLUE, "r")
        self.text(f"QUÁI HẠ: {g.kills}", 1256, 98, 24, YELLOW, "r")
        secs = int(g.frame / 60)
        self.text(f"{secs // 60:02d}:{secs % 60:02d}", 1256, 130, 24, GRAY, "r")
        where = ("ĐÊM" if g.night else "NGÀY") + " · " + THEMES[g.theme]["name"]
        self.text(where, 24, 128, 22, GRAY, "l")
        self.text(g.mode_name, 24, 158, 22, YELLOW, "l")
        if g.mode_i == 1:
            left = max(0, g.time_left // FPS)
            self.text(f"CÒN LẠI: {left // 60:02d}:{left % 60:02d}",
                      24, 188, 22, (255, 215, 90), "l")
        elif g.mode_i == 2:
            self.text(f"SĂN QUÁI: {g.kills}/{g.kill_goal}",
                      24, 188, 22, (255, 215, 90), "l")
        self.text("P: tạm dừng", 24, 696, 20, GRAY, "l")
        self.text("KHOẢNG CÁCH TỚI TƯỜNG", 640, 62, 18, GRAY)

    def draw_alerts(self):
        g = self.game
        if g.dead:
            return
        pulse = 160 + int(95 * math.sin(g.frame * 0.25))
        if g.stun > 0:
            self.text("TƯỜNG ĐANG TIẾN TỚI!", 640, 120, 44, RED, alpha=pulse)
        elif g.surge_warn:
            self.text("!! TƯỜNG SẮP LAO TỚI !!", 640, 120, 44, RED, alpha=pulse)
        elif g.surge_on:
            self.text("TƯỜNG ĐANG LAO TỚI! CHẠY!", 640, 120, 44, RED, alpha=pulse)
        if g.overheated:
            self.text("SÚNG QUÁ NHIỆT!", 640, 640, 36, (255, 140, 60), alpha=pulse)
        if g.status_t > 0:
            self.text(g.status_msg, 640, 165, 34, (120, 240, 170), alpha=pulse)
        if g.banner_t > 0:
            a = int(255 * min(1.0, g.banner_t / 60, (240 - g.banner_t) / 30 + 0.01))
            a = max(0, min(255, a))
            self.text(g.banner, 640, 250, 60, YELLOW, alpha=a)
            self.text("ĐỊA HÌNH MỚI", 640, 306, 26, WHITE, alpha=a)

    def render(self):
        self.layout()
        scr = self.screen
        scr.fill((0, 0, 0))
        playing = self.state == "playing"
        in_game = playing or self.in_pause_bg()
        g = self.game if in_game else self.demo
        sx, sy = g.draw(self.canvas, hud=in_game)
        if not self.s["shake"] or not playing:
            sx = sy = 0
        frame = pygame.transform.scale(self.canvas, (self.rw, self.rh))
        scr.blit(frame, (self.ox + sx * self.scale, self.oy + sy * self.scale))

        if playing:
            self.draw_hud()
            self.draw_alerts()
            if g.dead:
                self.dim(150)
                self.text("CHIẾN THẮNG!" if g.won else g.death_cause,
                          640, 230, 64, (120, 240, 150) if g.won else RED)
                self.text(f"Điểm: {g.score()}   |   Quái hạ: {g.kills}   |   "
                          f"Chế độ: {g.mode_name}", 640, 320, 34)
                if g.new_record:
                    self.text("*** KỶ LỤC MỚI! ***", 640, 375, 36, YELLOW)
                if not g.won:
                    self.text(g.death_cause, 640, 415, 28, RED)
                self.text("R / Enter: chơi lại      Esc: menu chính",
                          640, 450, 30, YELLOW)
            elif g.frame < 360:
                self.text("Chạy! Bắn quái để đẩy bức tường lùi lại!",
                          640, 180, 36, YELLOW)
                self.text(
                    f"{key_name(self.s['key_jump'])}: nhảy (nhấn 2 lần = nhảy đôi)   |   "
                    f"{key_name(self.s['key_shoot'])} / chuột trái: bắn",
                    640, 224, 26)
        elif self.state == "menu":
            self.dim(110)
            cfgd = DIFFS[self.s["difficulty"]]
            best = self.s["best"][self.s["difficulty"]]
            self.draw_menu("CHẠY TRỐN BỨC TỬ",
                           "Bắn quái, nhảy qua gai, đừng để bức tường chạm vào bạn!")
            self.text(f"[{cfgd['name']}]  {cfgd['desc']}", 640, 570, 22, cfgd["color"])
            self.text(GAME_MODES[self.s["mode"]], 640, 602, 21, YELLOW)
            self.text(f"Kỷ lục ({cfgd['name']}): {best}", 640, 636, 30, LBLUE)
        elif self.state == "paused":
            self.dim(150)
            self.draw_menu("TẠM DỪNG")
        else:  # settings / rebind
            self.dim(170)
            self.draw_menu("CÀI ĐẶT")
            if self.sel == 0:
                cfgd = DIFFS[self.s["difficulty"]]
                self.text(cfgd["desc"], 640, 660, 21, cfgd["color"])
                if self.prev == "paused":
                    self.text("(độ khó mới áp dụng từ ván sau)", 640, 636, 20, GRAY)
            elif self.sel == 1:
                self.text("Mỗi chu kỳ: đổi ngày/đêm và mở thêm biom mới. "
                          "Dùng 30 GIÂY để xem thử.", 640, 660, 21, GRAY)
            elif self.sel == 5:
                self.text("F11 bật/tắt toàn màn hình. Chế độ cửa sổ giữ tỷ lệ pixel.",
                          640, 660, 21, GRAY)
            elif self.sel == 6:
                self.text("Điều chỉnh độ sáng và vùng sáng khi chơi ban đêm.",
                          640, 660, 21, GRAY)
            elif self.sel == 7:
                self.text("Tắt hạt nếu muốn ưu tiên hiệu năng.", 640, 660, 21, GRAY)
            self.text("↑↓: chọn     ←→: đổi giá trị     Enter: xác nhận     Esc: quay lại",
                      640, 695, 21, GRAY)
            if self.state == "rebind":
                self.dim(190)
                name = "NHẢY" if self.rebind_key == "key_jump" else "BẮN"
                self.text(f"Nhấn phím mới cho: {name}", 640, 320, 50, YELLOW)
                self.text("(Esc để huỷ)", 640, 390, 28, GRAY)
        pygame.display.flip()

    # ---------------- vòng lặp chính
    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(FPS)


if __name__ == "__main__":
    App().run()