from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

DEFAULT_CHAT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_EMBED_MODEL = "gemini-embedding-001"

FREE_SHIPPING_THRESHOLD_EUR = 500.0
SHIPPING_COST_EUR = 25.0
MIN_ORDER_VALUE_EUR = 150.0
MIN_ORDER_SURCHARGE_EUR = 20.0
CUTTING_COST_EUR = 20.0
SAFETY_BUFFER_BUSINESS_DAYS = 1

LOW_CONFIDENCE_R2 = 0.7
HIGH_CONFIDENCE_R2 = 0.9
DEFAULT_RISK_HORIZON_DAYS = 7
DEFAULT_BUNDLE_HORIZON_DAYS = 14
DEFAULT_BUNDLE_WINDOW_DAYS = 5


@dataclass(frozen=True)
class FileHints:
    rack_main: tuple[str, ...] = ("rack", "regal", "csv")
    pricing: tuple[str, ...] = ("pricing", "leadtimes", "csv")
    single_drums_dir_name: str = "einzeltrommeln"


FILE_HINTS = FileHints()