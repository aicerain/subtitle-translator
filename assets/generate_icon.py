"""
图标生成器 — 用 Pillow 直接绘制(不依赖 cairo / SVG),输出:
- icon_1024.png         : 主图,Mac & Win 都用
- icon.iconset/         : macOS 标准 iconset 目录(10 个尺寸)
- icon.ico              : Windows 多分辨率 ICO

设计:macOS Big Sur 风格 squircle,蓝→紫斜向渐变,
中上白色播放三角(柔和阴影),下方双字幕条(白色 + 半透明),
左侧色块标注 A / 文 暗示中英互译。
"""
import math
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Windows CI 默认 cp1252 编码,打印中文会 UnicodeEncodeError
# 强制 stdout/stderr 用 utf-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


ROOT = Path(__file__).resolve().parent
SIZE = 1024


# ==================== 调色 ====================
COLOR_TOP_LEFT = (10, 132, 255)     # #0A84FF Apple 蓝
COLOR_BOT_RIGHT = (94, 92, 230)     # #5E5CE6 Apple 紫
WHITE = (255, 255, 255)


# ==================== 字体定位 ====================
def find_font(size: int, cjk: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []
    if cjk:
        candidates = [
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except OSError:
                pass
    return ImageFont.load_default()


# ==================== 绘制 ====================

def gradient_squircle(size: int) -> Image.Image:
    """生成 squircle 形状 + 斜向渐变,返回 RGBA 图像"""
    # 1. 斜向 RGB 渐变
    grad = Image.new("RGB", (size, size))
    px = grad.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            r = int(COLOR_TOP_LEFT[0] * (1 - t) + COLOR_BOT_RIGHT[0] * t)
            g = int(COLOR_TOP_LEFT[1] * (1 - t) + COLOR_BOT_RIGHT[1] * t)
            b = int(COLOR_TOP_LEFT[2] * (1 - t) + COLOR_BOT_RIGHT[2] * t)
            px[x, y] = (r, g, b)

    # 2. squircle 蒙版: |x|^n + |y|^n <= 1
    n = 5.0
    cx = cy = size / 2
    radius = size / 2
    mask = Image.new("L", (size, size), 0)
    mpx = mask.load()
    for y in range(size):
        for x in range(size):
            dx = (x - cx) / radius
            dy = (y - cy) / radius
            d = (abs(dx) ** n + abs(dy) ** n) ** (1 / n)
            if d <= 0.97:
                mpx[x, y] = 255
            elif d <= 1.0:
                # 抗锯齿过渡
                mpx[x, y] = int(255 * (1.0 - d) / 0.03)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def add_subtle_glow(img: Image.Image) -> Image.Image:
    """顶部加一道极淡的白色高光(玻璃质感),严格剪到 squircle 内"""
    size = img.width
    # 单独画一张高光 RGBA
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    # 画一个椭圆形的柔和白色高光,在上半部
    ellipse_w = int(size * 0.95)
    ellipse_h = int(size * 0.5)
    ex = (size - ellipse_w) // 2
    ey = -int(size * 0.15)
    for i in range(40):
        a = max(0, 18 - i // 3)
        hd.ellipse(
            [ex - i, ey - i, ex + ellipse_w + i, ey + ellipse_h + i],
            outline=(255, 255, 255, a),
        )
    highlight = highlight.filter(ImageFilter.GaussianBlur(20))

    # 用底图的 alpha 通道做蒙版,保证不画到 squircle 外
    base_alpha = img.split()[3]
    # 把高光的 alpha 与 base_alpha 相乘 (0..255 → 0..1 乘法)
    h_alpha = highlight.split()[3]
    new_alpha = Image.eval(h_alpha, lambda v: v).point(lambda v: v)
    # 用底图 alpha 限制 (相当于 min(h_alpha, base_alpha))
    combined = Image.eval(h_alpha, lambda v: v)
    # 实际操作:通过 Image.composite 让 highlight 只显示在 base 非透明的部分
    masked_highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    masked_highlight.paste(highlight, (0, 0), base_alpha)
    return Image.alpha_composite(img, masked_highlight)


def draw_play_triangle(img: Image.Image) -> Image.Image:
    """中上画一个圆润的白色播放三角(带柔和阴影)"""
    size = img.width
    # 三角形参数
    cx = size / 2 + size * 0.02   # 略偏右(视觉补偿,因为三角向右指)
    cy = size * 0.40              # 上 1/3 区域
    side = size * 0.30
    h = side * math.sqrt(3) / 2   # 等边三角高
    p1 = (cx - h / 2, cy - side / 2)
    p2 = (cx - h / 2, cy + side / 2)
    p3 = (cx + h / 2, cy)

    # 1. 阴影层(向下偏移 + 模糊)
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    off = int(size * 0.012)
    sd.polygon(
        [(p1[0], p1[1] + off), (p2[0], p2[1] + off), (p3[0], p3[1] + off)],
        fill=(0, 0, 0, 70),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(int(size * 0.012)))
    img = Image.alpha_composite(img, shadow_layer)

    # 2. 实心白色三角(角点微圆角效果通过缩进顶点 + 适当抗锯齿实现)
    tri_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tri_layer)
    td.polygon([p1, p2, p3], fill=(255, 255, 255, 255))
    # 极轻微的抗锯齿模糊使边缘柔和
    tri_layer = tri_layer.filter(ImageFilter.GaussianBlur(0.6))
    img = Image.alpha_composite(img, tri_layer)
    return img


def draw_subtitle_section(img: Image.Image) -> Image.Image:
    """下方两条圆角字幕条 + 左侧 A / 文 标签徽章"""
    size = img.width
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    bar_h = int(size * 0.085)
    radius = bar_h // 2

    # 上条 (原文) — 不透明白
    y1 = int(size * 0.66)
    x1 = int(size * 0.20)
    x2 = int(size * 0.84)
    draw.rounded_rectangle(
        [x1, y1, x2, y1 + bar_h], radius=radius, fill=(255, 255, 255, 248),
    )
    # 下条 (译文) — 半透明白
    y2 = y1 + bar_h + int(size * 0.04)
    x3 = int(size * 0.20)
    x4 = int(size * 0.66)   # 略短,暗示译文不一定等长
    draw.rounded_rectangle(
        [x3, y2, x4, y2 + bar_h], radius=radius, fill=(255, 255, 255, 175),
    )

    img = Image.alpha_composite(img, layer)

    # 左侧徽章 (覆盖在字幕条左端,显示 A / 文 表示语言)
    badge_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_layer)
    badge = int(bar_h * 1.55)
    bx = int(size * 0.13)

    # 上徽章 A — 蓝色
    bcy1 = y1 + bar_h // 2 - badge // 2
    bd.rounded_rectangle(
        [bx, bcy1, bx + badge, bcy1 + badge],
        radius=int(badge * 0.30), fill=COLOR_TOP_LEFT,
    )
    # 下徽章 文 — 紫色
    bcy2 = y2 + bar_h // 2 - badge // 2
    bd.rounded_rectangle(
        [bx, bcy2, bx + badge, bcy2 + badge],
        radius=int(badge * 0.30), fill=COLOR_BOT_RIGHT,
    )
    img = Image.alpha_composite(img, badge_layer)

    # 文字层 (分开做以便用不同字体)
    txt = Image.new("RGBA", img.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(txt)
    font_en = find_font(int(badge * 0.65), cjk=False)
    font_zh = find_font(int(badge * 0.65), cjk=True)

    def center_text(d, x, y, w, h, text, font):
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        d.text((x + (w - tw) // 2 - bbox[0], y + (h - th) // 2 - bbox[1]),
               text, font=font, fill=WHITE)

    center_text(td, bx, bcy1, badge, badge, "A", font_en)
    center_text(td, bx, bcy2, badge, badge, "文", font_zh)
    img = Image.alpha_composite(img, txt)
    return img


# ==================== 主流程 ====================

def build_icon(size: int = SIZE) -> Image.Image:
    img = gradient_squircle(size)
    img = add_subtle_glow(img)
    img = draw_play_triangle(img)
    img = draw_subtitle_section(img)
    return img


def main():
    print(f"==> 生成 {SIZE}×{SIZE} 主图...")
    master = build_icon(SIZE)
    master_path = ROOT / "icon_1024.png"
    master.save(master_path, "PNG")
    print(f"   ✓ {master_path}")

    macos_sizes = [
        (16,   "icon_16x16.png"),
        (32,   "icon_16x16@2x.png"),
        (32,   "icon_32x32.png"),
        (64,   "icon_32x32@2x.png"),
        (128,  "icon_128x128.png"),
        (256,  "icon_128x128@2x.png"),
        (256,  "icon_256x256.png"),
        (512,  "icon_256x256@2x.png"),
        (512,  "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    iconset_dir = ROOT / "icon.iconset"
    iconset_dir.mkdir(exist_ok=True)
    print(f"\n==> 生成 macOS iconset → {iconset_dir.name}/")
    for sz, name in macos_sizes:
        if sz == SIZE:
            scaled = master
        else:
            scaled = master.resize((sz, sz), Image.LANCZOS)
        out = iconset_dir / name
        scaled.save(out, "PNG")
        print(f"   ✓ {name:32s} ({sz}×{sz})")

    print("\n==> 生成 Windows icon.ico (多分辨率)...")
    ico_path = ROOT / "icon.ico"
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"   ✓ {ico_path}")

    print()
    print("=" * 60)
    print("完成!Mac 端把 icon.iconset 转 .icns:")
    print("   iconutil -c icns assets/icon.iconset -o assets/icon.icns")
    print()
    print("或直接运行: ./assets/make_icns.sh")


if __name__ == "__main__":
    main()
