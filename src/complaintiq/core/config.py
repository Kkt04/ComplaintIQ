import os
from pathlib import Path
from typing import Any, Dict, List
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CONFIGS_DIR = BASE_DIR / "configs"


def load_yaml(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "ComplaintIQ"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    PORT: int = 8000

    # MongoDB Configuration
    MONGODB_URL: str = Field(default="mongodb://localhost:27017")
    DATABASE_NAME: str = "complaintiq"
    USE_MOCK_DB_IF_UNAVAILABLE: bool = True  # Ensures zero crashes if MongoDB daemon is not running locally

    # YAML Loaded Configurations
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    routing: Dict[str, Any] = Field(default_factory=dict)
    model_config_data: Dict[str, Any] = Field(default_factory=dict)
    data_config: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **values: Any):
        super().__init__(**values)
        self.thresholds = load_yaml(CONFIGS_DIR / "thresholds.yaml")
        self.routing = load_yaml(CONFIGS_DIR / "routing.yaml")
        self.model_config_data = load_yaml(CONFIGS_DIR / "model.yaml")
        self.data_config = load_yaml(CONFIGS_DIR / "data.yaml")

    @property
    def product_confidence_threshold(self) -> float:
        return float(self.thresholds.get("product_confidence_threshold", 0.85))

    @property
    def issue_confidence_threshold(self) -> float:
        return float(self.thresholds.get("issue_confidence_threshold", 0.70))

    @property
    def min_char_length(self) -> int:
        return int(self.data_config.get("validation", {}).get("min_char_length", 20))

    @property
    def max_char_length(self) -> int:
        return int(self.data_config.get("validation", {}).get("max_char_length", 10000))


settings = Settings()
