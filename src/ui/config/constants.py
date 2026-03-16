# """Глобальные константы и конфигурация приложения"""
from typing import Dict, Any

# Пути к файлам
TEST_DATA_FILE: str = "data/test_data.json"
RESULT_FILE: str = "data/result.json"

# Параметры визуализации
PALLET_BASE_HEIGHT: int = 10  # мм
MIN_SCENE_HEIGHT: int = 500   # мм
GRID_STEP: int = 200          # мм
DEFAULT_PLOT_HEIGHT: int = 700

# Настройки паллеты по умолчанию
DEFAULT_PALLET: Dict[str, Any] = {
    "length_mm": 1200,
    "width_mm": 800,
    "max_height_mm": 1800,
    "max_weight_kg": 1500.0
}

# Цветовая схема (тёмная тема)
THEME = {
    "bg_primary": "#2b2b2b",
    "bg_secondary": "#3a3a3a",
    "text_primary": "#eee",
    "text_secondary": "#ccc",
    "grid_color": "#555",
    "axis_color": "#ccc",
    "pallet_color": "#555"
}