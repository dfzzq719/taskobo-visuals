#!/usr/bin/env python3
"""Compose icon generation jobs from an Agent-authored semantic brief; no AI/API call."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import BadZipFile
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from brief_contract import BriefNotReady, TYPOGRAPHY, apply_profile, inspect_brief, normalize_ready, resolve_style
from company_profile import load_profile, profile_references, validate_profile

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def prepare(brief, context=None, contact_sheet=False, allow_illustrations=False, profile=None, profile_refs=None):
    catalog = read_json(ROOT / 'references/style-recipes.json')
    inline = brief.get('organizationProfile') if isinstance(brief, dict) else None
    if profile is not None:
        profile = validate_profile(profile, catalog)
        if inline is not None and validate_profile(inline, catalog) != profile:
            raise ValueError('Inline company profile differs from --profile; choose one explicit version.')
    elif inline is not None:
        profile = validate_profile(inline, catalog)
    if profile is not None:
        brief = apply_profile(brief, profile, catalog)
        if profile.get('references') and not profile_refs:
            raise ValueError('Company reference bytes must be validated with --profile before generation jobs can be prepared.')
        expected_company_refs = [(r['sha256'], r['role']) for r in profile.get('references', [])]
        actual_company_refs = [(r.get('sha256'), r.get('role')) for r in profile_refs or []]
        if actual_company_refs != expected_company_refs:
            raise ValueError('Company reference images do not match the declared company profile.')
    elif profile_refs:
        raise ValueError('Company reference images require an explicit company profile.')
    report = inspect_brief(brief, context, allow_illustrations, catalog)
    if not report['ready']:
        raise BriefNotReady(report)
    direction = brief.get('direction', {})
    recipe = resolve_style(direction, catalog)
    locked_company_refs = [r for r in (brief.get('styleLock') or {}).get('referenceImages', []) if r.get('origin') == 'organization']
    if locked_company_refs and [(r.get('sha256'), r.get('role')) for r in locked_company_refs] != [(r.get('sha256'), r.get('role')) for r in profile_refs or []]:
        raise ValueError('Locked company reference images require the matching company profile and validated reference bytes.')
    skill_version = re.search(r'version:\s*"([^"]+)"', (ROOT / 'SKILL.md').read_text(encoding='utf-8'))[1]
    references = []
    if recipe.get('styleReference'):
        reference = recipe['styleReference']
        reference_path = (ROOT / reference['file']).resolve()
        if not reference_path.is_relative_to(ROOT.resolve()) or not reference_path.is_file():
            raise ValueError('Bundled style reference is missing or escapes the Skill folder.')
        if hashlib.sha256(reference_path.read_bytes()).hexdigest() != reference['sha256']:
            raise ValueError('Bundled style reference hash mismatch.')
        references.append(reference)
    for reference in profile_refs or []:
        reference_path = Path(reference['file']).resolve()
        if not reference_path.is_file() or hashlib.sha256(reference_path.read_bytes()).hexdigest() != reference['sha256']:
            raise ValueError('Company reference bytes changed after profile validation.')
        references.append(reference)
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
        raise ValueError('Provide 1 to 48 planned assets; split a larger series.')
    ids = [a.get('id') for a in assets]
    if any(not isinstance(i, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Asset ids must be distinct lowercase slugs.')
    palette_text = '; '.join(f'{k}: {v}' for k, v in roles.items())
    layout = brief.get('layout', {})
    typography = dict(TYPOGRAPHY, **brief.get('typography', {}))
    language = brief.get('medium', {}).get('language')
    if layout.get('base', 'none') != 'none':
        raise ValueError('This workflow uses no decorative display base.')
    viewpoint = layout.get('viewpoint', recipe.get('defaultViewpoint', 'front'))
    if recipe['id'] == 'technical-spot' and viewpoint not in ('front', 'side', 'three-quarter', 'shallow-isometric'):
        raise ValueError('Unsupported Technical Spot drawing viewpoint.')
    jobs = []
    for asset in assets:
        kind = asset.get('kind', 'icon')
        if kind not in ('icon', 'illustration') or (kind == 'illustration' and not allow_illustrations):
            raise ValueError('Use prepare_visual_jobs.py for shared illustration and icon jobs.')
        if kind not in recipe.get('assetKinds', []):
            raise ValueError('The shared style does not support this asset kind.')
        forbidden = {'direction', 'recipe', 'preset', 'styleId', 'illustrationStyle', 'iconStyle'}
        if forbidden.intersection(asset) or {'illustrationStyle', 'iconStyle'}.intersection(brief) or {'illustrationStyle', 'iconStyle'}.intersection(direction):
            raise ValueError('Use one direction.styleId for the whole series; per-asset drawing-style overrides are not supported.')
        if not all(isinstance(asset.get(k), str) and asset[k].strip() for k in ('meaning', 'subject')):
            raise ValueError('Each asset needs an Agent-authored meaning and subject.')
        size = asset.get('iconSizePx', brief.get('medium', {}).get('iconSizePx', 96))
        if isinstance(size, bool) or not isinstance(size, int) or not 24 <= size <= 1024:
            raise ValueError('iconSizePx must be an integer between24 and1024, representing actual display size.')
        level = asset.get('detailLevel', layout.get('detailLevel', 'standard' if kind == 'illustration' else 'symbol' if size <= 48 else 'compact' if size <= 128 else 'standard'))
        if level not in ('symbol', 'compact', 'standard'):
            raise ValueError('detailLevel must be symbol, compact or standard.')
        parts = asset.get('subjectParts')
        if parts is not None:
            if not isinstance(parts, list) or not parts or any(not isinstance(p, str) or not p.strip() for p in parts):
                raise ValueError('subjectParts must be a nonempty list: primary object first, then necessary cues.')
            if kind == 'icon' and recipe['id'] == 'technical-spot' and level in ('symbol', 'compact') and len(parts) > (1 if level == 'symbol' else 2):
                raise ValueError('Technical Spot small icons exceed their primary-object/supporting-cue budget; simplify the semantic plan before generation.')
        refs = asset.get('sourceRefs', [])
        if not isinstance(refs, list) or any(not isinstance(r, str) for r in refs):
            raise ValueError('sourceRefs must be a list of extracted reference strings.')
        if context and (not refs or not set(refs) <= known_refs):
            raise ValueError('Each document-derived asset must cite known nonempty sourceRefs.')
        if not context and refs:
            raise ValueError('Provide --context to validate document sourceRefs.')
        background = asset.get('background', 'transparent')
        if background not in ('transparent', 'opaque') or (kind == 'icon' and background != 'transparent'):
            raise ValueError('Icons require transparent backgrounds; illustrations accept transparent or explicitly opaque.')
        transparent = background == 'transparent'
        framing = asset.get('framing', 'freeform' if transparent else 'full-scene')
        if framing not in ('freeform', 'vignette', 'full-scene'):
            raise ValueError('framing must be freeform, vignette or full-scene.')
        if (framing in ('freeform', 'vignette')) != transparent:
            raise ValueError('Freeform/vignette require transparent backgrounds; full-scene requires an explicitly opaque background.')
        framing_text = {
            'freeform': 'Natural freeform outer silhouette on transparent Alpha. Compose the subject and only necessary scene fragments as one coherent unframed artwork. No rectangular picture area, photo/card border, rounded panel, oval/circle clipping mask, decorative blob or backing plate. Keep complete important figures and objects; no accidental straight-edge cutoffs. Leave a modest safe transparent margin, with the artwork large enough to read. Preserve the selected style\'s object outlines; unframed does not mean outline-free.',
            'vignette': 'Unframed vignette with irregular peripheral scene fragments fading smoothly to zero Alpha. Keep the main subject, faces, hands and business actions sharp and opaque. Fade only the periphery; do not blur the whole image or change the shared drawing method. No rectangular/oval mask boundary, visible white halo, frame, card or background plate. Preserve the selected style\'s object outlines.',
            'full-scene': 'Explicit full-scene composition with an opaque setting filling the canvas. No added picture frame, photo-card border or decorative panel. Keep the selected shared drawing method.'
        }[framing]
        composition = asset.get('composition', 'A clear composition with one primary visual task.')
        display_size = asset.get('displaySize', 'Use the intended document placement size.')
        if not isinstance(composition, str) or not isinstance(display_size, str):
            raise ValueError('composition and displaySize must be descriptive strings.')
        avoid = asset.get('avoid', [])
        if not isinstance(avoid, list) or any(not isinstance(v, str) for v in avoid):
            raise ValueError('avoid must be a list of visual misreadings.')
        prompt = '\n'.join([
            'Use case: productivity-visual. Asset: a standalone enterprise explanatory ' + kind + '.',
            'Reader should recognize: ' + asset['meaning'],
            'Draw this current subject/action: ' + asset['subject'],
            'Drawing treatment: ' + recipe['treatment'],
            'Use the exact same drawing method for this series\'s illustrations and icons: contours, fill, material, texture and lighting. Adapt composition and detail only; never substitute a related style.',
            f'Actual icon display size: {size}px; detail level: {level}. Judge at this size, not at native export resolution.' if kind == 'icon' else f'Illustration placement: {display_size}; detail level: {level}. Composition: {composition}',
            *(['Compact Technical Spot: one dominant object plus at most one necessary supporting cue. Broad flat fills and medium clear contours; at96px about2–3px outer lines and1–1.5px necessary inner lines. Remove dense circuitry, cooling fins, repeated ports, screws, miniature instruments and multi-device clusters. Keep a few meaningful structural lines; technical subject matter is not a reason to add parts.'] if kind == 'icon' and recipe['id'] == 'technical-spot' and level == 'compact' else []),
            *(['Make a single simplified symbol with no structural microdetail; a larger explanatory spot cannot simply be shrunk to this size.'] if level == 'symbol' else []),
            'Viewpoint: ' + viewpoint + '. Preserve the shared contour, fill, material, texture and lighting method; scale detail to each asset size.',
            'Image framing: ' + framing_text,
            'Palette roles: ' + palette_text + '. These override reference and example colors.',
            'Output: genuinely transparent PNG with real Alpha, isolated artwork, generous safe edge, no baked paper/white/checkerboard ground.' if transparent else 'Output: opaque full-scene artwork as explicitly requested; background and composition follow the current asset brief.',
            'No decorative base, pedestal, backing plate, brand, watermark or embedded labels. Object surfaces remain opaque where appropriate.',
            'A style reference supplies drawing treatment only; do not copy its topics, objects, layout, labels or colors.',
            *(['Inspect and pass the bundled shared style reference to the image tool. Its drawing method applies to both asset kinds; compact detail density applies only at small display sizes.'] if references else []),
            'Avoid these semantic errors: ' + ('; '.join(avoid) if avoid else 'inventing approval, outcomes, figures or relationships absent from the brief.')
        ])
        jobs.append({'id': asset['id'], 'kind': kind, 'styleId': recipe['id'], 'styleVersion': recipe.get('styleVersion', '1'), 'label': asset.get('label', asset['id']),
                     'meaning': asset['meaning'], 'subject': asset['subject'],
                     'sourceRefs': refs, 'avoid': avoid, 'status': 'planned',
                     **({'iconSizePx': size} if kind == 'icon' else {'displaySize': display_size, 'composition': composition}),
                     'detailLevel': level, 'referenceImages': references,
                     'framing': framing,
                     'language': language,
                     'typography': typography,
                     'tool': 'host-image-generation', 'transparent_background': transparent,
                     'prompt': prompt})
    result = {'schema': 'taskobo-visuals.generation-jobs/v1', 'status': 'planned',
              'recipe': {'number': recipe['number'], 'id': recipe['id'], 'version': catalog['version']},
              'styleLock': {'skillVersion': skill_version, 'styleId': recipe['id'], 'recipeId': recipe['id'],
                            'styleVersion': recipe.get('styleVersion', '1'), 'drawingTreatment': recipe['treatment'], 'viewpoint': viewpoint,
                            'referenceImages': references, 'palette': roles, 'typography': typography},
              'source': context['source'] if context else None, 'palette': roles, 'jobs': jobs,
              'limits': 'Reference existence is validated; semantic judgment and generated images require review. No generation was performed.'}
    if profile is not None:
        result['organizationProfile'] = brief['organizationProfile']
    if contact_sheet:
        if any(j['kind'] != 'icon' for j in jobs):
            raise ValueError('--contact-sheet is an icon-only overview; request illustration compositions separately in assets.')
        result['contactSheet'] = {'transparent_background': True, 'referenceImages': references, 'status': 'planned',
            'prompt': '\n\n'.join([
                'Generate ONE review sheet of ' + str(len(jobs)) + ' distinct coordinated icons. Arrange left-to-right in the given order with equal generous gaps; no panel backgrounds, labels, dividers or captions. This is an overview, not separate asset delivery.',
                *[f"ICON {i}:\n{j['prompt']}" for i, j in enumerate(jobs, 1)]])}
    return result


def main(allow_illustrations=False):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=('Compose illustration and icon jobs from a shared, ready semantic brief; no AI/API call.' if allow_illustrations else __doc__))
    parser.add_argument('--brief', required=True, type=Path)
    parser.add_argument('--context', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--contact-sheet', action='store_true')
    parser.add_argument('--validate-only', action='store_true', help='Report missing fields without making generation tasks')
    parser.add_argument('--normalize-ready', action='store_true', help='Explicitly mark a complete, reviewed semantic plan ready; writes a brief, not tasks')
    parser.add_argument('--profile', type=Path, help='Company profile JSON or a verified profile ZIP')
    parser.add_argument('--profile-assets', type=Path, help='Extract approved ZIP references here, only for actual task preparation')
    args = parser.parse_args()
    try:
        if args.validate_only and args.normalize_ready:
            raise ValueError('Choose --validate-only or --normalize-ready, not both.')
        brief = read_json(args.brief)
        context = read_json(args.context) if args.context else None
        profile, entries = load_profile(args.profile) if args.profile else (None, None)
        if profile is not None:
            if brief.get('organizationProfile') is not None and validate_profile(brief['organizationProfile']) != profile:
                raise ValueError('Inline company profile differs from --profile; choose one explicit version.')
            brief = apply_profile(brief, profile)
        if args.validate_only:
            result = inspect_brief(brief, context, allow_illustrations)
            exit_code = 0 if result['ready'] else 2
        elif args.normalize_ready:
            result = normalize_ready(brief, context, allow_illustrations)
            exit_code = 0
        else:
            report = inspect_brief(brief, context, allow_illustrations)
            if not report['ready']:
                raise BriefNotReady(report)
            output_folder = args.profile_assets or (args.output.parent / (args.output.stem+'.profile') if args.output else None)
            refs = profile_references(args.profile, profile, entries, output_folder) if args.profile else None
            result = prepare(brief, context, args.contact_sheet, allow_illustrations, profile, refs)
            result['briefSha256'] = hashlib.sha256(args.brief.read_bytes()).hexdigest()
            exit_code = 0
        raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if args.output:
            if args.output.resolve() in {p.resolve() for p in (args.brief, args.context, args.profile) if p}:
                raise ValueError('Output cannot overwrite an input document.')
            args.output.write_bytes(raw)
        else:
            print(raw.decode('utf-8'), end='')
        return exit_code
    except BriefNotReady as exc:
        print(json.dumps(exc.report, ensure_ascii=False), file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError, TypeError, BadZipFile) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
