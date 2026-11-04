"""런처 아이콘(launcher.ico) — 그라데이션 스퀘어클 위에 입체 키캡과 초록 표시등. 1024px 로 그려 줄인다."""
from PIL import Image, ImageDraw, ImageFilter

S = 1024


def vgrad(w, h, top, bot):
    g = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(g)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,))
    return g


def rmask(box, r, size=S):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=r, fill=255)
    return m


im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
# 바탕 스퀘어클: 코발트 → 남색
bg = (40, 40, S - 40, S - 40)
im.paste(vgrad(S, S, (88, 120, 255), (34, 52, 190)), (0, 0), rmask(bg, 230))
# 윗부분 광택
gloss = Image.new("RGBA", (S, S), (255, 255, 255, 0))
ImageDraw.Draw(gloss).ellipse((-200, -620, S + 200, 420), fill=(255, 255, 255, 38))
im.alpha_composite(Image.composite(gloss, Image.new("RGBA", (S, S), (0, 0, 0, 0)), rmask(bg, 230)))

# 키캡 그림자
sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle((240, 330, S - 240, S - 170), radius=110, fill=(10, 20, 80, 150))
im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(40)))
# 초록 언더글로
glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse((300, S - 260, S - 300, S - 180), fill=(43, 210, 120, 230))
im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(34)))
# 키캡 옆면 + 윗면
side = (230, 250, S - 230, S - 205)
im.paste(vgrad(S, S, (214, 220, 230), (168, 176, 190)), (0, 0), rmask(side, 110))
top = (230, 230, S - 230, S - 265)
im.paste(vgrad(S, S, (255, 255, 255), (236, 239, 244)), (0, 0), rmask(top, 104))
d = ImageDraw.Draw(im)
# 표시등 + 각인 막대
d.ellipse((S // 2 - 34, 560, S // 2 + 34, 628), fill=(43, 194, 116))
d.rounded_rectangle((350, 360, S - 350, 410), radius=25, fill=(28, 36, 52))
d.rounded_rectangle((350, 448, S - 470, 486), radius=19, fill=(150, 160, 176))

im.save("launcher.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
im.resize((256, 256), Image.LANCZOS).save("out/launcher_icon_preview.png")
