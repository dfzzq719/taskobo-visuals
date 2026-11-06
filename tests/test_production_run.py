"""Synthetic file/receipt tests; no image generation or visual approval is performed."""
import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import production_run as runs

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')


class ProductionRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.ref = self.folder/'ref.png'; self.ref.write_bytes(PNG)
        self.jobs = {'schema':'taskobo-visuals.generation-jobs/v1', 'status':'planned',
                     'styleLock': {'styleId':'monoline','styleVersion':'2'},
                     'jobs':[{'id': name, 'kind':'icon' if name == 'beta' else 'illustration', 'styleId':'monoline',
                              'styleVersion':'2','prompt':'PRIVATE TEST PROMPT '+name,
                              'referenceImages':[{'file':'ref.png','sha256':runs.digest(PNG),'role':'style'}]}
                             for name in ('alpha','beta')]}
        self.jobs_file = self.folder/'jobs.json'; self.jobs_file.write_bytes(runs.json_bytes(self.jobs))
        self.run = self.folder/'run'
        self.image = self.folder/'output.png'; self.image.write_bytes(PNG)
        self.receipt = self.folder/'tool.json'; self.receipt.write_bytes(runs.json_bytes({
            'schema':'taskobo-visuals.tool-receipt/v1','tool':'synthetic-test-tool','outcome':'succeeded'}))

    def init(self, maximum=3):
        return runs.init_run(self.jobs_file,self.run,'test-run',maximum)

    def test_init_pending_and_relative_snapshots_only(self):
        result = self.init()
        self.assertEqual(result['assets']['alpha']['status'],'pending')
        self.assertNotIn('PRIVATE TEST PROMPT',json.dumps(result))
        manifest = runs.read_json(self.run/'run.json')
        self.assertEqual(manifest['jobsSha256'],runs.digest(self.jobs_file.read_bytes()))
        self.assertNotIn(str(self.folder),json.dumps(manifest))
        self.assertEqual(self.jobs_file.read_bytes(),runs.json_bytes(self.jobs))
        with self.assertRaises(ValueError): self.init()

    def test_invalid_reference_never_claims_initialized(self):
        self.ref.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.init()
        self.assertFalse(self.run.exists())

    def test_malformed_or_missing_shared_style_lock_cannot_initialize(self):
        for lock in (None, [], True, {}, {'styleId':'monoline'}, {'styleId':'monoline','styleVersion':''}):
            jobs = copy.deepcopy(self.jobs); jobs['styleLock'] = lock
            self.jobs_file.write_bytes(runs.json_bytes(jobs))
            with self.subTest(lock=lock), self.assertRaises(ValueError):
                self.init()
            self.assertFalse(self.run.exists())

    def test_start_snapshots_exact_prompt_and_reference_bytes(self):
        self.init()
        actual = self.folder/'actual.txt'; actual.write_bytes(b'Exact revised prompt, no approved claim.')
        result = runs.start_attempt(self.run,'alpha',prompt_file=actual)
        self.assertEqual(result['attempt'],1)
        self.assertEqual((self.run/result['prompt']['file']).read_bytes(),actual.read_bytes())
        self.assertEqual((self.run/result['referenceImages'][0]['file']).read_bytes(),PNG)
        self.assertNotIn('Exact revised prompt',json.dumps(result))
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'alpha')
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'not-real')

    def test_success_needs_real_file_and_receipt_unknown_ids_stay_null(self):
        self.init(); runs.start_attempt(self.run,'alpha')
        with self.assertRaises(ValueError): runs.record_result(self.run,'alpha',1)
        with self.assertRaises(ValueError): runs.record_result(self.run,'alpha',1,self.receipt,self.jobs_file)
        result = runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        self.assertEqual(result['status'],'generated-unreviewed')
        saved = runs.read_json(self.run/'attempts/alpha/0001/result.json')
        self.assertEqual(saved['output']['sha256'],runs.digest(PNG))
        self.assertTrue(all(saved['toolReceipt'][key] is None for key in ('model','seed','hostRequestId')))
        with self.assertRaises(ValueError): runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'alpha',retry=True)

    def test_failed_item_retries_are_bounded_and_preserve_other_asset(self):
        self.init(maximum=2)
        runs.start_attempt(self.run,'beta'); runs.record_result(self.run,'beta',1,self.receipt,self.image)
        protected = {str(p.relative_to(self.run)):runs.digest(p.read_bytes()) for p in (self.run/'attempts/beta').rglob('*') if p.is_file()}
        runs.start_attempt(self.run,'alpha'); runs.record_result(self.run,'alpha',1,error='Synthetic timeout, no image returned.')
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'alpha')
        runs.start_attempt(self.run,'alpha',retry=True); runs.record_result(self.run,'alpha',2,error='Second synthetic timeout.')
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'alpha',retry=True)
        self.assertEqual(protected,{str(p.relative_to(self.run)):runs.digest(p.read_bytes()) for p in (self.run/'attempts/beta').rglob('*') if p.is_file()})
        status = runs.run_status(self.run)
        self.assertEqual(status['assets']['alpha']['remainingAttempts'],0)
        self.assertEqual(status['assets']['beta']['status'],'generated-unreviewed')

    def test_completed_asset_requires_explicit_regenerate(self):
        self.init(); runs.start_attempt(self.run,'alpha'); runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        previous = (self.run/'attempts/alpha/0001/result.json').read_bytes()
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'alpha')
        self.assertEqual(runs.start_attempt(self.run,'alpha',regenerate=True)['attempt'],2)
        self.assertEqual((self.run/'attempts/alpha/0001/result.json').read_bytes(),previous)

    def test_retry_keeps_latest_actual_prompt_without_explicit_replacement(self):
        self.init()
        revised = self.folder/'revised.txt'; revised.write_bytes(b'Actual revised prompt that must not reset.')
        first = runs.start_attempt(self.run,'alpha',prompt_file=revised)
        runs.record_result(self.run,'alpha',1,error='Synthetic timeout.')
        second = runs.start_attempt(self.run,'alpha',retry=True)
        self.assertEqual(second['prompt']['sha256'],first['prompt']['sha256'])
        self.assertEqual((self.run/second['prompt']['file']).read_bytes(),revised.read_bytes())
        self.assertEqual([r['sha256'] for r in second['referenceImages']],[r['sha256'] for r in first['referenceImages']])

    def test_identical_partial_record_can_resume_but_divergent_bytes_cannot(self):
        self.init(); runs.start_attempt(self.run,'alpha')
        original = runs.write_new
        def interrupted(path,data):
            if Path(path).name == 'result.json': raise OSError('Synthetic interruption before terminal result.')
            return original(path,data)
        with mock.patch.object(runs,'write_new',side_effect=interrupted), self.assertRaises(OSError):
            runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        self.assertEqual(runs.run_status(self.run)['assets']['alpha']['status'],'running')
        saved = (self.run/'attempts/alpha/0001/tool-receipt.json').read_bytes()
        other = self.folder/'other.json'; other.write_bytes(runs.json_bytes({'schema':'taskobo-visuals.tool-receipt/v1','tool':'different-tool','outcome':'succeeded'}))
        with self.assertRaises(ValueError): runs.record_result(self.run,'alpha',1,other,self.image)
        self.assertEqual((self.run/'attempts/alpha/0001/tool-receipt.json').read_bytes(),saved)
        result = runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        self.assertEqual(result['status'],'generated-unreviewed')

    def test_interrupted_start_never_publishes_an_unloadable_attempt(self):
        self.init()
        original = runs.write_new
        def interrupted(path,data):
            if Path(path).name == 'start.json': raise OSError('Synthetic interruption before complete start snapshot.')
            return original(path,data)
        with mock.patch.object(runs,'write_new',side_effect=interrupted), self.assertRaises(OSError):
            runs.start_attempt(self.run,'alpha')
        self.assertEqual(runs.run_status(self.run)['assets']['alpha']['status'],'pending')
        self.assertFalse((self.run/'attempts/alpha/0001').exists())
        self.assertEqual(runs.start_attempt(self.run,'alpha')['attempt'],1)

    def test_reviews_append_and_cannot_imply_automatic_approval(self):
        self.init(); runs.start_attempt(self.run,'alpha')
        with self.assertRaises(ValueError): runs.review_attempt(self.run,'alpha',1,'passed','human','Looks good')
        runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        self.assertEqual(runs.run_status(self.run)['assets']['alpha']['status'],'generated-unreviewed')
        first = runs.review_attempt(self.run,'alpha',1,'changes-requested','agent','Synthetic review asks for less detail.')
        self.assertEqual(first['status'],'changes-requested')
        original = (self.run/'attempts/alpha/0001/review-0001.json').read_bytes()
        second = runs.review_attempt(self.run,'alpha',1,'passed','human','Caller records an explicit human review; not provider authentication.')
        self.assertEqual(second['reviewNumber'],2)
        self.assertEqual((self.run/'attempts/alpha/0001/review-0001.json').read_bytes(),original)
        self.assertEqual(runs.run_status(self.run)['assets']['alpha']['status'],'reviewed')
        self.assertNotIn('approved',runs.run_status(self.run)['assets']['alpha'])

    def test_delivery_evidence_binds_jobs_asset_output_and_attempt(self):
        self.init(); runs.start_attempt(self.run,'alpha'); runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        evidence = runs.delivery_evidence(self.run,'alpha',runs.digest(PNG))
        self.assertEqual(evidence['runId'],'test-run')
        self.assertEqual(evidence['assetId'],'alpha')
        self.assertEqual(evidence['attempt'],1)
        self.assertEqual(evidence['jobsSha256'],runs.digest(self.jobs_file.read_bytes()))
        with self.assertRaises(ValueError): runs.delivery_evidence(self.run,'beta',runs.digest(PNG))
        with self.assertRaises(ValueError): runs.delivery_evidence(self.run,'alpha','0'*64)
        runs.start_attempt(self.run,'alpha',regenerate=True); runs.record_result(self.run,'alpha',2,self.receipt,self.image)
        with self.assertRaises(ValueError): runs.delivery_evidence(self.run,'alpha',runs.digest(PNG))

    def test_modified_output_or_attempt_prompt_invalidates_evidence(self):
        self.init(); started = runs.start_attempt(self.run,'alpha'); result=runs.record_result(self.run,'alpha',1,self.receipt,self.image)
        path = self.run/result['output']['file']; path.write_bytes(PNG+b'modified')
        with self.assertRaises(ValueError): runs.delivery_evidence(self.run,'alpha',runs.digest(PNG))
        path.write_bytes(PNG)
        (self.run/started['prompt']['file']).write_text('changed')
        with self.assertRaises(ValueError): runs.run_status(self.run)

    def test_path_traversal_invalid_ids_and_retry_flags_fail(self):
        self.init()
        for asset in ('../alpha','ALPHA','alpha/beta','missing'):
            with self.assertRaises(ValueError): runs.start_attempt(self.run,asset)
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'alpha',retry=True)
        with self.assertRaises(ValueError): runs.start_attempt(self.run,'alpha',retry=True,regenerate=True)
        with self.assertRaises(ValueError): runs.inside(self.run,'../escape.png')

    def test_cli_status_never_prints_prompt_contents(self):
        self.init(); runs.start_attempt(self.run,'alpha')
        result = subprocess.run([sys.executable,'-B',str(ROOT/'scripts/production_run.py'),'status','--run-dir',str(self.run)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['assets']['alpha']['status'],'running')
        self.assertNotIn('PRIVATE TEST PROMPT',result.stdout)


if __name__ == '__main__':
    unittest.main()
