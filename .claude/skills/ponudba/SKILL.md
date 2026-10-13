---
name: ponudba
description: whenever a new quote is needed, this skill will generate a quote based on the provided job codes and customer information from the provided link.
argument-hint: <url> <jobs-csv> <quote> [issimple]
arguments: [url, jobs, quote, issimple]
disable-model-invocation: true
allowed-tools: Read Write WebFetch Bash(curl:*) Bash(.venv/bin/python:*) Bash(python3:*)
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

Parsed from the bizi.si page by `fetch_customer.py` before this prompt reached you:

!`.venv/bin/python ${CLAUDE_SKILL_DIR}/fetch_customer.py "$url"`

If the output is four `KEY=value` lines (`C_NAME`, `C_ADDRESS`, `C_ID`, `C_VAT`), use them as they are. If it says `FAILED: ...`, or a value looks wrong (e.g. odd name, `C_ID` not digits, `C_VAT` not `SI` + 8 digits), fall back to reading the page yourself: fetch `$url` with WebFetch (it summarises with a small model, so ask for values verbatim) or `curl`, and identify each value by its meaning, since bizi.si labels vary. If still unsure, ask the user. Do not guess.

| Variable    | Where on bizi.si                                  | Notes                                                           |
| ----------- | ------------------------------------------------- | --------------------------------------------------------------- |
| `C_NAME`    | page heading / company name (e.g. "PANARCH d.o.o.") | as shown                                                         |
| `C_ADDRESS` | address in the contact line                       | as shown, e.g. "Šuceva ulica 25, Kranj, 4000 Kranj"             |
| `C_ID`      | "Matična" / "Matična številka"                    | digits only                                                     |
| `C_VAT`     | "Davčna številka SI" / "ID za DDV"                | with the `SI` prefix, e.g. `SI43524788`                         |

Show the four values to the user in the final report so they can be checked.

### 2. Generate the PDF

Job code check, run before this prompt reached you (`--check` only validates, it writes nothing):

!`.venv/bin/python ${CLAUDE_SKILL_DIR}/make_quote.py --check --jobs "$jobs" $([ "$issimple" = true ] && echo --simple)`

If it says `MISSING: ...`, tell the user and ask how to proceed (skip the code, or a likely typo such as `PROIZ0` -> `PROIZN`) before generating. If the command above failed because `.venv` is missing, recreate it with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

Run the script with the project virtual environment (always call `.venv/bin/python` directly):

```
.venv/bin/python ${CLAUDE_SKILL_DIR}/make_quote.py --quote "$quote" --name "<C_NAME>" \
  --address "<C_ADDRESS>" --id "<C_ID>" --vat "<C_VAT>" --jobs "$jobs" [--simple]
```

Pass `--simple` when `$issimple` is true (it uses `quote_simple.pdf`; `--jobs` may be omitted). The script's docstring (`--help`) describes what it does; only read it if something goes wrong. It prints warnings (stderr) for job codes that match no column and for placeholders left unfilled.

### 3. Output

The script saves `<YYYY-MM-DD>_<C_NAME>_<QUOTE>.pdf` (today's date, ISO) in the `ponudbe/` folder of the project root (created by the script if it does not exist) and prints the path. Render the pages to images and look at them to check for overflow and left-over `<...>` placeholders, then report the path and the four customer values used.
