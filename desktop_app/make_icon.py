"""Draws icon.ico (drone + live dot). Run once: python make_icon.py"""
from PIL import Image, ImageDraw

S = 1024  # draw large, downscale for smooth edges
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Background: rounded square with a subtle vertical gradient
bg = Image.new("RGBA", (S, S))
for y in range(S):
    t = y / S
    bg.paste((int(26 - 9 * t), int(34 - 14 * t), int(48 - 22 * t), 255), (0, y, S, y + 1))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=220, fill=255)
img.paste(bg, (0, 0), mask)

cyan = (79, 209, 255, 255)
c, arm, rotor, w = S // 2, 255, 130, 60
dark = (20, 25, 33, 255)

# Arms (X shape) and rotor rings
corners = [(c + dx * arm, c + dy * arm + 40) for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]]
for x, y in corners:
    d.line((c, c + 40, x, y), fill=cyan, width=w)
for x, y in corners:
    d.ellipse((x - rotor, y - rotor, x + rotor, y + rotor), fill=dark, outline=cyan, width=w - 12)
    d.ellipse((x - 28, y - 28, x + 28, y + 28), fill=cyan)

# Body + camera lens
d.rounded_rectangle((c - 115, c - 105, c + 115, c + 185), radius=70, fill=cyan)
d.ellipse((c - 50, c + 70, c + 50, c + 170), fill=(17, 20, 24, 255))
d.ellipse((c - 20, c + 100, c + 20, c + 140), fill=cyan)

# Red "live" dot with a dark ring, top-right
r, lx, ly = 62, c, 150
d.ellipse((lx - r, ly - r, lx + r, ly + r), fill=(239, 68, 68, 255))

img = img.resize((256, 256), Image.LANCZOS)
img.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save("icon.png")
print("wrote icon.ico + icon.png")
