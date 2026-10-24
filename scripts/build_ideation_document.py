"""Render the team discussion Markdown as a self-contained printable HTML file."""
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'docs' / '樹咱遊戲化與季節影像發想.md'
target = source.with_suffix('.html')


def inline(text):
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'https://[^\s<）]+', lambda m: f'<a href="{m[0]}">{m[0]}</a>', text)


lines = source.read_text(encoding='utf-8').splitlines()
parts, toc = [], []
i = 0
while i < len(lines):
    line = lines[i].strip()
    if not line:
        i += 1
        continue
    heading = re.match(r'^(#{1,3}) (.+)$', line)
    if heading:
        level, text = len(heading[1]), heading[2]
        anchor = f'section-{i}'
        parts.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
        if level == 2:
            toc.append(f'<a href="#{anchor}">{escape(text)}</a>')
    elif line.startswith('|'):
        rows = []
        while i < len(lines) and lines[i].strip().startswith('|'):
            cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?', c) for c in cells):
                rows.append(cells)
            i += 1
        head = '<tr>' + ''.join(f'<th scope="col">{inline(c)}</th>' for c in rows[0]) + '</tr>'
        body = ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in row) + '</tr>' for row in rows[1:])
        parts.append(f'<div class="table-scroll"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>')
        continue
    elif line.startswith('- '):
        items = []
        while i < len(lines) and lines[i].strip().startswith('- '):
            items.append('<li>' + inline(lines[i].strip()[2:]) + '</li>')
            i += 1
        parts.append('<ul>' + ''.join(items) + '</ul>')
        continue
    else:
        parts.append(f'<p>{inline(line)}</p>')
    i += 1

css = '''
:root{color-scheme:light;--green:#294e36;--paper:#faf6eb;--muted:#626f5c;--line:#dedfce}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f2efe6;color:#29352b;font-family:"Microsoft JhengHei","Noto Sans TC",sans-serif;font-size:16px;line-height:1.95}
.shell{max-width:1200px;margin:40px auto;display:grid;grid-template-columns:220px minmax(0,1fr);gap:28px;padding:0 24px}
nav{position:sticky;top:24px;align-self:start;font-size:13px;line-height:1.7;padding:12px 0}nav strong{display:block;color:var(--green);margin-bottom:14px}nav a{display:block;color:#58694e;text-decoration:none;margin:0 0 12px}nav a:hover{text-decoration:underline}
main{min-width:0;padding:44px 52px;background:#fffdf7;border:1px solid var(--line);border-radius:14px;box-shadow:0 3px 16px #294e3607}
h1,h2,h3{color:#000;line-height:1.55;font-weight:600;scroll-margin-top:28px}h1{font-size:29px;margin:0 0 10px}h2{font-size:23px;margin:40px 0 16px}h3{font-size:18px;margin:26px 0 10px}p{margin:0 0 16px}strong{font-weight:700}a{color:#45673e;overflow-wrap:anywhere}ul{padding-left:1.4em;margin:12px 0 22px}li{padding-left:4px;margin-bottom:9px}
.table-scroll{overflow:auto;margin:20px 0 26px}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.75}th,td{border:1px solid #d9d9d9;padding:12px 14px;text-align:left;vertical-align:middle}th{background:#e7ebed;color:#000;font-weight:600}tr:nth-child(even) td{background:#f5f6f1}th:first-child{width:23%}
.document-note{color:var(--muted);font-size:12px;margin-top:36px;padding-top:16px;border-top:1px solid var(--line)}
@media(max-width:850px){.shell{display:block;margin:16px auto;padding:0 12px}nav{position:static;display:flex;gap:12px;flex-wrap:wrap;padding:8px 4px}nav strong{width:100%;margin:0}nav a{margin:0 0 8px}main{padding:28px 22px}h1{font-size:25px}h2{font-size:21px}table{min-width:560px}}
@media print{@page{size:letter portrait;margin:18mm 18mm 18mm}body{background:white;font-size:10.5pt;line-height:1.8}.shell{display:block;margin:0;padding:0;max-width:none}nav{display:none}main{border:0;box-shadow:none;border-radius:0;padding:0}h1{font-size:22pt}h2{font-size:16pt;margin-top:22pt;break-after:avoid}h3{font-size:12pt;break-after:avoid}p,li{orphans:3;widows:3}table{font-size:9.5pt;line-height:1.6}thead{display:table-header-group}tr{break-inside:avoid}th,td{padding:7pt 8pt}.table-scroll{overflow:visible}a{color:#294e36;text-decoration:none}ul{margin-bottom:12pt}}
'''
html = '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>樹咱遊戲化與季節影像發想</title><style>' + css + '</style></head><body><div class="shell"><nav aria-label="文件目錄"><strong>組員討論稿 v1.0</strong>' + ''.join(toc) + '</nav><main>' + ''.join(parts) + '<p class="document-note">樹咱團隊討論用文件　2026 年 10 月 21 日　提案尚待原型與實地驗證</p></main></div></body></html>'
target.write_text(html, encoding='utf-8')
print(target)
