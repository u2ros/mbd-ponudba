---
name: ponudba-ot
description: whenever a quote for an occupational health risk assessment (zdravstvena ocena tveganja, quote-ot.pdf) is needed, this skill generates it from the number of job types, doctor on-site hours, a discount and the customer information from the provided link.
argument-hint: <url> <jobs> <hours> <discount> <quote>
arguments: [url, jobs, hours, discount, quote]
disable-model-invocation: true
allowed-tools: Read Write WebFetch Bash(curl:*) Bash(.venv/bin/python:*) Bash(python3:*)
---

# ponudba-ot

## Arguments

- `$url`: bizi.si company page for the customer data
- `$jobs`: number of job types (delovna mesta) to assess, e.g. `4`
- `$hours`: number of hours of on-site examination of the work process by a medical doctor, e.g. `2` (decimals allowed, `2.5`)
- `$discount`: discount in percent, e.g. `10` (use `0` for none)
- `$quote`: quote number, used in the file name and on the quote

Example: `/ponudba-ot https://www.bizi.si/... 4 2 10 2026-001`

## Instructions

### 1. Customer data

Parsed from the bizi.si page by `fetch_customer.py` before this prompt reached you:

!`.venv/bin/python ${CLAUDE_SKILL_DIR}/../ponudba/fetch_customer.py "$url"`

If the output is four `KEY=value` lines (`C_NAME`, `C_ADDRESS`, `C_ID`, `C_VAT`), use them as they are. If it says `FAILED: ...`, or a value looks wrong (e.g. odd name, `C_ID` not digits, `C_VAT` neither `SI` + 8 digits nor, for a company that is not a VAT payer, plain 8 digits), fall back to reading the page yourself: fetch `$url` with WebFetch (it summarises with a small model, so ask for values verbatim) or `curl`, and identify each value by its meaning, since bizi.si labels vary. If still unsure, ask the user. Do not guess.

| Variable    | Where on bizi.si                                  | Notes                                                           |
| ----------- | ------------------------------------------------- | --------------------------------------------------------------- |
| `C_NAME`    | page heading / company name (e.g. "PANARCH d.o.o.") | as shown                                                         |
| `C_ADDRESS` | address in the contact line                       | as shown, e.g. "Šuceva ulica 25, Kranj, 4000 Kranj"             |
| `C_ID`      | "Matična" / "Matična številka"                    | digits only                                                     |
| `C_VAT`     | "Davčna številka SI" / "ID za DDV"                | with the `SI` prefix, e.g. `SI43524788`; if "Zavezanec za DDV: Ne", plain "Davčna številka" (8 digits, no prefix) |

Show the four values to the user in the final report so they can be checked.

### 2. Generate the PDF

Run the script with the project virtual environment (always call `.venv/bin/python` directly; if `.venv` is missing, recreate it with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`):

```
.venv/bin/python ${CLAUDE_SKILL_DIR}/make_quote_ot.py --quote "$quote" --name "<C_NAME>" \
  --address "<C_ADDRESS>" --id "<C_ID>" --vat "<C_VAT>" --jobs "$jobs" --hours "$hours" --discount "$discount"
```

It fills `quote-ot.pdf`: page 1 customer placeholders as in `ponudba`; page 2 price table at 120 EUR per job and 100 EUR per doctor hour: line amounts = quantity x price, `Skupaj brez popusta` = their sum, discount = sum x `$discount`%, `Skupaj s popustom` = sum - discount (also repeated in the note under the table). Amounts are formatted Slovenian style (`1.234,50`). The script's docstring (`--help`) has the details; only read it if something goes wrong. It prints a warning (stderr) for placeholders left unfilled.

If `$jobs`, `$hours` or `$discount` is not a number (or discount is outside 0-100), ask the user instead of guessing.

### 3. Output

The script saves `<YYYY-MM-DD>_<C_NAME>_<QUOTE>.pdf` (today's date, ISO) in the `ponudbe/` folder of the project root (created by the script if it does not exist) and prints the path. Render the pages to images and look at them to check for overflow and left-over `<...>` placeholders, then report the path, the four customer values used and the computed amounts (total, discount, final).
