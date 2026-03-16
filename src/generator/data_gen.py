import json
import random
import os
import sys
from typing import Dict, Any, List, Tuple, Optional, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

# ==============================
# 1. Константы и Архетипы (База)
# ==============================

GLOBAL_SEED = 42

PALLETS = [
    {"id": "EUR_1200x800", "length_mm": 1200, "width_mm": 800, "max_height_mm": 1800, "max_weight_kg": 1000.0},
    {"id": "EUR_1200x1000", "length_mm": 1200, "width_mm": 1000, "max_height_mm": 2000, "max_weight_kg": 1000.0},
    {"id": "US_48x40", "length_mm": 1219, "width_mm": 1016, "max_height_mm": 2000, "max_weight_kg": 1000.0}
]

FOOD_RETAIL_ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "banana":  {"desc": "Bananas Box", "l": 502, "w": 394, "h": 239, "wt": 19.0, "upright": True,  "fragile": False, "strong": True},
    "sugar":   {"desc": "Sugar 10kg",  "l": 400, "w": 300, "h": 150, "wt": 10.0, "upright": False, "fragile": False, "strong": True},
    "water":   {"desc": "Water Pack",  "l": 280, "w": 190, "h": 330, "wt": 9.2,  "upright": True,  "fragile": False, "strong": True},
    "wine":    {"desc": "Wine Case",   "l": 250, "w": 170, "h": 320, "wt": 8.0,  "upright": True,  "fragile": True,  "strong": False},
    "chips":   {"desc": "Chips Carton","l": 600, "w": 400, "h": 400, "wt": 1.8,  "upright": False, "fragile": True,  "strong": False},
    "eggs":    {"desc": "Eggs 360pcs", "l": 630, "w": 320, "h": 350, "wt": 22.0, "upright": True,  "fragile": True,  "strong": False},
    "canned":  {"desc": "Canned Peas", "l": 300, "w": 200, "h": 120, "wt": 6.0,  "upright": True,  "fragile": False, "strong": True},
    "glass":   {"desc": "Glass Jars",  "l": 300, "w": 200, "h": 250, "wt": 12.0, "upright": True,  "fragile": True,  "strong": False},
    "frozen":  {"desc": "Frozen Food", "l": 400, "w": 300, "h": 200, "wt": 8.5,  "upright": False, "fragile": False, "strong": True},
    "paper":   {"desc": "Paper Towels","l": 500, "w": 400, "h": 450, "wt": 4.0,  "upright": False, "fragile": False, "strong": False}
}

# ==============================
# 2. Конфигурация и Сложность
# ==============================

class ComplexityLevel(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    CHAOS = "chaos"

@dataclass
class GenerationConfig:
    seed: int = GLOBAL_SEED
    complexity: ComplexityLevel = ComplexityLevel.MEDIUM
    
    pallet_count_min: int = 1
    pallet_count_max: int = 3
    pallet_type_ids: Optional[List[str]] = None
    
    sku_count_min: int = 2
    sku_count_max: int = 5
    quantity_per_sku_min: int = 10
    quantity_per_sku_max: int = 50
    
    dimension_noise_ratio: float = 0.0
    weight_noise_ratio: float = 0.0
    
    force_fragile_ratio: float = 0.0
    force_upright_ratio: float = 0.0
    enable_load_bearing: bool = False
    
    include_archetypes: Optional[List[str]] = None
    exclude_archetypes: Optional[List[str]] = None

    def apply_complexity_profile(self):
        if self.complexity == ComplexityLevel.EASY:
            self.sku_count_min, self.sku_count_max = 2, 3
            self.dimension_noise_ratio = 0.0
            self.force_fragile_ratio = 0.0
            self.enable_load_bearing = False
            self.quantity_per_sku_min, self.quantity_per_sku_max = 50, 100
            
        elif self.complexity == ComplexityLevel.MEDIUM:
            self.sku_count_min, self.sku_count_max = 4, 6
            self.dimension_noise_ratio = 0.02
            self.weight_noise_ratio = 0.02
            self.force_fragile_ratio = 0.3
            self.enable_load_bearing = True
            
        elif self.complexity == ComplexityLevel.HARD:
            self.sku_count_min, self.sku_count_max = 7, 10
            self.dimension_noise_ratio = 0.05
            self.weight_noise_ratio = 0.05
            self.force_fragile_ratio = 0.6
            self.enable_load_bearing = True
            self.quantity_per_sku_min, self.quantity_per_sku_max = 20, 80
            
        elif self.complexity == ComplexityLevel.CHAOS:
            self.sku_count_min, self.sku_count_max = 8, len(FOOD_RETAIL_ARCHETYPES)
            self.dimension_noise_ratio = 0.10
            self.weight_noise_ratio = 0.10
            self.force_fragile_ratio = 0.8
            self.enable_load_bearing = True
            self.pallet_count_min, self.pallet_count_max = 5, 10

# ==============================
# 3. Генератор Сценариев
# ==============================

class PalletScenarioGenerator:
    def __init__(self, config: GenerationConfig):
        self.config = config
        self.config.apply_complexity_profile()
        random.seed(self.config.seed)

    def _get_available_archetypes(self) -> List[str]:
        keys = list(FOOD_RETAIL_ARCHETYPES.keys())
        if self.config.exclude_archetypes:
            keys = [k for k in keys if k not in self.config.exclude_archetypes]
        if self.config.include_archetypes:
            keys = [k for k in keys if k in self.config.include_archetypes]
        return keys

    def _apply_noise(self, value: float, ratio: float) -> float:
        if ratio == 0:
            return value
        noise = random.uniform(1 - ratio, 1 + ratio)
        return round(value * noise, 2)

    def _generate_box(self, archetype_key: str) -> Dict[str, Any]:
        base = FOOD_RETAIL_ARCHETYPES[archetype_key]
        
        l = int(round(self._apply_noise(base["l"], self.config.dimension_noise_ratio)))
        w = int(round(self._apply_noise(base["w"], self.config.dimension_noise_ratio)))
        h = int(round(self._apply_noise(base["h"], self.config.dimension_noise_ratio)))
        
        wt = round(self._apply_noise(base["wt"], self.config.weight_noise_ratio), 2)
        
        is_fragile = base["fragile"]
        if random.random() < self.config.force_fragile_ratio:
            is_fragile = True
            
        is_upright = base["upright"]
        if random.random() < self.config.force_upright_ratio:
            is_upright = True

        box = {
            "sku_id": f"SKU-{archetype_key.upper()}-{random.randint(1000, 9999)}",
            "description": base["desc"],
            "dimensions_mm": [l, w, h],
            "weight_kg": wt,
            "quantity": random.randint(self.config.quantity_per_sku_min, self.config.quantity_per_sku_max),
            "strict_upright": is_upright,
            "fragile": is_fragile,
            "stackable": not is_fragile
        }

        if self.config.enable_load_bearing:
            if is_fragile:
                box["load_bearing_kg"] = round(wt * random.uniform(0.5, 1.5), 2)
                box["max_stack_layers"] = random.randint(1, 3)
            else:
                box["load_bearing_kg"] = round(wt * random.uniform(5.0, 20.0), 2)
                box["max_stack_layers"] = random.randint(5, 15)

        return box

    def _generate_pallets(self, count: int) -> List[Dict[str, Any]]:
        pallets = []
        available_ids = self.config.pallet_type_ids or [p["id"] for p in PALLETS]
        
        for i in range(count):
            p_id = random.choice(available_ids)
            template = next(p for p in PALLETS if p["id"] == p_id)
            pallets.append({
                "pallet_index": i,
                "type_id": template["id"],
                "dimensions_mm": [template["length_mm"], template["width_mm"]],
                "max_height_mm": template["max_height_mm"],
                "max_weight_kg": template["max_weight_kg"],
            })
        return pallets

    def _config_to_dict(self) -> Dict[str, Any]:
        """FIX: Конвертирует конфиг в JSON-сериализуемый словарь"""
        config_dict = asdict(self.config)
        config_dict['complexity'] = self.config.complexity.value
        return config_dict

    def generate(self, task_id: str) -> Dict[str, Any]:
        p_count = random.randint(self.config.pallet_count_min, self.config.pallet_count_max)
        pallets = self._generate_pallets(p_count)
        
        available_keys = self._get_available_archetypes()
        available_count = len(available_keys)
        
        # FIX: Корректируем диапазоны SKU в зависимости от доступных архетипов
        # Если доступных типов меньше, чем требует минимум, уменьшаем минимум
        actual_min = min(self.config.sku_count_min, available_count)
        actual_max = min(self.config.sku_count_max, available_count)
        
        # Защита от ситуации, когда минимум всё ещё больше максимума
        if actual_min > actual_max:
            actual_min = actual_max
        
        # Защита от пустого списка
        if available_count == 0:
            raise ValueError("No archetypes available for generation. Check include/exclude filters.")
        
        sku_count = random.randint(actual_min, actual_max)
        selected_keys = random.sample(available_keys, sku_count)
        
        boxes = [self._generate_box(key) for key in selected_keys]
        
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "config_used": self._config_to_dict(),
            "complexity_profile": self.config.complexity.value
        }

        return {
            "task_id": task_id,
            "metadata": metadata,
            "shipment_info": {
                "total_pallets": len(pallets),
                "total_sku_types": len(boxes),
                "total_boxes_estimated": sum(b["quantity"] for b in boxes)
            },
            "pallets": pallets,
            "boxes": boxes
        }

# ==============================
# 4. Утилиты и Запуск
# ==============================

def save_scenario(scenario: Dict[str, Any], directory: str = "src/generator/data"):
    os.makedirs(directory, exist_ok=True)
    filename = f"{directory}/request.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=2, ensure_ascii=False)
    return filename

if __name__ == "__main__":
    print("=== Pallet Data Generator v2.0 ===")
    
    scenarios_to_generate = [
        ("demo_easy", ComplexityLevel.EASY),
        ("demo_medium", ComplexityLevel.MEDIUM),
        ("demo_hard", ComplexityLevel.HARD),
    ]
    
    for name, level in scenarios_to_generate:
        cfg = GenerationConfig(complexity=level, seed=42 + hash(name))
        generator = PalletScenarioGenerator(cfg)
        
        scenario = generator.generate(f"task_{name}")
        path = save_scenario(scenario)
        
        b_count = sum(b['quantity'] for b in scenario['boxes'])
        print(f"[OK] {path} | Pallets: {len(scenario['pallets'])} | Boxes: {b_count} | Complexity: {level.value}")

    # Custom scenario
    custom_cfg = GenerationConfig(
        complexity=ComplexityLevel.HARD,
        seed=999,
        include_archetypes=["glass", "wine"],
        force_fragile_ratio=1.0,
        pallet_count_min=1,
        pallet_count_max=1
    )
    
    gen_custom = PalletScenarioGenerator(custom_cfg)
    scenario_custom = gen_custom.generate("task_custom_glass")
    path_custom = save_scenario(scenario_custom)
    print(f"[OK] {path_custom} | Custom Scenario (Fragile Only)")