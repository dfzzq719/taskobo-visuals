#!/usr/bin/env python3
"""Inspect PNG files and make diagnostic compositing previews; never edit originals."""
import argparse
import hashlib
import json
import re
import sys
import warnings
from io import BytesIO
from pathlib import Path


def pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        raise ValueError('Pillow is unavailable. Use an environment with Pillow for PNG checks; this tool does not install packages.') from None


def parse_size(value):
    match = re.fullmatch(r'([1-9][0-9]{0,3})(?:x([1-9][0-9]{0,3}))?', value)
    if not match:
        raise argparse.ArgumentTypeError('Use a display size such as 96 or 640x360.')
    size = (int(match[1]), int(match[2] or match[1]))
    if max(size) > 4096:
        raise argparse.ArgumentTypeError('Diagnostic display sizes cannot exceed4096px per side.')
    return size


def parse_color(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise argparse.ArgumentTypeError('A document background must be a six-digit sRGB HEX value.')
    return value.upper()


def extrema_at_edge(alpha):
    width, height = alpha.size
    strips = [(0, 0, width, 1), (0, height - 1, width, height),
              (0, 0, 1, height), (width - 1, 0, width, height)]
    return max(alpha.crop(box).getextrema()[1] for box in strips)


def inspect_asset(path, expected_transparent=True):
    """Read one PNG. Warnings identify risks; they do not decide visual quality."""
    Image = pillow()
    path = Path(path)
    try:
        raw = path.read_bytes()
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format != 'PNG':
                    raise ValueError('Only actual PNG files are inspected by this entry point.')
                source.verify()
            with Image.open(BytesIO(raw)) as source:
                source.load()
                mode = source.mode
                has_alpha = 'A' in source.getbands() or 'transparency' in source.info
                image = source.convert('RGBA')
    except ValueError:
        raise
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('PNG could not be safely decoded; the file may be missing, damaged or too large.') from None
    alpha = image.getchannel('A')
    alpha_min, alpha_max = alpha.getextrema()
    bbox = alpha.getbbox()
    # Ignore almost transparent peripheral pixels when measuring meaningful margins.
    core = alpha.point(lambda value: 255 if value >= 16 else 0)
    core_bbox = core.getbbox()
    width, height = image.size
    edge_max = extrema_at_edge(alpha)
    errors, risks = [], []
    if alpha_max == 0:
        errors.append({'code': 'all-transparent', 'message': 'The file contains no visible pixels.'})
    elif expected_transparent and not has_alpha:
        errors.append({'code': 'missing-alpha', 'message': 'A transparent asset was requested, but the PNG has no Alpha channel or transparency entry.'})
    elif expected_transparent and alpha_min == 255:
        errors.append({'code': 'fully-opaque', 'message': 'A transparent asset was requested, but every pixel is opaque.'})
    margins = None
    if core_bbox:
        left, top, right, bottom = core_bbox
        margins = {'left': left / width, 'top': top / height,
                   'right': (width - right) / width, 'bottom': (height - bottom) / height}
        bbox_fraction = ((right - left) * (bottom - top)) / (width * height)
        if expected_transparent and (max(margins.values()) > 0.25 or bbox_fraction < 0.35):
            risks.append({'code': 'large-transparent-margins', 'message': 'The meaningful content occupies a small or offset region. Check readability at the intended placement size; this can be intentional.'})
    if expected_transparent and edge_max >= 128:
        risks.append({'code': 'opaque-edge-contact', 'message': 'Substantial Alpha reaches the canvas edge. Inspect for clipped subjects or shadows; edge contact alone does not prove a defect.'})
    elif expected_transparent and edge_max > 0:
        risks.append({'code': 'soft-alpha-at-edge', 'message': 'Only translucent pixels reach the edge. This may be a soft shadow or fade; inspect the composite preview.'})
    result = {
        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
        'format': 'PNG', 'mode': mode, 'dimensions': [width, height],
        'expectedBackground': 'transparent' if expected_transparent else 'opaque-or-full-page',
        'hasAlpha': has_alpha, 'alphaExtrema': [alpha_min, alpha_max],
        'visibleBoundingBox': list(bbox) if bbox else None,
        'coreBoundingBoxAtAlpha16': list(core_bbox) if core_bbox else None,
        'coreMarginFractions': margins, 'maximumEdgeAlpha': edge_max,
        'errors': errors, 'warnings': risks,
        'status': 'generated-unreviewed',
        'machineChecks': 'attention-required' if errors else 'passed-with-warnings' if risks else 'passed',
        'visualReview': 'not-performed', 'semanticReview': 'not-performed', 'styleReview': 'not-performed'
    }
    return result, image


def preview_bytes(image, display_size, background=None):
    """Resize/composite for inspection only. Returns an unlabelled diagnostic PNG."""
    Image = pillow()
    width, height = display_size
    backgrounds = [('light', '#FFFFFF'), ('dark', '#202124')]
    if background:
        backgrounds.append(('document', background))
    margin, gap = 16, 16
    panel_width, panel_height = width + margin * 2, height + margin * 2
    sheet = Image.new('RGB', (panel_width * len(backgrounds) + gap * (len(backgrounds) - 1), panel_height), '#B6B8BC')
    # Always preserve the source's aspect ratio, including the transparent margins.
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    rendered = image.resize(size, Image.Resampling.LANCZOS)
    panels = []
    for index, (name, color) in enumerate(backgrounds):
        x = index * (panel_width + gap)
        panel = Image.new('RGBA', (panel_width, panel_height), color)
        panel.alpha_composite(rendered, ((panel_width - size[0]) // 2, (panel_height - size[1]) // 2))
        sheet.paste(panel.convert('RGB'), (x, 0))
        panels.append({'role': name, 'background': color, 'box': [x, 0, x + panel_width, panel_height]})
    stream = BytesIO()
    sheet.save(stream, format='PNG')
    return stream.getvalue(), {'panelsLeftToRight': panels, 'placementBoxPx': [width, height], 'renderedImagePx': list(size), 'labels': 'No text is baked into this diagnostic image; panel roles are in this JSON.'}


def check_assets(paths, output, display_size=(96, 96), background=None, opaque=False):
    Image = pillow()  # Fail before creating any output if Pillow is unavailable.
    del Image
    paths = [Path(p).resolve() for p in paths]
    if not paths or len(paths) > 48 or len(set(paths)) != len(paths):
        raise ValueError('Provide1 to48 distinct input files.')
    output = Path(output).resolve()
    if output in paths or (output.exists() and not output.is_dir()):
        raise ValueError('Output must be a directory and cannot overwrite an input.')
    protected = set(paths)
    if (output / 'report.json').resolve() in protected:
        raise ValueError('The report destination would overwrite an input.')
    records, pending = [], []
    for index, path in enumerate(paths, 1):
        identity = f'asset-{index:02d}'
        try:
            record, image = inspect_asset(path, expected_transparent=not opaque)
            name = identity + '-' + record['sha256'][:12] + '-preview.png'
            if (output / name).resolve() in protected:
                raise ValueError('A preview destination would overwrite an input.')
            preview, layout = preview_bytes(image, display_size, background)
            image.close()
            pending.append((output / name, preview))
            record.update(id=identity, preview=name, previewLayout=layout)
        except ValueError as exc:
            # Do not place absolute paths or source document contents in the report.
            record = {'id': identity, 'status': 'generated-unreviewed', 'machineChecks': 'attention-required',
                      'errors': [{'code': 'input-unavailable-or-invalid', 'message': str(exc)}], 'warnings': [],
                      'visualReview': 'not-performed', 'semanticReview': 'not-performed', 'styleReview': 'not-performed'}
        records.append(record)
    report = {'schema': 'taskobo-visuals.asset-checks/v1', 'status': 'generated-unreviewed',
              'passed': all(not r['errors'] for r in records), 'assets': records,
              'scope': 'File integrity, Alpha, geometry and diagnostic compositing only. No semantic, style, font, white-halo or human-anatomy approval is inferred.'}
    # All inspection has finished before any generated file is written.
    output.mkdir(parents=True, exist_ok=True)
    for target, data in pending:
        if target.resolve() in protected:
            raise ValueError('Output cannot overwrite an input.')
        target.write_bytes(data)
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, action='append', type=Path, help='Repeat for each PNG; originals remain read-only.')
    parser.add_argument('--output', required=True, type=Path, help='Explicit directory for report.json and diagnostic preview PNGs.')
    parser.add_argument('--display-size', type=parse_size, default=(96, 96), help='Actual placement box:96 or640x360; source aspect ratio is preserved.')
    parser.add_argument('--background', type=parse_color, help='Additional document background, e.g. #EDF3FF.')
    parser.add_argument('--opaque', action='store_true', help='Inspect a deliberately opaque illustration/full-page image; do not require transparent pixels.')
    args = parser.parse_args()
    try:
        report = check_assets(args.input, args.output, args.display_size, args.background, args.opaque)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['passed'] else 2
    except (ValueError, OSError) as exc:
        # OSError text may contain private paths; retain only the error type.
        message = str(exc) if isinstance(exc, ValueError) else 'Output could not be written; check the explicitly selected directory.'
        print(json.dumps({'error': message, 'status': 'not-checked'}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
