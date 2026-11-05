"""Validate reusable visual briefs without inventing their business content."""
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYPOGRAPHY = {'zh-CN': 'Microsoft YaHei', 'ja': 'Meiryo UI'}
BRIEF_SCHEMA = 'taskobo-illustration.visual-brief/v1'


class BriefNotReady(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__(json.dumps(report, ensure_ascii=False))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def skill_version(root=ROOT):
    return re.search(r'version:\s*["\']([^"\']+)', (root / 'SKILL.md').read_text(encoding='utf-8'))[1]


def resolve_style(direction, catalog=None):
    catalog = catalog or read_json(ROOT / 'references/style-recipes.json')
    if not isinstance(direction, dict):
        raise ValueError('direction must be an object.')
    selections = [direction[k] for k in ('styleId', 'recipe', 'preset') if direction.get(k) is not None]
    if not selections:
        raise ValueError('Choose direction.styleId; a broad family such as Editorial is not a concrete drawing style.')
    resolved = []
    for selection in selections:
        key = str(selection).strip().casefold()
        matches = []
        for style in catalog['styles']:
            aliases = {str(style[k]).casefold() for k in ('id', 'nameZh', 'nameJa', 'nameEn')}
            if style.get('number') is not None:
                aliases.update((str(style['number']), f"{style['number']:02d}"))
            if key in aliases:
                matches.append(style)
        if len(matches) != 1:
            raise ValueError('Style must uniquely match the shared style registry; no fallback is allowed.')
        if matches[0].get('status', 'active') != 'active':
            raise ValueError('The selected shared style is retired for illustrations and icons.')
        resolved.append(matches[0])
    if any(s['id'] != resolved[0]['id'] for s in resolved):
        raise ValueError('Style selections conflict; illustrations and icons require the same shared style ID.')
    return resolved[0]


def palette_errors(palette):
    if not isinstance(palette, dict) or not isinstance(palette.get('roles'), dict):
        return [('palette.roles', 'Provide palette roles with ink and primary colors.')]
    roles = palette['roles']
    issues = [(f'palette.roles.{key}', 'Choose this color explicitly or resolve it from the document.') for key in ('ink', 'primary') if key not in roles]
    issues += [(f'palette.roles.{key}', 'Use a six-digit sRGB HEX value.') for key, value in roles.items()
               if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value)]
    locked = palette.get('lockedRoles', [])
    if not isinstance(locked, list) or any(not isinstance(k, str) or k not in roles for k in locked):
        issues.append(('palette.lockedRoles', 'Locked roles must name colors present in palette.roles.'))
    return issues


def validate_style_lock(lock, recipe, catalog=None, root=ROOT):
    if lock is None:
        return
    if not isinstance(lock, dict):
        raise ValueError('styleLock must be an object.')
    for field, expected in [('skillVersion', skill_version(root)), ('styleId', recipe['id']),
                            ('recipeId', recipe['id']), ('styleVersion', recipe.get('styleVersion', '1'))]:
        if field in lock and str(lock[field]) != str(expected):
            raise ValueError(f'styleLock.{field} differs from the installed version; review and re-lock explicitly.')
    if 'drawingTreatment' in lock and lock['drawingTreatment'] != recipe['treatment']:
        raise ValueError('styleLock drawing treatment differs from the installed shared style.')
    if 'referenceImages' in lock:
        expected = [recipe['styleReference']] if recipe.get('styleReference') else []
        # Profile-specific references are checked separately by the profile loader.
        given = lock['referenceImages']
        if not isinstance(given, list) or any(not isinstance(r, dict) for r in given):
            raise ValueError('styleLock.referenceImages must be an array.')
        bundled = [r for r in given if r.get('origin') != 'organization']
        if [(r.get('file'), r.get('sha256')) for r in bundled] != [(r['file'], r['sha256']) for r in expected]:
            raise ValueError('styleLock reference hashes differ from the current shared style.')


def apply_profile(brief, profile, catalog=None):
    """Fill absent choices from a validated profile; explicit conflicts are errors."""
    if not isinstance(brief, dict):
        raise ValueError('Brief must be a JSON object.')
    result = copy.deepcopy(brief)
    direction = result.setdefault('direction', {})
    if not isinstance(direction, dict):
        raise ValueError('direction must be an object before applying a company profile.')
    selected = any(direction.get(k) is not None for k in ('styleId', 'recipe', 'preset'))
    if selected and resolve_style(direction, catalog)['id'] != profile['styleId']:
        raise ValueError('Company profile style conflicts with the explicit brief style; choose a profile or revise the choice explicitly.')
    direction['styleId'] = profile['styleId']
    palette = result.setdefault('palette', {})
    if not isinstance(palette, dict):
        raise ValueError('palette must be an object before applying a company profile.')
    roles = palette.setdefault('roles', {})
    if not isinstance(roles, dict):
        raise ValueError('palette.roles must be an object before applying a company profile.')
    locked = palette.get('lockedRoles', [])
    if not isinstance(locked, list) or any(not isinstance(role, str) for role in locked):
        raise ValueError('palette.lockedRoles must be an array of role names.')
    for role, color in profile['palette']['roles'].items():
        if role in profile['palette']['lockedRoles'] and role in roles and str(roles[role]).upper() != color.upper():
            raise ValueError(f'Company profile locked color {role} conflicts with the explicit brief color.')
        roles.setdefault(role, color)
    palette['lockedRoles'] = sorted(set(palette.get('lockedRoles', [])) | set(profile['palette']['lockedRoles']))
    typography = result.setdefault('typography', {})
    if not isinstance(typography, dict):
        raise ValueError('typography must be an object before applying a company profile.')
    for language, font in profile['typography'].items():
        if language in typography and typography[language] != font:
            raise ValueError(f'Company profile typography conflicts for {language}.')
        typography[language] = font
    result['organizationProfile'] = copy.deepcopy(profile)
    return result


def inspect_brief(brief, context=None, allow_illustrations=True, catalog=None, ignore_draft=False):
    """Return all actionable readiness findings, never a made-up subject or palette."""
    issues = []
    def add(path, message):
        issues.append({'path': path, 'message': message})
    if not isinstance(brief, dict):
        return {'schema': 'taskobo-visuals.brief-validation/v1', 'ready': False, 'status': 'draft',
                'issues': [{'path': '$', 'message': 'Brief must be a JSON object.'}]}
    if 'organizationProfile' in brief:
        try:
            from company_profile import validate_profile
            brief = apply_profile(brief, validate_profile(brief['organizationProfile'], catalog), catalog)
        except (ValueError, TypeError, KeyError) as exc:
            add('organizationProfile', str(exc))
    if brief.get('schema', BRIEF_SCHEMA) != BRIEF_SCHEMA:
        add('schema', 'Unsupported visual-brief schema.')
    declared = brief.get('status')
    if declared is not None and declared not in ('draft', 'ready'):
        add('status', 'Brief status must be draft or ready; generated/reviewed are asset states.')
    if declared == 'draft' and not ignore_draft:
        add('status', 'After completing and reviewing the semantic plan, use --normalize-ready or explicitly set status to ready.')
    recipe = None
    try:
        recipe = resolve_style(brief.get('direction', {}), catalog)
        validate_style_lock(brief.get('styleLock'), recipe, catalog)
        lock = brief.get('styleLock') or {}
        if isinstance(lock, dict):
            if 'palette' in lock:
                current_roles = brief.get('palette', {}).get('roles', {}) if isinstance(brief.get('palette'), dict) else {}
                locked_roles = lock['palette']
                if not isinstance(locked_roles, dict) or {k: str(v).upper() for k, v in locked_roles.items()} != {k: str(v).upper() for k, v in current_roles.items()}:
                    raise ValueError('styleLock palette differs from the explicit brief colors; review and re-lock explicitly.')
            current_typography = brief.get('typography', {}) if isinstance(brief.get('typography', {}), dict) else {}
            current_layout = brief.get('layout', {}) if isinstance(brief.get('layout', {}), dict) else {}
            if 'typography' in lock and lock['typography'] != dict(TYPOGRAPHY, **current_typography):
                raise ValueError('styleLock typography differs from the brief typography.')
            if 'viewpoint' in lock and lock['viewpoint'] != current_layout.get('viewpoint', recipe.get('defaultViewpoint', 'front')):
                raise ValueError('styleLock viewpoint differs from the brief viewpoint.')
    except (ValueError, TypeError, KeyError) as exc:
        add('direction.styleId', str(exc))
    for path, message in palette_errors(brief.get('palette', {})):
        add(path, message)
    typography = brief.get('typography', {})
    if not isinstance(typography, dict):
        add('typography', 'Typography must map language codes to font names.')
    else:
        for lang, font in TYPOGRAPHY.items():
            if lang in typography and typography[lang] != font:
                add(f'typography.{lang}', f'The shared delivery font is {font}; do not silently substitute another font.')
    assets = brief.get('assets', [])
    if not isinstance(assets, list) or not 1 <= len(assets) <= 48:
        add('assets', 'Provide 1 to 48 planned assets; split a larger series.')
        assets = []
    seen = set()
    forbidden = {'direction', 'recipe', 'preset', 'styleId', 'illustrationStyle', 'iconStyle'}
    direction = brief.get('direction', {}) if isinstance(brief.get('direction', {}), dict) else {}
    if {'illustrationStyle', 'iconStyle'}.intersection(brief) or {'illustrationStyle', 'iconStyle'}.intersection(direction):
        add('direction', 'Use one shared style ID for all asset kinds.')
    known = set()
    if context:
        if not isinstance(context, dict) or not isinstance(context.get('units'), list) or any(not isinstance(u, dict) or not isinstance(u.get('ref'), str) for u in context.get('units', [])) or not isinstance(context.get('source'), dict) or not isinstance(context.get('source', {}).get('sha256'), str) or not context.get('source', {}).get('sha256'):
            add('context', 'Provide an extracted context with source metadata and referenced units.'); context = None
        else:
            known = {u['ref'] for u in context['units']}
    source = brief.get('source', {}) if isinstance(brief.get('source', {}), dict) else {}
    if context and source.get('sha256') != context['source'].get('sha256'):
        add('source.sha256', 'Brief source hash does not match the extracted context.')
    layout = brief.get('layout', {})
    if not isinstance(layout, dict):
        add('layout', 'Layout must be an object.'); layout = {}
    if layout.get('base', 'none') != 'none':
        add('layout.base', 'Decorative display bases are not supported.')
    if recipe and recipe['id'] == 'technical-spot' and layout.get('viewpoint', recipe.get('defaultViewpoint', 'front')) not in ('front', 'side', 'three-quarter', 'shallow-isometric'):
        add('layout.viewpoint', 'Unsupported Technical Spot drawing viewpoint.')
    medium = brief.get('medium', {})
    if not isinstance(medium, dict):
        add('medium', 'Medium must be an object.'); medium = {}
    for i, asset in enumerate(assets):
        p = f'assets[{i}]'
        if not isinstance(asset, dict):
            add(p, 'Each asset must be an object.'); continue
        asset_id = asset.get('id')
        if not isinstance(asset_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', asset_id) or asset_id in seen:
            add(p+'.id', 'Use a distinct lowercase asset slug.')
        if isinstance(asset_id, str):
            seen.add(asset_id)
        kind = asset.get('kind', 'icon')
        if kind not in ('icon', 'illustration') or (kind == 'illustration' and not allow_illustrations):
            add(p+'.kind', 'Use prepare_visual_jobs.py for illustration and icon jobs; the compatibility entry is icons only.')
        if recipe and kind not in recipe.get('assetKinds', []):
            add(p+'.kind', 'The chosen style does not support this asset kind.')
        if forbidden.intersection(asset):
            add(p, 'Per-asset style overrides are not allowed; use direction.styleId once.')
        for key in ('meaning', 'subject'):
            if not isinstance(asset.get(key), str) or not asset[key].strip():
                add(p+'.'+key, 'Complete this business meaning/object/action from the topic or document; no automatic invention.')
        size = asset.get('iconSizePx', medium.get('iconSizePx', 96))
        valid_size = not isinstance(size, bool) and isinstance(size, int) and 24 <= size <= 1024
        if not valid_size:
            add(p+'.iconSizePx', 'Use an integer between 24 and 1024 for actual display size.')
        level = asset.get('detailLevel', layout.get('detailLevel', 'standard' if kind == 'illustration' else 'symbol' if valid_size and size <= 48 else 'compact' if valid_size and size <= 128 else 'standard'))
        if level not in ('symbol', 'compact', 'standard'):
            add(p+'.detailLevel', 'Choose symbol, compact or standard.')
        parts = asset.get('subjectParts')
        if parts is not None:
            if not isinstance(parts, list) or not parts or any(not isinstance(x, str) or not x.strip() for x in parts):
                add(p+'.subjectParts', 'Provide a nonempty list with the primary object first.')
            elif kind == 'icon' and recipe and recipe['id'] == 'technical-spot' and level in ('symbol', 'compact') and len(parts) > (1 if level == 'symbol' else 2):
                add(p+'.subjectParts', 'Reduce small Technical Spot icons to one primary object and at most one supporting cue.')
        refs = asset.get('sourceRefs', [])
        if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
            add(p+'.sourceRefs', 'Use a list of extracted source references.')
        elif context and (not refs or not set(refs) <= known):
            add(p+'.sourceRefs', 'Cite known, nonempty references from the extracted document.')
        elif not context and refs:
            add(p+'.sourceRefs', 'Provide --context to check these document references.')
        background = asset.get('background', 'transparent')
        if background not in ('transparent', 'opaque') or (kind == 'icon' and background != 'transparent'):
            add(p+'.background', 'Independent icons require transparent backgrounds; illustrations may be explicitly opaque.')
        framing = asset.get('framing', 'freeform' if background == 'transparent' else 'full-scene')
        if framing not in ('freeform', 'vignette', 'full-scene') or ((framing in ('freeform', 'vignette')) != (background == 'transparent')):
            add(p+'.framing', 'Freeform/vignette require transparency; full-scene requires opaque background.')
        for key in ('composition', 'displaySize'):
            if key in asset and not isinstance(asset[key], str):
                add(p+'.'+key, 'Use a descriptive string.')
        if not isinstance(asset.get('avoid', []), list) or any(not isinstance(x, str) for x in asset.get('avoid', [])):
            add(p+'.avoid', 'Use a list of visual misreadings to avoid.')
    return {'schema': 'taskobo-visuals.brief-validation/v1', 'ready': not issues,
            'status': 'ready' if not issues else 'draft', 'issues': issues,
            'legacyBrief': declared is None,
            'styleId': recipe['id'] if recipe else None,
            'limits': 'Readiness validates the plan, not business semantics or a generated image.'}


def normalize_ready(brief, context=None, allow_illustrations=True):
    report = inspect_brief(brief, context, allow_illustrations, ignore_draft=True)
    if not report['ready']:
        raise BriefNotReady(report)
    result = copy.deepcopy(brief)
    if 'organizationProfile' in result:
        from company_profile import validate_profile
        result = apply_profile(result, validate_profile(result['organizationProfile']))
    result['schema'] = BRIEF_SCHEMA
    result['status'] = 'ready'
    result.setdefault('direction', {})['styleId'] = report['styleId']
    result.setdefault('typography', {}).update(TYPOGRAPHY)
    return result
