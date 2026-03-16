"""Утилиты для 3D-визуализации"""
from typing import Dict, List, Tuple, Optional


def create_box_mesh(
    x: float, y: float, z: float,
    length: float, width: float, height: float
) -> Tuple[List[List[float]], List[List[int]]]:
    """
    Создаёт вершины и треугольники для 3D-коробки.
    
    Args:
        x, y, z: Координаты левого нижнего угла
        length, width, height: Габариты коробки
    
    Returns:
        Tuple[vertices, triangles] для plotly.Mesh3d
    """
    # 8 вершин параллелепипеда
    vertices = [
        [x, y, z],           # 0: передний низ левый
        [x + length, y, z],  # 1: передний низ правый
        [x + length, y + width, z],   # 2: задний низ правый
        [x, y + width, z],            # 3: задний низ левый
        [x, y, z + height],           # 4: передний верх левый
        [x + length, y, z + height],  # 5: передний верх правый
        [x + length, y + width, z + height],  # 6: задний верх правый
        [x, y + width, z + height]            # 7: задний верх левый
    ]
    
    # 12 треугольников (2 на каждую из 6 граней)
    triangles = [
        # Низ
        [0, 1, 2], [0, 2, 3],
        # Верх
        [4, 6, 5], [4, 7, 6],
        # Перед
        [0, 4, 5], [0, 5, 1],
        # Зад
        [2, 6, 7], [2, 7, 3],
        # Право
        [1, 5, 6], [1, 6, 2],
        # Лево
        [0, 3, 7], [0, 7, 4]
    ]
    
    return vertices, triangles


def build_hover_text(
    sku_id: str,
    position: Dict[str, int],
    dimensions: Dict[str, int],
    properties: Optional[Dict] = None,
    color: str = "#999999"
) -> str:
    """
    Формирует HTML-текст для hover-подсказки.
    
    Args:
        sku_id: Идентификатор товара
        position: {"x_mm": ..., "y_mm": ..., "z_mm": ...}
        dimensions: {"length_mm": ..., "width_mm": ..., "height_mm": ...}
        properties: Доп. свойства (weight, fragile, etc.)
        color: HEX цвет для индикатора
    
    Returns:
        HTML-строка для hoverinfo
    """
    properties = properties or {}
    
    # Цветной индикатор
    color_indicator = (
        f"<span style='display:inline-block;width:12px;height:12px;"
        f"background:{color};border-radius:50%;margin-right:6px;"
        f"vertical-align:middle;border:1px solid #666'></span>"
    )
    
    lines = [
        f"<div style='display:flex;align-items:center;gap:8px'>"
        f"<b style='color:#1a1a1a'>{color_indicator}{sku_id}</b></div>",
        f"📍 Позиция: ({position['x_mm']}, {position['y_mm']}, {position['z_mm']}) мм",
        f"📏 Габариты: {dimensions['length_mm']}×{dimensions['width_mm']}×{dimensions['height_mm']} мм"
    ]
    
    # Дополнительные свойства
    if properties:
        if 'weight_kg' in properties:
            lines.append(f"⚖️ Вес: {properties['weight_kg']} кг")
        if properties.get('fragile'):
            lines.append("<span style='color:#c0392b'>🍷 Хрупкое</span>")
        if properties.get('strict_upright'):
            lines.append("<span style='color:#2980b9'>⬆️ Не переворачивать</span>")
        if not properties.get('stackable', True):
            lines.append("<span style='color:#7f8c8d'>🚫 Не ставить сверху</span>")
    
    return "<br>".join(lines)


def format_dimension_mm(value: int) -> str:
    """Форматирует значение в мм с пробелами"""
    return f"{value:,}".replace(",", " ")