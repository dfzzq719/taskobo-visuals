"""Build Taskobo's static Japanese showcase and reusable fictional samples.

Requires Pillow only for lossless-source web exports. No model or API call.
Run from any directory; --output selects the static deployment directory.
"""
import argparse
import hashlib
import html
import json
import math
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = '/free-tools/taskobo-visuals/'
ORIGIN = 'https://taskobo.com'
REPO = 'https://github.com/dfzzq719/taskobo-visuals'
VERSION = re.search(r'version:\s*[\"\']([^\"\']+)', (ROOT / 'SKILL.md').read_text(encoding='utf-8'))[1]
CATALOG = json.loads((ROOT / 'examples/catalog.json').read_text(encoding='utf-8'))
E = html.escape
ARROW = '<svg class="ill-arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6"/></svg>'

PHRASES = {
    '制作条件を整え、AIに渡す。': ['制作条件を整え、', 'AIに渡す。'],
    '伝えたい仕事を、伝わる絵に。': ['伝えたい仕事を、', '伝わる絵に。'],
    '品質を確かめ、次の工程へつなぐ。': ['品質を確かめ、', '次の工程へ', 'つなぐ。'],
    '商品だけでなく、対応の流れも伝える。': ['商品だけでなく、', '対応の流れも', '伝える。'],
    '支える人と、支えられる人を同じ目線で。': ['支える人と、', '支えられる人を', '同じ目線で。'],
    '学ぶ、試す、振り返る。その場面を描く。': ['学ぶ、試す、', '振り返る。', 'その場面を描く。'],
    'あなたのAIに、共通の制作基準を。': ['あなたのAIに、', '共通の制作基準を。'],
    '同じ資料に、同じ表現のアイコンを。': ['同じ資料に、', '同じ表現の', 'アイコンを。'],
    '自分の業務に、置き換えて使う。': ['自分の業務に、', '置き換えて使う。'],
    'ほかの業務の表現も見る。': ['ほかの業務の', '表現も見る。'],
    '違う仕事にも、伝わる画風を。': ['違う仕事にも、', '伝わる画風を。'],
    '変えるところと、そろえるところ。': ['変えるところと、', 'そろえるところ。'],
    '自分の条件で、依頼文を作る。': ['自分の条件で、', '依頼文を作る。'],
    'あなたのAIに、Skillを追加する。': ['あなたのAIに、', 'Skillを追加する。'],
    '現在できることを、確かめて使う。': ['現在できることを、', '確かめて使う。'],
    '図表は正確に。挿絵は、伝わるように。': ['図表は正確に。', '挿絵は、', '伝わるように。'],
}

def phrase_headings(content):
    def replace(match):
        text = html.unescape(re.sub(r'<[^>]*>', '', match[2]))
        parts = PHRASES.get(text)
        if parts is None:
            return match[0]
        return match[1] + '<wbr>'.join('<span class="ill-phrase">' + E(p) + '</span>' for p in parts) + match[3]
    return re.sub(r'(<h[12][^>]*>)(.*?)(</h[12]>)', replace, content)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def archive(path, entries):
    with ZipFile(path, 'w') as z:
        for name, data in sorted(entries):
            info = ZipInfo(name, (2026, 10, 22, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    with ZipFile(path) as z:
        assert z.testzip() is None

def arrow_svg(path, tip, tangent, color, length=16, half_width=10):
    """Draw an open chevron aligned to the actual shaft's terminal tangent."""
    tx, ty = tip
    magnitude = math.hypot(*tangent)
    ux, uy = tangent[0] / magnitude, tangent[1] / magnitude
    bx, by = tx - length * ux, ty - length * uy
    left = (bx - half_width * uy, by + half_width * ux)
    right = (bx + half_width * uy, by - half_width * ux)
    head = f'M{left[0]:.3f} {left[1]:.3f}L{tx:g} {ty:g}L{right[0]:.3f} {right[1]:.3f}'
    return f'<g data-icon-arrow="true" fill="none" stroke="{color}" stroke-width="5"><path data-arrow-shaft="true" d="{path}"/><path data-arrow-head="true" d="{head}"/></g>'


def icon_svg(key, title, accent, wash):
    # Geometric outline/fill icons; no embedded bitmap, text shapes or external refs.
    body = {
        'inspection': '<path fill="{wash}" d="m98 39 48 28v56l-48 28-48-28V67Z"/><path d="m50 67 48 28 48-28M98 95v56"/><circle fill="#FCFBF8" cx="158" cy="151" r="34"/><path stroke="{accent}" d="m144 151 10 11 20-23"/><path stroke-width="10" d="m183 177 26 27"/>',
        'instructions': '<rect fill="{wash}" x="60" y="45" width="136" height="170" rx="9"/><rect fill="{accent}" x="99" y="34" width="58" height="25" rx="7"/><path d="m82 91 8 8 15-17m-23 50 8 8 15-17m-23 50 8 8 15-17M121 92h50m-50 41h50m-50 41h38"/>',
        'traceability': '<path fill="{wash}" d="M46 74h105l47 47-47 47H46Z"/><circle fill="{accent}" cx="167" cy="121" r="7"/><path stroke-width="6" d="M68 96v49m14-49v49m19-49v49m11-49v49m17-49v49"/>',
        'exception': '<path fill="{wash}" d="m43 108 54-24 54 24v77l-54 25-54-25Z"/><path d="m43 108 54 26 54-26m-54 26v76m-28-113 55 25v25"/><path fill="#FCFBF8" d="M143 43h58q12 0 12 12v49q0 12-12 12h-29l-23 21v-21h-6q-12 0-12-12V55q0-12 12-12Z"/><path stroke="{accent}" stroke-width="6" d="M172 61v23m0 14v1"/>',
        'maintenance': '<rect fill="{wash}" x="44" y="76" width="130" height="123" rx="8"/><path d="M44 109h130M60 91h1m13 0h1M64 132h42v42H64m-8 25v13m101-13v13"/><path fill="{accent}" d="M196 44q-25-8-39 11-13 17-2 36l-48 48a14 14 0 0 0 20 20l48-48q24 11 40-8 11-15 5-32l-20 21-21-20Z"/>',
        'shipment': '<path fill="{wash}" d="m48 80 60-28 60 28v81l-60 28-60-28Z"/><path d="m48 80 60 28 60-28m-60 28v81M78 66l60 28v27"/><path d="M43 213h62"/>',
        'inventory': '<path d="M45 46v167m166-167v167M45 116h166M45 198h166"/><rect fill="{wash}" x="61" y="59" width="54" height="57" rx="3"/><rect fill="{accent}" x="133" y="70" width="59" height="46" rx="3"/><rect fill="{wash}" x="72" y="139" width="74" height="59" rx="3"/><path d="M88 59v18m72-7v15m-52 54v20"/>',
        'order': '<rect fill="{wash}" x="40" y="58" width="73" height="126" rx="7"/><path d="M58 82h36M58 101h28M58 124h30M58 143h24"/><rect fill="#FCFBF8" x="150" y="75" width="66" height="126" rx="7"/><path d="m166 166 9 9 24-27"/>',
        'payment': '<rect fill="{wash}" x="91" y="63" width="113" height="150" rx="12"/><rect fill="{accent}" x="108" y="80" width="79" height="37" rx="4"/><path d="M113 140h12m18 0h12m18 0h10M113 162h12m18 0h12m18 0h10M113 184h12m18 0h12"/><rect fill="#FCFBF8" x="38" y="36" width="113" height="71" rx="8"/><path stroke="{accent}" stroke-width="9" d="M39 56h111"/><path d="M56 85h23"/>',
        'return': '<path fill="{wash}" d="m66 111 57-26 57 26v77l-57 26-57-26Z"/><path d="m66 111 57 27 57-27m-57 27v76m-28-116 55 26v23"/>',
        'support': '<path fill="{wash}" d="M47 51h114q14 0 14 14v65q0 14-14 14H99l-34 27v-27H47q-14 0-14-14V65q0-14 14-14Z"/><path fill="{accent}" d="M175 107h25q14 0 14 14v60q0 14-14 14h-12v21l-28-21h-44q-14 0-14-14v-16"/><path d="M61 84h83M61 108h55"/><path stroke="#FCFBF8" d="M135 162h50m-50 17h31"/>',
        'loyalty': '<rect fill="{wash}" x="47" y="61" width="162" height="117" rx="10"/><circle fill="{accent}" cx="89" cy="105" r="18"/><path d="M66 149q4-25 23-25t23 25m19-55h53m-53 22h37"/>',
        'appointment': '<rect fill="{wash}" x="43" y="57" width="154" height="143" rx="9"/><path fill="{accent}" d="M43 66q0-9 9-9h136q9 0 9 9v32H43Z"/><path d="M81 39v36m78-36v36M64 119h14m17 0h14m17 0h14M64 145h14m17 0h14"/><circle fill="#FCFBF8" cx="177" cy="173" r="38"/><path stroke="{accent}" stroke-width="5" d="M177 151v23l15 10"/>',
        'consultation': '<path fill="{wash}" d="M46 47h106q14 0 14 14v61q0 14-14 14h-39l-29 26v-26H46q-14 0-14-14V61q0-14 14-14Z"/><path fill="{accent}" d="M155 111h48q15 0 15 15v52q0 15-15 15h-15v21l-27-21h-43q-14 0-14-14v-21"/><path d="M61 80h75M61 104h49"/><path stroke="#FCFBF8" d="M141 148h47m-47 21h32"/>',
        'consent': '<path fill="{wash}" d="M60 39h92l41 41v127H60Z"/><path d="M152 39v41h41M82 105h86M82 128h57"/><path stroke="{accent}" stroke-width="4" d="m82 173 13-17 9 16 13-9 8 10h25"/><circle fill="#FCFBF8" cx="183" cy="188" r="31"/><path stroke="{accent}" stroke-width="5" d="m167 187 11 12 21-24"/>',
        'records': '<path fill="{wash}" d="M38 79h66l19 18h88v101H38Z"/><path fill="#FCFBF8" d="M61 49h94l35 35v93H61Z"/><path d="M155 49v35h35M82 101h64m-64 22h53"/><rect fill="{accent}" x="135" y="149" width="71" height="59" rx="8"/><path d="M149 148v-13a22 22 0 0 1 44 0v13"/><path stroke="#FCFBF8" stroke-width="5" d="M171 172v15"/>',
        'follow-up': '<rect fill="{wash}" x="46" y="44" width="125" height="162" rx="8"/><path stroke="{accent}" stroke-width="9" d="M108 73v42m-21-21h42"/><path d="M67 142h80m-80 23h51"/><circle fill="#FCFBF8" stroke="none" cx="178" cy="175" r="39"/><path stroke="{accent}" stroke-width="5" d="M178 151v25l17 10"/>',
        'accessibility': '<circle fill="{accent}" cx="115" cy="49" r="17"/><path stroke="{accent}" stroke-width="9" d="m108 80 4 62h53l26 49m-76-88h44"/><path d="M92 113a49 49 0 1 0 62 71m30 7h24"/><path fill="{wash}" d="M110 146h45v16h-45Z"/>',
        'curriculum': '<rect fill="{wash}" x="43" y="45" width="112" height="153" rx="8"/><path d="M71 45v153M91 76h43m-43 22h31"/><path d="M56 211h134"/>',
        'materials': '<path fill="{wash}" d="M128 65q-38-22-84-7v133q45-15 84 8 39-23 84-8V58q-46-15-84 7Z"/><path d="M128 65v134M62 86q25-7 47 5M62 111q25-7 47 5M62 137q25-7 47 5M147 91q24-12 47-5M147 116q24-12 47-5M147 142q24-12 47-5"/><path fill="{accent}" d="M174 53v60l11-7 11 7V53Z"/>',
        'practice': '<rect fill="{wash}" x="43" y="68" width="114" height="129" rx="8"/><path d="M43 99h114M60 84h20m-37 91h114M67 124h28v28H67"/><path fill="{accent}" d="M197 44q-25-5-38 13-11 16-2 33l-43 43a13 13 0 0 0 19 19l43-43q22 9 37-7 12-13 8-29l-21 18-19-19Z"/>',
        'mentoring': '<path fill="{wash}" d="M46 46h112q13 0 13 13v63q0 13-13 13h-40l-29 24v-24H46q-13 0-13-13V59q0-13 13-13Z"/><path fill="{accent}" d="M183 113h19q15 0 15 15v52q0 15-15 15h-18v21l-28-21h-39q-15 0-15-15v-17"/>',
        'assessment': '<rect fill="{wash}" x="48" y="46" width="126" height="161" rx="8"/><rect fill="{accent}" x="82" y="34" width="58" height="24" rx="6"/><path d="m68 88 7 7 12-15m-19 42 7 7 12-15M101 88h48m-48 35h33M68 159h48m-48 21h34"/><circle fill="#FCFBF8" cx="173" cy="172" r="30"/><path stroke="{accent}" stroke-width="5" d="m159 171 10 10 19-20"/><path stroke-width="8" d="m195 196 17 17"/>',
        'completion': '<path fill="{wash}" d="M55 53h146v134H55Z"/><path d="M72 72h111M76 96h104m-88 23h72M75 168h31"/><circle fill="{accent}" cx="157" cy="157" r="32"/><path fill="{wash}" d="m137 182-9 36 28-15 29 15-9-36"/><path stroke="#FCFBF8" stroke-width="5" d="m142 155 10 11 21-23"/>'
    }[key].replace('{accent}', accent).replace('{wash}', wash)
    arrows = {
        'traceability': [('M76 186H164', (164, 186), (1, 0), accent), ('M139 58H91', (91, 58), (-1, 0), accent)],
        'shipment': [('M136 191H212', (212, 191), (1, 0), accent)],
        'inventory': [('M159 167H194', (194, 167), (1, 0), accent)],
        'order': [('M121 132H142', (142, 132), (1, 0), accent, 12, 8)],
        'return': [('M197 82C183 47 140 34 106 52C91 60 79 73 73 89', (73, 89), (-6, 16), accent)],
        'loyalty': [('M67 204C90 221 127 220 150 205', (150, 205), (23, -15), accent), ('M190 36C167 22 133 24 113 38', (113, 38), (-20, 14), accent)],
        'follow-up': [('M208 200A39 39 0 1 1 208 150', (208, 150), (25, 30), accent)],
        'curriculum': [('M93 176H130V148H165V119H210', (210, 119), (1, 0), accent)],
        'mentoring': [('M61 90H136', (136, 90), (1, 0), accent), ('M188 160H142', (142, 160), (-1, 0), '#FCFBF8')],
    }
    body += ''.join(arrow_svg(*spec) for spec in arrows.get(key, []))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256" role="img" aria-label="{E(title)}"><title>{E(title)}</title><metadata>Original Taskobo geometric icon; editable SVG; 2026-10-22.</metadata><g fill="none" stroke="#0D2046" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>'

def request(case):
    return f'''$taskobo-visuals を使い、次の条件で企業資料用の素材を制作する。

内容テーマ：{case['theme']}
読者：{case['audience']}
用途：{case['uses']}
制作物：メインイラスト1点、テーマ別アイコン6点。
画風：挿絵とアイコンの両方に同じ enterprise-narrative の画法を使う。線・塗り・質感・光を共通化し、サイズに応じて構図と細部の量を調整する。
配色：主色 {case['accent']}、浅色 {case['wash']}、濃色 #0D2046、背景 #FCFBF8。

人物、対象物、行動の関係が伝わる構図にする。テーマと画風と色系は別々に扱う。
実在の企業や利用者の情報、架空の数値・導入効果を加えない。
イラストは高解像度画像、編集可能な図形アイコンは独立SVGと透明PNGで納品する。
小サイズの一覧で確認し、用途・配色・生成プロンプトを保存する。'''

def image(case, small=False):
    assets = case['assets']
    src = assets['small' if small else 'large']
    sizes = '(max-width: 600px) calc(100vw - 40px), (max-width: 1020px) calc(100vw - 96px), 1280px'
    if small:
        sizes = '(max-width: 600px) calc(100vw - 40px), (max-width: 1020px) 45vw, 600px'
    return f'<img src="{BASE}assets/{src}" srcset="{BASE}assets/{assets["small"]} 768w, {BASE}assets/{assets["large"]} 1440w" sizes="{sizes}" width="1672" height="941" alt="{E(case["alt"])}" {"loading=lazy" if small else "fetchpriority=high"} decoding="async">'

def copy_block(text, ident='sample-prompt'):
    return f'<div class="ill-prompt-block"><div class="ill-result-label"><label for="{ident}">AIに渡す依頼文</label><button class="ill-copy" type="button" data-copy="{ident}" data-status="{ident}-status">依頼文をコピー</button></div><textarea class="ill-prompt" id="{ident}" readonly spellcheck="false">{E(text)}</textarea><p class="ill-status" id="{ident}-status" role="status" data-copy-status></p></div>'

def palette_buttons(accent):
    return ''.join(f'<button type="button" data-accent="{c["accent"]}" data-wash="{c["wash"]}" aria-pressed="{str(c["accent"] == accent).lower()}"><i aria-hidden="true" style="--swatch:{c["accent"]}"></i>{c["paletteName"]}</button>' for c in CATALOG)

def sample(case):
    icons = ''
    for key, title, meaning in case['icons']:
        svg = (ROOT / 'examples' / case['id'] / 'icons' / (key + '.svg')).read_text(encoding='utf-8')
        svg = svg.replace(case['accent'], 'var(--sample-accent)').replace(case['wash'], 'var(--sample-wash)')
        icons += f'<article class="ill-icon"><div class="ill-icon-stage">{svg}</div><h3>{E(title)}</h3><p>{E(meaning)}</p><div class="ill-icon-links"><a href="{BASE}assets/icons/{case["assets"]["icons"][key]["svg"]}" download aria-label="{E(title)}のSVGを保存">SVG</a><a href="{BASE}assets/icons/{case["assets"]["icons"][key]["png"]}" download aria-label="{E(title)}のPNGを保存">PNG</a></div></article>'
    related = ''.join(f'<a href="{BASE}samples/{c["id"]}/">{image(c, True)}<strong>{E(c["name"])} {ARROW}</strong></a>' for c in CATALOG if c['id'] != case['id'])
    return f'''<div class="container"><nav class="ill-breadcrumbs" aria-label="パンくずリスト"><a href="/">ホーム</a><span>/</span><a href="{BASE}">Taskobo Visuals</a><span>/</span><span aria-current="page">{E(case['name'])}</span></nav>
<header class="ill-intro"><h1>{E(case['title'])}</h1><p>{E(case['description'])}</p><div class="ill-actions"><a class="button button-primary" href="#sample-icons">テーマ別アイコンを見る {ARROW}</a><a href="{BASE}downloads/{case['assets']['zip']}" download>このサンプル一式を保存</a></div></header>
<figure class="ill-art">{image(case)}<figcaption>Taskobo Visualsで制作した架空の業務場面。AI生成のイラストと、独立したSVGアイコンを組み合わせたサンプル。</figcaption></figure>
<dl class="ill-brief"><div><dt>対象</dt><dd>{E(case['audience'])}</dd></div><div><dt>用途</dt><dd>{E(case['uses'])}</dd></div><div><dt>配色</dt><dd class="ill-palette-sample"><span class="ill-swatch" style="--swatch:{case['accent']}" aria-hidden="true"></span><span>{case['paletteName']}<br>{case['accent']}</span></dd></div></dl>
<section class="ill-section" id="sample-icons" aria-labelledby="icon-heading" data-palette-scope style="--sample-accent:{case['accent']};--sample-wash:{case['wash']}"><div class="ill-section-head"><h2 id="icon-heading">同じ資料に、同じ表現のアイコンを。</h2><p>輪郭、線幅、余白をそろえた6点。意味が異なる対象は形でも区別し、名称は画像の外に置く。</p></div><div class="ill-palette" aria-label="アイコンの配色プレビュー">{palette_buttons(case['accent'])}</div><p class="ill-status" data-palette-status role="status">アイコンのみ配色を切り替えて比較できる。上のイラストとダウンロード素材は元のサンプル配色。</p><div class="ill-icon-grid">{icons}</div><p class="ill-icon-caption">個別SVGは図形を編集でき、PNGは透明背景の768px。サンプル一式には元の配色、SVG・PNG、イラスト、依頼文を収録。プレビューでの色変更はダウンロード素材には反映されない。</p></section>
<section class="ill-section"><div class="ill-split"><div><h2>自分の業務に、置き換えて使う。</h2><p>{E(case['meaning'])}</p></div><div><p>まず目的、読者、伝えたい行動を決める。その後に画風と配色を選ぶ。添付文書がある場合は、AIにページや段落の根拠を示させ、実際の業務に合うか確認する。</p>{copy_block(request(case))}<div class="ill-actions" style="margin-top:20px"><a href="{BASE}assets/{case['assets']['original']}" download>イラストのPNGを保存</a><a href="{REPO}/tree/main/examples/{case['id']}">元データと生成プロンプト</a></div></div></div></section>
<section class="ill-section"><div class="ill-split"><div><h2>あなたのAIに、共通の制作基準を。</h2><p>テーマは業務に合わせて変え、社内の色と表現は引き継ぐ。</p></div><div><p>Skillを導入したAIに依頼文を渡す。利用するAIの画像生成機能やローカル実行環境が必要だ。制作ツールで依頼文を調整し、Skillの導入手順も確認できる。</p><div class="ill-actions"><a class="button button-primary" href="{BASE}tool/#install">Skillの導入手順 {ARROW}</a><a href="{BASE}tool/?sample={case['id']}">自分の条件で依頼文を作る</a></div></div></div></section>
<section class="ill-section"><h2>ほかの業務の表現も見る。</h2><div class="ill-related">{related}</div></section>
<p class="ill-license">2026年10月22日公開。架空の業務サンプル。実企業の導入実績や効果を示すものではない。<a href="{REPO}/blob/main/LICENSE">MITライセンス</a>。生成画像は業務の正確性を確認し、図表や手順書の代わりに使う場合は専門担当者が検証する。</p></div>'''

def homepage(hero):
    gallery = ''.join(f'<article class="ill-work"><a href="{BASE}samples/{c["id"]}/">{image(c, True)}<div class="ill-work-title"><h3>{c["name"]}</h3>{ARROW}</div><p>{c["description"]}</p></a></article>' for c in CATALOG)
    nav = ''.join(f'<a href="{BASE}samples/{c["id"]}/">{c["name"]}{ARROW}</a>' for c in CATALOG)
    return f'''<div class="container"><nav class="ill-breadcrumbs" aria-label="パンくずリスト"><a href="/">ホーム</a><span>/</span><a href="/#free-tools">無料ツール</a><span>/</span><span aria-current="page">Taskobo Visuals</span></nav>
<header class="ill-intro"><h1>伝えたい仕事を、伝わる絵に。</h1><p>企業向けイラスト・アイコン制作。テーマや文書から内容を決め、画風と配色を選び、チームで共通の表現を育てるAI Skill。</p><div class="ill-actions"><a class="button button-primary" href="{BASE}tool/">制作ツールを使う {ARROW}</a><a href="#samples">業種別サンプルを見る</a><a href="{REPO}">GitHub</a></div><p class="ill-fineprint">Skill v{VERSION}公開中。画像は、制作ツールで条件を整えて利用中のAIで生成する。</p></header>
<figure class="ill-portfolio"><img src="{BASE}assets/{hero['large']}" srcset="{BASE}assets/{hero['small']} 768w, {BASE}assets/{hero['large']} 1440w" sizes="(max-width:600px) calc(100vw - 40px), (max-width:1020px) calc(100vw - 96px), 1280px" width="1671" height="941" alt="アイコンと挿絵で業務の話をわかりやすく伝える、Taskobo Visualsのプレゼンテーション画像。構図・配色・共通の画法を説明し、提案書・報告書・研修資料・Webへの展開を示す" fetchpriority="high" decoding="async"><figcaption>同じ画法のアイコンと挿絵を組み合わせた、Skillによるオリジナル作例。<a href="{REPO}/tree/main/examples/service-story">3枚の作例と生成プロンプトを見る</a>。</figcaption></figure>
<nav class="ill-industry-nav" aria-label="業種別サンプル">{nav}</nav>
<section class="ill-section" id="samples"><div class="ill-section-head"><h2>違う仕事にも、伝わる画風を。</h2><p>各ページでメインイラスト、テーマ別アイコン6点、配色、依頼文を確認できる。4業種は入口で、ほかの業種も内容に合わせて制作する。</p></div><div class="ill-gallery">{gallery}</div></section>
<section class="ill-section"><div class="ill-split"><div><h2>変えるところと、そろえるところ。</h2><p>見た目を毎回ゼロから決めず、仕事に必要な表現に集中する。</p></div><dl class="ill-definitions"><div><dt>内容テーマ</dt><dd>何を、誰に、何のために伝えるか。文書がある場合は、AIが本文と出典を確認して挿絵を提案する。</dd></div><div><dt>画風</dt><dd>輪郭、立体感、構図、細部の量。イラストとアイコンに同じスタイルID・同じ画法を使う。線・塗り・質感は共通に、大きさに応じて構図と細部の量を調整する。</dd></div><div><dt>色系</dt><dd>自社の指定色、サンプルの配色、文書の配色から選ぶ。文書のテーマ色と、正式なブランド規定は区別する。</dd></div><div><dt>全社の基準</dt><dd>色の役割、画風、承認済みの見本を版として共有する。生成画像の構図や細部には差が出るため、採用する素材は人が確認する。</dd></div></dl></div></section>
<section class="ill-section"><div class="ill-split"><div><h2>自分の業務に、置き換えて使う。</h2><p>制作ツールでテーマ・用途・画風・配色を選び、AIに渡す依頼文を作成する。</p></div><div><p>気になるサンプルから始めるか、あなたの業務を入力して始められる。Skillの導入手順とダウンロードも制作ツールにまとめた。</p><div class="ill-actions"><a class="button button-primary" href="{BASE}tool/">制作ツールを開く {ARROW}</a><a href="{BASE}tool/#install">Skillの導入手順</a></div></div></div></section>
<section class="ill-section"><h2>現在できることを、確かめて使う。</h2><div class="ill-scope"><div><h3>Skillと利用中のAIで</h3><ul><li>テーマ、用途、ブランドから挿絵を計画する。</li><li>利用できる生成機能でイラストを制作する。</li><li>シリーズアイコンの輪郭・配色・表示サイズをそろえる。</li><li>PPTX・DOCX・テキストの内容と色の根拠を読み、AIが提案する。</li></ul></div><div><h3>このWebページで</h3><ul><li>業種別の実作品とSVGアイコンを比較する。</li><li>アイコンの色を切り替え、素材をダウンロードする。</li><li><a href="{BASE}tool/">制作ツール</a>で依頼文と制作ブリーフを作成する。</li><li>Skill、サンプル、ソースコードを入手する。</li></ul></div></div><p class="ill-note">文書の画像内文字やレイアウト理解には、利用するAIの対応機能が必要。Web上での文書解析・画像生成、WordやPPTへの自動配置は本ページでは提供していない。実際の内容、利用権、人物表現と業務上の正確性は人が確認する。</p></section>
<section class="ill-section"><div class="ill-split"><h2>図表は正確に。<br>挿絵は、伝わるように。</h2><div><p>イラストとアイコンはTaskobo Visuals。計画と議事録からのWBS・RACI・工程表の更新はTaskobo Diagrams。用途に合わせて使い分け、同じ文書の中で組み合わせられる。</p><nav class="ill-inline-links" aria-label="関連ツール"><a href="/free-tools/taskobo-diagrams/">Taskobo Diagrams</a><a href="/free-tools/mermaid/">Mermaidスタイルメーカー</a><a href="https://docskobo.com/app?lang=ja">DOCSKOBO</a></nav></div></div></section>
<p class="ill-license">2026年10月22日公開。サンプルはすべて架空の業務場面から制作したオリジナル。実企業の導入事例ではない。素材・Skillの条件は<a href="{REPO}/blob/main/LICENSE">MITライセンス</a>、生成手法と範囲は<a href="{REPO}/blob/main/docs/guide.ja.md">利用ガイド</a>で確認できる。</p></div>'''


def product_nav(path):
    is_tool = path == 'tool/'
    return f'<nav class="ill-product-nav" aria-label="Taskobo Visuals"><a href="{BASE}"' + (' aria-current="page"' if not path else ' aria-current="true"' if not is_tool else '') + '>サンプルを見る</a><a href="' + BASE + 'tool/"' + (' aria-current="page"' if is_tool else '') + '>制作ツール</a></nav>'


def toolpage(skill_zip):
    presets = json.dumps({c['id']: {'name':c['name'], 'theme':c['theme'], 'accent':c['accent']} for c in CATALOG}, ensure_ascii=False).replace('<', chr(92)+'u003c')
    return f'''<div class="container"><nav class="ill-breadcrumbs" aria-label="パンくずリスト"><a href="/">ホーム</a><span>/</span><a href="{BASE}">Taskobo Visuals</a><span>/</span><span aria-current="page">制作ツール</span></nav>
<header class="ill-tool-intro"><h1>制作条件を整え、AIに渡す。</h1><p>企業向けイラスト・アイコン制作の条件を整える。テーマ、用途、画風、配色を選び、AIに渡す依頼文を作る。</p></header>
<p class="ill-tool-note">入力はブラウザー内で処理する。画像の生成と文書の確認は、Skillを導入した利用中のAIで行う。<a href="#install">Skillの導入手順</a></p>
<p class="ill-preset-status" id="preset-status" role="status" hidden></p>
<section class="ill-tool-layout" id="request" aria-label="制作条件と依頼文">
<div class="ill-tool-settings"><h2>制作条件</h2><p class="ill-request-help">内容と見た目を、それぞれ指定する。</p><form id="request-form" class="ill-form"><label class="ill-field ill-full">内容テーマ<input name="topic" required maxlength="300" value="新入社員のオンボーディングとチームの連携"><small>どんな仕事・行動・関係を伝えたいかを書く。</small></label><label class="ill-field">用途<select name="use"><option>社内研修のPPT</option><option>サービス紹介の提案書</option><option>事業報告書</option><option>書籍・記事</option><option>Webサイトの紹介画像</option></select></label><label class="ill-field">制作物<select name="kind"><option value="both">イラスト＋アイコン</option><option value="illustration">イラスト</option><option value="icons">テーマ別アイコン</option></select></label><label class="ill-field">画風<select name="direction"><option value="editorial">Editorial · 企業エディトリアル</option><option value="enterprise-narrative">Enterprise Narrative · 人と仕事の叙事表現</option><option value="precision">Precision · 精密な輪郭と塗り</option><option value="technical-spot">Technical Spot · 技術テーマの小さな説明イラスト</option><option value="dimensional">Dimensional · 落ち着いた立体表現</option></select></label><label class="ill-field">イラストの外形<select name="framing" aria-describedby="framing-help"><option value="freeform">自然な輪郭・透過（枠なし）</option><option value="vignette">周辺をぼかす・透過（枠なし）</option><option value="full-scene">背景付きの場面（全面）</option></select><small id="framing-help">画風はそのままに、外形と背景を選ぶ。標準は自然な輪郭の透過素材。</small></label><label class="ill-field">配色<select name="palette"><option value="blue">コバルトブルー</option><option value="teal">ディープティール</option><option value="terra">テラコッタ</option><option value="indigo">インディゴ</option><option value="custom">主色を指定</option><option value="document">文書に合わせて提案</option></select></label><label class="ill-field">指定する主色<input type="color" name="customColor" value="#1456d9" disabled></label><div class="ill-palette-sample"><span class="ill-swatch" data-color-swatch aria-hidden="true" style="--swatch:#1456D9"></span><span>AIに渡す配色の方向<br><small>画像の再生成は行わない</small></span></div><button class="ill-full" type="submit">依頼文を更新 {ARROW}</button></form></div>
<div class="ill-tool-output"><h2>AIに渡す依頼文</h2><p class="ill-request-help">条件を更新した後にコピーし、Skillを導入したAIに貼り付ける。</p><div class="ill-result"><div class="ill-result-label"><label for="request-output">利用中のAIに渡す</label><button class="ill-copy" type="button" data-copy="request-output" data-status="request-status">コピー</button></div><textarea class="ill-prompt" id="request-output" readonly spellcheck="false"></textarea><p class="ill-status" id="request-status" role="status">条件から依頼文を作成した。</p><button class="ill-copy secondary" id="download-brief" type="button">制作ブリーフをJSONで保存</button><noscript><p>依頼文の作成にはJavaScriptが必要。各サンプルページの依頼文はそのまま選択してコピーできる。</p></noscript></div><p class="ill-note">JSONにはテーマ、画風、色の役割と制作物の計画を保存する。社内で条件を共有するときに使える。</p></div>
</section>
<section class="ill-section" id="install"><div class="ill-split"><div><h2>あなたのAIに、Skillを追加する。</h2><p>無料・オープンソース。普段使っているAIと組み合わせ、素材と基準を手元に残す。</p><div class="ill-actions"><a class="button button-primary" href="{BASE}downloads/{skill_zip}" download>Skill v{VERSION}を保存 {ARROW}</a></div></div><div><ol class="ill-steps"><li><strong>ZIPを展開する。</strong><code>taskobo-visuals</code>フォルダーを、利用するAIソフトのSkill対応ディレクトリに置く。</li><li><strong>Skillを再読み込みする。</strong>対応AIソフトで新しいセッションを開き、<code>$taskobo-visuals</code>を指定する。導入場所は利用ソフトによって異なる。</li><li><strong>依頼文と必要な資料を渡す。</strong>題材・用途・色を指定する。画像生成には、そのAIソフトで使える画像生成機能が必要。図形アイコンはSVGで制作できる。</li><li><strong>見本を確認し、社内に共有する。</strong>用語、表現、配色、小サイズでの見やすさを確認する。採用した見本と制作ブリーフを版付きで残す。</li></ol><p class="ill-note">Skill本体の説明文は現在、中国語。日本語の利用ガイドとサンプルを公開している。ローカルの文書抽出スクリプトにはPython 3.10以上が必要で、PDFの文字抽出は追加のpypdfに依存する。モデルやAPIキーは同梱しない。</p><nav class="ill-inline-links" aria-label="導入資料"><a href="{REPO}/blob/main/docs/guide.ja.md">日本語の導入ガイド</a><a href="{REPO}/blob/main/SKILL.md">Skillの内容</a><a href="{REPO}/blob/main/LICENSE">ライセンス</a></nav></div></div></section>

<p class="ill-license">このツールは依頼文と制作ブリーフを作成する。Web上での画像生成・文書アップロード・WordやPPTへの自動配置は提供していない。<a href="{BASE}">作品と業種別サンプルを見る</a> · <a href="{REPO}">GitHub</a></p>
<script type="application/json" id="sample-presets">{presets}</script></div>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'site')
    parser.add_argument('--icons-only', action='store_true', help='Regenerate editable icon sources before PNG export')
    args = parser.parse_args()
    if args.icons_only:
        for case in CATALOG:
            folder = ROOT / 'examples' / case['id'] / 'icons'
            folder.mkdir(parents=True, exist_ok=True)
            for key, title, _ in case['icons']:
                (folder / (key + '.svg')).write_text(icon_svg(key, title, case['accent'], case['wash']), encoding='utf-8')
        print('Updated 24 editable SVG sources')
        return
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'assets/icons').mkdir(parents=True, exist_ok=True)
    (out / 'downloads').mkdir(exist_ok=True)
    def put_asset(name, data, directory='assets'):
        stem, ext = name.rsplit('.', 1)
        filename = f'{stem}-{digest(data)[:12]}.{ext}'
        (out / directory / filename).write_bytes(data)
        return filename
    css = put_asset('illustration.css', (ROOT / 'website/illustration.css').read_bytes())
    js = put_asset('illustration.js', (ROOT / 'website/illustration.js').read_bytes())
    def exports(path, stem, prompt, generated_date='2026-10-22'):
        from io import BytesIO
        image = Image.open(path).convert('RGB')
        values = {}
        metadata = f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/" dc:source="Taskobo original; built-in image generation; {generated_date}" dc:description="{E(prompt, quote=True)}"/></rdf:RDF></x:xmpmeta>'.encode('utf-8')
        for key, width in [('small', 768), ('large', 1440)]:
            thumb = image.copy()
            thumb.thumbnail((width, width), Image.Resampling.LANCZOS)
            buf = BytesIO()
            thumb.save(buf, format='WEBP', quality=86, method=6, xmp=metadata)
            values[key] = put_asset(f'{stem}-{width}.webp', buf.getvalue())
        values['original'] = put_asset(stem + '.png', path.read_bytes())
        return values
    hero = exports(ROOT / 'examples/service-story/page-02.png', 'service-story-02', (ROOT / 'examples/service-story/page-02.prompt.txt').read_text(encoding='utf-8'), '2026-10-26')
    for case in CATALOG:
        folder = ROOT / 'examples' / case['id']
        folder.mkdir(exist_ok=True)
        (folder / 'icons').mkdir(exist_ok=True)
        case['assets'] = exports(folder / 'illustration.png', case['id'], (folder / 'generation.prompt.txt').read_text(encoding='utf-8'))
        (folder / 'request.ja.txt').write_text(request(case) + '\n', encoding='utf-8', newline='\n')
        case['assets']['icons'] = {}
        for key, title, meaning in case['icons']:
            svg = icon_svg(key, title, case['accent'], case['wash'])
            (folder / 'icons' / (key + '.svg')).write_text(svg, encoding='utf-8')
            case['assets']['icons'][key] = {'svg': put_asset(f'{case["id"]}-{key}.svg', svg.encode('utf-8'), 'assets/icons')}
            (out / 'assets/icons' / f'{case["id"]}-{key}.svg').write_bytes(svg.encode('utf-8'))
            png = folder / 'icons' / (key + '.png')
            if png.exists():
                case['assets']['icons'][key]['png'] = put_asset(f'{case["id"]}-{key}.png', png.read_bytes(), 'assets/icons')
                (out / 'assets/icons' / f'{case["id"]}-{key}.png').write_bytes(png.read_bytes())
        archive_name = f'taskobo-visuals-{case["id"]}.zip'
        entries = [(p.relative_to(folder.parent).as_posix(), p.read_bytes()) for p in folder.rglob('*') if p.is_file() and p.name != 'index.html']
        archive(out / 'downloads' / archive_name, entries)
        old = out / 'downloads' / archive_name
        case['assets']['zip'] = put_asset(archive_name, old.read_bytes(), 'downloads')
        old.unlink()
    skill_paths = [ROOT / 'SKILL.md', ROOT / 'LICENSE']
    for name in ['agents', 'references', 'scripts', 'assets']:
        skill_paths.extend(p for p in (ROOT / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    archive(out / f'downloads/taskobo-visuals-v{VERSION}.zip', [('taskobo-visuals/' + p.relative_to(ROOT).as_posix(), p.read_bytes()) for p in skill_paths])
    skill_zip = put_asset(f'taskobo-visuals-v{VERSION}.zip', (out / f'downloads/taskobo-visuals-v{VERSION}.zip').read_bytes(), 'downloads')
    (out / f'downloads/taskobo-visuals-v{VERSION}.zip').unlink()
    template = (ROOT / 'website/portal-shell.html').read_text(encoding='utf-8')
    routes = []
    def page(path, title, description, content, og_asset, breadcrumb):
        url = ORIGIN + BASE + path
        data = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'WebPage', 'name': title, 'description': description, 'url': url, 'inLanguage': 'ja', 'isPartOf': {'@id': ORIGIN + '/#website'}},
            {'@type': 'BreadcrumbList', 'itemListElement': [{'@type': 'ListItem', 'position': i+1, 'name': name, 'item': link} for i, (name, link) in enumerate(breadcrumb)]}
        ]}
        head = f'<title>{E(title)}</title><meta name="description" content="{E(description)}"><link rel="canonical" href="{url}"><meta property="og:type" content="website"><meta property="og:site_name" content="Taskobo"><meta property="og:locale" content="ja_JP"><meta property="og:url" content="{url}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(description)}"><meta property="og:image" content="{ORIGIN}{BASE}assets/{og_asset}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(description)}"><meta name="twitter:image" content="{ORIGIN}{BASE}assets/{og_asset}"><script type="application/ld+json">{json.dumps(data, ensure_ascii=False).replace("<", chr(92) + "u003c")}</script><link rel="stylesheet" href="{BASE}assets/{css}"><script defer src="{BASE}assets/{js}"></script>'
        target = out / path / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        content = content.replace('</nav>', '</nav>' + product_nav(path), 1)
        target.write_text(template.replace('%%HEAD%%', head).replace('%%MAIN%%', phrase_headings(content)), encoding='utf-8', newline='\n')
        routes.append(BASE + path)
    page('', 'Taskobo Visuals | 企業資料のイラスト・テーマ別アイコンをつくるAI Skill', 'テーマや文書から企業向けのイラストとアイコンを制作する無料のAI Skill。製造・物流、小売・サービス、医療・ケア、教育・研修の実作品と配色プレビューを公開。独立した制作ツールで依頼文の作成とSkillの導入ができる。', homepage(hero), hero['large'], [('ホーム', ORIGIN + '/'), ('Taskobo Visuals', ORIGIN + BASE)])
    page('tool/', '制作ツール | Taskobo Visuals', 'テーマ・用途・画風・配色から、企業資料用イラストとアイコンの依頼文を作成。制作ブリーフをJSONで保存し、無料Skillと組み合わせて利用中のAIに渡せる。', toolpage(skill_zip), hero['large'], [('ホーム', ORIGIN + '/'), ('Taskobo Visuals', ORIGIN + BASE), ('制作ツール', ORIGIN + BASE + 'tool/')])
    for case in CATALOG:
        page('samples/' + case['id'] + '/', f'{case["name"]}のイラスト・アイコン例 | Taskobo Visuals', case['description'] + 'メインイラスト、編集可能なSVGアイコン6点、透明PNG、配色とAIへの依頼文を公開。', sample(case), case['assets']['large'], [('ホーム', ORIGIN + '/'), ('Taskobo Visuals', ORIGIN + BASE), (case['name'], ORIGIN + BASE + 'samples/' + case['id'] + '/')])
    manifest = {'skillVersion': VERSION, 'routes': routes, 'skillZip': skill_zip, 'hero': hero, 'cases': CATALOG, 'files': [{'path': p.relative_to(out).as_posix(), 'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()]}
    (ROOT / 'website/build-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    gallery_path = ROOT / 'docs/gallery.ja.md'
    marker = '<!-- industry-samples -->'
    authored_gallery = gallery_path.read_text(encoding='utf-8') if gallery_path.exists() else ''
    gallery = (authored_gallery.split(marker, 1)[0].rstrip() + '\n\n' if marker in authored_gallery else '# 業種別サンプル / Industry samples\n\n[公開README](../README.md) · [画風と素材の作例](icon-styles.ja.md) · [制作ツール](https://taskobo.com/free-tools/taskobo-visuals/tool/)\n\n架空の業務場面から制作したオリジナル。実企業の導入事例ではない。\n\n')
    gallery += marker + '\n\n'
    for case in CATALOG:
        gallery += f'## {case["name"]}\n\n{case["description"]}\n\n![{case["alt"]}](../examples/{case["id"]}/illustration.png)\n\n[Webで作品とアイコンを見る]({ORIGIN}{BASE}samples/{case["id"]}/) · [素材とプロンプト](../examples/{case["id"]}/)\n\n'
    (ROOT / 'docs/gallery.ja.md').write_bytes(gallery.encode('utf-8'))
    print(json.dumps({'pages': len(routes), 'icons': 24, 'files': len(manifest['files']), 'skillZip': skill_zip}))

if __name__ == '__main__':
    main()
