from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_ground_truth_from_sec import _html_schedule_rows
from scripts.extract_vanguard_prices import _primary_document

path = PROJECT_ROOT / "data/raw/ground_truth/sec_filings/VG500_2006_N-CSR_0000932471-07-000538.txt"
text = _primary_document(path.read_text(encoding="utf-8", errors="replace"))
rows = _html_schedule_rows(text)

for i in range(130, 155):
    print(f"row {i}: {rows[i]}")
