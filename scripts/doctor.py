#!/usr/bin/env python3
"""Read-only installation checks; no network, package install or automatic repair."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def skill_metadata(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    front = re.match(r'\A---\s*\n(.*?)\n---(?:\s*\n|$)', text, re.S)
    if not front:
        raise ValueError('Skill frontmatter is missing.')
    def field(name):
        match = re.search(r'^\s*' + name + r':\s*[\"\']?([^\"\'\s]+)[\"\']?\s*$', front[1], re.M)
        return match[1] if match else None
    name, version = field('name'), field('version')
    if not name or not version or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?', version):
        raise ValueError('Skill name or semantic version is invalid.')
    return {'name': name, 'version': version}


def installation_report(root=ROOT, expected_version=None, skills_root=None, include_paths=False):
    root = Path(root).resolve()
    checks, errors, notes = [], [], []
    report = {'schema': 'taskobo-visuals.doctor/v1', 'readOnly': True,
              'scope': 'Installation and reference integrity only; no images are generated or visually approved.'}
    try:
        meta = skill_metadata(root / 'SKILL.md')
        if meta['name'] != 'taskobo-visuals':
            raise ValueError('This folder does not identify the taskobo-visuals Skill.')
        report['skill'] = meta
        checks.append('skill-metadata')
        if expected_version and meta['version'] != expected_version:
            errors.append({'code': 'version-mismatch', 'message': 'Installed Skill does not match the explicitly expected version.', 'expected': expected_version, 'actual': meta['version']})
    except (OSError, UnicodeError, ValueError):
        errors.append({'code': 'invalid-skill', 'message': 'Skill name/version metadata could not be read or is invalid.'})
        meta = {'name': 'taskobo-visuals'}
    try:
        registry_path = root / 'references/style-recipes.json'
        raw = registry_path.read_bytes()
        registry = json.loads(raw.decode('utf-8-sig'))
        styles = registry['styles']
        ids = [s['id'].casefold() for s in styles]
        if not styles or any(not x for x in ids) or len(ids) != len(set(ids)):
            raise ValueError('Style identifiers must be nonempty and unique.')
        if 'version' in meta and registry['version'] != meta['version']:
            errors.append({'code': 'registry-version-mismatch', 'message': 'The registry and Skill versions differ.'})
        retired = []
        pointer = registry.get('retiredStyleRegistry')
        if pointer is not None:
            if not isinstance(pointer, dict) or not isinstance(pointer.get('file'), str):
                raise ValueError('Invalid retired-style registry pointer.')
            relative = Path(pointer['file'])
            retired_path = (root / relative).resolve()
            if relative.is_absolute() or not retired_path.is_relative_to(root):
                raise ValueError('Unsafe retired-style metadata path.')
            tombstones = json.loads(retired_path.read_text(encoding='utf-8-sig'))
            if (tombstones.get('schema') != 'taskobo-visuals.retired-styles/v1'
                    or tombstones.get('version') != registry['version'] or not isinstance(tombstones.get('styles'), list)):
                raise ValueError('Invalid retired-style metadata schema or version.')
            retired = tombstones['styles']
            for style in retired:
                if (style.get('status') != 'retired'
                        or not all(isinstance(style.get(k), str) and style[k].strip()
                                   for k in ('id', 'nameZh', 'nameJa', 'nameEn', 'retiredIn', 'reason'))
                        or any(k in style for k in ('treatment', 'styleReference', 'styleVersion'))):
                    errors.append({'code': 'invalid-retired-style', 'message': 'Retired styles must contain refusal metadata without callable recipes.'})
            checks.append('retired-style-metadata')
        all_ids, numbers, aliases = set(), set(), set()
        for style in [*styles, *retired]:
            identity = style['id'].strip().casefold()
            if not identity or identity in all_ids:
                errors.append({'code': 'style-id-collision', 'message': 'Active and retired style identifiers must remain unique.'})
            all_ids.add(identity)
            number = style.get('number')
            if number is not None:
                if isinstance(number, bool) or not isinstance(number, int) or number < 1 or number in numbers:
                    errors.append({'code': 'style-number-collision', 'message': 'Legacy recipe numbers must be positive, unique and never reassigned.'})
                numbers.add(number)
            current_aliases = {str(style[k]).strip().casefold() for k in ('id', 'nameZh', 'nameJa', 'nameEn') if style.get(k)}
            if isinstance(number, int) and not isinstance(number, bool):
                current_aliases.update((str(number), f'{number:02d}'))
            if aliases.intersection(current_aliases):
                errors.append({'code': 'style-alias-collision', 'message': 'Current and retired names or legacy numbers resolve ambiguously.'})
            aliases.update(current_aliases)
        expected_count = registry.get('policy', {}).get('activeStyleCount')
        if expected_count is not None and (len(styles) != expected_count or any(s.get('status') != 'active' for s in styles)):
            errors.append({'code': 'active-style-count-mismatch', 'message': 'The current registry must contain exactly the declared number of active styles; retirement metadata belongs in its separate file.'})
        display_order = [style.get('displayOrder') for style in styles]
        if any(v is not None for v in display_order) and (any(isinstance(v, bool) or not isinstance(v, int) for v in display_order)
                                                        or sorted(display_order) != list(range(1, len(styles) + 1))):
            errors.append({'code': 'invalid-display-order', 'message': 'Display positions must be contiguous and independent of immutable legacy numbers.'})
        references = []
        for style in styles:
            if set(style.get('assetKinds', [])) != {'illustration', 'icon'}:
                errors.append({'code': 'shared-style-contract', 'styleId': style['id'], 'message': 'A shared style must support both asset kinds.'})
            reference = style.get('styleReference')
            if not reference:
                continue
            file = Path(reference['file'])
            resolved = (root / file).resolve()
            if file.is_absolute() or not resolved.is_relative_to(root) or not resolved.is_file():
                errors.append({'code': 'missing-or-unsafe-reference', 'styleId': style['id'], 'message': 'A bundled reference is missing or escapes the Skill folder.'})
                continue
            actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if actual != reference.get('sha256'):
                errors.append({'code': 'reference-hash-mismatch', 'styleId': style['id'], 'message': 'A bundled style reference differs from its recorded hash.'})
            references.append({'styleId': style['id'], 'sha256': actual})
        report['registry'] = {'version': registry['version'], 'sha256': hashlib.sha256(raw).hexdigest(), 'styles': len(styles), 'retiredStyles': len(retired), 'references': references}
        checks.append('shared-registry-and-reference-hashes')
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
        errors.append({'code': 'invalid-registry', 'message': 'The shared style registry could not be validated.'})
    required = ['prepare_icon_jobs.py', 'prepare_visual_jobs.py', 'extract_context.py', 'check_palette.py', 'check_assets.py',
                'production_run.py', 'delivery_manifest.py', 'asset_catalog.py']
    helpers = [p.name for p in sorted((root / 'scripts').glob('*.py')) if p.name != 'doctor.py']
    missing = sorted(set(required) - set(helpers))
    if missing:
        errors.append({'code': 'missing-helpers', 'files': missing, 'message': 'Required helper scripts are missing.'})
    for name in helpers:
        try:
            ast.parse((root / 'scripts' / name).read_text(encoding='utf-8-sig'), filename=name)
        except (OSError, UnicodeError, SyntaxError):
            errors.append({'code': 'helper-syntax-error', 'file': name, 'message': 'A helper could not be parsed.'})
    if not missing and not any(e['code'] == 'helper-syntax-error' for e in errors):
        # Import entry points in an isolated process with bytecode disabled. No CLI main runs.
        code = "import importlib,sys; sys.dont_write_bytecode=True; sys.path.insert(0,sys.argv[1]); [importlib.import_module(n) for n in sys.argv[2:]]"
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        try:
            result = subprocess.run([sys.executable, '-B', '-c', code, str(root / 'scripts'), *[Path(n).stem for n in helpers]],
                                    capture_output=True, env=env, timeout=15)
            if result.returncode:
                errors.append({'code': 'helper-import-error', 'message': 'A helper could not be imported. No automatic installation was attempted.'})
            else:
                checks.append('helper-imports')
        except (OSError, subprocess.TimeoutExpired):
            errors.append({'code': 'helper-import-error', 'message': 'The isolated helper import check could not complete.'})
    report['dependencies'] = {'pillowAvailable': importlib.util.find_spec('PIL') is not None,
                              'pdfTextAvailable': importlib.util.find_spec('pypdf') is not None}
    if not report['dependencies']['pillowAvailable']:
        notes.append('Pillow is optional for generation-task preparation; PNG diagnostics require an environment that already provides it.')
    if skills_root is not None:
        skills_root = Path(skills_root).resolve()
        candidates, unreadable = [], 0
        try:
            # Discovery scope is one installed-skill directory level, including named backups.
            for folder in sorted(skills_root.iterdir()):
                if not folder.is_dir() or not (folder / 'SKILL.md').is_file():
                    continue
                try:
                    candidate = skill_metadata(folder / 'SKILL.md')
                    if candidate['name'] == meta['name']:
                        item = {'version': candidate['version']}
                        if include_paths:
                            item['path'] = str(folder)
                        candidates.append(item)
                except (OSError, UnicodeError, ValueError):
                    unreadable += 1
            report['discovery'] = {'matchingSkillCount': len(candidates), 'candidates': candidates, 'unreadableMetadataCount': unreadable}
            if len(candidates) > 1:
                errors.append({'code': 'duplicate-skill-name', 'message': 'More than one discovered folder has the same Skill name. Review installation locations; this tool does not move or delete them.'})
            if unreadable:
                notes.append('Some unrelated Skill metadata could not be read; contents and paths are omitted.')
            checks.append('explicit-discovery-root')
        except OSError:
            errors.append({'code': 'unreadable-skills-root', 'message': 'The explicitly supplied installed-skills directory could not be read.'})
    else:
        notes.append('Duplicate discovery was not checked. Supply --skills-root explicitly to inspect an installed-skills directory.')
    if include_paths:
        report['skillRoot'] = str(root)
    report.update(passed=not errors, status='ready' if not errors else 'attention-required', checks=checks, errors=errors, notes=notes)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-version', help='Reject a different installed version rather than silently continuing.')
    parser.add_argument('--skills-root', type=Path, help='Explicit discovery directory for checking duplicate Skill names.')
    parser.add_argument('--skill-root', type=Path, default=ROOT, help='Skill to inspect; defaults to this script installation.')
    parser.add_argument('--include-paths', action='store_true', help='Include local installation paths for private troubleshooting only.')
    args = parser.parse_args()
    report = installation_report(args.skill_root, args.expected_version, args.skills_root, args.include_paths)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
