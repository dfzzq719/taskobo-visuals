#!/usr/bin/env python3
"""Verify independent asset delivery against planned IDs; no visual approval or generation."""
import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from check_assets import inspect_asset

JOBS_SCHEMA = 'taskobo-visuals.generation-jobs/v1'
FILES_SCHEMA = 'taskobo-visuals.delivery-files/v1'
MANIFEST_SCHEMA = 'taskobo-visuals.delivery-manifest/v1'
SLUG = r'[a-z0-9][a-z0-9-]{0,63}'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative_file(value, root):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('Asset files must be safe relative POSIX paths.')
    p = PurePosixPath(value)
    if p.is_absolute() or any(s in ('', '.', '..') for s in value.split('/')):
        raise ValueError('Asset paths cannot be absolute or contain traversal.')
    resolved = (Path(root) / Path(*p.parts)).resolve()
    if not resolved.is_relative_to(Path(root).resolve()) or not resolved.is_file():
        raise ValueError('An asset is missing or escapes the explicitly selected files directory.')
    return resolved


def inspect_svg(path):
    """Verify a self-contained vector subset, not its visual quality or transparency."""
    raw = Path(path).read_bytes()
    if len(raw) > 5 * 1024 * 1024 or re.search(rb'<!\s*(?:DOCTYPE|ENTITY)', raw, re.I) or re.search(rb'<\?(?!xml(?:\s|\?>))', raw):
        raise ValueError('SVG is too large or contains a prohibited declaration/processing instruction.')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError('SVG XML could not be parsed.') from None
    tag = lambda node: node.tag.rsplit('}', 1)[-1]
    if root.tag not in ('svg', '{http://www.w3.org/2000/svg}svg'):
        raise ValueError('An SVG file requires an svg root element.')
    allowed = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
               'defs', 'linearGradient', 'radialGradient', 'stop', 'clipPath', 'mask', 'title', 'desc',
               'filter', 'feGaussianBlur', 'feOffset', 'feComposite', 'feBlend', 'feFlood',
               'feColorMatrix', 'feMerge', 'feMergeNode'}
    drawable = {'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon'}
    nodes = list(root.iter())
    if any('}' in n.tag and not n.tag.startswith('{http://www.w3.org/2000/svg}') for n in nodes):
        raise ValueError('SVG geometry cannot use foreign XML namespaces.')
    if len(nodes) > 10000:
        raise ValueError('SVG contains too many nodes for this independent-file checker.')
    if any(tag(n).lower() == 'image' for n in nodes):
        raise ValueError('SVG contains an embedded or linked image; it is not an editable-vector delivery.')
    if any(tag(n) not in allowed for n in nodes):
        raise ValueError('SVG contains unsupported active, text, external or non-vector elements.')
    for node in nodes:
        for name, value in node.attrib.items():
            local = name.rsplit('}', 1)[-1].lower()
            if local.startswith('on') or local in ('href', 'src', 'style', 'base'):
                raise ValueError('SVG must use self-contained declarative shapes, not events, CSS or resource links.')
            if 'url(' in value.lower() and not re.fullmatch(r'url\(\s*#[a-zA-Z_][a-zA-Z0-9_.:-]*\s*\)', value):
                raise ValueError('SVG paint references must be local fragment IDs.')
            if re.search(r'(?:https?:|file:|data:|javascript:|@import)', value, re.I):
                raise ValueError('SVG contains an external or executable resource reference.')
    try:
        box = [float(v) for v in re.split(r'[\s,]+', root.attrib.get('viewBox', '').strip())]
        if len(box) != 4 or not all(math.isfinite(v) for v in box) or box[2] <= 0 or box[3] <= 0:
            raise ValueError
    except ValueError:
        raise ValueError('SVG requires a finite, positive viewBox.') from None
    count = sum(tag(n) in drawable for n in nodes)
    if not count:
        raise ValueError('SVG has no independent vector geometry.')
    return {'format': 'SVG', 'representation': 'editable-vector', 'sha256': digest(raw), 'bytes': len(raw),
            'viewBox': box, 'geometryElements': count, 'errors': [], 'warnings': [],
            'machineChecks': 'passed', 'transparency': 'not-raster-verified',
            'visualReview': 'not-performed', 'styleReview': 'not-performed', 'semanticReview': 'not-performed'}


def display_size(job):
    return (str(job.get('iconSizePx', 96)) + 'px') if job['kind'] == 'icon' else job.get('displaySize', 'unspecified')


def portable_lock(lock):
    result = {key: lock[key] for key in ('skillVersion', 'styleId', 'recipeId', 'styleVersion', 'drawingTreatment', 'viewpoint', 'palette', 'typography') if key in lock}
    # A delivery record retains reference identity without leaking private extraction paths.
    result['referenceImages'] = [{key: ref[key] for key in ('sha256', 'role', 'origin', 'status') if key in ref}
                                 for ref in lock.get('referenceImages', []) if isinstance(ref, dict)]
    return result


def accept_delivery(jobs_path, files_path, output, run_dir=None):
    jobs_path, files_path, output = (Path(p).resolve() for p in (jobs_path, files_path, output))
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Delivery output must be a new or empty directory; existing files are never replaced.')
    jobs_raw, files_raw = jobs_path.read_bytes(), files_path.read_bytes()
    jobs, files = json.loads(jobs_raw.decode('utf-8-sig')), json.loads(files_raw.decode('utf-8-sig'))
    if not isinstance(jobs, dict) or jobs.get('schema') != JOBS_SCHEMA or not isinstance(jobs.get('jobs'), list):
        raise ValueError('Provide actual generation-jobs output, not a brief or a contact-sheet request.')
    expected = jobs['jobs']
    if not 1 <= len(expected) <= 48 or any(not isinstance(j, dict) or not isinstance(j.get('id'), str) or not re.fullmatch(SLUG, j['id']) or j.get('kind') not in ('icon', 'illustration') for j in expected):
        raise ValueError('Generation jobs require1 to48 distinct independent illustration/icon IDs.')
    expected_ids = [j['id'] for j in expected]
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError('Generation job IDs are not unique.')
    lock = jobs.get('styleLock')
    if not isinstance(lock, dict) or not lock.get('styleId') or not lock.get('styleVersion'):
        raise ValueError('Generation jobs must preserve a shared style lock.')
    if any(j.get('styleId') != lock['styleId'] or str(j.get('styleVersion')) != str(lock['styleVersion']) for j in expected):
        raise ValueError('All delivery jobs must match the same shared drawing style and version.')
    if not isinstance(files, dict) or files.get('schema') != FILES_SCHEMA or not isinstance(files.get('assets'), list):
        raise ValueError('Use taskobo-visuals.delivery-files/v1 with an assets array.')
    declared = files['assets']
    if len(declared) > 48 or any(not isinstance(a, dict) or not isinstance(a.get('id'), str) for a in declared):
        raise ValueError('Each declared independent file needs its expected asset ID; at most48 files.')
    ids = [a['id'] for a in declared]
    errors = []
    def issue(code, message, asset_id=None):
        errors.append(dict(code=code, message=message, **({'assetId': asset_id} if asset_id else {})))
    if len(ids) != len(set(ids)):
        issue('duplicate-asset-id', 'Each expected asset ID can be delivered once only.')
    for asset_id in sorted(set(expected_ids) - set(ids)):
        issue('missing-asset', 'An expected independent asset file was not provided.', asset_id)
    for asset_id in sorted(set(ids) - set(expected_ids)):
        issue('unexpected-asset', 'An extra or overview asset cannot replace the expected independent files.', asset_id)
    records, payloads, seen_paths, seen_hashes = [], [], set(), set()
    by_id = {a['id']: a for a in declared}
    for job in expected:
        asset_id = job['id']
        item = by_id.get(asset_id)
        if item is None:
            continue
        if item.get('role') != 'independent':
            issue('not-independent', 'A contact sheet, overview or unspecified role is not independent delivery.', asset_id)
            continue
        if 'kind' in item and item['kind'] != job['kind']:
            issue('kind-mismatch', 'The delivered asset kind differs from the planned kind.', asset_id)
            continue
        try:
            path = relative_file(item.get('file'), files_path.parent)
            if path in (jobs_path, files_path) or path in seen_paths:
                raise ValueError('The same physical source file cannot be assigned to multiple assets.')
            raw = path.read_bytes()
            sha = digest(raw)
            if sha in seen_hashes:
                raise ValueError('Identical file bytes cannot satisfy different expected asset IDs, even after renaming.')
            seen_paths.add(path); seen_hashes.add(sha)
            suffix = path.suffix.lower()
            if suffix == '.png':
                if item.get('representation') != 'generated-raster':
                    raise ValueError('PNG delivery must be explicitly labelled generated-raster, never editable-vector.')
                checked, image = inspect_asset(path, expected_transparent=job.get('transparent_background', True))
                image.close()
                if checked['sha256'] != sha:
                    raise ValueError('The input file changed during inspection.')
                if checked['errors']:
                    for error in checked['errors']:
                        issue(error['code'], error['message'], asset_id)
                    continue
                if job.get('transparent_background', True) and checked['alphaExtrema'][0] != 0:
                    issue('no-fully-transparent-pixels', 'An independent transparent PNG needs fully transparent ground pixels, not a nearly opaque canvas.', asset_id)
                    continue
            elif suffix == '.svg':
                if item.get('representation') != 'editable-vector':
                    raise ValueError('SVG must be explicitly declared and verified as editable-vector; raster containers are rejected.')
                checked = inspect_svg(path)
                if checked['sha256'] != sha:
                    raise ValueError('The SVG file changed during inspection.')
            else:
                raise ValueError('Independent delivery currently accepts actual PNG or verified native SVG files.')
            record = {'id': asset_id, 'kind': job['kind'], 'meaning': job.get('meaning', ''),
                      'file': 'assets/' + asset_id + suffix, 'sha256': sha, 'bytes': len(raw),
                      'representation': item['representation'], 'role': 'independent',
                      'styleId': lock['styleId'], 'styleVersion': str(lock['styleVersion']),
                      'palette': lock.get('palette', jobs.get('palette', {})), 'typography': lock.get('typography', {}),
                      'displaySize': display_size(job), 'checks': checked,
                      'visualReview': 'not-performed', 'semanticReview': 'not-performed', 'styleReview': 'not-performed'}
            profile = jobs.get('organizationProfile')
            record['profile'] = {'name': profile.get('name'), 'version': profile.get('version')} if isinstance(profile, dict) else None
            if run_dir is not None:
                from production_run import delivery_evidence
                proof = delivery_evidence(Path(run_dir), asset_id, sha)
                if proof.get('jobsSha256') != digest(jobs_raw):
                    raise ValueError('Production run jobs snapshot differs from the delivery generation-jobs file.')
                record['production'] = proof
            records.append(record)
            payloads.append((record['file'], raw))
        except (ValueError, OSError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else 'A declared independent asset could not be read.'
            issue('invalid-independent-file', message, asset_id)
    accepted = not errors and len(records) == len(expected)
    manifest = {'schema': MANIFEST_SCHEMA, 'status': 'generated-unreviewed', 'accepted': accepted,
                'acceptanceScope': 'Independent-file coverage, file identity and format checks only; not visual, semantic, style or user approval.',
                'jobsSha256': digest(jobs_raw), 'filesDeclarationSha256': digest(files_raw), 'styleLock': portable_lock(lock),
                'expectedAssets': [{'id': j['id'], 'kind': j['kind']} for j in expected],
                'assets': records if accepted else [], 'errors': errors,
                'visualReview': 'not-performed', 'userApproval': 'not-performed',
                'limits': 'The checker rejects declared overviews and reused files; pixel checks cannot prove that a renamed image depicts only the intended subject. Inspect each independent image.'}
    # Avoid leaving apparently delivered files when coverage or format validation fails.
    output.mkdir(parents=True, exist_ok=True)
    if accepted:
        for name, raw in payloads:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
    with (output / 'delivery-manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', required=True, type=Path)
    parser.add_argument('--files', required=True, type=Path, help='Explicit ID/file/representation/role mapping; files relative to this JSON directory.')
    parser.add_argument('--output', required=True, type=Path, help='New/empty self-contained delivery directory.')
    parser.add_argument('--run-dir', type=Path, help='Require matching production-run receipts for each file and the exact jobs snapshot.')
    args = parser.parse_args()
    try:
        result = accept_delivery(args.jobs, args.files, args.output, args.run_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['accepted'] else 2
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Delivery could not be checked; verify the explicit files and required helper scripts.'
        print(json.dumps({'accepted': False, 'error': message, 'status': 'not-checked'}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
