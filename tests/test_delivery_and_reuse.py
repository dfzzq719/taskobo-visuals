"""Synthetic geometry/PNG fixtures only; no image generation or visual approval proof."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import asset_catalog as catalog
import delivery_manifest as delivery

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.jobs = {'schema': delivery.JOBS_SCHEMA, 'status': 'planned',
                     'styleLock': {'skillVersion': '0.5.0', 'styleId': 'monoline', 'styleVersion': '2',
                                   'palette': {'primary': '#73385F', 'ink': '#2B1834'}, 'typography': {'ja': 'Meiryo UI'}, 'referenceImages': []},
                     'organizationProfile': {'name': 'Synthetic fixture company', 'version': '1.0.0'},
                     'jobs': [{'id': 'invoice', 'kind': 'icon', 'meaning': 'Synthetic fixture: pending invoice review',
                               'styleId': 'monoline', 'styleVersion': '2', 'iconSizePx': 96,
                               'transparent_background': True, 'prompt': 'SYNTHETIC TEST ONLY, not actual image generation.', 'referenceImages': []}]}
        self.jobs_file = self.folder / 'jobs.json'
        self.files_file = self.folder / 'files.json'
        self.files = {'schema': delivery.FILES_SCHEMA, 'assets': []}
        self.svg = self.folder / 'invoice.svg'
        self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="#73385F"/></svg>', encoding='utf-8')
        self.declare('invoice', 'invoice.svg', 'editable-vector')
        self.save()

    def declare(self, asset_id, file, representation='editable-vector', role='independent'):
        self.files['assets'].append({'id': asset_id, 'file': file, 'representation': representation, 'role': role})

    def save(self):
        self.jobs_file.write_text(json.dumps(self.jobs, ensure_ascii=False), encoding='utf-8')
        self.files_file.write_text(json.dumps(self.files, ensure_ascii=False), encoding='utf-8')

    def accept(self, name='delivery', run_dir=None):
        self.save()
        return delivery.accept_delivery(self.jobs_file, self.files_file, self.folder / name, run_dir)

    def prepare_catalog(self):
        manifest = self.accept()
        self.assertTrue(manifest['accepted'])
        self.catalog_dir = self.folder / 'catalog'
        catalog.init_catalog(self.catalog_dir)
        return self.folder / 'delivery/delivery-manifest.json'

    def approve(self):
        manifest = self.prepare_catalog()
        return catalog.approve_asset(self.catalog_dir, manifest, 'invoice', 'invoice-pending',
                                     'synthetic-test-reviewer', 'Synthetic unit-test assertion; not a real user approval.',
                                     {'zh-CN': ['待确认发票'], 'ja': ['請求書の保留'], 'en': ['awaiting invoice verification']})


class DeliveryTests(Fixture):
    def test_vector_delivery_is_independent_but_never_visually_approved(self):
        before = self.svg.read_bytes()
        result = self.accept()
        self.assertTrue(result['accepted'])
        self.assertEqual(result['status'], 'generated-unreviewed')
        self.assertEqual(result['userApproval'], 'not-performed')
        self.assertEqual(result['assets'][0]['checks']['transparency'], 'not-raster-verified')
        self.assertEqual((self.folder / 'delivery/assets/invoice.svg').read_bytes(), before)
        self.assertEqual(self.svg.read_bytes(), before)
        self.assertNotIn(str(self.folder), json.dumps(result))
        self.assertNotIn('production', result['assets'][0])

    def test_missing_and_extra_ids_reject_without_partial_assets(self):
        self.jobs['jobs'].append({**self.jobs['jobs'][0], 'id': 'extra-needed'})
        self.declare('overview', 'invoice.svg')
        result = self.accept()
        self.assertFalse(result['accepted'])
        self.assertIn('missing-asset', [e['code'] for e in result['errors']])
        self.assertIn('unexpected-asset', [e['code'] for e in result['errors']])
        self.assertFalse((self.folder / 'delivery/assets').exists())
        self.assertFalse(result['assets'])

    def test_declared_overview_cannot_satisfy_an_independent_id(self):
        self.files['assets'][0]['role'] = 'overview'
        result = self.accept()
        self.assertFalse(result['accepted'])
        self.assertEqual(result['errors'][0]['code'], 'not-independent')

    def test_duplicate_declarations_reject(self):
        self.files['assets'].append(copy.deepcopy(self.files['assets'][0]))
        result = self.accept()
        self.assertFalse(result['accepted'])
        self.assertIn('duplicate-asset-id', [e['code'] for e in result['errors']])

    def test_same_file_or_renamed_identical_bytes_cannot_satisfy_multiple_jobs(self):
        self.jobs['jobs'].append({**self.jobs['jobs'][0], 'id': 'second'})
        self.declare('second', 'invoice.svg')
        self.assertFalse(self.accept('same-path')['accepted'])
        (self.folder / 'renamed.svg').write_bytes(self.svg.read_bytes())
        self.files['assets'][1]['file'] = 'renamed.svg'
        self.assertFalse(self.accept('same-bytes')['accepted'])

    def test_actual_distinct_files_satisfy_distinct_ids(self):
        self.jobs['jobs'].append({**self.jobs['jobs'][0], 'id': 'second'})
        (self.folder / 'second.svg').write_bytes(self.svg.read_bytes().replace(b'r="8"', b'r="7"'))
        self.declare('second', 'second.svg')
        result = self.accept()
        self.assertTrue(result['accepted'])
        self.assertEqual(len(result['assets']), 2)

    def test_kind_mismatch_is_rejected(self):
        self.files['assets'][0]['kind'] = 'illustration'
        result = self.accept()
        self.assertFalse(result['accepted'])
        self.assertEqual(result['errors'][0]['code'], 'kind-mismatch')

    def test_existing_target_and_input_escape_are_rejected(self):
        target = self.folder / 'delivery'
        target.mkdir(); protected = target / 'existing.txt'; protected.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'new or empty'):
            self.accept()
        self.assertEqual(protected.read_bytes(), b'keep')
        self.files['assets'][0]['file'] = '../outside.svg'
        result = self.accept('bad-path')
        self.assertFalse(result['accepted'])
        self.assertNotIn(str(self.folder), json.dumps(result))

    def test_vector_claim_rejects_embedded_bitmap_and_executable_xml(self):
        fixtures = [
            '<svg viewBox="0 0 24 24"><image href="data:image/png;base64,abc"/></svg>',
            '<svg viewBox="0 0 24 24"><script>alert(1)</script><path d="M1 1h1"/></svg>',
            '<svg viewBox="0 0 24 24"><path onload="x" d="M1 1h1"/></svg>',
            '<!DOCTYPE svg [<!ENTITY x "y">]><svg viewBox="0 0 24 24"><path d="M1 1h1"/></svg>',
            '<svg xmlns="urn:not-svg" viewBox="0 0 24 24"><path d="M1 1h1"/></svg>',
            '<svg viewBox="0 0 24 24"><path fill="url(https://example.com/x)" d="M1 1h1"/></svg>',
            '<svg viewBox="0 0 nan 24"><path d="M1 1h1"/></svg>',
            '<?xml-stylesheet type="text/css" href="https://example.com/x.css"?><svg viewBox="0 0 24 24"><path d="M1 1h1"/></svg>',
            '<?work xsl="file:///private.xsl"?><svg viewBox="0 0 24 24"><path d="M1 1h1"/></svg>',
        ]
        for i, source in enumerate(fixtures):
            self.svg.write_text(source, encoding='utf-8')
            self.assertFalse(self.accept('bad-vector-'+str(i))['accepted'])

    def test_mixed_drawing_styles_reject_the_jobs_contract(self):
        self.jobs['jobs'][0]['styleId'] = 'different'
        with self.assertRaisesRegex(ValueError, 'same shared'):
            self.accept()

    def test_standard_xml_declaration_remains_valid(self):
        self.svg.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>'+self.svg.read_bytes())
        self.assertTrue(self.accept()['accepted'])

    def test_private_reference_paths_are_not_copied_into_manifest(self):
        self.jobs['styleLock']['referenceImages'] = [{'file': 'C:/private/extracted/company-reference.png', 'sha256': 'a'*64, 'role': 'style', 'origin': 'organization'}]
        result = self.accept()
        self.assertTrue(result['accepted'])
        self.assertNotIn('C:/private', json.dumps(result))
        self.assertEqual(result['styleLock']['referenceImages'][0]['sha256'], 'a'*64)

    def test_optional_run_link_requires_matching_jobs_and_actual_bytes(self):
        import production_run as run
        self.save()
        run_dir = self.folder / 'run'
        run.init_run(self.jobs_file, run_dir, 'synthetic-delivery-test')
        run.start_attempt(run_dir, 'invoice')
        receipt = self.folder / 'tool.json'
        receipt.write_text(json.dumps({'schema': 'taskobo-visuals.tool-receipt/v1', 'tool': 'synthetic-unit-test', 'outcome': 'succeeded'}), encoding='utf-8')
        run.record_result(run_dir, 'invoice', 1, receipt, self.svg)
        result = self.accept('linked', run_dir)
        self.assertTrue(result['accepted'], result)
        self.assertEqual(result['assets'][0]['production']['runId'], 'synthetic-delivery-test')
        self.jobs['jobs'][0]['meaning'] = 'Changed synthetic meaning after the run snapshot'
        result = self.accept('different-jobs', run_dir)
        self.assertFalse(result['accepted'])

    def test_cli_returns_2_for_missing_independent_files(self):
        self.files['assets'] = []; self.save()
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/delivery_manifest.py'), '--jobs', str(self.jobs_file), '--files', str(self.files_file), '--output', str(self.folder / 'cli')], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)['accepted'])


@unittest.skipUnless(Image is not None, 'PNG inspection requires optional Pillow.')
class PngDeliveryTests(Fixture):
    def png(self, mode='RGBA', color=(0, 0, 0, 0)):
        path = self.folder / 'invoice.png'
        image = Image.new(mode, (100, 100), color)
        ImageDraw.Draw(image).rectangle((12, 12, 87, 87), fill=(20, 70, 150, 255) if mode == 'RGBA' else (20, 70, 150))
        image.save(path)
        self.files['assets'][0].update(file='invoice.png', representation='generated-raster')
        return path

    def test_png_alpha_background_and_identity(self):
        path = self.png(); before = path.read_bytes()
        result = self.accept()
        self.assertTrue(result['accepted'])
        self.assertEqual(result['assets'][0]['checks']['alphaExtrema'], [0, 255])
        self.assertEqual(path.read_bytes(), before)

    def test_rgb_and_nearly_opaque_alpha_reject_for_transparent_asset(self):
        self.png('RGB', (255, 255, 255))
        self.assertFalse(self.accept('rgb')['accepted'])
        self.png('RGBA', (255, 255, 255, 254))
        result = self.accept('nearly-opaque')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['errors'][0]['code'], 'no-fully-transparent-pixels')

    def test_explicit_full_scene_can_be_opaque(self):
        self.png('RGB', (255, 255, 255))
        self.jobs['jobs'][0].update(kind='illustration', transparent_background=False, displaySize='640x360px')
        result = self.accept()
        self.assertTrue(result['accepted'])
        self.assertEqual(result['assets'][0]['displaySize'], '640x360px')


class CatalogTests(Fixture):
    def test_explicit_approval_and_multilingual_search(self):
        entry = self.approve()
        for query in ['PENDING INVOICE', 'invoice-pending', '請求書', '待确认发票', 'verification']:
            result = catalog.search_catalog(self.catalog_dir, query=query, style_id='monoline', style_version='2', display_size='96px')
            self.assertEqual([e['id'] for e in result['matches']], [entry['id']])
        self.assertEqual(entry['review']['type'], 'explicit')
        self.assertIn('Synthetic', entry['review']['source'])

    def test_no_machine_acceptance_becomes_catalog_approval_implicitly(self):
        manifest = self.prepare_catalog()
        self.assertFalse(catalog.search_catalog(self.catalog_dir)['matches'])
        with self.assertRaisesRegex(ValueError, 'reviewer'):
            catalog.approve_asset(self.catalog_dir, manifest, 'invoice', 'invoice-pending', '', 'fake source')
        self.assertFalse(catalog.search_catalog(self.catalog_dir)['matches'])

    def test_filters_are_exact_and_never_substitute(self):
        self.approve()
        self.assertEqual(len(catalog.search_catalog(self.catalog_dir, profile_version='1.0.0')['matches']), 1)
        for filters in [dict(style_id='matte-3d'), dict(style_version='1'), dict(profile_version='2.0.0'), dict(display_size='48px'), dict(kind='illustration'), dict(palette={'primary': '#123456', 'ink': '#2B1834'})]:
            self.assertFalse(catalog.search_catalog(self.catalog_dir, **filters)['matches'])
        exact = {'palette': {'roles': {'primary': '#73385f', 'ink': '#2b1834'}}}
        self.assertEqual(len(catalog.search_catalog(self.catalog_dir, palette=exact)['matches']), 1)

    def test_changed_files_are_excluded_from_search_and_block_reuse(self):
        entry = self.approve()
        (self.catalog_dir / entry['file']).write_bytes(b'changed')
        result = catalog.search_catalog(self.catalog_dir)
        self.assertFalse(result['matches'])
        self.assertEqual(len(result['integrityExcluded']), 1)
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            catalog.reuse_asset(self.catalog_dir, entry['id'], self.folder / 'reuse.svg')
        self.assertFalse((self.folder / 'reuse.svg').exists())

    def test_reuse_preserves_approved_bytes_and_rejects_wrong_format_or_size(self):
        entry = self.approve()
        target = self.folder / 'reused.svg'
        result = catalog.reuse_asset(self.catalog_dir, entry['id'], target, style_id='monoline', display_size='96')
        self.assertEqual(result['transformation'], 'none')
        self.assertEqual(target.read_bytes(), (self.catalog_dir / entry['file']).read_bytes())
        with self.assertRaises(ValueError): catalog.reuse_asset(self.catalog_dir, entry['id'], target)
        with self.assertRaisesRegex(ValueError, 'format'): catalog.reuse_asset(self.catalog_dir, entry['id'], self.folder/'bitmap.png')
        with self.assertRaisesRegex(ValueError, 'filters'): catalog.reuse_asset(self.catalog_dir, entry['id'], self.folder/'wrong-size.svg', display_size='192px')

    def test_unapproved_metadata_is_never_returned(self):
        entry = self.approve()
        path = self.catalog_dir/'catalog.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['assets'][0]['review']['status'] = 'generated-unreviewed'
        path.write_text(json.dumps(data), encoding='utf-8')
        self.assertFalse(catalog.search_catalog(self.catalog_dir)['matches'])
        with self.assertRaises(ValueError): catalog.reuse_asset(self.catalog_dir, entry['id'], self.folder/'unapproved.svg')

    def test_changed_delivery_bytes_and_duplicate_approval_are_rejected(self):
        manifest = self.prepare_catalog()
        delivered = self.folder/'delivery/assets/invoice.svg'
        before = delivered.read_bytes()
        delivered.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed after acceptance'):
            catalog.approve_asset(self.catalog_dir, manifest, 'invoice', 'invoice-pending', 'fixture-reviewer', 'Fixture, not actual review')
        delivered.write_bytes(before)
        catalog.approve_asset(self.catalog_dir, manifest, 'invoice', 'invoice-pending', 'fixture-reviewer', 'Fixture, not actual review')
        with self.assertRaisesRegex(ValueError, 'already have'):
            catalog.approve_asset(self.catalog_dir, manifest, 'invoice', 'invoice-pending', 'fixture-reviewer', 'Fixture, not actual review')

    def test_catalog_cannot_silently_reinitialize_existing_data(self):
        self.approve()
        before = (self.catalog_dir/'catalog.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'new or empty'): catalog.init_catalog(self.catalog_dir)
        self.assertEqual((self.catalog_dir/'catalog.json').read_bytes(), before)

    def test_second_approval_is_busy_until_first_writer_finishes(self):
        manifest = self.prepare_catalog()
        entered, release = threading.Event(), threading.Event()
        original = catalog.save_catalog
        errors = []
        def pause(*args, **kwargs):
            entered.set()
            if not release.wait(5): raise RuntimeError('Synthetic test barrier timeout')
            return original(*args, **kwargs)
        def first():
            try: catalog.approve_asset(self.catalog_dir, manifest, 'invoice', 'invoice-pending', 'fixture', 'Synthetic approval fixture')
            except Exception as error: errors.append(error)
        with mock.patch.object(catalog, 'save_catalog', pause):
            thread = threading.Thread(target=first)
            thread.start()
            self.assertTrue(entered.wait(5))
            try:
                with self.assertRaisesRegex(ValueError, 'busy'):
                    catalog.approve_asset(self.catalog_dir, manifest, 'invoice', 'second-meaning', 'fixture', 'Synthetic fixture')
            finally:
                release.set(); thread.join(5)
        self.assertFalse(errors, errors)
        self.assertEqual(len(catalog.search_catalog(self.catalog_dir)['matches']), 1)
        self.assertFalse((self.catalog_dir/'.catalog-write.lock').exists())

    def test_new_file_reuse_cannot_overwrite_a_concurrent_creation(self):
        entry = self.approve()
        output = self.folder/'competing.svg'
        original = Path.open
        def compete(path, mode='r', *args, **kwargs):
            if path == output and mode == 'xb':
                with original(path, 'wb') as stream: stream.write(b'competing writer')
            return original(path, mode, *args, **kwargs)
        with mock.patch.object(Path, 'open', compete):
            with self.assertRaises(FileExistsError):
                catalog.reuse_asset(self.catalog_dir, entry['id'], output)
        self.assertEqual(output.read_bytes(), b'competing writer')


if __name__ == '__main__':
    unittest.main()
