#!/usr/bin/env python3
"""Validate and package one company's selected visual standard; no document upload."""
import argparse
import hashlib
import json
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from brief_contract import ROOT, TYPOGRAPHY, palette_errors, read_json, resolve_style

SCHEMA = 'taskobo-visuals.organization-profile/v1'
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 64
PROFILE_FIELDS = ('schema', 'name', 'version', 'styleId', 'styleVersion', 'palette', 'typography', 'references')


def safe_name(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('Reference names must be safe relative POSIX paths.')
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Reference names cannot be absolute or contain traversal.')
    if any(part.endswith(('.', ' ')) or re.fullmatch(r'(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part) for part in p.parts):
        raise ValueError('Reference names cannot use reserved or ambiguous Windows path segments.')
    if p.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('Approved style references must be PNG, JPEG or WebP image files.')
    return p.as_posix()


def validate_profile(profile, catalog=None):
    if not isinstance(profile, dict) or profile.get('schema') != SCHEMA:
        raise ValueError('Unsupported company visual profile schema.')
    if not isinstance(profile.get('name'), str) or not profile['name'].strip() or len(profile['name']) > 160:
        raise ValueError('Company profile name is required (up to 160 characters).')
    if not isinstance(profile.get('version'), str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?', profile['version']):
        raise ValueError('Company profile version must be a semantic version such as 1.0.0.')
    style = resolve_style({'styleId': profile.get('styleId')}, catalog)
    if str(profile.get('styleVersion')) != str(style.get('styleVersion', '1')):
        raise ValueError('Company profile styleVersion differs from the installed registry; review and re-publish the profile explicitly.')
    errors = palette_errors(profile.get('palette', {}))
    if errors:
        raise ValueError('; '.join(path+': '+message for path, message in errors))
    if profile.get('typography') != TYPOGRAPHY:
        raise ValueError('Company typography requires zh-CN Microsoft YaHei and ja Meiryo UI.')
    refs = profile.get('references', [])
    if not isinstance(refs, list) or len(refs) > MAX_FILES - 2:
        raise ValueError('Company references must be an array of at most 62 approved images.')
    seen = set()
    for reference in refs:
        if not isinstance(reference, dict):
            raise ValueError('Each approved reference needs file, sha256 and role.')
        name = safe_name(reference.get('file'))
        if name in seen or name.casefold() in {s.casefold() for s in seen}:
            raise ValueError('Reference names must be unique, including case-insensitive filesystems.')
        seen.add(name)
        if not re.fullmatch(r'[0-9a-f]{64}', str(reference.get('sha256', ''))):
            raise ValueError('Each approved reference needs a lowercase SHA-256 checksum.')
        if not isinstance(reference.get('role'), str) or not reference['role'].strip():
            raise ValueError('Each approved reference needs an explicit style role.')
    # Export only visual configuration. Free-text document/source/path fields are never bundled.
    clean = {k: profile[k] for k in PROFILE_FIELDS if k in profile}
    clean['styleId'] = style['id']
    clean['styleVersion'] = str(style.get('styleVersion', '1'))
    clean['references'] = [{k: r[k] for k in ('file', 'sha256', 'role')} for r in refs]
    clean['palette'] = {'roles': dict(profile['palette']['roles']), 'lockedRoles': list(profile['palette'].get('lockedRoles', []))}
    clean['typography'] = dict(TYPOGRAPHY)
    return clean


def _local_bytes(profile, folder):
    entries = {}
    base = Path(folder).resolve()
    for reference in profile['references']:
        p = (base / reference['file']).resolve()
        if not p.is_relative_to(base) or not p.is_file() or p.is_symlink():
            raise ValueError('Approved reference is missing or escapes the profile directory.')
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != reference['sha256']:
            raise ValueError('Company reference hash mismatch: '+reference['file'])
        entries[reference['file']] = data
    if sum(map(len, entries.values())) > MAX_TOTAL:
        raise ValueError('Company reference package exceeds 64 MiB.')
    return entries


def read_archive(path, catalog=None):
    """Read only whitelisted members and validate all hashes before writing anything."""
    with ZipFile(path) as z:
        members = z.infolist()
        if len(members) > MAX_FILES or sum(i.file_size for i in members) > MAX_TOTAL:
            raise ValueError('Company profile archive is too large.')
        names = [i.filename for i in members]
        if len(set(n.casefold() for n in names)) != len(names):
            raise ValueError('Duplicate archive members are not allowed.')
        for info in members:
            name = info.filename
            p = PurePosixPath(name)
            mode = info.external_attr >> 16
            if p.is_absolute() or '\\' in name or ':' in name or any(part in ('', '.', '..') for part in name.split('/')) or stat.S_ISLNK(mode) or info.flag_bits & 1:
                raise ValueError('Unsafe or encrypted archive member.')
        if 'profile.json' not in names or 'manifest.json' not in names:
            raise ValueError('Company profile archive needs profile.json and manifest.json.')
        profile = validate_profile(json.loads(z.read('profile.json')), catalog)
        manifest = json.loads(z.read('manifest.json'))
        expected = {'profile.json'} | {r['file'] for r in profile['references']}
        if set(names) != expected | {'manifest.json'} or manifest.get('schema') != 'taskobo-visuals.profile-manifest/v1' or set(manifest.get('files', {})) != expected:
            raise ValueError('Archive contains undeclared files or an invalid manifest.')
        entries = {name: z.read(name) for name in expected}
        for name, data in entries.items():
            if hashlib.sha256(data).hexdigest() != manifest['files'][name]:
                raise ValueError('Archive manifest hash mismatch: '+name)
        for ref in profile['references']:
            if hashlib.sha256(entries[ref['file']]).hexdigest() != ref['sha256']:
                raise ValueError('Company reference hash mismatch: '+ref['file'])
        return profile, entries


def load_profile(path, catalog=None):
    """Return validated metadata and explicit approved bytes; never extracts implicitly."""
    path = Path(path).resolve()
    if path.suffix.lower() == '.zip':
        return read_archive(path, catalog)
    profile = validate_profile(read_json(path), catalog)
    return profile, _local_bytes(profile, path.parent)


def export_profile(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('Profile export cannot overwrite an existing file.')
    profile, entries = load_profile(source)
    entries = {r['file']: entries[r['file']] for r in profile['references']}
    entries['profile.json'] = (json.dumps(profile, ensure_ascii=False, indent=2)+'\n').encode()
    manifest = {'schema': 'taskobo-visuals.profile-manifest/v1', 'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(entries.items())}}
    entries['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    if destination.parent == source and source.is_dir():
        raise ValueError('Output must be a ZIP file.')
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED) as z:
        for name, data in sorted(entries.items()):
            info = ZipInfo(name, (2026, 11, 5, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    read_archive(destination)
    return profile


def import_profile(source, destination):
    profile, entries = read_archive(source)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Import destination already exists; use a new directory to preserve previous standards.')
    destination.mkdir(parents=False)
    for name, data in entries.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # Imported profile.json is portable; manifest is retained for audit.
    with ZipFile(source) as z:
        (destination / 'manifest.json').write_bytes(z.read('manifest.json'))
    return profile


def profile_references(path, profile, entries, output_folder=None):
    """Provide actual image-tool paths after explicit JSON/ZIP loading."""
    path = Path(path).resolve()
    if not profile['references']:
        return []
    if path.suffix.lower() == '.zip':
        if output_folder is None:
            raise ValueError('A profile ZIP with references requires --profile-assets DIR (or --output jobs.json).')
        base = Path(output_folder).resolve()
        if base.exists():
            # Reuse a previous extraction only if all approved bytes still match.
            for ref in profile['references']:
                candidate = (base / ref['file']).resolve()
                if not candidate.is_relative_to(base) or not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).hexdigest() != ref['sha256']:
                    raise ValueError('Existing profile reference directory differs; choose a new output directory.')
        else:
            base.mkdir(parents=True)
            for ref in profile['references']:
                target = base / ref['file']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(entries[ref['file']])
    else:
        base = path.parent
    return [{**r, 'file': str((base / r['file']).resolve()), 'origin': 'organization'} for r in profile['references']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    validate = sub.add_parser('validate'); validate.add_argument('--profile', type=Path, required=True)
    export = sub.add_parser('export'); export.add_argument('--profile', type=Path, required=True); export.add_argument('--output', type=Path, required=True)
    unpack = sub.add_parser('import'); unpack.add_argument('--archive', type=Path, required=True); unpack.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'validate':
            profile, _ = load_profile(args.profile)
        elif args.action == 'export':
            profile = export_profile(args.profile, args.output)
        else:
            profile = import_profile(args.archive, args.output)
        print(json.dumps({'valid': True, 'name': profile['name'], 'version': profile['version'], 'styleId': profile['styleId'],
                          'approvedReferences': len(profile['references']), 'limits': 'This packages a visual standard, not a pixel-identical image generator.'}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, BadZipFile, RuntimeError) as exc:
        print(json.dumps({'valid': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
