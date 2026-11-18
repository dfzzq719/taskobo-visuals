"""A website-only copy update must keep the installed Skill and its catalog paired."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

try:
    from tools import build_site as web
except ModuleNotFoundError as exc:
    if exc.name != 'PIL':
        raise
    web = None


@unittest.skipIf(web is None, 'The website builder requires Pillow')
class WebCopyUpdateTests(unittest.TestCase):
    def test_refreshes_copy_and_preserves_the_published_catalog_and_shell(self):
        manifest = json.loads((web.ROOT / 'website/build-manifest.json').read_text(encoding='utf-8'))
        recipe = json.loads((web.ROOT / 'references/style-recipes.json').read_text(encoding='utf-8'))
        catalog = {'schema': 'taskobo-visuals.web-style-catalog/v1', 'skillVersion': web.VERSION,
                   'version': recipe['version'], 'styles': recipe['styles'][:1]}
        template = '<html><head>%%HEAD%%</head><body><main>%%MAIN%%</main><footer>Existing navigation</footer></body></html>'
        old_js = b'/* Old release */'
        name = 'illustration-' + web.digest(old_js)[:12] + '.js'
        original_cases = web.CATALOG[:]
        self.addCleanup(lambda: web.CATALOG.__setitem__(slice(None), original_cases))
        web.CATALOG[:] = manifest['cases']
        pages = {'': web.homepage(manifest['hero']), 'tool/': web.toolpage(manifest['skillZip'], catalog)}
        pages.update({'samples/' + case['id'] + '/': web.sample(case) for case in manifest['cases']})
        with tempfile.TemporaryDirectory() as temporary:
            baseline, updated = (Path(temporary) / n for n in ('baseline', 'updated'))
            (baseline / 'assets').mkdir(parents=True)
            (baseline / 'assets' / name).write_bytes(old_js)
            for route, body in pages.items():
                target = baseline / route / 'index.html'
                target.parent.mkdir(parents=True, exist_ok=True)
                page = web.render_page(route, 'Previous title', 'Previous description', body, manifest['hero']['large'],
                                       [], template, 'illustration-000000000000.css', name)
                page = page.replace('制作条件をJSONで保存</button>', 'Old download label</button>')
                if route.startswith('samples/'):
                    page = page.replace(web.PAGE_MODIFIED, '2026-10-23')
                target.write_text(page, encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                web.render_web_update(updated, baseline)
            tool = (updated / 'tool/index.html').read_text(encoding='utf-8')
            self.assertIn('制作条件をJSONで保存</button>', tool)
            self.assertIn(web.TOOL_TITLE, tool)
            self.assertIn('Existing navigation', tool)
            self.assertIn(manifest['skillZip'], tool)
            self.assertEqual(tool.count('/assets/usage-20261118.js'), 1)
            self.assertIn(json.dumps(catalog, ensure_ascii=False), tool)
            for case in manifest['cases']:
                page = (updated / 'samples' / case['id'] / 'index.html').read_text(encoding='utf-8')
                self.assertIn('"dateModified": "2026-10-23"', page)
