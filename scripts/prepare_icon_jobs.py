#!/usr/bin/env python3
"""Compose icon generation jobs from an Agent-authored semantic brief; no AI/API call."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def prepare(brief, context=None, contact_sheet=False):
    catalog = read_json(ROOT / 'references/icon-style-recipes.json')
    direction = brief.get('direction', {})
    selection = direction.get('recipe') or direction.get('preset')
    if selection is None:
        raise ValueError('Choose direction.recipe by number/id/name, or direction.preset.')
    key = str(selection).strip().casefold()
    matches = [s for s in catalog['styles'] if key in {
        str(s['number']), f"{s['number']:02d}", s['id'].casefold(),
        s['nameZh'].casefold(), s['nameJa'].casefold(), s['nameEn'].casefold()}]
    if len(matches) != 1:
        raise ValueError('Style must uniquely match the bundled recipe catalog.')
    recipe = matches[0]
    declared_preset = direction.get('preset')
    if declared_preset and declared_preset != recipe['id']:
        raise ValueError('direction.recipe conflicts with direction.preset.')
    roles = brief.get('palette', {}).get('roles', {})
    if not {'ink', 'primary'} <= roles.keys():
        raise ValueError('Palette roles require ink and primary; no hidden blue default.')
    if any(not isinstance(v, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', v) for v in roles.values()):
        raise ValueError('Each palette role must contain a six-digit sRGB HEX value.')
    known_refs = {u['ref'] for u in context['units']} if context else set()
    if context and brief.get('source', {}).get('sha256') != context['source']['sha256']:
        raise ValueError('Brief source hash does not match the extracted context.')
    assets = brief.get('assets', [])
    if not assets or len(assets) > 48:
        raise ValueError('Provide 1 to 48 planned icons; split a larger series.')
    ids = [a.get('id') for a in assets]
    if any(not isinstance(i, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Asset ids must be distinct lowercase slugs.')
    palette_text = '; '.join(f'{k}: {v}' for k, v in roles.items())
    layout = brief.get('layout', {})
    if layout.get('base', 'none') != 'none':
        raise ValueError('This icon workflow uses no decorative display base.')
    viewpoint = layout.get('viewpoint', recipe.get('defaultViewpoint', 'front'))
    if recipe['id'] == 'technical-spot' and viewpoint not in ('front', 'side', 'three-quarter', 'shallow-isometric'):
        raise ValueError('Unsupported Technical Spot drawing viewpoint.')
    jobs = []
    for asset in assets:
        if asset.get('kind', 'icon') != 'icon':
            raise ValueError('This helper composes icon jobs only; plan illustrations separately.')
        if not all(isinstance(asset.get(k), str) and asset[k].strip() for k in ('meaning', 'subject')):
            raise ValueError('Each icon needs an Agent-authored meaning and subject.')
        refs = asset.get('sourceRefs', [])
        if not isinstance(refs, list) or any(not isinstance(r, str) for r in refs):
            raise ValueError('sourceRefs must be a list of extracted reference strings.')
        if context and (not refs or not set(refs) <= known_refs):
            raise ValueError('Each document-derived icon must cite known nonempty sourceRefs.')
        if not context and refs:
            raise ValueError('Provide --context to validate document sourceRefs.')
        if asset.get('background', 'transparent') != 'transparent':
            raise ValueError('Use the main workflow for explicitly opaque scene artwork.')
        avoid = asset.get('avoid', [])
        if not isinstance(avoid, list) or any(not isinstance(v, str) for v in avoid):
            raise ValueError('avoid must be a list of visual misreadings.')
        prompt = '\n'.join([
            'Use case: productivity-visual. Asset: a standalone enterprise explanatory icon.',
            'Reader should recognize: ' + asset['meaning'],
            'Draw this current subject/action: ' + asset['subject'],
            'Drawing treatment: ' + recipe['treatment'],
            'Viewpoint: ' + viewpoint + '. Match line hierarchy, detail density and optical weight across the series.',
            'Palette roles: ' + palette_text + '. These override reference and example colors.',
            'Output: genuinely transparent PNG with real Alpha, isolated artwork, generous safe edge, no baked paper/white/checkerboard ground.',
            'No decorative base, pedestal, backing plate, brand, watermark or embedded labels. Object surfaces remain opaque where appropriate.',
            'A style reference supplies drawing treatment only; do not copy its topics, objects, layout, labels or colors.',
            'Avoid these semantic errors: ' + ('; '.join(avoid) if avoid else 'inventing approval, outcomes, figures or relationships absent from the brief.')
        ])
        jobs.append({'id': asset['id'], 'label': asset.get('label', asset['id']),
                     'meaning': asset['meaning'], 'subject': asset['subject'],
                     'sourceRefs': refs, 'avoid': avoid, 'status': 'planned',
                     'tool': 'host-image-generation', 'transparent_background': True,
                     'prompt': prompt})
    result = {'schema': 'taskobo-visuals.generation-jobs/v1', 'status': 'planned',
              'recipe': {'number': recipe['number'], 'id': recipe['id'], 'version': catalog['version']},
              'source': context['source'] if context else None, 'palette': roles, 'jobs': jobs,
              'limits': 'Reference existence is validated; semantic judgment and generated images require review. No generation was performed.'}
    if contact_sheet:
        result['contactSheet'] = {'transparent_background': True, 'status': 'planned',
            'prompt': '\n\n'.join([
                'Generate ONE review sheet of ' + str(len(jobs)) + ' distinct coordinated icons. Arrange left-to-right in the given order with equal generous gaps; no panel backgrounds, labels, dividers or captions. This is an overview, not separate asset delivery.',
                *[f"ICON {i}:\n{j['prompt']}" for i, j in enumerate(jobs, 1)]])}
    return result


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brief', required=True, type=Path)
    parser.add_argument('--context', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--contact-sheet', action='store_true')
    args = parser.parse_args()
    try:
        result = prepare(read_json(args.brief), read_json(args.context) if args.context else None, args.contact_sheet)
        result['briefSha256'] = hashlib.sha256(args.brief.read_bytes()).hexdigest()
        raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if args.output:
            if args.output.resolve() in {p.resolve() for p in (args.brief, args.context) if p}:
                raise ValueError('Output cannot overwrite an input document.')
            args.output.write_bytes(raw)
        else:
            print(raw.decode('utf-8'), end='')
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
