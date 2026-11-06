#!/usr/bin/env python3
"""Keep local, immutable image-attempt evidence. This script never generates images."""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RUN_SCHEMA = 'taskobo-visuals.production-run/v1'
RESULT_SCHEMA = 'taskobo-visuals.attempt-result/v1'
MAX_BYTES = 128 * 1024 * 1024
ASSET_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
RUN_ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read_bytes(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Expected a local file no larger than 128 MiB.')
    return path.read_bytes()


def read_json(path):
    return json.loads(read_bytes(path).decode('utf-8-sig'))


def inside(base, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative or '\x00' in relative:
        raise ValueError('Run artifact paths must be relative POSIX paths.')
    parts = relative.split('/')
    if PurePosixPath(relative).is_absolute() or any(p in ('', '.', '..') for p in parts):
        raise ValueError('Run artifact paths cannot escape the run directory.')
    candidate = (Path(base) / relative).resolve()
    if not candidate.is_relative_to(Path(base).resolve()):
        raise ValueError('Run artifact path escapes the run directory.')
    return candidate


def write_new(path, data):
    """Create-only write: never replace a prior snapshot, including on network drives."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ValueError('Snapshot already exists; previous evidence cannot be overwritten.')
    try:
        with path.open('xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise ValueError('Snapshot already exists; previous evidence cannot be overwritten.') from None


def verify_file(base, entry):
    if not isinstance(entry, dict) or not re.fullmatch(r'[0-9a-f]{64}', str(entry.get('sha256', ''))):
        raise ValueError('Run file evidence needs a SHA-256 checksum.')
    data = read_bytes(inside(base, entry['file']))
    if digest(data) != entry['sha256'] or ('bytes' in entry and len(data) != entry['bytes']):
        raise ValueError('Recorded file bytes have changed: '+entry['file'])
    return data


def preserve_or_write(path, data):
    """Resume a partial attempt only if any already-saved bytes are identical."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Partial evidence cannot be a symbolic link.')
    if path.exists():
        if read_bytes(path) != data:
            raise ValueError('Partial evidence differs; preserve it and select a new attempt.')
        return
    write_new(path, data)


@contextmanager
def locked(run_dir):
    lock_path = Path(run_dir) / '.production.lock'
    deadline = time.monotonic()+5
    while True:
        try:
            handle = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError('This run is busy or has a stale lock. Inspect .production.lock before retrying.') from None
            time.sleep(0.05)
    try:
        os.write(handle, json_bytes({'pid': os.getpid(), 'createdAt': timestamp()}))
        os.close(handle)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def load_run(run_dir):
    base = Path(run_dir).resolve()
    manifest = read_json(base / 'run.json')
    if not isinstance(manifest, dict) or manifest.get('schema') != RUN_SCHEMA or not RUN_ID.fullmatch(str(manifest.get('runId', ''))):
        raise ValueError('Not a Taskobo Visuals production run.')
    assets = manifest.get('assets')
    if not isinstance(assets, dict) or not assets or any(not ASSET_ID.fullmatch(k) or not isinstance(a, dict) for k, a in assets.items()):
        raise ValueError('Run contains invalid asset records.')
    maximum = manifest.get('maxAttempts')
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 5:
        raise ValueError('Run retry limit is invalid.')
    return base, manifest


def _reference_bytes(reference, jobs_path):
    if not isinstance(reference, dict) or not isinstance(reference.get('file'), str):
        raise ValueError('Each planned reference needs file and sha256.')
    name = reference['file']
    source = Path(name)
    candidates = [source] if source.is_absolute() else [Path(jobs_path).parent/source, ROOT/source]
    expected = reference.get('sha256')
    if not re.fullmatch(r'[0-9a-f]{64}', str(expected)):
        raise ValueError('Planned references need a SHA-256 checksum.')
    for candidate in candidates:
        if candidate.is_file():
            data = read_bytes(candidate)
            if digest(data) == expected:
                suffix = candidate.suffix.lower()
                if suffix not in ('.png', '.jpg', '.jpeg', '.webp'):
                    raise ValueError('Reference snapshots must be PNG, JPEG or WebP.')
                return data, suffix
    raise ValueError('Planned reference is missing or differs from its recorded hash.')


def init_run(jobs_path, run_dir, run_id=None, max_attempts=3):
    raw = read_bytes(jobs_path)
    jobs = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(jobs, dict) or jobs.get('schema') != 'taskobo-visuals.generation-jobs/v1' or jobs.get('status') != 'planned':
        raise ValueError('Initialize from planned prepare_visual_jobs output, not a draft brief or a generated claim.')
    planned = jobs.get('jobs')
    if not isinstance(planned, list) or not 1 <= len(planned) <= 48:
        raise ValueError('A production run needs 1 to 48 independently planned assets.')
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
        raise ValueError('max-attempts must be between 1 and 5.')
    run_id = run_id or ('run-'+uuid.uuid4().hex[:20])
    if not RUN_ID.fullmatch(run_id):
        raise ValueError('Run ID must be 1 to 64 letters, digits, hyphens or underscores.')
    assets, files = {}, {}
    lock = jobs.get('styleLock')
    if not isinstance(lock, dict) or not isinstance(lock.get('styleId'), str) or not ASSET_ID.fullmatch(lock['styleId']) or not isinstance(lock.get('styleVersion'), str) or not lock['styleVersion'].strip():
        raise ValueError('Generation jobs need one shared styleLock.')
    shared_style = lock['styleId']
    for job in planned:
        if not isinstance(job, dict) or not ASSET_ID.fullmatch(str(job.get('id', ''))) or job['id'] in assets:
            raise ValueError('Run asset IDs must be distinct lowercase slugs.')
        if job.get('kind') not in ('icon', 'illustration') or not isinstance(job.get('prompt'), str) or not job['prompt'].strip():
            raise ValueError('Each asset needs its actual planned prompt and asset kind.')
        if shared_style and job.get('styleId') != shared_style:
            raise ValueError('All assets must retain the generation plan shared style ID.')
        if str(job.get('styleVersion')) != str(lock.get('styleVersion')):
            raise ValueError('Asset style versions must match the generation plan shared style version.')
        asset_id = job['id']
        prompt = job['prompt'].encode('utf-8')
        prompt_file = f'plan/prompts/{asset_id}.txt'
        files[prompt_file] = prompt
        refs = []
        if not isinstance(job.get('referenceImages', []), list):
            raise ValueError('referenceImages must be a list.')
        for reference in job.get('referenceImages', []):
            data, suffix = _reference_bytes(reference, jobs_path)
            target = 'plan/references/'+digest(data)+suffix
            files[target] = data
            refs.append({'file': target, 'sha256': digest(data), 'bytes': len(data), 'role': reference.get('role', 'style')})
        assets[asset_id] = {'kind': job['kind'], 'styleId': job.get('styleId'), 'styleVersion': job.get('styleVersion'),
                            'prompt': {'file': prompt_file, 'sha256': digest(prompt), 'bytes': len(prompt)},
                            'referenceImages': refs}
    if sum(len(data) for data in files.values()) > MAX_BYTES:
        raise ValueError('Combined run plan and reference snapshots exceed 128 MiB.')
    base = Path(run_dir).resolve()
    if base.exists() or base.is_symlink():
        raise ValueError('Run directory already exists; initialize into a new directory.')
    base.mkdir(parents=False)
    for name, data in files.items():
        write_new(inside(base, name), data)
    portable_lock = {k: lock[k] for k in ('skillVersion', 'styleId', 'recipeId', 'styleVersion', 'drawingTreatment', 'viewpoint', 'palette', 'typography') if k in lock}
    manifest = {'schema': RUN_SCHEMA, 'runId': run_id, 'createdAt': timestamp(), 'jobsSha256': digest(raw),
                'maxAttempts': max_attempts, 'styleLock': portable_lock, 'assets': assets,
                'limits': 'Local task and caller-supplied tool evidence only. No generation, authenticated provider verification or visual approval.'}
    write_new(base/'run.json', json_bytes(manifest))
    return run_status(base)


def attempt_dir(base, asset_id, attempt):
    if not ASSET_ID.fullmatch(str(asset_id)) or isinstance(attempt, bool) or not isinstance(attempt, int) or not 1 <= attempt <= 5:
        raise ValueError('Invalid asset ID or attempt number.')
    return inside(base, f'attempts/{asset_id}/{attempt:04d}')


def load_attempt(base, manifest, asset_id, attempt):
    if asset_id not in manifest['assets']:
        raise ValueError('Unknown asset ID; no other asset will be changed.')
    folder = attempt_dir(base, asset_id, attempt)
    started = read_json(folder/'start.json')
    if started.get('schema') != 'taskobo-visuals.attempt-start/v1' or started.get('runId') != manifest['runId'] or started.get('assetId') != asset_id or started.get('attempt') != attempt:
        raise ValueError('Attempt identity does not match this run.')
    verify_file(base, started['prompt'])
    for reference in started['referenceImages']:
        verify_file(base, reference)
    return folder, started


def _attempts(base, manifest, asset_id):
    folder = inside(base, 'attempts/'+asset_id)
    if not folder.exists():
        return []
    numbers = sorted(int(p.name) for p in folder.iterdir() if p.is_dir() and re.fullmatch(r'\d{4}', p.name))
    if numbers != list(range(1, len(numbers)+1)) or len(numbers) > manifest['maxAttempts']:
        raise ValueError('Attempt sequence is inconsistent.')
    return numbers


def _state(base, manifest, asset_id, attempt):
    folder, started = load_attempt(base, manifest, asset_id, attempt)
    result_path = folder/'result.json'
    if not result_path.exists():
        return {'attempt': attempt, 'status': 'running'}
    result = read_json(result_path)
    if result.get('schema') != RESULT_SCHEMA or result.get('runId') != manifest['runId'] or result.get('assetId') != asset_id or result.get('attempt') != attempt:
        raise ValueError('Attempt result identity is inconsistent.')
    status = result.get('status')
    if status not in ('failed', 'generated-unreviewed'):
        raise ValueError('Unsupported attempt result status.')
    if status == 'generated-unreviewed':
        verify_file(base, result['output'])
    if result.get('toolReceipt'):
        verify_file(base, result['toolReceipt'])
    reviews = sorted(folder.glob('review-*.json'))
    if reviews:
        if [p.name for p in reviews] != [f'review-{i:04d}.json' for i in range(1,len(reviews)+1)]:
            raise ValueError('Review sequence is inconsistent.')
        review = read_json(reviews[-1])
        if status != 'generated-unreviewed' or review.get('schema') != 'taskobo-visuals.attempt-review/v1' or review.get('decision') not in ('passed','changes-requested') or review.get('reviewer') not in ('agent','human') or review.get('runId') != manifest['runId'] or review.get('assetId') != asset_id or review.get('attempt') != attempt or review.get('resultSha256') != digest(read_bytes(result_path)):
            raise ValueError('Review does not match the recorded output.')
        status = 'reviewed' if review['decision'] == 'passed' else 'changes-requested'
    return {'attempt': attempt, 'status': status, 'output': result.get('output'), 'reviewCount': len(reviews)}


def run_status(run_dir):
    base, manifest = load_run(run_dir)
    assets = {}
    for asset_id in manifest['assets']:
        numbers = _attempts(base, manifest, asset_id)
        assets[asset_id] = _state(base, manifest, asset_id, numbers[-1]) if numbers else {'attempt': None, 'status': 'pending'}
        assets[asset_id]['remainingAttempts'] = manifest['maxAttempts']-len(numbers)
    return {'schema': 'taskobo-visuals.run-status/v1', 'runId': manifest['runId'], 'assets': assets,
            'limits': 'File checks and caller-recorded reviews do not authenticate a provider or prove semantic/visual quality.'}


def start_attempt(run_dir, asset_id, retry=False, regenerate=False, prompt_file=None):
    base, manifest = load_run(run_dir)
    if asset_id not in manifest['assets'] or (retry and regenerate):
        raise ValueError('Select one known asset and at most one retry/regenerate action.')
    with locked(base):
        numbers = _attempts(base, manifest, asset_id)
        if len(numbers) >= manifest['maxAttempts']:
            raise ValueError('The per-asset attempt limit has been reached; review before starting a new run.')
        if numbers:
            state = _state(base, manifest, asset_id, numbers[-1])['status']
            if state == 'running':
                raise ValueError('The selected asset already has a running attempt; record its result or failure first.')
            if state in ('failed', 'changes-requested') and not retry:
                raise ValueError('Retry only this failed/rejected asset with --retry.')
            if state in ('generated-unreviewed', 'reviewed') and not regenerate:
                raise ValueError('Completed assets are preserved; use --regenerate to explicitly select this asset again.')
        elif retry or regenerate:
            raise ValueError('An unstarted asset uses the initial start action, not retry/regenerate.')
        asset = manifest['assets'][asset_id]
        latest = load_attempt(base, manifest, asset_id, numbers[-1])[1] if numbers else asset
        prompt = read_bytes(prompt_file) if prompt_file else verify_file(base, latest['prompt'])
        if not prompt.decode('utf-8-sig').strip():
            raise ValueError('Actual prompt must be nonempty UTF-8 text.')
        reference_bytes = [(ref, verify_file(base, ref)) for ref in latest['referenceImages']]
        attempt = len(numbers)+1
        folder = attempt_dir(base, asset_id, attempt)
        staging = folder.parent / ('.pending-'+uuid.uuid4().hex)
        staging.mkdir(parents=True, exist_ok=False)
        prefix = folder.relative_to(base).as_posix()
        prompt_ref = {'file': prefix+'/prompt.txt', 'sha256': digest(prompt), 'bytes': len(prompt)}
        write_new(staging/'prompt.txt', prompt)
        references = []
        for index, (ref, data) in enumerate(reference_bytes, 1):
            name = prefix+f'/references/{index:02d}'+Path(ref['file']).suffix
            write_new(staging/(f'references/{index:02d}'+Path(ref['file']).suffix), data)
            references.append({'file': name, 'sha256': digest(data), 'bytes': len(data), 'role': ref['role']})
        started = {'schema': 'taskobo-visuals.attempt-start/v1', 'runId': manifest['runId'], 'assetId': asset_id,
                   'attempt': attempt, 'createdAt': timestamp(), 'action': 'retry' if retry else 'regenerate' if regenerate else 'initial',
                   'prompt': prompt_ref, 'referenceImages': references, 'styleId': asset.get('styleId'), 'styleVersion': asset.get('styleVersion')}
        write_new(staging/'start.json', json_bytes(started))
        if folder.exists():
            raise ValueError('Attempt destination already exists; previous evidence is preserved.')
        staging.rename(folder)
    return {'runId': manifest['runId'], 'assetId': asset_id, 'attempt': attempt, 'status': 'running',
            'prompt': prompt_ref, 'referenceImages': references,
            'limits': 'The host must actually send this prompt and these references to its image tool. No generation was performed.'}


def _tool_receipt(path, outcome):
    raw = read_bytes(path)
    value = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(value, dict) or value.get('schema') != 'taskobo-visuals.tool-receipt/v1' or value.get('outcome') != outcome or not isinstance(value.get('tool'), str) or not value['tool'].strip():
        raise ValueError('Provide a tool-receipt/v1 with explicit tool and matching succeeded/failed outcome.')
    for key in ('model', 'hostRequestId'):
        if value.get(key) is not None and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError('Unknown '+key+' must be null; otherwise use the actual nonempty value.')
    seed = value.get('seed')
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, (int, str)) or (isinstance(seed, str) and not seed.strip())):
        raise ValueError('Unknown seed must be null; otherwise record the actual seed value.')
    return raw, {key: value.get(key) for key in ('tool', 'model', 'seed', 'hostRequestId')}


def _artifact(path):
    data = read_bytes(path)
    suffix = Path(path).suffix.lower()
    valid = ((suffix == '.png' and data.startswith(b'\x89PNG\r\n\x1a\n')) or
             (suffix in ('.jpg', '.jpeg') and data.startswith(b'\xff\xd8\xff')) or
             (suffix == '.webp' and data[:4] == b'RIFF' and data[8:12] == b'WEBP') or
             (suffix == '.svg' and b'<svg' in data[:4096]))
    if not valid:
        raise ValueError('Record an actual PNG, JPEG, WebP or SVG file, not a prompt or placeholder path.')
    return data, suffix


def record_result(run_dir, asset_id, attempt, receipt_path=None, output_path=None, error=None):
    base, manifest = load_run(run_dir)
    failed = error is not None
    if failed and (not isinstance(error, str) or not error.strip()):
        raise ValueError('Record the actual failure reason.')
    if not failed and (receipt_path is None or output_path is None):
        raise ValueError('Successful recording needs an actual tool receipt and an existing output file.')
    if failed and output_path is not None:
        raise ValueError('A failed attempt cannot simultaneously claim a generated output.')
    tool_raw, tool = _tool_receipt(receipt_path, 'failed' if failed else 'succeeded') if receipt_path else (None, None)
    output, suffix = _artifact(output_path) if output_path else (None, None)
    with locked(base):
        folder, started = load_attempt(base, manifest, asset_id, attempt)
        if (folder/'result.json').exists():
            raise ValueError('This attempt already has a result; previous evidence cannot be overwritten.')
        prefix = folder.relative_to(base).as_posix()
        receipt = None
        if tool_raw is not None:
            receipt = {'file': prefix+'/tool-receipt.json', 'sha256': digest(tool_raw), 'bytes': len(tool_raw), **tool}
            preserve_or_write(base/receipt['file'], tool_raw)
        artifact = None
        if output is not None:
            artifact = {'file': prefix+'/output'+suffix, 'sha256': digest(output), 'bytes': len(output)}
            preserve_or_write(base/artifact['file'], output)
        result = {'schema': RESULT_SCHEMA, 'runId': manifest['runId'], 'assetId': asset_id, 'attempt': attempt,
                  'recordedAt': timestamp(), 'status': 'failed' if failed else 'generated-unreviewed',
                  'promptSha256': started['prompt']['sha256'], 'referenceHashes': [r['sha256'] for r in started['referenceImages']],
                  'toolReceipt': receipt, 'output': artifact, 'error': error if failed else None,
                  'limits': 'Caller-supplied host evidence and file properties; no independent provider authentication or visual approval.'}
        write_new(folder/'result.json', json_bytes(result))
    return {'runId': manifest['runId'], 'assetId': asset_id, 'attempt': attempt, 'status': result['status'],
            'output': artifact, 'runReceiptSha256': digest(json_bytes(result))}


def review_attempt(run_dir, asset_id, attempt, decision, reviewer, note):
    if decision not in ('passed', 'changes-requested') or reviewer not in ('agent', 'human') or not isinstance(note, str) or not note.strip():
        raise ValueError('Review requires passed/changes-requested, an explicit agent/human reviewer and a review note.')
    base, manifest = load_run(run_dir)
    with locked(base):
        folder, _ = load_attempt(base, manifest, asset_id, attempt)
        state = _state(base, manifest, asset_id, attempt)
        if state['status'] in ('running', 'failed'):
            raise ValueError('Only recorded generated assets can be visually reviewed.')
        number = len(list(folder.glob('review-*.json')))+1
        review = {'schema': 'taskobo-visuals.attempt-review/v1', 'runId': manifest['runId'], 'assetId': asset_id,
                  'attempt': attempt, 'reviewedAt': timestamp(), 'decision': decision, 'reviewer': reviewer, 'note': note,
                  'resultSha256': digest(read_bytes(folder/'result.json')),
                  'limits': 'An explicit caller-recorded review, not authenticated user approval or proof of all future outputs.'}
        write_new(folder/f'review-{number:04d}.json', json_bytes(review))
    return {'runId': manifest['runId'], 'assetId': asset_id, 'attempt': attempt,
            'status': 'reviewed' if decision == 'passed' else 'changes-requested', 'reviewNumber': number}


def delivery_evidence(run_dir, asset_id, sha256):
    """Return portable provenance only for one unique, byte-verified generated attempt."""
    base, manifest = load_run(run_dir)
    if asset_id not in manifest['assets'] or not re.fullmatch(r'[0-9a-f]{64}', str(sha256)):
        raise ValueError('Delivery evidence requires a known asset and actual output SHA-256.')
    matches = []
    for attempt in _attempts(base, manifest, asset_id):
        _state(base, manifest, asset_id, attempt)
        folder = attempt_dir(base, asset_id, attempt)
        if not (folder/'result.json').exists():
            continue
        raw = read_bytes(folder/'result.json')
        result = json.loads(raw)
        if result['status'] == 'generated-unreviewed' and result['output']['sha256'] == sha256:
            matches.append({'runId': manifest['runId'], 'assetId': asset_id, 'attempt': attempt,
                            'runReceiptSha256': digest(raw), 'jobsSha256': manifest['jobsSha256']})
    if len(matches) != 1:
        raise ValueError('No unique recorded generation attempt matches this asset and output hash.')
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    init = sub.add_parser('init'); init.add_argument('--jobs', type=Path, required=True); init.add_argument('--run-dir', type=Path, required=True)
    init.add_argument('--run-id'); init.add_argument('--max-attempts', type=int, default=3)
    status = sub.add_parser('status'); status.add_argument('--run-dir', type=Path, required=True)
    for action in ('start', 'record', 'fail', 'review'):
        command = sub.add_parser(action); command.add_argument('--run-dir', type=Path, required=True); command.add_argument('--asset', required=True)
        if action == 'start':
            flags = command.add_mutually_exclusive_group(); flags.add_argument('--retry', action='store_true'); flags.add_argument('--regenerate', action='store_true')
            command.add_argument('--prompt-file', type=Path)
        else:
            command.add_argument('--attempt', type=int, required=True)
            if action in ('record', 'fail'):
                command.add_argument('--receipt', type=Path, required=action == 'record')
                if action == 'record': command.add_argument('--output', type=Path, required=True)
                else: command.add_argument('--error', required=True)
            else:
                command.add_argument('--decision', choices=['passed', 'changes-requested'], required=True)
                command.add_argument('--reviewer', choices=['agent', 'human'], required=True); command.add_argument('--note', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'init': result = init_run(args.jobs, args.run_dir, args.run_id, args.max_attempts)
        elif args.action == 'status': result = run_status(args.run_dir)
        elif args.action == 'start': result = start_attempt(args.run_dir, args.asset, args.retry, args.regenerate, args.prompt_file)
        elif args.action == 'record': result = record_result(args.run_dir, args.asset, args.attempt, args.receipt, args.output)
        elif args.action == 'fail': result = record_result(args.run_dir, args.asset, args.attempt, args.receipt, error=args.error)
        else: result = review_attempt(args.run_dir, args.asset, args.attempt, args.decision, args.reviewer, args.note)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
