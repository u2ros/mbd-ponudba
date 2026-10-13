#!/usr/bin/env python3
"""Extract customer data from a bizi.si company page (stdlib only).

Usage: fetch_customer.py <url>
Prints C_NAME / C_ADDRESS / C_ID / C_VAT as KEY=value lines. Exits 1 and prints
"FAILED: ..." for anything it cannot find, so the caller can fall back to reading the page.
"""
import html, re, sys, urllib.request


def text(fragment):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', fragment))).strip().replace('\xa0', ' ')


def parse(page):
    out = {}
    m = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.S)
    if m:
        out['C_NAME'] = text(m.group(1))
    m = (re.search(r'<a[^>]*(?:_aAddress|i-ostalo-lokacija)[^>]*>(.*?)</a>', page, re.S)
         or re.search(r'name="Description" content="[^"]*?,\s*([^"]*?)\.\s*Davčna', page))
    if m:
        out['C_ADDRESS'] = text(m.group(1))
    body = text(re.sub(r'<script.*?</script>|<style.*?</style>', ' ', page, flags=re.S))
    m = re.search(r'Matična(?: številka)?\s*:\s*(\d+)', body)
    if m:
        out['C_ID'] = m.group(1)
    m = re.search(r'\b(SI\d{8})\b', body) or re.search(r'Davčna številka\s*SI\s*:\s*(\d{8})', body)
    if m:
        out['C_VAT'] = 'SI' + m.group(1).removeprefix('SI')
    return out


def main():
    req = urllib.request.Request(sys.argv[1], headers={'User-Agent': 'Mozilla/5.0'})
    try:
        page = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'replace')
    except Exception as e:
        print(f'FAILED: could not fetch page ({e})')
        sys.exit(1)
    data = parse(page)
    missing = [k for k in ('C_NAME', 'C_ADDRESS', 'C_ID', 'C_VAT') if k not in data]
    if missing:
        print('FAILED: not found: ' + ', '.join(missing))
        sys.exit(1)
    for k in ('C_NAME', 'C_ADDRESS', 'C_ID', 'C_VAT'):
        print(f'{k}={data[k]}')


if __name__ == '__main__':
    main()
