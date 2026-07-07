"""Paths to source data (xlsx files on Google Drive)."""
from pathlib import Path

GRADES_DIR = Path(r"G:\Meu Drive\random\grades")
EMENTAS_PATH = Path(r"G:\Meu Drive\random\Ementas_v2.xlsx")
ADS2000_PATH = GRADES_DIR / "Grade ADS 2000.xlsx"

APP_ROOT = Path(__file__).parent
STATIC_DIR = APP_ROOT / "static"
STATE_PATH = APP_ROOT / "state.json"
DB_PATH = APP_ROOT / "grade_lab.db"

AGENDA_PATH = APP_ROOT / "data_analysis" / "agenda_2026.xlsx"
