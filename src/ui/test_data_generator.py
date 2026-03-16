#!/usr/bin/env python3
"""
Генератор случайных тестовых данных для визуализатора паллет.

Использование:
    python -m data.generator --output ./data --boxes 10 --seed 42
"""
import argparse
import json
import random
from pathlib import Path
from typing import List, Dict
from datetime import datetime


# Шаблоны данных для генерации
SKU_TEMPLATES = [
    {"prefix": "SKU-SHO", "desc": "Shoe Box", "dims": [(330, 190, 115)], "weight": 1.0, "props": {"strict_upright": True, "fragile": False, "stackable": True}},
    {"prefix": "SKU-WIN", "desc": "Wine Case", "dims": [(350, 260, 300)], "weight": 16.0, "props": {"strict_upright": True, "fragile": True, "stackable": False}},
    {"prefix": "SKU-BOX", "desc": "Standard Box", "dims": [(200, 200, 200), (400, 300, 250), (150, 150, 300)], "weight": 2.5, "props": {"strict_upright": False, "fragile": False, "stackable": True}},
    {"prefix": "SKU-ELEC", "desc": "Electronics", "dims": [(500, 400, 200)], "weight": 8.0, "props": {"strict_upright": True, "fragile": True, "stackable": False}},
    {"prefix": "SKU-FOOD", "desc": "Food Package", "dims": [(300, 200, 150)], "weight": 3.5, "props": {"strict_upright": False, "fragile": False, "stackable": True}},
]

PALLET_PRESETS = {
    "euro": {"length_mm": 1200, "width_mm": 800, "max_height_mm": 1800, "max_weight_kg": 1500.0},
    "industrial": {"length_mm": 1200, "width_mm": 1000, "max_height_mm": 2000, "max_weight_kg": 2000.0},
    "small": {"length_mm": 800, "width_mm": 600, "max_height_mm": 1500, "max_weight_kg": 500.0},
}


def generate_sku(template: Dict, index: int) -> Dict:
    """Генерирует данные коробки на основе шаблона"""
    dims = random.choice(template["dims"])
    return {
        "sku_id": f"{template['prefix']}-{random.randint(1000, 9999)}",
        "description": template["desc"],
        "length_mm": dims[0] + random.randint(-20, 20),
        "width_mm": dims[1] + random.randint(-20, 20),
        "height_mm": dims[2] + random.randint(-20, 20),
        "weight_kg": round(template["weight"] * random.uniform(0.8, 1.2), 2),
        "strict_upright": template["props"]["strict_upright"],
        "fragile": template["props"]["fragile"],
        "stackable": template["props"]["stackable"],
    }


def generate_placement(sku: Dict, pallet: Dict, placed_count: int) -> Dict:
    """Генерирует позицию размещения для коробки"""
    # Простая эвристика: размещаем в сетке по X
    x_step = sku["length_mm"] + 10
    x = (placed_count % (pallet["length_mm"] // x_step)) * x_step
    y = 0
    z = 0
    
    return {
        "sku_id": sku["sku_id"],
        "instance_index": placed_count,
        "position": {"x_mm": x, "y_mm": y, "z_mm": z},
        "dimensions_placed": {
            "length_mm": sku["length_mm"],
            "width_mm": sku["width_mm"],
            "height_mm": sku["height_mm"]
        },
        "rotation_code": "LWH"
    }


def generate_test_data(num_boxes: int, pallet_type: str = "euro", seed: int = None) -> Dict:
    """Генерирует тестовые данные задачи"""
    if seed is not None:
        random.seed(seed)
    
    pallet = PALLET_PRESETS.get(pallet_type, PALLET_PRESETS["euro"]).copy()
    boxes = []
    
    for i in range(num_boxes):
        template = random.choice(SKU_TEMPLATES)
        boxes.append(generate_sku(template, i))
    
    return {
        "task_id": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.now().isoformat(),
        "pallet": pallet,
        "boxes": boxes,
        "metadata": {
            "num_boxes": num_boxes,
            "pallet_type": pallet_type,
            "seed": seed
        }
    }


def generate_result_data(test_data: Dict, placement_ratio: float = 0.9) -> Dict:
    """Генерирует результат размещения (симуляция)"""
    placements = []
    unplaced = []
    boxes = test_data["boxes"]
    pallet = test_data["pallet"]
    
    # Симуляция: часть коробок не размещается
    num_to_place = int(len(boxes) * placement_ratio)
    random.shuffle(boxes)
    
    for i, box in enumerate(boxes):
        if i < num_to_place:
            placements.append(generate_placement(box, pallet, i))
        else:
            unplaced.append({
                "sku_id": box["sku_id"],
                "quantity_unplaced": 1,
                "reason": random.choice(["weight_limit_exceeded", "space_constraint", "fragility_conflict"])
            })
    
    return {
        "task_id": test_data["task_id"],
        "solver_version": "1.2.3",
        "solve_time_ms": random.randint(50, 500),
        "placements": placements,
        "unplaced": unplaced,
        "stats": {
            "total_boxes": len(boxes),
            "placed": len(placements),
            "unplaced": len(unplaced)
        }
    }


def save_json(data: Dict, filepath: Path):
    """Сохраняет данные в JSON с форматированием"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Генератор тестовых данных для визуализатора паллет")
    parser.add_argument("--output", "-o", type=str, default="./data", help="Папка для выходных файлов")
    parser.add_argument("--boxes", "-b", type=int, default=10, help="Количество коробок для генерации")
    parser.add_argument("--pallet", "-p", type=str, default="euro", choices=PALLET_PRESETS.keys(), help="Тип паллеты")
    parser.add_argument("--seed", "-s", type=int, default=None, help="Seed для воспроизводимости")
    parser.add_argument("--ratio", "-r", type=float, default=0.9, help="Доля размещённых коробок (0.0-1.0)")
    
    args = parser.parse_args()
    output_dir = Path(args.output)
    
    print(f"🎲 Генерация тестовых данных: {args.boxes} коробок, паллета '{args.pallet}'")
    
    # Генерация
    test_data = generate_test_data(args.boxes, args.pallet, args.seed)
    result_data = generate_result_data(test_data, args.ratio)
    
    # Сохранение
    test_path = output_dir / "test_data.json"
    result_path = output_dir / "result.json"
    
    save_json(test_data, test_path)
    save_json(result_data, result_path)
    
    print(f"✅ Сохранено:")
    print(f"   📄 {test_path}")
    print(f"   📄 {result_path}")
    print(f"📊 Статистика: {result_data['stats']['placed']} размещено, {result_data['stats']['unplaced']} не размещено")


if __name__ == "__main__":
    main()