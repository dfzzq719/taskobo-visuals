import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from brief_contract import TYPOGRAPHY, apply_profile, inspect_brief, normalize_ready, read_json, resolve_style, skill_version
from company_profile import export_profile, import_profile, load_profile, profile_references, validate_profile
from prepare_icon_jobs import prepare


def brief():
    return {'direction': {'styleId': 'enterprise-narrative'},
            'palette': {'roles': {'ink': '#0D2046', 'primary': '#1456D9'}},
            'assets': [{'id': 'review', 'kind': 'illustration', 'meaning': 'Review is pending',
                        'subject': 'Two colleagues inspect a document without an approval mark.',
                        'avoid': ['Do not imply the document is approved.']},
                       {'id': 'pending', 'kind': 'icon', 'meaning': 'Review is pending',
                        'subject': 'A document with one waiting cue.', 'iconSizePx': 96}]}


def profile():
    style = resolve_style({'styleId': 'enterprise-narrative'})
    return {'schema': 'taskobo-visuals.organization-profile/v1', 'name': 'Test Standard', 'version': '1.0.0',
            'styleId': style['id'], 'styleVersion': style.get('styleVersion', '1'),
            'palette': {'roles': {'ink': '#0D2046', 'primary': '#1456D9'}, 'lockedRoles': ['primary']},
            'typography': dict(TYPOGRAPHY), 'references': []}


class BriefContractTests(unittest.TestCase):
    def test_legacy_complete_brief_still_compiles(self):
        result = prepare(brief(), allow_illustrations=True)
        self.assertEqual([j['kind'] for j in result['jobs']], ['illustration', 'icon'])
        self.assertTrue(all(j['styleId'] == result['styleLock']['styleId'] for j in result['jobs']))
        self.assertEqual(result['styleLock']['typography'], TYPOGRAPHY)

    def test_draft_does_not_invent_content(self):
        source = {'schema': 'taskobo-illustration.visual-brief/v1', 'status': 'draft',
                  'direction': {'styleId': 'monoline'}, 'palette': {'roles': {}},
                  'assets': [{'id': 'visual-01', 'kind': 'illustration', 'meaning': '', 'subject': ''}]}
        before = copy.deepcopy(source)
        report = inspect_brief(source)
        self.assertFalse(report['ready'])
        self.assertEqual(source, before)
        paths = {e['path'] for e in report['issues']}
        self.assertTrue({'palette.roles.ink', 'palette.roles.primary', 'assets[0].meaning', 'assets[0].subject', 'status'} <= paths)
        with self.assertRaises(ValueError):
            normalize_ready(source)

    def test_complete_draft_requires_explicit_ready_action(self):
        source = brief(); source['status'] = 'draft'
        with self.assertRaises(ValueError):
            prepare(source, allow_illustrations=True)
        normalized = normalize_ready(source)
        self.assertEqual(normalized['status'], 'ready')
        self.assertEqual(source['status'], 'draft')
        self.assertEqual(normalized['assets'], source['assets'])
        self.assertTrue(prepare(normalized, allow_illustrations=True)['jobs'])

    def test_family_is_not_silently_mapped_to_specific_style(self):
        source = brief(); source['direction'] = {'id': 'editorial'}
        report = inspect_brief(source)
        self.assertFalse(report['ready'])
        self.assertTrue(any(e['path'] == 'direction.styleId' for e in report['issues']))

    def test_retired_unknown_and_conflicting_style_choices_fail(self):
        catalog = read_json(ROOT / 'references/style-recipes.json')
        catalog['styles'][0]['status'] = 'retired'
        with self.assertRaises(ValueError): resolve_style({'styleId': catalog['styles'][0]['id']}, catalog)
        with self.assertRaises(ValueError): resolve_style({'styleId': 'unknown-style'})
        with self.assertRaises(ValueError): resolve_style({'styleId': 'technical-spot', 'preset': 'enterprise-narrative'})

    def test_asset_style_override_fails(self):
        source = brief(); source['assets'][1]['styleId'] = 'technical-spot'
        with self.assertRaises(ValueError): prepare(source, allow_illustrations=True)

    def test_stale_installation_or_reference_lock_fails(self):
        source = brief(); source['styleLock'] = {'skillVersion': '0.0.0'}
        self.assertFalse(inspect_brief(source)['ready'])
        source['styleLock'] = {'skillVersion': skill_version(), 'styleId': 'enterprise-narrative', 'referenceImages': []}
        self.assertFalse(inspect_brief(source)['ready'])

    def test_style_lock_palette_change_is_explicit(self):
        source = brief(); source['styleLock'] = {'palette': {'ink': '#0D2046', 'primary': '#1456D9'}}
        self.assertTrue(inspect_brief(source)['ready'])
        source['palette']['roles']['primary'] = '#FF0000'
        self.assertFalse(inspect_brief(source)['ready'])

    def test_source_hash_and_reference_remain_required(self):
        context = {'source': {'sha256': 'abc'}, 'units': [{'ref': 'slide:1'}]}
        source = brief(); source['source'] = {'sha256': 'other'}
        for a in source['assets']: a['sourceRefs'] = ['slide:1']
        self.assertFalse(inspect_brief(source, context)['ready'])
        source['source']['sha256'] = 'abc'; source['assets'][1]['sourceRefs'] = ['slide:9']
        self.assertFalse(inspect_brief(source, context)['ready'])
        source['assets'][1]['sourceRefs'] = ['slide:1']
        self.assertTrue(prepare(source, context, allow_illustrations=True)['jobs'])

    def test_profile_fills_absent_choices_but_preserves_unlocked_colors(self):
        source = brief(); source['palette']['roles']['ink'] = '#112233'
        result = apply_profile(source, profile())
        self.assertEqual(result['palette']['roles']['ink'], '#112233')
        self.assertEqual(result['palette']['roles']['primary'], '#1456D9')
        self.assertEqual(result['organizationProfile']['version'], '1.0.0')
        self.assertNotIn('typography', source)

    def test_inline_profile_enforces_company_choices(self):
        source = brief(); source['organizationProfile'] = profile()
        source['palette']['roles']['primary'] = '#FF0000'
        self.assertFalse(inspect_brief(source)['ready'])
        with self.assertRaises(ValueError): prepare(source, allow_illustrations=True)
        source['palette']['roles']['primary'] = '#1456D9'
        self.assertEqual(prepare(source, allow_illustrations=True)['organizationProfile']['version'], '1.0.0')

    def test_profile_style_font_and_version_conflicts_fail(self):
        for change in ['style', 'font', 'version']:
            source = brief(); standard = profile()
            if change == 'style': source['direction']['styleId'] = 'monoline'
            elif change == 'font': source['typography'] = {'ja': 'Arial'}
            else: standard['styleVersion'] = '999'
            with self.subTest(change=change), self.assertRaises(ValueError):
                prepare(source, allow_illustrations=True, profile=standard)

    def test_malformed_inline_profile_briefs_report_instead_of_crashing(self):
        for key in ('direction', 'palette', 'typography', 'medium', 'layout'):
            for value in (None, [], True, 1, ''):
                source = brief(); source['organizationProfile'] = profile(); source[key] = value
                with self.subTest(field=key, value=value):
                    self.assertFalse(inspect_brief(source)['ready'])

    def test_company_archive_roundtrip_omits_nonvisual_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            standard = profile(); standard['sourceDocument'] = 'PRIVATE CUSTOMER DOCUMENT'
            standard['localAbsolutePath'] = 'C:/private/customer.docx'
            image = b'approved-test-reference'
            (folder/'approved.png').write_bytes(image)
            standard['references'] = [{'file': 'approved.png', 'sha256': hashlib.sha256(image).hexdigest(), 'role': 'style-approved-by-company'}]
            source = folder/'company.json'; source.write_text(json.dumps(standard), encoding='utf-8')
            package = folder/'standard.zip'; exported = export_profile(source, package)
            loaded, entries = load_profile(package)
            self.assertEqual(loaded, exported)
            self.assertNotIn('sourceDocument', loaded)
            self.assertEqual(entries['approved.png'], image)
            destination = folder/'imported'; import_profile(package, destination)
            self.assertEqual((destination/'approved.png').read_bytes(), image)
            with self.assertRaises(ValueError): import_profile(package, destination)
            with self.assertRaises(ValueError): export_profile(source, package)

    def test_archive_tampering_and_traversal_fail_before_import(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); source = folder/'company.json'; source.write_text(json.dumps(profile()))
            package = folder/'standard.zip'; export_profile(source, package)
            with ZipFile(package, 'a') as z: z.writestr('../escape.png', b'bad')
            with self.assertRaises(ValueError): import_profile(package, folder/'unsafe')
            self.assertFalse((folder/'unsafe').exists())
            standard = profile(); standard['references'] = [{'file': '../outside.png', 'sha256': '0'*64, 'role': 'style'}]
            with self.assertRaises(ValueError): validate_profile(standard)

    def test_profile_reference_hash_and_bytes_are_both_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); standard = profile()
            image = b'first'; (folder/'approved.png').write_bytes(image)
            standard['references'] = [{'file': 'approved.png', 'sha256': hashlib.sha256(image).hexdigest(), 'role': 'style'}]
            source = folder/'company.json'; source.write_text(json.dumps(standard))
            package = folder/'standard.zip'; export_profile(source, package)
            loaded, entries = load_profile(package)
            refs = profile_references(package, loaded, entries, folder/'reference-output')
            result = prepare(brief(), allow_illustrations=True, profile=loaded, profile_refs=refs)
            self.assertEqual(result['jobs'][0]['referenceImages'][-1]['origin'], 'organization')
            Path(refs[0]['file']).write_bytes(b'changed')
            with self.assertRaises(ValueError): prepare(brief(), allow_illustrations=True, profile=loaded, profile_refs=refs)
            (folder/'approved.png').write_bytes(b'changed')
            with self.assertRaises(ValueError): load_profile(source)

    def test_cli_validation_returns_machine_readable_missing_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'draft.json'; p.write_text(json.dumps({'status': 'draft', 'assets': []}))
            command = [sys.executable, '-B', str(ROOT/'scripts/prepare_visual_jobs.py'), '--brief', str(p), '--validate-only']
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertFalse(report['ready'])
            self.assertTrue(any(e['path'] == 'assets' for e in report['issues']))

    def test_web_draft_to_ready_tasks_forward_handoff(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is unavailable; pure Web contract is checked separately.')
        script = r'''const fs=require('node:fs');
const {buildDraft,makeOrganization}=require('./website/illustration.js');
const catalog=JSON.parse(fs.readFileSync('references/style-recipes.json','utf8'));
catalog.skillVersion=/version:\s*"([^"]+)"/.exec(fs.readFileSync('SKILL.md','utf8'))[1];
const values={topic:'取引先への追加確認',use:'提案書',kind:'both',direction:'enterprise-narrative',framing:'freeform',palette:'custom',primary:'#7D3C98',language:'ja',targetSize:'半ページ',iconCount:'2',iconSizePx:'96'};
const first=buildDraft(values,catalog); const org=makeOrganization(first,catalog,'調達部','1.0.0');
process.stdout.write(JSON.stringify(buildDraft(values,catalog,org)));'''
        result = subprocess.run([node, '-e', script], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
        source = json.loads(result.stdout)
        initial = inspect_brief(source)
        paths = {e['path'] for e in initial['issues']}
        self.assertTrue({'status', 'assets[0].meaning', 'assets[0].subject'} <= paths)
        for asset in source['assets']:
            asset['meaning'] = 'Further confirmation is pending; it is not approved.'
            asset['subject'] = 'Two colleagues examine a missing item in a document.' if asset['kind'] == 'illustration' else 'One document with a waiting cue.'
            asset['avoid'] = ['No approval check mark.']
        ready = normalize_ready(source)
        tasks = prepare(ready, allow_illustrations=True)
        self.assertEqual(tasks['organizationProfile']['name'], '調達部')
        self.assertTrue(all(j['styleId'] == source['direction']['styleId'] for j in tasks['jobs']))
        self.assertTrue(all(j['language'] == 'ja' and j['typography']['ja'] == 'Meiryo UI' for j in tasks['jobs']))
        self.assertEqual(tasks['palette']['primary'], '#7D3C98')


if __name__ == '__main__':
    unittest.main()
