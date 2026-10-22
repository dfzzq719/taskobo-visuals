#!/usr/bin/env python3
"""Read document text/color evidence for an Agent; never infer the topic or upload data."""
import argparse
import hashlib
import json
import posixpath
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}
MAX_FILE = 40 * 1024 * 1024
MAX_MEMBER = 4 * 1024 * 1024
MAX_PACKAGE = 128 * 1024 * 1024
MAX_UNITS = 300


def clean(value):
    return re.sub(r'[ \t]+', ' ', value).strip()


def hex_color(value):
    return '#' + value.upper() if value and re.fullmatch(r'[0-9a-fA-F]{6}', value) else None


class Package:
    def __init__(self, filename):
        self.zip = zipfile.ZipFile(filename)
        members = self.zip.infolist()
        if len(members) > 10000 or sum(i.file_size for i in members) > MAX_PACKAGE:
            self.zip.close()
            raise ValueError('Office package exceeds the local extraction limit.')
        if len({i.filename for i in members}) != len(members):
            self.zip.close()
            raise ValueError('Duplicate Office package entries are unsupported.')
        self.names = {i.filename for i in members}

    def xml(self, name):
        info = self.zip.getinfo(name)
        if info.file_size > MAX_MEMBER:
            raise ValueError('Office XML part exceeds the local extraction limit: ' + name)
        raw = self.zip.read(info)
        declarations = raw.upper().replace(b'\x00', b'')
        if b'<!DOCTYPE' in declarations or b'<!ENTITY' in declarations:
            raise ValueError('XML declarations with entities are unsupported.')
        return ET.fromstring(raw)

    def close(self):
        self.zip.close()


def themes(package, prefix):
    result = []
    for name in sorted(package.names):
        if not re.fullmatch(prefix + r'/theme/theme\d+\.xml', name):
            continue
        root = package.xml(name)
        for scheme in root.findall('.//a:clrScheme', NS):
            colors = []
            for slot in scheme:
                for node in slot:
                    color = hex_color(node.get('val')) or hex_color(node.get('lastClr'))
                    if color:
                        colors.append({'slot': slot.tag.rsplit('}', 1)[-1], 'hex': color})
                        break
            result.append({'part': name, 'name': scheme.get('name', ''), 'colors': colors})
    return result


def pptx(package, result):
    root = package.xml('ppt/presentation.xml')
    relationships = package.xml('ppt/_rels/presentation.xml.rels')
    targets = {r.get('Id'): r for r in relationships}
    ids = root.findall('p:sldIdLst/p:sldId', NS)
    if len(ids) > MAX_UNITS:
        result['warnings'].append('Only the first 300 slides are included.')
    for index, item in enumerate(ids[:MAX_UNITS], 1):
        relation = targets.get(item.get('{' + NS['r'] + '}id'))
        if relation is None or relation.get('TargetMode') == 'External':
            raise ValueError('Slide relationship is missing or external.')
        target = relation.get('Target', '')
        part = target.lstrip('/') if target.startswith('/') else posixpath.normpath('ppt/' + target)
        if not part.startswith('ppt/slides/') or not part.endswith('.xml'):
            raise ValueError('Unexpected slide relationship target.')
        slide = package.xml(part)
        # A paragraph may contain run properties. Only DrawingML text is content.
        paragraphs = [clean(''.join(t.text or '' for t in p.findall('.//a:t', NS))) for p in slide.findall('.//a:p', NS)]
        title = ''
        for shape in slide.findall('.//p:sp', NS):
            ph = shape.find('p:nvSpPr/p:nvPr/p:ph', NS)
            if ph is not None and ph.get('type') in ('title', 'ctrTitle'):
                title = clean(' '.join(t.text or '' for t in shape.findall('.//a:t', NS)))
                break
        result['units'].append({'ref': f'slide:{index}', 'part': part, 'title': title,
                                'hidden': slide.get('show') == '0',
                                'text': '\n'.join(p for p in paragraphs if p)})
        counts = Counter(hex_color(n.get('val')) for n in slide.findall('.//a:srgbClr', NS))
        result['directColors'].extend({'ref': f'slide:{index}', 'hex': color, 'xmlOccurrences': count}
                                      for color, count in counts.items() if color)
    result['themes'] = themes(package, 'ppt')
    result['warnings'].append('Text extraction does not read notes, embedded images, or visual relationships. Theme parts are candidates, not certified brand colors.')


def docx(package, result):
    root = package.xml('word/document.xml')
    paragraphs = root.findall('w:body//w:p', NS)
    if len(paragraphs) > MAX_UNITS:
        result['warnings'].append('Only the first 300 paragraphs are included.')
    for index, paragraph in enumerate(paragraphs[:MAX_UNITS], 1):
        style = paragraph.find('w:pPr/w:pStyle', NS)
        style_id = style.get('{' + NS['w'] + '}val', '') if style is not None else ''
        text = clean(''.join(t.text or '' for t in paragraph.findall('.//w:t', NS)))
        result['units'].append({'ref': f'paragraph:{index}', 'style': style_id, 'text': text})
        counts = Counter(hex_color(c.get('{' + NS['w'] + '}val')) for c in paragraph.findall('.//w:color', NS))
        result['directColors'].extend({'ref': f'paragraph:{index}', 'hex': color, 'xmlOccurrences': count}
                                      for color, count in counts.items() if color)
    result['themes'] = themes(package, 'word')
    result['warnings'].append('Paragraph references are not rendered page numbers. Headers, footers, tracked-change decisions and drawing content require document-specific review.')


def pdf(filename, result):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError('PDF text extraction requires pypdf in this Python environment; use a host PDF tool or provide a text snapshot.') from exc
    reader = PdfReader(str(filename))
    if reader.is_encrypted:
        raise ValueError('Encrypted PDF is unsupported by this helper.')
    if len(reader.pages) > MAX_UNITS:
        result['warnings'].append('Only the first 300 PDF pages are included.')
    for index, page in enumerate(reader.pages[:MAX_UNITS], 1):
        result['units'].append({'ref': f'page:{index}', 'text': (page.extract_text() or '').strip()})
    result['warnings'].append('PDF text only: no OCR, page-layout interpretation, or exact theme-color extraction.')


def extract(filename, max_chars):
    if not filename.is_file() or filename.stat().st_size > MAX_FILE:
        raise ValueError('Input is missing or exceeds 40 MiB.')
    suffix = filename.suffix.lower()
    result = {'schema': 'taskobo-illustration.document-context/v1',
              'source': {'name': filename.name, 'format': suffix.lstrip('.'),
                         'sha256': hashlib.sha256(filename.read_bytes()).hexdigest()},
              'units': [], 'themes': [], 'directColors': [], 'warnings': [],
              'inference': {'status': 'not-performed', 'next': 'Agent proposes content topic, visual direction and palette separately, citing unit refs.'}}
    if suffix in ('.pptx', '.docx'):
        package = Package(filename)
        try:
            (pptx if suffix == '.pptx' else docx)(package, result)
        finally:
            package.close()
    elif suffix in ('.md', '.txt'):
        lines = filename.read_text(encoding='utf-8-sig').splitlines()
        # Preserve source line locations; group paragraphs without inventing pages.
        current, start = [], 1
        for index, line in enumerate(lines + [''], 1):
            if line.strip():
                if not current:
                    start = index
                current.append(line)
            elif current:
                result['units'].append({'ref': f'line:{start}-{index-1}', 'text': '\n'.join(current)})
                current = []
                if len(result['units']) == MAX_UNITS and index < len(lines):
                    result['warnings'].append('Only the first 300 text blocks are included.')
                    break
    elif suffix == '.pdf':
        pdf(filename, result)
    else:
        raise ValueError('Supported inputs: .pptx, .docx, .md, .txt; .pdf with pypdf installed.')
    remaining = max_chars
    for unit in result['units']:
        text = unit['text']
        unit['truncated'] = len(text) > remaining
        unit['text'] = text[:remaining]
        remaining -= len(unit['text'])
    if any(unit['truncated'] for unit in result['units']):
        result['warnings'].append('Text budget reached; analyze missing sections with host tools before making whole-document claims.')
    if not any(unit['text'].strip() for unit in result['units']):
        result['warnings'].append('No usable text found; OCR or another host reader may be required. Do not infer a topic from this empty result.')
    result['textCharacters'] = max_chars - remaining
    result['colorScope'] = 'Office theme definitions and direct XML occurrences; not visual area, computed style, or verified brand identity.'
    return result


def main():
    # Machine-readable UTF-8 output must not depend on a Windows console locale.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--max-chars', type=int, default=60000)
    args = parser.parse_args()
    try:
        if not 100 <= args.max_chars <= 500000:
            raise ValueError('--max-chars must be between 100 and 500000.')
        result = extract(args.input, args.max_chars)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
