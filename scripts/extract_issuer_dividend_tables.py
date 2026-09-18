#!/usr/bin/env python3
"""Extract per-quarter dividends declared and quarter-end stock prices from SEC EDGAR filings.

Python 3 standard library only.
Strictly implements the project's 'reconcile-or-withhold' rule:
- A year's quarterly dividends are published only when they reconcile with the filing's annual figure.
- If they do not, or if the annual figure is missing, the year is withheld into the 'withheld' list.
- Structural failures (high < low, close outside high/low, dividend > 25% of price, or dividend and close both null)
  are rejected into 'structural_rejects'.
- Documents within the same EDGAR submission (including EX-13) are scanned before refusing a filing.
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PINNED_FILINGS_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "issuer_filing_manifest.json"
SPLITS_PATH = PROJECT_ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "ground_truth" / "issuer_dividend_tables.json"

DEFAULT_CACHE_DIR = Path("/tmp/sec_edgar_filings_cache")
HEADERS = {"User-Agent": "AcademicResearch sp500strategy@example.com"}

SPLIT_PATTERN = re.compile(
    r"\b(?:\d+-for-\d+|(?:two|three|four|five|six|seven|eight|nine|ten)-for-(?:one|two|three|four|five)|reverse\s+stock\s+split|stock\s+split(?:\s+effective)?)\b",
    re.IGNORECASE,
)

# A detector, not an extractor. The published quotation is the whole sentence the
# detector fired on: anchoring the quotation on the pattern itself is what produced the
# truncated statements this dataset first carried, because a 1990s filing wraps a
# sentence across lines and abbreviates its own registrant's name mid-subject.
NEVER_PAID_PATTERN = re.compile(
    r"(?:never\s+(?:declared|paid)|not\s+(?:declared|paid)\s+(?:any\s+)?cash\s+dividends"
    r"|no\s+cash\s+dividends\s+have\s+been\s+paid)",
    re.IGNORECASE,
)

MONTH_TO_Q = {
    "january": 1, "jan": 1,
    "february": 1, "feb": 1,
    "march": 1, "mar": 1,
    "april": 2, "apr": 2,
    "may": 2, "june": 2, "jun": 2,
    "july": 3, "jul": 3,
    "august": 3, "aug": 3,
    "september": 3, "sep": 3, "sept": 3,
    "october": 4, "oct": 4,
    "november": 4, "nov": 4,
    "december": 4, "dec": 4,
}


def clean_num(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s.endswith("."):
        s = s[:-1]
    if s in ["-", "--", "$ -", "$-", "None", ""]:
        return None
    parts = s.split()
    try:
        if len(parts) == 2 and "/" in parts[1]:
            w = float(parts[0])
            n, d = parts[1].split("/")
            return round(w + float(n) / float(d), 4)
        elif len(parts) == 1 and "/" in parts[0]:
            n, d = parts[0].split("/")
            return round(float(n) / float(d), 4)
        else:
            return round(float(s), 4)
    except Exception:
        return None


def extract_numbers_from_line(line: str) -> List[float]:
    pattern = r"\$?\s*(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+)"
    raw_tokens = re.findall(pattern, line)
    return [clean_num(t) for t in raw_tokens if clean_num(t) is not None]


def fetch_filing(cik: str, accession: str, cache_dir: Path) -> str:
    cache_path = cache_dir / f"{accession}.txt"
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    cik_clean = str(cik).lstrip("0")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession}.txt"
    time.sleep(0.12)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=90) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def extract_split_sentences(text: str, accession: str) -> List[Dict[str, str]]:
    t_clean = re.sub(r"<[^>]+>", " ", text)
    t_clean = html.unescape(t_clean)
    sentences = re.split(r"(?<=[.!?])\s+", t_clean)
    collected = []
    seen = set()
    for s in sentences:
        s_norm = " ".join(s.split()).strip()
        if SPLIT_PATTERN.search(s_norm) and 15 < len(s_norm) < 1200:
            if s_norm not in seen:
                seen.add(s_norm)
                collected.append({
                    "accession_number": accession,
                    "sentence": s_norm,
                })
    return collected


# A sentence that begins mid-page carries whatever the page put in front of it: the tail
# of a price table, a phone number, a dotted leader, a footnote marker. Each of those is a
# token no English sentence opens with, so the strip is token-based rather than a set of
# ad-hoc prefixes. This is the same correction docs/DATA_PROVENANCE.md 4.3.13 applied to
# Nortel's split quotation, where a page number was captured inside the quotation.
SYMBOLIC_TOKEN = re.compile(r"^[\$\d/.,()\-\u2013\u2014%*:;|_=+\[\]]+$")
LIST_MARKER = re.compile(r"^\(?[a-z0-9]{1,3}[).]$")
LABEL_TOKEN = re.compile(r"^[A-Za-z][A-Za-z\-]*:$")
# All-caps section headings that sit immediately above the statement. Kept as an explicit
# vocabulary rather than a rule about capitalisation, so that a registrant whose own name
# is capitalised -- EMC, GTE -- is never mistaken for a heading and stripped.
HEADING_TOKENS = {"DIVIDEND", "DIVIDENDS", "MARKET", "ITEM", "NOTE", "GENERAL", "COMMON", "STOCK"}
# Above this, a "sentence" is an artefact of protected abbreviations swallowing an address
# or a table, not a sentence. Re-split it unprotected and keep the fragment that matched.
SENTENCE_BUDGET = 400


# A token that cannot appear inside one of these statements: a transfer agent's address,
# a URL, a page number. Its presence marks where the surrounding page ends and the
# sentence begins. Abbreviations are exempt -- "Viacom Inc." is the subject, not furniture.
ABBREVIATION_TOKEN = re.compile(
    r"^(?:Inc|Corp|Co|Ltd|Cos|plc|PLC|Jr|Sr|St|No|Nos|Mr|Mrs|Ms|Dr|[A-Z])\.$"
)


def _is_furniture(token: str) -> bool:
    # Abbreviations are checked first and always kept: "Inc." is a subject, and a list
    # marker pattern will happily match it otherwise.
    if ABBREVIATION_TOKEN.match(token):
        return False
    # A trailing comma is prose punctuation, never a table cell. Without this, the date
    # qualifier in "During 1996 and 1995, the Company has not declared..." reads as
    # furniture and the statement loses the years it is about.
    if token.endswith(","):
        return False
    if SYMBOLIC_TOKEN.match(token) or LIST_MARKER.match(token) or LABEL_TOKEN.match(token):
        return True
    if token.isupper() and token.upper() in HEADING_TOKENS:
        return True
    return bool(re.search(r"\d", token)) or "." in token[:-1] or "@" in token


def strip_furniture(sentence: str, match_start: int = 0) -> str:
    """Trim the page furniture a mid-page sentence carries, keeping the subject intact.

    Leading furniture is dropped first. Then, because an address block can sit between the
    sentence start and the statement itself, the quotation is trimmed forward to the last
    run of prose that reaches the matched phrase -- never past it, so the subject survives.
    """
    tokens = sentence.split()
    index = 0
    while index < len(tokens) - 1 and _is_furniture(tokens[index]):
        index += 1
    # Index of the first token at or after the matched phrase, in the trimmed list.
    consumed = 0
    match_token = 0
    for position, token in enumerate(tokens):
        if consumed >= match_start:
            match_token = position
            break
        consumed += len(token) + 1
        match_token = position
    start = index
    for position in range(match_token, index - 1, -1):
        if _is_furniture(tokens[position]):
            start = position + 1
            break
    trimmed = " ".join(tokens[max(start, index):])
    # A trim that lands mid-clause ("and 1995, the Company has not declared...") has cut
    # into the sentence rather than the page around it. Keep the wider text instead: an
    # extra clause of context is a smaller defect than a quotation that starts nowhere.
    if trimmed and trimmed[0].islower():
        return " ".join(tokens[index:])
    return trimmed


# A period after an abbreviation is not a sentence boundary. Splitting on it is what cut
# "Viacom Inc. has not declared cash dividends..." down to its predicate.
ABBREVIATION = re.compile(
    r"\b(Inc|Corp|Co|Ltd|Cos|plc|PLC|Jr|Sr|St|No|Nos|Mr|Mrs|Ms|Dr|vs|etc|Div)\.",
)
INITIAL = re.compile(r"\b([A-Z])\.")
_GUARD = "\x00"


def clean_document_text(text: str) -> str:
    """Markup-stripped, entity-decoded, whitespace-collapsed document text.

    A 1990s fixed-width filing wraps a sentence across lines, so any pattern anchored on
    a newline truncates it. Collapsing first is what lets a sentence be matched whole.
    """
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def split_sentences(text: str, protect_initials: bool = True) -> List[str]:
    """Sentences, with abbreviation periods protected from the boundary split.

    `protect_initials` also guards single capitals, which keeps "U.S.A." intact. That is
    right for a first pass and wrong for a second: an address block ending in "U.S.A."
    then swallows the sentence after it, so the over-budget re-split leaves it off and
    protects only the company suffixes that carry a subject.
    """
    guarded = ABBREVIATION.sub(lambda m: m.group(1) + _GUARD, text)
    if protect_initials:
        guarded = INITIAL.sub(lambda m: m.group(1) + _GUARD, guarded)
    return [s.replace(_GUARD, ".") for s in re.split(r"(?<=[.!?])\s+", guarded)]


def extract_never_paid(text: str, accession: str = "", form: str = "", filing_date: str = "") -> List[Dict[str, str]]:
    """Whole never-paid sentences, each carrying the filing it was read in.

    Returns every distinct statement rather than the first: a registrant's wording changes
    across years, and the filing date is what bounds the claim. A statement filed in 2000
    says nothing about 2003, so the consumer needs the date, not just the sentence. Viacom
    is why that matters -- it filed these statements for eight years and then began paying
    a dividend in 2003 (4.3.15).
    """
    collected: List[Dict[str, str]] = []
    seen = set()
    for sentence in split_sentences(clean_document_text(text)):
        if not NEVER_PAID_PATTERN.search(sentence):
            continue
        if len(sentence) > SENTENCE_BUDGET:
            # An address or a table has been swallowed by a protected abbreviation.
            # Re-split without the protection and keep only the fragment that matched.
            fragments = [f for f in split_sentences(sentence, protect_initials=False) if NEVER_PAID_PATTERN.search(f)]
            sentence = fragments[-1] if fragments else sentence
        normalised = " ".join(sentence.split()).strip()
        found = NEVER_PAID_PATTERN.search(normalised)
        sentence = strip_furniture(normalised, found.start() if found else 0)
        if not (20 < len(sentence) < 400) or sentence in seen:
            continue
        seen.add(sentence)
        collected.append({
            "accession_number": accession,
            "form": form,
            "filing_date": filing_date,
            "sentence": sentence,
        })
    return collected


def find_annual_dividends(text: str) -> Dict[int, float]:
    annuals = {}
    m_sel = list(re.finditer(r"(?:Item\s+6[\.\:\s\-]|Selected\s+Financial\s+Data|Selected\s+Financial\s+and\s+Operating\s+Data|Five-Year\s+Financial\s+Summary)", text, re.I))
    for m in m_sel:
        chunk = text[m.start():m.start() + 18000]
        m_cut = re.search(r"\bItem\s+7\b", chunk[50:], re.I)
        if m_cut:
            chunk = chunk[:50 + m_cut.start()]

        years = []
        lines = chunk.splitlines()
        for idx, l in enumerate(lines):
            yrs = re.findall(r"\b(19[789]\d|20[012]\d)\b", l)
            if len(yrs) >= 2 and len(yrs) > len(years):
                years = [int(y) for y in yrs]
            
            cand_lines = [l]
            if idx + 1 < len(lines):
                cand_lines.append(l.strip() + " " + lines[idx + 1].strip())

            for line_to_check in cand_lines:
                if years and re.search(r"dividends?\s+(?:declared\s+)?(?:per\s+)?(?:common\s+)?share", line_to_check, re.I):
                    m_lbl = re.search(r"(?:per\s+)?(?:common\s+)?share", line_to_check, re.I)
                    rem = line_to_check[m_lbl.end():] if m_lbl else line_to_check
                    nums = extract_numbers_from_line(rem)
                    if len(nums) == len(years):
                        for y, val in zip(years, nums):
                            if y not in annuals:
                                annuals[y] = val
                    elif len(nums) > len(years) and len(years) >= 2:
                        if years[0] > years[-1]:
                            for y, val in zip(years, nums[:len(years)]):
                                if y not in annuals:
                                    annuals[y] = val
                        else:
                            for y, val in zip(years, nums[-len(years):]):
                                if y not in annuals:
                                    annuals[y] = val
    return annuals



def extract_raw_quarters_from_text(text: str, acc: str, f_date: str, form: str) -> Dict[str, Dict[str, Any]]:
    quarters: Dict[str, Dict[str, Any]] = {}

    chunks = []
    for m in re.finditer(r"(?:Item\s+5[\.\:\s\-]|Item\s+5\b)", text, re.I):
        start = m.start()
        end = min(len(text), start + 12000)
        m_cut = re.search(r"\b(?:Item\s+[6789]|Signatures|Item\s+14)\b", text[start + 100:end], re.I)
        if m_cut:
            end = start + 100 + m_cut.start()
        chunk = text[start:end]
        if "quarter" in chunk.lower() or "high" in chunk.lower() or "first" in chunk.lower():
            chunks.append((chunk, "Item 5", False))

    for m in re.finditer(r"(?:Quarterly\s+Financial\s+Information|Quarterly\s+Financial\s+Data|Quarterly\s+Information|Quarterly\s+Results|Quarterly\s+Data|Selected\s+Quarterly\s+Data|Supplemental\s+Information)", text, re.I):
        start = m.start()
        end = min(len(text), start + 15000)
        m_cut = re.search(r"\b(?:Note\s+\d+|Item\s+\d+|Report\s+of\s+Independent|Stock\s+Data)\b", text[start + 100:end], re.I)
        if m_cut:
            end = start + 100 + m_cut.start()
        chunk = text[start:end]
        if "quarter" in chunk.lower() or "high" in chunk.lower() or "dividend" in chunk.lower() or "first" in chunk.lower():
            is_unaudited = "unaudited" in chunk[:300].lower() or "(unaudited)" in text[max(0, start - 100):start + 200].lower()
            chunks.append((chunk, "Note", not is_unaudited))

    for chunk, sec_type, audited in chunks:
        basis_note = ""
        m_bn = re.search(r"([^.\n;]*(?:reflects|adjusted\s+for|restated\s+for|giving\s+effect\s+to)[^.\n;]*(?:stock\s+split|split)[^.\n;]*)", chunk, re.I)
        if m_bn:
            basis_note = " ".join(m_bn.group(0).split()).strip()

        lines = [l.strip() for l in chunk[:500].splitlines() if l.strip()]
        caption = "Quarterly Information"
        for l in lines[:5]:
            if any(w in l.lower() for w in ["market price", "common stock", "quarterly", "dividends", "sales price"]):
                caption = l
                break
        basis_evidence = lines[0] if lines else sec_type

        # Pattern A: Row-based quarters (First Quarter...)
        curr_year = None
        for l in chunk.splitlines():
            m_yr = re.match(r"^\s*(?:Fiscal\s+year\s+)?(199\d|200\d)\s*[:\-\.]?\s*$", l, re.I)
            if m_yr:
                curr_year = int(m_yr.group(1))

            m_q = re.match(r"^\s*(?:(?:199\d|200\d)\s+)?(First|Second|Third|Fourth|1st|2nd|3rd|4th)\s+(?:Quarter|quarter)(?:\s*\([^\)]*\))?\s*(?:\.{2,}|\-{2,}|\:|\s{2,}|\t)", l, re.I)
            if m_q and curr_year:
                lower = l.lower()
                if any(w in lower for w in ["included", "resulted", "restatement", "operating expense", "million", "billion"]):
                    continue
                q_name = m_q.group(1).lower()
                q_num = 1 if ("1" in q_name or "first" in q_name) else (2 if ("2" in q_name or "second" in q_name) else (3 if ("3" in q_name or "third" in q_name) else 4))
                key = f"{curr_year}-Q{q_num}"

                after_q = l[m_q.end():]
                nums = extract_numbers_from_line(after_q)
                # Check for High Low Close pattern (e.g. SBC in EX-13)
                if len(nums) >= 7 and "close" in chunk[:1500].lower():
                    # operating data preceding prices, last 3 numbers are High, Low, Close
                    h, low, close = nums[-3], nums[-2], nums[-1]
                    if key not in quarters:
                        quarters[key] = {
                            "dividend_declared_per_share": None,
                            "high": h,
                            "low": low,
                            "quarter_end_close": close,
                            "accession_number": acc,
                            "form": form,
                            "filing_date": f_date,
                            "table_caption": caption,
                            "as_filed_basis_note": basis_note,
                            "audited": audited,
                            "basis_evidence": basis_evidence,
                        }
                elif len(nums) >= 3:
                    h, low, div = nums[0], nums[1], nums[2]
                    if key not in quarters:
                        quarters[key] = {
                            "dividend_declared_per_share": div,
                            "high": h,
                            "low": low,
                            "quarter_end_close": None,
                            "accession_number": acc,
                            "form": form,
                            "filing_date": f_date,
                            "table_caption": caption,
                            "as_filed_basis_note": basis_note,
                            "audited": audited,
                            "basis_evidence": basis_evidence,
                        }
                elif len(nums) == 2:
                    h, low = nums[0], nums[1]
                    if key not in quarters:
                        quarters[key] = {
                            "dividend_declared_per_share": None,
                            "high": h,
                            "low": low,
                            "quarter_end_close": None,
                            "accession_number": acc,
                            "form": form,
                            "filing_date": f_date,
                            "table_caption": caption,
                            "as_filed_basis_note": basis_note,
                            "audited": audited,
                            "basis_evidence": basis_evidence,
                        }

        # Pattern B: Date-based rows (September 30, 1997 .... High Low)
        for l in chunk.splitlines():
            m_dt = re.match(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*(199\d|200\d)\b(?:\.{2,}|\s{2,}|\t)", l, re.I)
            if m_dt:
                mon = m_dt.group(1).lower()
                yr = int(m_dt.group(2))
                q_num = MONTH_TO_Q.get(mon)
                if q_num:
                    key = f"{yr}-Q{q_num}"
                    after_dt = l[m_dt.end():]
                    nums = extract_numbers_from_line(after_dt)
                    if len(nums) >= 3:
                        h, low, div = nums[0], nums[1], nums[2]
                        if key not in quarters:
                            quarters[key] = {
                                "dividend_declared_per_share": div,
                                "high": h,
                                "low": low,
                                "quarter_end_close": None,
                                "accession_number": acc,
                                "form": form,
                                "filing_date": f_date,
                                "table_caption": caption,
                                "as_filed_basis_note": basis_note,
                                "audited": audited,
                                "basis_evidence": basis_evidence,
                            }
                    elif len(nums) == 2:
                        h, low = nums[0], nums[1]
                        if key not in quarters:
                            quarters[key] = {
                                "dividend_declared_per_share": None,
                                "high": h,
                                "low": low,
                                "quarter_end_close": None,
                                "accession_number": acc,
                                "form": form,
                                "filing_date": f_date,
                                "table_caption": caption,
                                "as_filed_basis_note": basis_note,
                                "audited": audited,
                                "basis_evidence": basis_evidence,
                            }

        # Pattern C: Column-based quarters
        chunk_lines = chunk.splitlines()
        i = 0
        while i < len(chunk_lines):
            l = chunk_lines[i]
            m_yr = re.match(r"^\s*(?:Fiscal\s+year\s+)?(199\d|200\d)(?:\s+Quarters)?\s*$", l, re.I)
            if m_yr:
                col_yr = int(m_yr.group(1))
                divs, highs, lows, closes = None, None, None, None
                j = i + 1
                while j < min(len(chunk_lines), i + 35):
                    sub_l = chunk_lines[j]
                    if re.match(r"^\s*(?:Fiscal\s+year\s+)?(199\d|200\d)(?:\s+Quarters)?\s*$", sub_l, re.I):
                        break
                    # Dividends row
                    if re.search(r"(?:Dividends\s+declared|Cash\s+dividends|\bDividends\b)", sub_l, re.I) and not divs:
                        lbl_end = re.search(r"(?:declared|dividends|common\s+stocks|par\s+value)", sub_l, re.I)
                        after = sub_l[lbl_end.end():] if lbl_end else sub_l
                        toks = extract_numbers_from_line(after)
                        if len(toks) < 4 and j + 1 < len(chunk_lines):
                            toks += extract_numbers_from_line(chunk_lines[j + 1])
                        if len(toks) >= 4:
                            divs = toks[:4]
                    # High row
                    if re.search(r"\bHigh\b", sub_l, re.I) and not highs:
                        m_h = re.search(r"\bHigh\b", sub_l, re.I)
                        after = sub_l[m_h.end():]
                        toks = extract_numbers_from_line(after)
                        if len(toks) >= 4:
                            highs = toks[:4]
                    # Low row
                    if re.search(r"\bLow\b", sub_l, re.I) and not lows:
                        m_low = re.search(r"\bLow\b", sub_l, re.I)
                        after = sub_l[m_low.end():]
                        toks = extract_numbers_from_line(after)
                        if len(toks) >= 4:
                            lows = toks[:4]
                    # Quarter-end close row
                    if re.search(r"\b(?:Quarter-end\s+close|Close)\b", sub_l, re.I) and not closes:
                        m_c = re.search(r"\b(?:Quarter-end\s+close|Close)\b", sub_l, re.I)
                        after = sub_l[m_c.end():]
                        toks = extract_numbers_from_line(after)
                        if len(toks) >= 4:
                            closes = toks[:4]
                    j += 1
                if col_yr and (divs or highs or lows or closes):
                    for q_num in range(1, 5):
                        k = f"{col_yr}-Q{q_num}"
                        if k not in quarters:
                            quarters[k] = {
                                "dividend_declared_per_share": divs[q_num - 1] if divs else None,
                                "high": highs[q_num - 1] if highs else None,
                                "low": lows[q_num - 1] if lows else None,
                                "quarter_end_close": closes[q_num - 1] if closes else None,
                                "accession_number": acc,
                                "form": form,
                                "filing_date": f_date,
                                "table_caption": caption,
                                "as_filed_basis_note": basis_note,
                                "audited": audited,
                                "basis_evidence": basis_evidence,
                            }
                i = j - 1
            i += 1

    return quarters


def validate_row(h: Optional[float], low: Optional[float], close: Optional[float], div: Optional[float]) -> Tuple[bool, str]:
    if h is not None and low is not None and h < low:
        return False, f"high {h} < low {low}"
    if close is not None:
        if h is not None and close > h * 1.05:
            return False, f"close {close} > high {h}"
        if low is not None and close < low * 0.95:
            return False, f"close {close} < low {low}"
    ref_price = close if close is not None else low
    if div is not None and ref_price is not None and ref_price > 0:
        if div > 0.25 * ref_price:
            return False, f"dividend {div} exceeds 25% of price {ref_price}"
    if div is None and close is None:
        return False, "both dividend and close are null"
    return True, "ok"


def main():
    parser = argparse.ArgumentParser(description="Extract issuer dividend tables and stock prices from SEC filings.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Directory to cache downloaded filings.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Path for output JSON file.")
    args = parser.parse_args()

    with open(PINNED_FILINGS_PATH, "r", encoding="utf-8") as f:
        pinned = json.load(f)["filings_by_ticker"]

    with open(SPLITS_PATH, "r", encoding="utf-8") as f:
        splits_doc = json.load(f)
    cik_map = {t: splits_doc.get("splits_by_ticker", {}).get(t, {}).get("cik") for t in pinned.keys()}

    output_data: Dict[str, Any] = {}
    total_fetched = 0
    total_refused = 0
    refusals_recovered_ex13 = 0
    structural_rejects_count = 0
    years_reconciled = 0
    years_withheld = 0

    all_structural_rejects = []
    all_withheld_list = []
    refusals_list = []

    for ticker in sorted(pinned.keys()):
        cik = cik_map.get(ticker)
        ticker_obj: Dict[str, Any] = {
            "quarters": {},
            "never_paid_statements": [],
            "split_language": [],
            "reconciliation": {},
            "withheld": [],
        }

        annual_divs_found: Dict[int, float] = {}
        annual_divs_by_acc: Dict[str, Dict[int, float]] = {}
        ticker_splits: List[Dict[str, str]] = []
        raw_quarters_by_year: Dict[int, Dict[str, Dict[str, Any]]] = {}

        for f_date, form, acc in pinned[ticker]:
            total_fetched += 1
            if acc not in annual_divs_by_acc:
                annual_divs_by_acc[acc] = {}
            try:
                full_submission = fetch_filing(str(cik), acc, args.cache_dir)
            except Exception as e:
                refusals_list.append({
                    "ticker": ticker,
                    "accession_number": acc,
                    "form": form,
                    "filing_date": f_date,
                    "reason": f"Fetch failure: {e}",
                })
                total_refused += 1
                continue

            # Split sentences across whole submission
            splits = extract_split_sentences(full_submission, acc)
            ticker_splits.extend(splits)

            np_statements = extract_never_paid(full_submission, acc, form, f_date)
            ticker_obj["never_paid_statements"].extend(np_statements)
            np_quote = np_statements[0]["sentence"] if np_statements else None

            # Scan all documents in submission (including EX-13)
            sub_docs = re.split(r"<DOCUMENT>", full_submission, flags=re.I)
            primary_text = sub_docs[0] if sub_docs else full_submission

            found_in_primary = False
            found_in_ex13 = False

            for doc_idx, doc_text in enumerate(sub_docs):
                is_ex13 = bool(re.search(r"<TYPE>(?:EX-13|13)\b", doc_text[:500], re.I))

                # Annual dividends
                doc_ann = find_annual_dividends(doc_text)
                for y, val in doc_ann.items():
                    if y not in annual_divs_by_acc[acc]:
                        annual_divs_by_acc[acc][y] = val
                    if y not in annual_divs_found:
                        annual_divs_found[y] = val

                # Raw quarters
                doc_q = extract_raw_quarters_from_text(doc_text, acc, f_date, form)
                if doc_q:
                    if is_ex13:
                        found_in_ex13 = True
                    else:
                        found_in_primary = True

                    for q_k, q_v in doc_q.items():
                        yr = int(q_k.split("-")[0])
                        if yr not in raw_quarters_by_year:
                            raw_quarters_by_year[yr] = {}
                        if q_k not in raw_quarters_by_year[yr]:
                            raw_quarters_by_year[yr][q_k] = q_v

            if not found_in_primary and found_in_ex13:
                refusals_recovered_ex13 += 1

            if not found_in_primary and not found_in_ex13:
                if np_quote:
                    reason = f"Issuer never declared or paid cash dividends ({np_quote[:80]})"
                elif "incorporated by reference" in primary_text.lower():
                    reason = "Item 5 / financial statements incorporated by reference to annual report to shareholders / proxy statement; table absent in filing"
                else:
                    reason = "No quarterly dividend or price table present in filing text"
                refusals_list.append({
                    "ticker": ticker,
                    "accession_number": acc,
                    "form": form,
                    "filing_date": f_date,
                    "reason": reason,
                })
                total_refused += 1

        ticker_obj["split_language"] = ticker_splits

        # Apply Rule 1 & Rule 3: Reconcile-or-withhold and structural rejection
        for yr, q_dict in sorted(raw_quarters_by_year.items()):
            q_keys = [f"{yr}-Q{i}" for i in range(1, 5)]
            has_all_4 = all(k in q_dict for k in q_keys)

            # Check structural validity of each candidate row
            valid_rows = True
            reject_reason = ""
            for k in list(q_dict.keys()):
                q_row = q_dict[k]
                h = q_row.get("high")
                low = q_row.get("low")
                close = q_row.get("quarter_end_close")
                div = q_row.get("dividend_declared_per_share")
                ok, reason = validate_row(h, low, close, div)
                if not ok:
                    valid_rows = False
                    reject_reason = reason
                    structural_rejects_count += 1
                    all_structural_rejects.append({
                        "ticker": ticker,
                        "quarter": k,
                        "accession_number": q_row.get("accession_number"),
                        "reason": reason,
                        "values": {"high": h, "low": low, "quarter_end_close": close, "dividend": div},
                    })
                    break

            if not valid_rows:
                # Withhold year on structural failure
                years_withheld += 1
                withheld_entry = {
                    "year": yr,
                    "reason": f"Structural validation failure: {reject_reason}",
                    "quarters": list(q_dict.keys()),
                }
                ticker_obj["withheld"].append(withheld_entry)
                all_withheld_list.append((ticker, withheld_entry))
                continue

            # If row has close but no dividend (non-dividend payers or close-only tables)
            div_counts = sum(1 for k in q_dict.values() if k.get("dividend_declared_per_share") is not None)
            if div_counts == 0:
                # Close-only series: valid if closes exist
                for k, q_val in q_dict.items():
                    if q_val.get("quarter_end_close") is not None:
                        ticker_obj["quarters"][k] = q_val
                continue

            # Dividend series must reconcile 4 quarters with annual figure
            if not has_all_4:
                years_withheld += 1
                withheld_entry = {
                    "year": yr,
                    "reason": f"Incomplete quarters (found {len(q_dict)} of 4)",
                    "quarters": list(q_dict.keys()),
                }
                ticker_obj["withheld"].append(withheld_entry)
                all_withheld_list.append((ticker, withheld_entry))
                continue

            # All 4 quarters present: compute sum
            div_sum = round(sum(q_dict[k]["dividend_declared_per_share"] for k in q_keys if q_dict[k].get("dividend_declared_per_share") is not None), 4)
            q_acc = q_dict[q_keys[0]]["accession_number"]
            ann_val = None
            if q_acc in annual_divs_by_acc and yr in annual_divs_by_acc[q_acc]:
                ann_val = annual_divs_by_acc[q_acc][yr]
            elif yr in annual_divs_found:
                ann_val = annual_divs_found[yr]

            if ann_val is None:
                years_withheld += 1
                withheld_entry = {
                    "year": yr,
                    "reason": "Annual dividend figure not found in filing",
                    "quarterly_sum": div_sum,
                    "accession_number": q_acc,
                }
                ticker_obj["withheld"].append(withheld_entry)
                all_withheld_list.append((ticker, withheld_entry))
                continue

            if abs(div_sum - ann_val) > 1e-4:
                years_withheld += 1
                withheld_entry = {
                    "year": yr,
                    "reason": f"Reconciliation mismatch: quarterly_sum {div_sum} != annual {ann_val}",
                    "annual_dividend_declared_per_share": ann_val,
                    "quarterly_sum": div_sum,
                    "accession_number": q_acc,
                }
                ticker_obj["withheld"].append(withheld_entry)
                all_withheld_list.append((ticker, withheld_entry))
            else:
                # Reconciled clean! Publish the 4 quarters
                years_reconciled += 1
                ticker_obj["reconciliation"][str(yr)] = {
                    "annual_dividend_declared_per_share": ann_val,
                    "quarterly_sum": div_sum,
                    "reconciled": True,
                }
                for k in q_keys:
                    ticker_obj["quarters"][k] = q_dict[k]

        output_data[ticker] = ticker_obj

    # Summary metrics
    total_quarters_published = sum(len(t["quarters"]) for t in output_data.values())
    total_closes_published = sum(
        sum(1 for q in t["quarters"].values() if q.get("quarter_end_close") is not None)
        for t in output_data.values()
    )

    final_payload = {
        "metadata": {
            "source": "SEC EDGAR Form 10-K / 20-F filings",
            "total_filings_fetched": total_fetched,
            "total_filings_refused": total_refused,
            "refusals_recovered_ex13": refusals_recovered_ex13,
            "quarters_published": total_quarters_published,
            "years_reconciled": years_reconciled,
            "years_withheld": years_withheld,
            "closes_published": total_closes_published,
            "structural_rejects": structural_rejects_count,
            "total_split_sentences": sum(len(t["split_language"]) for t in output_data.values()),
        },
        "tickers": output_data,
        "refusals": refusals_list,
        "structural_rejects": all_structural_rejects,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, sort_keys=True)

    print(f"STATUS: done")
    print(f"QUARTERS PUBLISHED: {total_quarters_published}")
    print(f"YEARS RECONCILED: {years_reconciled}     YEARS WITHHELD: {years_withheld}")
    print(f"CLOSES PUBLISHED: {total_closes_published}")
    print(f"FILINGS: {total_fetched} / {total_refused}   REFUSALS RECOVERED FROM EX-13: {refusals_recovered_ex13}")
    print(f"STRUCTURAL REJECTS: {structural_rejects_count}")


if __name__ == "__main__":
    main()
