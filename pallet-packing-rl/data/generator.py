import json
import random
import os
from typing import Dict, Any, List, Tuple, Optional

# ==============================
# Настройки случайности
# ==============================

GLOBAL_SEED = 42

def set_seed(seed: int = GLOBAL_SEED):
    random.seed(seed)

# ==============================
# Паллеты (реальные типы)
# ==============================

PALLETS = [
    {
        "id": "EUR_1200x800",
        "length_mm": 1200,
        "width_mm": 800,
        "max_height_mm": 1800,
        "max_weight_kg": 1000.0
    },
    {
        "id": "EUR_1200x1000",
        "length_mm": 1200,
        "width_mm": 1000,
        "max_height_mm": 2000,
        "max_weight_kg": 1000.0
    },
    {
        "id": "US_48x40",
        "length_mm": 1219,
        "width_mm": 1016,
        "max_height_mm": 2000,
        "max_weight_kg": 1000.0
    }
]

# ==============================
# Архетипы SKU для фуд‑ритейла
# ==============================

FOOD_RETAIL_ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "banana":  {"desc": "Bananas Box", "l": 502, "w": 394, "h": 239, "wt": 19.0, "upright": True,  "fragile": False},
    "sugar":   {"desc": "Sugar 10kg",  "l": 400, "w": 300, "h": 150, "wt": 10.0, "upright": False, "fragile": False},
    "water":   {"desc": "Water Pack",  "l": 280, "w": 190, "h": 330, "wt": 9.2,  "upright": True,  "fragile": False},
    "wine":    {"desc": "Wine Case",   "l": 250, "w": 170, "h": 320, "wt": 8.0,  "upright": True,  "fragile": True},
    "chips":   {"desc": "Chips Carton","l": 600, "w": 400, "h": 400, "wt": 1.8,  "upright": False, "fragile": True},
    "eggs":    {"desc": "Eggs 360pcs", "l": 630, "w": 320, "h": 350, "wt": 22.0, "upright": True,  "fragile": True},
    "canned":  {"desc": "Canned Peas", "l": 300, "w": 200, "h": 120, "wt": 6.0,  "upright": True,  "fragile": False}
}

# ==============================
# Конфигурация количества коробок (Task 2)
# ==============================

class ShipmentConfig:
    """
    Класс для конфигурации параметров генерации задачи:
    - Количество паллет в отгрузке
    - Типы коробок и диапазоны их количества
    """
    def __init__(self, 
                 pallet_count_min: int = 1, 
                 pallet_count_max: int = 1,
                 pallet_type_id: Optional[str] = None):
        self.pallet_count_min = pallet_count_min
        self.pallet_count_max = pallet_count_max
        self.pallet_type_id = pallet_type_id  # Если None, выбирается случайно
        self.box_rules: Dict[str, Tuple[int, int]] = {}

    def add_box_type(self, archetype_key: str, qty_min: int, qty_max: int):
        """Добавляет правило генерации для типа коробки"""
        if archetype_key not in FOOD_RETAIL_ARCHETYPES:
            raise ValueError(f"Unknown archetype: {archetype_key}")
        self.box_rules[archetype_key] = (qty_min, qty_max)
        return self

    @classmethod
    def heavy_water_config(cls) -> 'ShipmentConfig':
        config = cls(pallet_count_min=2, pallet_count_max=3)
        config.add_box_type("water", 150, 250)
        config.add_box_type("sugar", 80, 120)
        return config

    @classmethod
    def fragile_tower_config(cls) -> 'ShipmentConfig':
        config = cls(pallet_count_min=1, pallet_count_max=2)
        config.add_box_type("banana", 20, 40)
        config.add_box_type("chips", 30, 60)
        config.add_box_type("eggs", 15, 25)
        return config

    @classmethod
    def liquid_tetris_config(cls) -> 'ShipmentConfig':
        config = cls(pallet_count_min=2, pallet_count_max=2)
        config.add_box_type("water", 50, 80)
        config.add_box_type("wine", 40, 60)
        config.add_box_type("canned", 60, 100)
        return config

    @classmethod
    def random_mixed_config(cls) -> 'ShipmentConfig':
        config = cls(pallet_count_min=3, pallet_count_max=5)
        # Добавляем случайные типы в __main__, здесь только база
        return config

# ==============================
# Утилиты
# ==============================

def _noise_int(x: int, rel: float = 0.02) -> int:
    """Небольшой шум размеров (±2%)"""
    return int(round(x * random.uniform(1 - rel, 1 + rel)))

def create_box(archetype_key: str, qty_min: int, qty_max: int) -> Dict[str, Any]:
    base = FOOD_RETAIL_ARCHETYPES[archetype_key]
    return {
        "sku_id": f"SKU-{archetype_key.upper()}-{random.randint(1000, 9999)}",
        "description": base["desc"],
        "length_mm": _noise_int(base["l"]),
        "width_mm": _noise_int(base["w"]),
        "height_mm": _noise_int(base["h"]),
        "weight_kg": round(base["wt"] * random.uniform(0.98, 1.02), 2),
        "quantity": random.randint(qty_min, qty_max),
        "strict_upright": base["upright"],
        "fragile": base["fragile"],
        "stackable": True
    }

# ==============================
# Генерация сценария (Task 1 & 2)
# ==============================

def generate_scenario(task_id: str, config: ShipmentConfig, seed: int = GLOBAL_SEED) -> Dict[str, Any]:
    set_seed(seed)  # воспроизводимость

    # 1. Генерация списка паллет (Task 1: много паллет)
    pallets: List[Dict[str, Any]] = []
    pallet_count = random.randint(config.pallet_count_min, config.pallet_count_max)
    
    for i in range(pallet_count):
        # Если в конфиге задан тип, используем его, иначе случайный
        if config.pallet_type_id:
            pallet_template = next((p for p in PALLETS if p["id"] == config.pallet_type_id), random.choice(PALLETS))
        else:
            pallet_template = random.choice(PALLETS)
            
        pallets.append({
            "pallet_index": i,
            "type_id": pallet_template["id"],
            "length_mm": pallet_template["length_mm"],
            "width_mm": pallet_template["width_mm"],
            "max_height_mm": pallet_template["max_height_mm"],
            "max_weight_kg": pallet_template["max_weight_kg"],
        })

    # 2. Генерация коробок согласно конфигу (Task 2)
    boxes: List[Dict[str, Any]] = []
    
    # Для random_mixed дополняем конфиг случайными типами, если правил нет
    if not config.box_rules and "random" in task_id.lower():
        keys = list(FOOD_RETAIL_ARCHETYPES.keys())
        k = random.randint(4, min(7, len(keys)))
        for key in random.sample(keys, k=k):
            config.add_box_type(key, 10, 30)

    for archetype_key, (q_min, q_max) in config.box_rules.items():
        boxes.append(create_box(archetype_key, q_min, q_max))

    return {
        "task_id": task_id,
        "shipment_info": {
            "total_pallets_available": pallet_count,
            "total_sku_types": len(boxes)
        },
        "pallets": pallets,  # Теперь список
        "boxes": boxes
    }


if __name__ == "__main__":
    # Глобальная инициализация
    set_seed(123)

    # Маппинг имен сценариев на конфигурации
    scenario_configs = {
        "heavy_water": ShipmentConfig.heavy_water_config(),
        "fragile_tower": ShipmentConfig.fragile_tower_config(),
        "liquid_tetris": ShipmentConfig.liquid_tetris_config(),
        "random_mixed": ShipmentConfig.random_mixed_config()
    }
    
    # Создаём папку data
    os.makedirs("scr/data", exist_ok=True)
    
    for sc_name, config in scenario_configs.items():
        # Уникальный сид для каждого сценария для разнообразия, но воспроизводимости
        seed = 123 + list(scenario_configs.keys()).index(sc_name)
        
        task = generate_scenario(f"task_{sc_name}", config, seed=seed)

        filename = f"scr/data/request_{sc_name}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2, ensure_ascii=False)
        print(f"Saved {filename} (Pallets: {len(task['pallets'])}, Boxes: {len(task['boxes'])})")