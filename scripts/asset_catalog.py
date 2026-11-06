#!/usr/bin/env python3
"""Explicit local approval, search and byte-preserving reuse of independent assets."""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from delivery_manifest import MANIFEST_SCHEMA, SLUG, digest, inspect_asset, inspect_svg, read_json, relative_file

SCHEMA = 'taskobo-visuals.asset-catalog/v1'


def normalize(value):
    return unicodedata.normalize('NFKC', str(value)).casefold().strip()


def palette_roles(value):
    if not isinstance(value, dict):
        raise ValueError('Palette must be an object with explicit role colors.')
    if 'palette' in value:
        value = value['palette']
    if not isinstance(value, dict):
        raise ValueError('Palette roles are invalid.')
    roles = value.get('roles', value)
    if not isinstance(roles, dict) or not {'ink', 'primary'} <= set(roles):
        raise ValueError('Palette roles must include ink and primary.')
    if any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', v) for k, v in roles.items()):
        raise ValueError('Use named palette roles with six-digit sRGB colors.')
    return {k: v.upper() for k, v in roles.items()}


def palette_key(value):
    return digest(json.dumps(palette_roles(value), sort_keys=True, separators=(',', ':')).encode())


def size_key(value):
    value = normalize(value)
    if re.fullmatch(r'[1-9][0-9]*(?:px)?', value):
        return value.removesuffix('px') + 'px'
    return value


def load_catalog(folder):
    folder = Path(folder).resolve()
    raw = (folder / 'catalog.json').read_bytes()
    data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('assets'), list) or len(data['assets']) > 10000:
        raise ValueError('Use a local Taskobo Visuals asset catalog with at most10000 entries.')
    ids = [a.get('id') for a in data['assets'] if isinstance(a, dict)]
    if len(ids) != len(data['assets']) or any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Catalog entries require distinct IDs.')
    return data, digest(raw)


def save_catalog(folder, data, expected_sha=None):
    folder = Path(folder).resolve()
    target = folder / 'catalog.json'
    if expected_sha is not None and (not target.is_file() or digest(target.read_bytes()) != expected_sha):
        raise ValueError('Catalog changed during approval; reload it before making a new explicit approval.')
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # A local temporary sibling allows atomic replacement without writing outside the selected catalog.
    with tempfile.NamedTemporaryFile(dir=folder, prefix='.catalog-', suffix='.tmp', delete=False) as stream:
        stream.write(raw)
        temporary = Path(stream.name)
    try:
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def init_catalog(folder):
    folder = Path(folder).resolve()
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise ValueError('Choose a new or empty catalog directory; existing files are never replaced.')
    folder.mkdir(parents=True, exist_ok=True)
    data = {'schema': SCHEMA, 'assets': [], 'scope': 'Locally approved exact files. Approval provenance is a recorded assertion, not an authenticated signature.'}
    save_catalog(folder, data)
    return {'schema': SCHEMA, 'status': 'initialized', 'assets': 0}


def validate_aliases(aliases):
    if aliases is None:
        return {'zh-CN': [], 'ja': [], 'en': []}
    if not isinstance(aliases, dict) or set(aliases) - {'zh-CN', 'ja', 'en'}:
        raise ValueError('Aliases must map zh-CN, ja and en to explicit business search terms.')
    result = {}
    for language in ('zh-CN', 'ja', 'en'):
        values = aliases.get(language, [])
        if not isinstance(values, list) or len(values) > 48 or any(not isinstance(v, str) or not v.strip() or len(v) > 160 for v in values):
            raise ValueError('Each language accepts up to48 nonempty aliases of at most160 characters.')
        result[language] = list(dict.fromkeys(v.strip() for v in values))
    return result


def approved(entry):
    review = entry.get('review', {})
    return (isinstance(review, dict) and review.get('status') == 'approved' and review.get('type') == 'explicit'
            and isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip())
            and isinstance(review.get('source'), str) and bool(review['source'].strip()))


@contextmanager
def writer_lock(folder):
    lock = Path(folder).resolve() / '.catalog-write.lock'
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError('Catalog approval is busy. Retry after the current writer completes; stale locks require explicit inspection.') from None
    try:
        yield
    finally:
        os.close(descriptor)
        lock.unlink()


def approve_asset(catalog_dir, manifest_path, asset_id, semantic_id, reviewer, source, aliases=None):
    with writer_lock(catalog_dir):
        return _approve_asset(catalog_dir, manifest_path, asset_id, semantic_id, reviewer, source, aliases)


def _approve_asset(catalog_dir, manifest_path, asset_id, semantic_id, reviewer, source, aliases=None):
    catalog_dir, manifest_path = Path(catalog_dir).resolve(), Path(manifest_path).resolve()
    if not isinstance(semantic_id, str) or not re.fullmatch(SLUG, semantic_id):
        raise ValueError('Use a stable lowercase semantic ID, such as invoice-review-pending.')
    if any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in (reviewer, source)):
        raise ValueError('Explicit approval requires a reviewer and a real review source/provenance (up to500 characters).')
    data, previous_sha = load_catalog(catalog_dir)
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw.decode('utf-8-sig'))
    if not isinstance(manifest, dict) or manifest.get('schema') != MANIFEST_SCHEMA or manifest.get('accepted') is not True:
        raise ValueError('A successful independent-file delivery manifest is required; it is not itself visual approval.')
    entries = manifest.get('assets', [])
    matches = [a for a in entries if isinstance(a, dict) and a.get('id') == asset_id]
    if len(matches) != 1:
        raise ValueError('Select exactly one independently delivered asset ID for explicit approval.')
    item = matches[0]
    if item.get('kind') not in ('icon', 'illustration') or item.get('role') != 'independent' or not isinstance(item.get('meaning'), str) or not item['meaning'].strip():
        raise ValueError('An approved entry needs its business meaning, independent role and actual asset kind.')
    if not isinstance(item.get('styleId'), str) or not item['styleId'] or not isinstance(item.get('styleVersion'), str) or not item['styleVersion']:
        raise ValueError('Style ID and version must be preserved from delivery.')
    path = relative_file(item.get('file'), manifest_path.parent)
    raw = path.read_bytes()
    if digest(raw) != item.get('sha256'):
        raise ValueError('Delivered asset bytes changed after acceptance. Recheck delivery before approval.')
    if item.get('representation') == 'editable-vector' and path.suffix.lower() == '.svg':
        inspect_svg(path)
    elif item.get('representation') == 'generated-raster' and path.suffix.lower() == '.png':
        is_transparent = item.get('checks', {}).get('expectedBackground') != 'opaque-or-full-page'
        checked, image = inspect_asset(path, expected_transparent=is_transparent)
        image.close()
        if checked['errors']:
            raise ValueError('Delivered PNG no longer meets its recorded file/background contract.')
    else:
        raise ValueError('Representation and actual delivered file format do not agree.')
    if not isinstance(item.get('displaySize'), str) or not item['displaySize'].strip():
        raise ValueError('Record an intended display size before adding an approved asset.')
    roles = palette_roles(item.get('palette', {}))
    profile = item.get('profile')
    if profile is not None and (not isinstance(profile, dict) or not isinstance(profile.get('name'), str) or not isinstance(profile.get('version'), str)):
        raise ValueError('Preserve an explicit company profile name/version, or null for no company profile.')
    entry = {'semanticId': semantic_id, 'meaning': item['meaning'], 'aliases': validate_aliases(aliases),
             'kind': item['kind'], 'styleId': item['styleId'], 'styleVersion': item['styleVersion'],
             'palette': roles, 'paletteSha256': palette_key(roles), 'profile': profile,
             'displaySize': item['displaySize'], 'sha256': item['sha256'], 'bytes': len(raw),
             'representation': item['representation'], 'deliveryAssetId': asset_id,
             'deliveryManifestSha256': digest(manifest_raw), 'jobsSha256': manifest.get('jobsSha256'),
             'production': item.get('production'),
             'review': {'status': 'approved', 'type': 'explicit', 'reviewer': reviewer.strip(),
                        'source': source.strip(), 'approvedAt': datetime.datetime.now(datetime.timezone.utc).isoformat()},
             'file': 'assets/' + item['sha256'] + path.suffix.lower()}
    identity = {k: entry[k] for k in ('semanticId', 'kind', 'styleId', 'styleVersion', 'paletteSha256', 'profile', 'displaySize', 'sha256')}
    entry['id'] = semantic_id + '-' + digest(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode())[:12]
    if any(a['id'] == entry['id'] for a in data['assets']):
        raise ValueError('This asset and exact usage metadata already have an approval entry; no approval was silently replaced.')
    target = catalog_dir / entry['file']
    if not target.resolve().is_relative_to(catalog_dir):
        raise ValueError('Catalog asset storage escapes the explicitly selected catalog directory.')
    if target.exists() and (not target.is_file() or digest(target.read_bytes()) != item['sha256']):
        raise ValueError('A catalog asset path is occupied by different bytes.')
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        with target.open('xb') as stream:
            stream.write(raw)
    data['assets'].append(entry)
    save_catalog(catalog_dir, data, previous_sha)
    return entry


def matches_filters(entry, query='', style_id=None, style_version=None, palette=None,
                    profile_version=None, display_size=None, kind=None):
    if not approved(entry):
        return False
    for field, expected in [('styleId', style_id), ('styleVersion', style_version), ('kind', kind)]:
        if expected is not None and str(entry.get(field)) != str(expected):
            return False
    if palette is not None and palette_key(entry.get('palette', {})) != palette_key(palette):
        return False
    if profile_version is not None and (entry.get('profile') or {}).get('version') != profile_version:
        return False
    if display_size is not None and size_key(entry.get('displaySize', '')) != size_key(display_size):
        return False
    aliases = entry.get('aliases', {})
    terms = [entry.get('semanticId', ''), entry.get('semanticId', '').replace('-', ' '), entry.get('meaning', '')]
    if isinstance(aliases, dict):
        terms += [value for values in aliases.values() if isinstance(values, list) for value in values if isinstance(value, str)]
    haystack = normalize(' '.join(terms))
    return all(term in haystack for term in normalize(query).split())


def entry_bytes(folder, entry):
    path = relative_file(entry.get('file'), folder)
    raw = path.read_bytes()
    if digest(raw) != entry.get('sha256'):
        raise ValueError('Approved catalog file hash changed; no reuse or silent regeneration is allowed.')
    return path, raw


def search_catalog(folder, **filters):
    if filters.get('palette') is not None:
        palette_roles(filters['palette'])
    data, _ = load_catalog(folder)
    matches, excluded = [], []
    for entry in data['assets']:
        try:
            if not matches_filters(entry, **filters):
                continue
            entry_bytes(folder, entry)
            matches.append(entry)
        except (ValueError, OSError):
            excluded.append({'id': entry['id'], 'reason': 'Approved metadata or file integrity could not be verified.'})
    return {'schema': 'taskobo-visuals.catalog-search/v1', 'status': 'matches-found' if matches else 'no-matches',
            'matches': matches, 'integrityExcluded': excluded,
            'limits': 'Only explicitly approved, exact-filter matches with unchanged bytes are returned. No image generation, recoloring or substitution was performed.'}


def reuse_asset(folder, entry_id, output, **filters):
    data, _ = load_catalog(folder)
    matches = [a for a in data['assets'] if a['id'] == entry_id]
    if len(matches) != 1 or not matches_filters(matches[0], **filters):
        raise ValueError('The selected catalog entry is not approved or does not match the explicit usage filters.')
    entry = matches[0]
    source, raw = entry_bytes(folder, entry)
    output = Path(output).resolve()
    if output.exists() or output == source or output == (Path(folder).resolve() / 'catalog.json'):
        raise ValueError('Choose a new output file; reuse cannot overwrite an input, existing file or catalog.')
    expected_suffix = '.svg' if entry['representation'] == 'editable-vector' else '.png'
    if output.suffix.lower() != expected_suffix:
        raise ValueError('Keep the approved file format; reuse does not convert a bitmap into SVG or vice versa.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(raw)
    return {'schema': 'taskobo-visuals.catalog-reuse/v1', 'status': 'reused-approved-asset',
            'entryId': entry_id, 'sha256': digest(raw), 'bytes': len(raw),
            'review': entry['review'], 'transformation': 'none', 'limits': 'Existing exact bytes were reused. A new placement still requires context/size review.'}


def add_filters(parser):
    parser.add_argument('--query', default='', help='Business search terms; multilingual meanings/aliases are matched, not silently translated.')
    parser.add_argument('--style-id')
    parser.add_argument('--style-version')
    parser.add_argument('--palette', type=Path, help='Exact role colors: raw roles, {roles:...}, or {palette:{roles:...}}.')
    parser.add_argument('--profile-version')
    parser.add_argument('--display-size', help='Intended size such as96px, not native PNG resolution.')
    parser.add_argument('--kind', choices=['icon', 'illustration'])


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('--catalog', required=True, type=Path)
    approve = sub.add_parser('approve')
    approve.add_argument('--catalog', required=True, type=Path)
    approve.add_argument('--manifest', required=True, type=Path)
    approve.add_argument('--asset-id', required=True)
    approve.add_argument('--semantic-id', required=True)
    approve.add_argument('--reviewer', required=True)
    approve.add_argument('--source', required=True, help='Actual approval provenance; supplying text records an assertion, not authenticated identity.')
    approve.add_argument('--aliases', type=Path)
    search = sub.add_parser('search'); search.add_argument('--catalog', required=True, type=Path); add_filters(search)
    reuse = sub.add_parser('reuse'); reuse.add_argument('--catalog', required=True, type=Path)
    reuse.add_argument('--id', required=True); reuse.add_argument('--output', required=True, type=Path); add_filters(reuse)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            result = init_catalog(args.catalog)
        elif args.command == 'approve':
            result = approve_asset(args.catalog, args.manifest, args.asset_id, args.semantic_id, args.reviewer, args.source, read_json(args.aliases) if args.aliases else None)
        else:
            palette = read_json(args.palette) if args.palette else None
            if palette is not None:
                palette_roles(palette)
            filters = dict(query=args.query, style_id=args.style_id, style_version=args.style_version,
                           palette=palette, profile_version=args.profile_version, display_size=args.display_size, kind=args.kind)
            result = search_catalog(args.catalog, **filters) if args.command == 'search' else reuse_asset(args.catalog, args.id, args.output, **filters)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Local catalog operation could not complete; check the explicit files and entry metadata.'
        print(json.dumps({'error': message, 'status': 'not-completed'}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
