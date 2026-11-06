import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import doctor


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.skill = self.folder / 'skill'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text('---\nname: taskobo-visuals\nmetadata:\n  version: "0.4.0"\n---\n', encoding='utf-8')
        (self.skill / 'references').mkdir()
        (self.skill / 'assets').mkdir()
        self.reference = self.skill / 'assets/reference.bin'
        self.reference.write_bytes(b'original master reference')
        self.registry = {'version': '0.4.0', 'styles': [{'id': 'test-style', 'assetKinds': ['illustration', 'icon'],
                         'styleReference': {'file': 'assets/reference.bin', 'sha256': hashlib.sha256(self.reference.read_bytes()).hexdigest()}}]}
        self.save_registry()
        (self.skill / 'scripts').mkdir()
        for name in ['prepare_icon_jobs.py', 'prepare_visual_jobs.py', 'extract_context.py', 'check_palette.py', 'check_assets.py', 'production_run.py', 'delivery_manifest.py', 'asset_catalog.py']:
            (self.skill / 'scripts' / name).write_text('VALUE = 1\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def save_registry(self):
        (self.skill / 'references/style-recipes.json').write_text(json.dumps(self.registry), encoding='utf-8')

    def test_valid_installation_is_read_only_and_private(self):
        before = {p.relative_to(self.skill).as_posix(): p.read_bytes() for p in self.skill.rglob('*') if p.is_file()}
        report = doctor.installation_report(self.skill, expected_version='0.4.0')
        self.assertTrue(report['passed'], report)
        self.assertIn('helper-imports', report['checks'])
        self.assertNotIn(str(self.folder), json.dumps(report))
        self.assertFalse(list(self.skill.rglob('__pycache__')))
        after = {p.relative_to(self.skill).as_posix(): p.read_bytes() for p in self.skill.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_expected_version_mismatch_does_not_mutate(self):
        report = doctor.installation_report(self.skill, expected_version='0.3.7')
        self.assertFalse(report['passed'])
        self.assertIn('version-mismatch', [e['code'] for e in report['errors']])

    def test_duplicate_name_found_even_when_backup_folder_name_differs(self):
        installed = self.folder / 'installed'
        for folder, version, name in [('taskobo-visuals', '0.4.0', 'taskobo-visuals'), ('visuals-backup-old', '0.3.6', 'taskobo-visuals'), ('other', '1.0.0', 'other')]:
            dest = installed / folder
            dest.mkdir(parents=True)
            (dest / 'SKILL.md').write_text(f'---\nname: {name}\nmetadata:\n  version: "{version}"\n---\n', encoding='utf-8')
        report = doctor.installation_report(self.skill, skills_root=installed)
        self.assertFalse(report['passed'])
        self.assertEqual(report['discovery']['matchingSkillCount'], 2)
        self.assertEqual(sorted(c['version'] for c in report['discovery']['candidates']), ['0.3.6', '0.4.0'])
        self.assertNotIn(str(installed), json.dumps(report))
        self.assertIn('duplicate-skill-name', [e['code'] for e in report['errors']])

    def test_discovery_is_opt_in(self):
        report = doctor.installation_report(self.skill)
        self.assertNotIn('discovery', report)
        self.assertTrue(report['passed'])

    def test_changed_reference_and_escape_are_rejected(self):
        self.reference.write_bytes(b'changed reference')
        report = doctor.installation_report(self.skill)
        self.assertIn('reference-hash-mismatch', [e['code'] for e in report['errors']])
        self.registry['styles'][0]['styleReference']['file'] = '../../outside.png'
        self.save_registry()
        report = doctor.installation_report(self.skill)
        self.assertIn('missing-or-unsafe-reference', [e['code'] for e in report['errors']])

    def test_missing_helper_and_bad_import_are_actionable(self):
        (self.skill / 'scripts/check_assets.py').unlink()
        report = doctor.installation_report(self.skill)
        self.assertIn('missing-helpers', [e['code'] for e in report['errors']])
        (self.skill / 'scripts/check_assets.py').write_text('import deliberately_missing_dependency_for_test\n', encoding='utf-8')
        report = doctor.installation_report(self.skill)
        self.assertIn('helper-import-error', [e['code'] for e in report['errors']])

    def test_single_asset_kind_is_not_a_shared_style(self):
        self.registry['styles'][0]['assetKinds'] = ['icon']
        self.save_registry()
        report = doctor.installation_report(self.skill)
        self.assertIn('shared-style-contract', [e['code'] for e in report['errors']])

    def test_registry_version_and_syntax_are_checked(self):
        self.registry['version'] = '0.3.7'
        self.save_registry()
        (self.skill / 'scripts/check_assets.py').write_text('def broken(', encoding='utf-8')
        report = doctor.installation_report(self.skill)
        codes = [e['code'] for e in report['errors']]
        self.assertIn('registry-version-mismatch', codes)
        self.assertIn('helper-syntax-error', codes)

    def test_cli_expected_version_has_nonzero_exit(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/doctor.py'), '--skill-root', str(self.skill), '--expected-version', '0.3.7'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'attention-required')
        self.assertNotIn(str(self.folder), result.stdout)


if __name__ == '__main__':
    unittest.main()
