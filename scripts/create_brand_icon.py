"""Build the minimal two-tree brand icon; run with Python + Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / 'assets'
SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#faf6eb"/>
<path d="M20 32v18M44 34v16" stroke="#77563e" stroke-width="6" stroke-linecap="round"/>
<circle cx="24" cy="25" r="17" fill="#294e36"/>
<circle cx="43" cy="30" r="14" fill="#a7b887"/>
<path d="M31 42q-9 6-3 14" fill="none" stroke="#faf6eb" stroke-width="5" stroke-linecap="round"/>
</svg>'''

if __name__ == '__main__':
    (ROOT / 'branding' / 'shu-tsan-mark.svg').write_text(SVG, encoding='utf-8')
    scale = 8
    image = Image.new('RGBA', (64*scale, 64*scale))
    draw = ImageDraw.Draw(image)
    def box(values):
        return tuple(v*scale for v in values)
    draw.rounded_rectangle(box((0, 0, 64, 64)), radius=14*scale, fill='#faf6eb')
    for x, y in [(20, 32), (44, 34)]:
        draw.line(box((x, y, x, 50)), fill='#77563e', width=6*scale)
    draw.ellipse(box((7, 8, 41, 42)), fill='#294e36')
    draw.ellipse(box((29, 16, 57, 44)), fill='#a7b887')
    draw.line([(31*scale, 42*scale), (26*scale, 49*scale), (28*scale, 56*scale)], fill='#faf6eb', width=5*scale, joint='curve')
    image.save(ROOT / 'favicon.ico', sizes=[(16,16), (24,24), (32,32), (48,48), (64,64)])
    image.resize((180,180), Image.Resampling.LANCZOS).save(ROOT / 'branding' / 'shu-tsan-touch-icon.png')
