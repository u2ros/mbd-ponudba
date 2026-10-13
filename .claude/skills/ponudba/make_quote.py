#!/usr/bin/env python3
"""Generate a quote PDF from quote.pdf / quote_simple.pdf (requires PyMuPDF).

Usage:
  make_quote.py --quote 2026-155 --name "PANARCH d.o.o." --address "..." \
      --id 6515525000 --vat SI43524788 --jobs AD,PROIZ [--simple] [--outdir DIR]

Templates and matrika.tsv are read from the project root (default: three levels
above this file), the output PDF is written to --outdir (default: <root>/ponudbe, created if missing).

What it does:
  - Replaces <QUOTE>, <DATE> (D.M.YYYY, today), <C_NAME>, <C_ADDRESS>, <C_ID>, <C_VAT> on page 1.
  - Non-simple: builds the table from matrika.tsv (row 1 header, row 2 job codes). Keeps the first
    4 columns (Postavka, Cena, Popust, Cena s popustom; no code) plus every column whose row-2 code
    matches --jobs (case-insensitive, trimmed), drops row 2, copies cell values as they are, keeps
    all rows including the bottom "Cena Predhodni" / "Cena Obdobni" rows. The table replaces <TABLE>
    on landscape page 2 with the disclaimer moved underneath. GRAD1 appends footnote (1) to it.
  - Simple (--simple): only placeholders are substituted, matrika.tsv / --jobs are not used.
  - Warns on stderr about job codes with no column and about unfilled placeholders.
  - --check: only validate --jobs against matrika.tsv (no PDF, no customer args needed).
"""
import argparse, csv, datetime, re, sys
from pathlib import Path

import pymupdf

FONT_R = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
FONT_B = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
TEAL = (0.043, 0.286, 0.353)
GRAD1_NOTE = ('(1) rezanje, brušenje betona, kamnoseštvo, peskanje, vrtanje, mešanje cementa, '
              'obdelava keramičnih ploščic, opeke, strešnikov, rušenje')
PLACEHOLDER = re.compile(r'<[A-Z_]+>')


def filtered_table(tsv, codes):
    """First 4 columns + columns whose row-2 code is in codes; row 2 dropped."""
    with open(tsv, encoding='utf-8-sig', newline='') as f:
        rows = [[c.strip() for c in r] for r in csv.reader(f, delimiter='\t')]
    rows = [r for r in rows if any(r)]
    wanted = [c.strip().upper() for c in codes if c.strip()]
    present = {c.upper() for c in rows[1]}
    missing = [c for c in wanted if c not in present]
    keep = [0, 1, 2, 3] + [i for i, c in enumerate(rows[1]) if c.upper() in wanted]
    return [[r[i] for i in keep] for k, r in enumerate(rows) if k != 1], missing


def fill_page1(page, data):
    spans = {}
    for b in page.get_text('dict')['blocks']:
        for line in b.get('lines', []):
            for s in line['spans']:
                t = s['text'].strip()
                if PLACEHOLDER.fullmatch(t) and t[1:-1] in data:
                    spans[t[1:-1]] = s
    for s in spans.values():
        page.add_redact_annot(pymupdf.Rect(s['bbox']) + (-1, -1, 40, 1), fill=(1, 1, 1))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    for k, s in spans.items():
        page.insert_text(s['origin'], data[k], fontname='R', fontfile=FONT_R, fontsize=s['size'])


def fill_table_page(page, table, grad1):
    trect = None
    for b in page.get_text('dict')['blocks']:
        for line in b.get('lines', []):
            for s in line['spans']:
                if s['text'].startswith('<TABLE>'):
                    trect = pymupdf.Rect(s['bbox'])
    if trect is None:
        return
    # disclaimer sits right under the placeholder; move it below the table
    below = pymupdf.Rect(60, trect.y1 + 8, page.rect.width - 40, trect.y1 + 70)
    disclaimer = page.get_text('text', clip=below).replace('\n', ' ').strip()
    page.add_redact_annot(trect + (-1, -1, 1, 1), fill=(1, 1, 1))
    page.add_redact_annot(below, fill=(1, 1, 1))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    if grad1:
        disclaimer += ' ' + GRAD1_NOTE

    fs, x0, y = 8, 72, trect.y0 - 4
    fr, fb = pymupdf.Font(fontfile=FONT_R), pymupdf.Font(fontfile=FONT_B)
    ncols = len(table[0])
    widths = [250, 60, 55, 75]
    widths += [(page.rect.width - 2 * x0 - sum(widths)) / (ncols - 4)] * (ncols - 4)

    def wrap(text, font, w):
        lines, cur = [], ''
        for word in text.split():
            t = (cur + ' ' + word).strip()
            if font.text_length(t, fs) <= w - 6:
                cur = t
            else:
                lines.append(cur)
                cur = word
        return lines + [cur]

    def row(cells, header=False):
        nonlocal y
        font = fb if header else fr
        wrapped = [wrap(c, font, widths[i]) for i, c in enumerate(cells)]
        h = max(len(w) for w in wrapped) * (fs + 2) + 6
        x = x0
        for i, lines in enumerate(wrapped):
            page.draw_rect(pymupdf.Rect(x, y, x + widths[i], y + h), color=(0.6, 0.6, 0.6),
                           fill=TEAL if header else None, width=0.5)
            ty = y + 3 + fs
            for ln in lines:
                tx = x + 3 if i == 0 else x + (widths[i] - font.text_length(ln, fs)) / 2
                page.insert_text((tx, ty), ln, fontname='B' if header else 'R',
                                 fontfile=FONT_B if header else FONT_R, fontsize=fs,
                                 color=(1, 1, 1) if header else (0, 0, 0))
                ty += fs + 2
            x += widths[i]
        y += h

    row(table[0], header=True)
    for r in table[1:]:
        row(r)
    page.insert_textbox(pymupdf.Rect(x0, y + 14, page.rect.width - x0, y + 70), disclaimer,
                        fontname='R', fontfile=FONT_R, fontsize=9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quote')
    ap.add_argument('--name')
    ap.add_argument('--address')
    ap.add_argument('--id')
    ap.add_argument('--vat')
    ap.add_argument('--jobs', default='', help='comma-separated job codes (ignored with --simple)')
    ap.add_argument('--simple', action='store_true')
    ap.add_argument('--check', action='store_true', help='only validate --jobs, write no PDF')
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument('--outdir', type=Path)
    a = ap.parse_args()

    if a.check:
        if a.simple:
            print('OK: simple quote, jobs not used')
            return
        _, missing = filtered_table(a.root / 'matrika.tsv', a.jobs.split(','))
        print('MISSING: ' + ', '.join(missing) if missing else 'OK: all job codes match')
        return
    for k in ('quote', 'name', 'address', 'id', 'vat'):
        if not getattr(a, k):
            ap.error(f'--{k} is required')

    today = datetime.date.today()
    data = {'QUOTE': a.quote, 'DATE': f'{today.day}.{today.month}.{today.year}',  # D.M.YYYY
            'C_NAME': a.name, 'C_ADDRESS': a.address, 'C_ID': a.id, 'C_VAT': a.vat}

    doc = pymupdf.open(a.root / ('quote_simple.pdf' if a.simple else 'quote.pdf'))
    fill_page1(doc[0], data)
    if not a.simple:
        codes = a.jobs.split(',')
        table, missing = filtered_table(a.root / 'matrika.tsv', codes)
        if missing:
            print('WARNING: no column for code(s): ' + ', '.join(missing), file=sys.stderr)
        fill_table_page(doc[1], table, 'GRAD1' in [c.strip().upper() for c in codes])

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
