import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_assets

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, 'Pillow is optional; PNG checks run in the Pillow CI job.')
class AssetChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def image(self, name='input.png', mode='RGBA', background=(0, 0, 0, 0), box=(12, 12, 87, 87)):
        path = self.folder / name
        image = Image.new(mode, (100, 100), background)
        if box is not None:
            ImageDraw.Draw(image).rectangle(box, fill=(20, 70, 150, 255) if mode == 'RGBA' else (20, 70, 150))
        image.save(path, format='PNG')
        return path

    def test_real_alpha_and_preview_do_not_modify_original(self):
        source = self.image()
        before = source.read_bytes()
        report = check_assets.check_assets([source], self.folder / 'qa', (96, 96), '#EDF3FF')
        item = report['assets'][0]
        self.assertTrue(report['passed'])
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(item['sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(item['dimensions'], [100, 100])
        self.assertEqual(item['coreBoundingBoxAtAlpha16'], [12, 12, 88, 88])
        self.assertEqual(item['maximumEdgeAlpha'], 0)
        self.assertEqual(item['visualReview'], 'not-performed')
        self.assertEqual(item['semanticReview'], 'not-performed')
        self.assertEqual(item['styleReview'], 'not-performed')
        self.assertEqual([p['role'] for p in item['previewLayout']['panelsLeftToRight']], ['light', 'dark', 'document'])
        preview = Image.open(self.folder / 'qa' / item['preview'])
        self.assertEqual(preview.size, (416, 128))
        # Preview backgrounds are actual composites, not a claim that the source was repaired.
        self.assertEqual(preview.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(preview.getpixel((144, 0)), (32, 33, 36))
        self.assertNotIn(str(self.folder), json.dumps(report))

    def test_rgb_is_error_for_transparent_and_valid_for_opaque(self):
        source = self.image(mode='RGB', background=(252, 251, 248))
        transparent, _ = check_assets.inspect_asset(source)
        self.assertEqual(transparent['errors'][0]['code'], 'missing-alpha')
        opaque, _ = check_assets.inspect_asset(source, expected_transparent=False)
        self.assertFalse(opaque['errors'])
        self.assertFalse(opaque['warnings'])

    def test_alpha_channel_without_transparency_is_error(self):
        source = self.image(background=(255, 255, 255, 255))
        result, _ = check_assets.inspect_asset(source)
        self.assertTrue(result['hasAlpha'])
        self.assertEqual(result['errors'][0]['code'], 'fully-opaque')

    def test_all_transparent_is_error_even_for_full_page(self):
        source = self.image(box=None)
        for transparent in (True, False):
            result, _ = check_assets.inspect_asset(source, expected_transparent=transparent)
            self.assertEqual(result['errors'][0]['code'], 'all-transparent')
            self.assertIsNone(result['visibleBoundingBox'])

    def test_faint_edge_alpha_is_warning_not_definite_clip(self):
        source = self.image()
        image = Image.open(source)
        image.putpixel((0, 50), (70, 70, 70, 1))
        image.save(source)
        result, _ = check_assets.inspect_asset(source)
        self.assertFalse(result['errors'])
        self.assertIn('soft-alpha-at-edge', [w['code'] for w in result['warnings']])
        self.assertNotIn('opaque-edge-contact', [w['code'] for w in result['warnings']])
        self.assertEqual(result['coreBoundingBoxAtAlpha16'], [12, 12, 88, 88])
        self.assertEqual(result['visibleBoundingBox'], [0, 12, 88, 88])

    def test_edge_subject_contact_and_excessive_margins_are_risks(self):
        edge = self.image('edge.png', box=(0, 10, 80, 90))
        result, _ = check_assets.inspect_asset(edge)
        self.assertIn('opaque-edge-contact', [w['code'] for w in result['warnings']])
        small = self.image('small.png', box=(45, 45, 54, 54))
        result, _ = check_assets.inspect_asset(small)
        self.assertIn('large-transparent-margins', [w['code'] for w in result['warnings']])
        self.assertFalse(result['errors'])

    def test_palette_png_transparency_is_recognized(self):
        source = self.folder / 'palette.png'
        image = Image.new('P', (100, 100), 0)
        image.putpalette([255, 255, 255, 20, 70, 150] + [0] * (768 - 6))
        ImageDraw.Draw(image).rectangle((12, 12, 87, 87), fill=1)
        image.save(source, transparency=0)
        result, _ = check_assets.inspect_asset(source)
        self.assertEqual(result['mode'], 'P')
        self.assertTrue(result['hasAlpha'])
        self.assertFalse(result['errors'])

    def test_preview_preserves_non_square_aspect(self):
        image = Image.new('RGBA', (200, 100), (10, 20, 30, 255))
        _, layout = check_assets.preview_bytes(image, (96, 96))
        self.assertEqual(layout['renderedImagePx'], [96, 48])

    def test_report_destination_cannot_overwrite_any_input(self):
        source = self.image('report.json')
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, 'overwrite an input'):
            check_assets.check_assets([source], self.folder)
        self.assertEqual(source.read_bytes(), before)

    def test_missing_and_non_png_inputs_are_private_errors(self):
        fake = self.folder / 'not-an-image.png'
        fake.write_text('private source data', encoding='utf-8')
        report = check_assets.check_assets([fake, self.folder / 'missing.png'], self.folder / 'qa')
        self.assertFalse(report['passed'])
        self.assertEqual(len(report['assets']), 2)
        self.assertNotIn('private source data', json.dumps(report))
        self.assertNotIn(str(self.folder), json.dumps(report))

    def test_cli_returns_actionable_error_status(self):
        source = self.image(mode='RGB', background=(255, 255, 255))
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/check_assets.py'), '--input', str(source), '--output', str(self.folder / 'qa')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)['passed'])


class OptionalDependencyTests(unittest.TestCase):
    def test_missing_pillow_fails_without_install_or_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'must-not-exist'
            with mock.patch.dict(sys.modules, {'PIL': None}):
                with self.assertRaisesRegex(ValueError, 'Pillow is unavailable'):
                    check_assets.check_assets([Path(folder) / 'image.png'], output)
            self.assertFalse(output.exists())

    def test_size_and_color_validation(self):
        self.assertEqual(check_assets.parse_size('640x360'), (640, 360))
        self.assertEqual(check_assets.parse_size('96'), (96, 96))
        self.assertEqual(check_assets.parse_color('#eDf3ff'), '#EDF3FF')
        for value in ['0', '99999', '96x0', '-96']:
            with self.assertRaises(Exception):
                check_assets.parse_size(value)
        with self.assertRaises(Exception):
            check_assets.parse_color('blue')


if __name__ == '__main__':
    unittest.main()
