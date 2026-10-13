---
name: ponudba
description: whenever a new quote is needed, this skill will generate a quote based on the provided job codes and customer information from the provided link.
argument-hint: <url> <jobs-csv> <quote> [issimple]
arguments: [url, jobs, quote, issimple]
allowed-tools: Read Write WebFetch Bash(curl:*) Bash(python3:*) Bash(pip:*) Bash(pip3:*)
---

# ponudba

## Arguments

| Name        | Type      | Required | Description                                              |
| ----------- | --------- | -------- | -------------------------------------------------------- |
| `$url`      | link      | yes      | bizi.si link from which to fetch customer information    |
| `$jobs`     | CSV array | yes      | list of job codes to fetch from matrika.tsv              |
| `$quote`    | string    | yes      | quote number used for file naming and value substitution |
| `$issimple` | boolean   | no       | use simplified quote template (default: false)           |

Example: `/ponudba https://www.bizi.si/... GRAD,KUH 2026-001 false`

## Instructions

### 1. Customer data

Fetch the page at `$url` and read the company details. bizi.si layout and labels vary between companies and over time, so on every visit look at what the page actually shows and identify each value by its meaning, not by an exact label. Typical places on bizi.si:

| Variable    | Where on bizi.si                                                   | Notes                                                           |
| ----------- | ------------------------------------------------------------------ | --------------------------------------------------------------- |
| `C_NAME`    | page heading / company name (e.g. "PANARCH d.o.o.")                | if several comma-separated names are shown, keep only the first |
| `C_ADDRESS` | address in the contact line (a "Naslov" / "Poslovni naslov" label) | use as shown, e.g. "Šuceva ulica 25, Kranj, 4000 Kranj"         |
| `C_ID`      | "Matična" / "Matična številka"                                     | digits only                                                     |
| `C_VAT`     | "Davčna številka SI" / "ID za DDV"                                 | write with the `SI` prefix, e.g. `SI43524788`                   |

WebFetch summarises the page with a small model, so ask for the values verbatim and, if a value looks wrong, inconsistent or missing, fetch again with `curl` or ask the user. Do not guess. Show the four values to the user in the final report so they can be checked.

### 2. Generate the PDF

Run the bundled script (needs PyMuPDF; if `import pymupdf` fails, create a virtual environment, e.g. in the scratchpad directory, and `pip install pymupdf` there):

```
python3 .claude/skills/ponudba/make_quote.py --quote "$quote" --name "<C_NAME>" \
  --address "<C_ADDRESS>" --id "<C_ID>" --vat "<C_VAT>" --jobs "$jobs" [--simple]
```

Pass `--simple` when `$issimple` is true. Then `quote_simple.pdf` is used, only the placeholders are substituted and `matrika.tsv` / `$jobs` are not used (`--jobs` may be omitted). Otherwise `quote.pdf` is used.

What the script does:

- Placeholders `<QUOTE>`, `<DATE>`, `<C_NAME>`, `<C_ADDRESS>`, `<C_ID>`, `<C_VAT>` are replaced on page 1. `<DATE>` is today's date written as `D.M.YYYY` (no leading zeros, e.g. `13.10.2026`).
- `matrika.tsv` is tab separated; row 1 is the header, row 2 holds job codes (the first 4 columns, `Postavka`, `Cena`, `Popust`, `Cena s popustom`, have no code). It keeps the first 4 columns plus every column whose row-2 code matches one of `$jobs` (case-insensitive, trimmed), drops row 2 and copies cell values (`x`, `i`, ...) as they are. There is no row filtering. Also copy the bottom 2 rows (the "Cena Predhodni" and "Cena Obdobni" rows). The script does not check for missing or extra columns, it just copies what is there.
- The table replaces `<TABLE>` on the landscape page 2, with the disclaimer moved underneath on the same page. Column widths are set so nothing overflows; logo and styling are kept.
- If the `GRAD1` code is used, the script appends this to the disclaimer: "(1) rezanje, brušenje betona, kamnoseštvo, peskanje, vrtanje, mešanje cementa, obdelava keramičnih ploščic, opeke, strešnikov, rušenje"

The script prints warnings (stderr) for job codes that match no column and for placeholders left unfilled. If a code matches no column, tell the user and ask how to proceed (skip it, or a likely typo such as `PROIZ0` -> `PROIZN`) before generating the final file.

### 3. Output

The script saves `<YYYY-MM-DD>_<C_NAME>_<QUOTE>.pdf` (today's date, ISO) in the `ponudbe/` folder of the project root (created by the script if it does not exist) and prints the path. Render the pages to images and look at them to check for overflow and left-over `<...>` placeholders, then report the path and the four customer values used.
