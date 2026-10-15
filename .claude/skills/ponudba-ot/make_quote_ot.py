#!/usr/bin/env python3
"""Generate an occupational-risk-assessment quote PDF from quote-ot.pdf (requires PyMuPDF).

Usage:
  make_quote_ot.py --quote 2026-155 --name "PANARCH d.o.o." --address "..." \
      --id 6515525000 --vat SI43524788 --jobs 4 --hours 2 --discount 10 [--outdir DIR]

The template and output folder work as in the ponudba skill (<root>/quote-ot.pdf, <root>/ponudbe).

What it does:
  - Page 1: replaces <QUOTE>, <DATE> (D.M.YYYY, today), <C_NAME>, <C_ADDRESS>, <C_ID>, <C_VAT>.
  - Page 2 (price table, unit prices 120 EUR per job, 100 EUR per hour of on-site doctor visit):
      <NUM_JOBS> = --jobs, <NUM_HOURS> = --hours, <TOTAL> = quantity * unit price (first
      occurrence jobs row, second hours row), <SUM_TOTAL> = sum of both, <DISCOUNT> = --discount (%),
      <DISCOUNT_SUM> = SUM_TOTAL * discount / 100, <FINAL_SUM> = SUM_TOTAL - DISCOUNT_SUM
      (bottom table row and the note under the table).
    Amounts are formatted Slovenian style (1.234,50). The template splits some placeholders over
    two lines (and has "<SUM TOTAL>" with a space); they are matched across lines and written on one line.
  - Warns on stderr about unfilled placeholders.
"""
import argparse, datetime, re, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pymupdf

def _font(*candidates):
    return next((p for p in candidates if Path(p).exists()), candidates[0])

FONT_R = _font('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
               '/System/Library/Fonts/Supplemental/Arial.ttf')
FONT_B = _font('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
               '/System/Library/Fonts/Supplemental/Arial Bold.ttf')
PRICE_JOB, PRICE_HOUR = Decimal(120), Decimal(100)
PLACEHOLDER = re.compile(r'<[A-Z_ ]+>')
INVISIBLE = '​'


def money(d):
    d = d.quantize(Decimal('0.01'), ROUND_HALF_UP)
    return f'{d:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def number(d):
    s = format(d.normalize(), 'f')
    return s.replace('.', ',')


def groups(page):
    """Spans containing a placeholder; a placeholder broken over lines ('<NUM_J' + 'OBS>') is one group.
    A lone 'EUR' span right below a completed placeholder is absorbed into it."""
    spans = [s for b in page.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
    out, i = [], 0
    while i < len(spans):
        s = spans[i]
        if '<' not in s['text']:
            i += 1
            continue
        grp = [s]
        while grp[-1]['text'].rfind('<') > grp[-1]['text'].rfind('>') and i + len(grp) < len(spans):
            grp.append(spans[i + len(grp)])
        i += len(grp)
        nxt = spans[i] if i < len(spans) else None
        if (nxt and nxt['text'].strip() == 'EUR' and abs(nxt['bbox'][0] - s['bbox'][0]) < 2
                and not ''.join(g['text'] for g in grp).rstrip().endswith('EUR')):
            grp.append(nxt)
            i += 1
        out.append(grp)
    return out


def fill_page(page, values):
    """values: key -> text, or key -> list of texts consumed in order of occurrence."""
    norm = lambda k: re.sub(r'[ _]', '', k)
    values = {norm(k): v for k, v in values.items()}
    todo, queues = [], {k: list(v) if isinstance(v, list) else None for k, v in values.items()}
    fb = pymupdf.Font(fontfile=FONT_B)
    fr = pymupdf.Font(fontfile=FONT_R)
    for grp in groups(page):
        full = ''.join(s['text'] for s in grp)
        start = full.index('<')

        def sub(m):
            key = norm(m.group(0)[1:-1])
            v = values.get(key)
            if v is None:
                return m.group(0)
            return queues[key].pop(0) if queues[key] is not None else v

        tail = re.sub(r'\s+', ' ', PLACEHOLDER.sub(sub, full[start:])).strip()
        if '<' in tail:
            continue
        first = grp[0]
        bold = 'Bold' in first['font']
        prefix = first['text'][:start].replace(INVISIBLE, '')
        x = first['bbox'][0] + (fb if bold else fr).text_length(prefix, first['size'])
        rects = [pymupdf.Rect(x, first['bbox'][1] + 1, first['bbox'][2], first['bbox'][3] - 1)]
        rects += [pymupdf.Rect(s['bbox']) + (0, 0, 0, -1) for s in grp[1:]]
        todo.append((rects, (x, first['origin'][1]), tail, first['size'], bold))
    for rects, _, _, _, _ in todo:
        for r in rects:
            page.add_redact_annot(r, fill=(1, 1, 1))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    for _, pos, text, size, bold in todo:
        page.insert_text(pos, text, fontname='B' if bold else 'R',
                         fontfile=FONT_B if bold else FONT_R, fontsize=size)


def dec(s):
    return Decimal(s.replace(',', '.'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quote', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--address', required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--vat', required=True)
    ap.add_argument('--jobs', required=True, type=dec, help='number of job types (delovna mesta)')
    ap.add_argument('--hours', required=True, type=dec, help='hours of on-site examination by a doctor')
    ap.add_argument('--discount', required=True, type=dec, help='discount in percent, e.g. 10')
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument('--outdir', type=Path)
    a = ap.parse_args()
    if a.jobs < 0 or a.hours < 0 or not 0 <= a.discount <= 100:
        ap.error('--jobs/--hours must be >= 0 and --discount between 0 and 100')

    q = Decimal('0.01')
    t_jobs, t_hours = (a.jobs * PRICE_JOB).quantize(q, ROUND_HALF_UP), (a.hours * PRICE_HOUR).quantize(q, ROUND_HALF_UP)
    total = t_jobs + t_hours
    disc = (total * a.discount / 100).quantize(q, ROUND_HALF_UP)
    final = total - disc

    today = datetime.date.today()
    page1 = {'QUOTE': a.quote, 'DATE': f'{today.day}.{today.month}.{today.year}',
             'C_NAME': a.name, 'C_ADDRESS': a.address, 'C_ID': a.id, 'C_VAT': a.vat}
    page2 = {'NUM_JOBS': number(a.jobs), 'NUM_HOURS': number(a.hours),
             'TOTAL': [money(t_jobs), money(t_hours)], 'SUM_TOTAL': money(total),
             'DISCOUNT': number(a.discount), 'DISCOUNT_SUM': money(disc), 'FINAL_SUM': money(final)}

    doc = pymupdf.open(a.root / 'quote-ot.pdf')
    fill_page(doc[0], page1)
    fill_page(doc[1], page2)

    left = PLACEHOLDER.findall(''.join(p.get_text() for p in doc))
    if left:
        print('WARNING: unfilled placeholders: ' + ', '.join(left), file=sys.stderr)

    outdir = a.outdir or a.root / 'ponudbe'
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f'{today.isoformat()}_{a.name}_{a.quote}.pdf'
    doc.save(out)
    print(out)


if __name__ == '__main__':
    main()
