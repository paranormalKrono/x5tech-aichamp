import streamlit as st
import plotly.graph_objects as go
import json
import os
import hashlib
import colorsys
from typing import Dict, List, Optional, Tuple

# === Константы ===
TEST_DATA_FILE = "src/generator/data/request.json"
RESULT_FILE = "src/core/data/result.json"
PALLET_BASE_HEIGHT = 10  # мм
MIN_SCENE_HEIGHT = 500   # мм
GRID_STEP = 200          # мм
DEFAULT_PALLET = {"length_mm": 1200, "width_mm": 800, "max_height_mm": 1800, "max_weight_kg": 1500.0}

st.set_page_config(layout="wide")
st.title("📦 3D Визуализация Паллеты")


# === 1. Загрузка данных с обработкой ошибок ===
@st.cache_data(ttl=3600, hash_funcs={dict: lambda x: json.dumps(x, sort_keys=True)})
def load_data(test_file: str, result_file: str) -> Tuple[Dict, Dict]:
    """Загружает и валидирует данные из JSON-файлов"""
    def safe_load(filepath: str, fallback: Dict) -> Dict:
        if not os.path.exists(filepath):
            return fallback
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            st.error(f"Ошибка чтения {filepath}: {e}")
            return fallback
    
    test_data = safe_load(test_file, {})
    result_data = safe_load(result_file, {})
    return test_data, result_data


# === 2. Демо-данные ===
def get_demo_data() -> Tuple[Dict, Dict]:
    """Возвращает демо-данные для тестирования"""
    test = {
        "task_id": "demo",
        "pallet": DEFAULT_PALLET,
        "boxes": [
            {"sku_id": "SKU-SHO-1234", "description": "Shoe Box", "length_mm": 330, "width_mm": 190, "height_mm": 115, "weight_kg": 1.0, "strict_upright": True, "fragile": False, "stackable": True},
            {"sku_id": "SKU-WIN-5678", "description": "Wine Case", "length_mm": 350, "width_mm": 260, "height_mm": 300, "weight_kg": 16.0, "strict_upright": True, "fragile": True, "stackable": False},
            {"sku_id": "SKU-BOX-NEW", "description": "New Item", "length_mm": 200, "width_mm": 200, "height_mm": 200, "weight_kg": 2.5, "strict_upright": False, "fragile": False, "stackable": True}
        ]
    }
    result = {
        "task_id": "demo",
        "placements": [
            {"sku_id": "SKU-SHO-1234", "instance_index": 0, "position": {"x_mm": 0, "y_mm": 0, "z_mm": 0}, "dimensions_placed": {"length_mm": 330, "width_mm": 190, "height_mm": 115}, "rotation_code": "LWH"},
            {"sku_id": "SKU-SHO-1234", "instance_index": 1, "position": {"x_mm": 330, "y_mm": 0, "z_mm": 0}, "dimensions_placed": {"length_mm": 330, "width_mm": 190, "height_mm": 115}, "rotation_code": "LWH"},
            {"sku_id": "SKU-WIN-5678", "instance_index": 2, "position": {"x_mm": 330, "y_mm": 250, "z_mm": 0}, "dimensions_placed": {"length_mm": 350, "width_mm": 260, "height_mm": 300}, "rotation_code": "LWH"},
            {"sku_id": "SKU-BOX-NEW", "instance_index": 3, "position": {"x_mm": 0, "y_mm": 400, "z_mm": 0}, "dimensions_placed": {"length_mm": 200, "width_mm": 200, "height_mm": 200}, "rotation_code": "LWH"}
        ],
        "unplaced": [{"sku_id": "SKU-WIN-5678", "quantity_unplaced": 1, "reason": "weight_limit_exceeded"}]
    }
    return test, result


# === 3. Генерация цветов для SKU ===
@st.cache_data
def generate_sku_colors(sku_list: List[str]) -> Dict[str, str]:
    """
    Генерирует визуально различимые HEX-цвета для списка SKU.
    - Детерминировано: один SKU = один цвет всегда
    - Использует HSL с равномерным распределением оттенка
    - Фиксированные насыщенность/яркость для читаемости
    """
    if not sku_list:
        return {}
    
    colors = {}
    n = len(sku_list)
    sorted_skus = sorted(sku_list)
    
    for i, sku in enumerate(sorted_skus):
        hash_offset = int(hashlib.md5(sku.encode()).hexdigest()[:4], 16) / 65535
        hue = (i / n + hash_offset * 0.1) % 1.0
        saturation = 0.75
        lightness = 0.65
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        colors[sku] = hex_color
    
    return colors


def get_contrast_text_color(hex_color: str) -> str:
    """Возвращает чёрный или белый цвет текста в зависимости от яркости фона"""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return "#1a1a1a" if brightness > 140 else "#ffffff"


# === 4. Вспомогательные функции визуализации ===
def get_sku_color(sku_id: str, color_map: Dict[str, str]) -> str:
    """Безопасное получение цвета из карты, с фоллбэком"""
    return color_map.get(sku_id, "#999999")


def create_box_mesh(x: float, y: float, z: float, l: float, w: float, h: float) -> Tuple[List, List]:
    """Создаёт вершины и треугольники для 3D-коробки"""
    vertices = [
        [x, y, z], [x+l, y, z], [x+l, y+w, z], [x, y+w, z],
        [x, y, z+h], [x+l, y, z+h], [x+l, y+w, z+h], [x, y+w, z+h]
    ]
    triangles = [
        [0,1,2], [0,2,3], [4,6,5], [4,7,6],
        [0,4,5], [0,5,1], [2,6,7], [2,7,3],
        [1,5,6], [1,6,2], [0,3,7], [0,7,4]
    ]
    return vertices, triangles


def build_hover_text(sku_id: str, pos: Dict, dim: Dict, props: Dict, color: str) -> str:
    """Формирует читаемый текст для hover с цветным индикатором"""
    color_indicator = f"<span style='display:inline-block;width:12px;height:12px;background:{color};border-radius:50%;margin-right:6px;vertical-align:middle;border:1px solid #666'></span>"
    
    lines = [
        f"<div style='display:flex;align-items:center;gap:8px'><b style='color:#1a1a1a'>{color_indicator}{sku_id}</b></div>",
        f"📍 Позиция: ({pos['x_mm']}, {pos['y_mm']}, {pos['z_mm']}) мм",
        f"📏 Габариты: {dim['length_mm']}×{dim['width_mm']}×{dim['height_mm']} мм"
    ]
    if props:
        if 'weight_kg' in props:
            lines.append(f"⚖️ Вес: {props['weight_kg']} кг")
        if props.get('fragile'): lines.append("<span style='color:#c0392b'>🍷 Хрупкое</span>")
        if props.get('strict_upright'): lines.append("<span style='color:#2980b9'>⬆️ Не переворачивать</span>")
        if not props.get('stackable', True): lines.append("<span style='color:#7f8c8d'>🚫 Не ставить сверху</span>")
    return "<br>".join(lines)


# === Основная логика ===
def main():
    # Загрузка данных
    test_data, result_data = load_data(TEST_DATA_FILE, RESULT_FILE)
    
    # Демо-режим если данные пустые
    #if not test_data or not result_data:
    # test_data, result_data = get_demo_data()
    
    # Индекс свойств коробок
    sku_properties = {
        box["sku_id"]: {
            "description": box.get("description", ""),
            "strict_upright": box.get("strict_upright", False),
            "fragile": box.get("fragile", False),
            "stackable": box.get("stackable", True),
            "weight_kg": box.get("weight_kg", 0)
        }
        for box in test_data.get("boxes", [])
    }
    
    pallet = test_data.get("pallet", DEFAULT_PALLET)
    placements = result_data.get("placements", [])
    
    # === Генерация цветов для уникальных SKU ===
    unique_skus = list(dict.fromkeys(p["sku_id"] for p in placements))
    sku_color_map = generate_sku_colors(unique_skus)
    
    # === 🆕 РАСЧЁТ МЕТРИК ===
    # 1. Объём паллеты и заполнение
    pallet_volume = pallet["length_mm"] * pallet["width_mm"] * pallet["max_height_mm"]
    occupied_volume = sum(
        p["dimensions_placed"]["length_mm"] * 
        p["dimensions_placed"]["width_mm"] * 
        p["dimensions_placed"]["height_mm"] 
        for p in placements
    )
    fill_percentage = (occupied_volume / pallet_volume * 100) if pallet_volume > 0 else 0

    # 2. Полнота заказа
    placed_count = len(placements)
    unplaced_count = sum(u["quantity_unplaced"] for u in result_data.get("unplaced", []))
    total_ordered = placed_count + unplaced_count
    completeness_percentage = (placed_count / total_ordered * 100) if total_ordered > 0 else 100.0

    # 3. Дополнительно: вес
    total_weight = sum(
        sku_properties.get(p["sku_id"], {}).get("weight_kg", 0) 
        for p in placements
    )
    max_weight = pallet.get("max_weight_kg", float("inf"))
    weight_percentage = (total_weight / max_weight * 100) if max_weight and max_weight < float("inf") else 0

    # === Настройки интерфейса ===
    with st.sidebar:
        st.subheader("⚙️ Вид")
        opacity = st.slider("Прозрачность коробок", 0.1, 1.0, 0.4)
        show_axes = st.checkbox("Оси координат", value=True)
        
        st.subheader("🎨 Информация")
        st.caption(f"Уникальных SKU: **{len(unique_skus)}**")
        
        if unique_skus:
            with st.expander("📋 Типы коробок", expanded=True):
                table_rows = []
                for sku in unique_skus:
                    props = sku_properties.get(sku, {})
                    color = sku_color_map[sku]
                    text_color = get_contrast_text_color(color)
                    
                    icons = []
                    if props.get('fragile'): icons.append("🍷")
                    if props.get('strict_upright'): icons.append("⬆️")
                    if not props.get('stackable', True): icons.append("🚫")
                    icons_str = " ".join(icons) if icons else "—"
                    
                    table_rows.append(
                        f"<tr style='border-bottom:1px solid #444'>"
                        f"<td style='padding:8px'><div style='width:20px;height:20px;background:{color};border-radius:3px;border:1px solid #666'></div></td>"
                        f"<td style='padding:8px;font-family:monospace;font-size:0.9em'>{sku}</td>"
                        f"<td style='padding:8px'>{props.get('description', '—')}</td>"
                        f"<td style='padding:8px'>{props.get('weight_kg', '—')} кг</td>"
                        f"<td style='padding:8px;text-align:center'>{icons_str}</td>"
                        f"</tr>"
                    )
                
                st.markdown(
                    f"""
                    <div style='background:#2b2b2b; border-radius:6px; padding:10px; overflow-x:auto'>
                    <table style='width:100%; border-collapse:collapse; font-size:0.85em; color:#eee'>
                        <thead>
                            <tr style='background:#3a3a3a; color:#ccc'>
                                <th style='padding:8px; text-align:left; border-bottom:2px solid #555'>🎨</th>
                                <th style='padding:8px; text-align:left; border-bottom:2px solid #555'>SKU</th>
                                <th style='padding:8px; text-align:left; border-bottom:2px solid #555'>Описание</th>
                                <th style='padding:8px; text-align:left; border-bottom:2px solid #555'>Вес</th>
                                <th style='padding:8px; text-align:left; border-bottom:2px solid #555'>Свойства</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(table_rows)}
                        </tbody>
                    </table>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    
    # === Расчёт границ сцены ===
    max_x = pallet.get("length_mm", 1200)
    max_y = pallet.get("width_mm", 800)
    max_z = pallet.get("max_height_mm", 1800)
    max_z = max(max_z, MIN_SCENE_HEIGHT)
    
    scale = max(max_x, max_y, max_z)
    aspect = dict(x=max_x/scale, y=max_y/scale, z=min(max_z/scale, 1.0))
    
    # === Построение графика ===
    fig = go.Figure()
    
    # Паллета
    verts, tris = create_box_mesh(0, 0, 0, max_x, max_y, PALLET_BASE_HEIGHT)
    fig.add_trace(go.Mesh3d(
        x=[v[0] for v in verts], y=[v[1] for v in verts], z=[v[2] for v in verts],
        i=[t[0] for t in tris], j=[t[1] for t in tris], k=[t[2] for t in tris],
        color='#555', opacity=0.2, name='Паллета', showscale=False
    ))
    
    # Коробки
    for p in placements:
        sku_id = p["sku_id"]
        pos, dim = p["position"], p["dimensions_placed"]
        props = sku_properties.get(sku_id, {})
        color = get_sku_color(sku_id, sku_color_map)
        
        verts, tris = create_box_mesh(
            pos["x_mm"], pos["y_mm"], pos["z_mm"],
            dim["length_mm"], dim["width_mm"], dim["height_mm"]
        )
        
        fig.add_trace(go.Mesh3d(
            x=[v[0] for v in verts], y=[v[1] for v in verts], z=[v[2] for v in verts],
            i=[t[0] for t in tris], j=[t[1] for t in tris], k=[t[2] for t in tris],
            color=color, opacity=opacity, name=sku_id, showscale=False,
            hoverinfo='text', hovertext=build_hover_text(sku_id, pos, dim, props, color)
        ))
    
    # Настройка тёмной темы для сцены
    axis_config = dict(
        visible=show_axes,
        showgrid=True,
        gridcolor='#555',
        gridwidth=0.5,
        zeroline=False,
        tickcolor='#777',
        color='#ccc'
    )
    
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='X, мм', range=[0, max_x], tickmode='linear', dtick=GRID_STEP, **axis_config),
            yaxis=dict(title='Y, мм', range=[0, max_y], tickmode='linear', dtick=GRID_STEP, **axis_config),
            zaxis=dict(title='Z, мм', range=[0, max_z], tickmode='linear', dtick=GRID_STEP, **axis_config),
            aspectmode='manual', aspectratio=aspect,
            bgcolor='#2b2b2b',
            camera=dict(eye=dict(x=1.8, y=1.8, z=1.8))
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=700,
        hoverlabel=dict(
            bgcolor="#3a3a3a",
            font_size=13,
            font_color="#eee",
            bordercolor="#666",
            namelength=-1
        ),
        paper_bgcolor='#2b2b2b',
        plot_bgcolor='#2b2b2b'
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # === 🆕 БЛОК МЕТРИК ===
    st.subheader("📊 Метрики размещения")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="📦 Заполнение объёма",
            value=f"{fill_percentage:.1f}%",
            delta=f"{occupied_volume:,} / {pallet_volume:,} мм³"
        )
        st.progress(min(fill_percentage / 100, 1.0))

    with col2:
        st.metric(
            label="✅ Полнота заказа", 
            value=f"{completeness_percentage:.1f}%",
            delta=f"{placed_count} из {total_ordered} коробок"
        )
        st.progress(min(completeness_percentage / 100, 1.0))

    with col3:
        if max_weight < float("inf"):
            st.metric(
                label="⚖️ Загрузка по весу",
                value=f"{weight_percentage:.1f}%",
                delta=f"{total_weight:.1f} / {max_weight:.1f} кг"
            )
            st.progress(min(weight_percentage / 100, 1.0))
        else:
            st.metric(
                label="⚖️ Загрузка по весу",
                value=f"{total_weight:.1f} кг",
                delta="без лимита"
            )
    
    # === Информация о задаче ===
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Task ID:** `{result_data.get('task_id', 'N/A')}`")
        st.info(f"**Solver:** v{result_data.get('solver_version', 'N/A')} | {result_data.get('solve_time_ms', 'N/A')} мс")
    with col2:
        st.success(f"✅ Размещено: {placed_count}")
        if unplaced_count: st.warning(f"⚠️ Не размещено: {unplaced_count}")
    
    # === Неразмещённые коробки ===
    if result_data.get("unplaced"):
        with st.expander("⚠️ Неразмещённые коробки", expanded=False):
            for item in result_data["unplaced"]:
                props = sku_properties.get(item["sku_id"], {})
                desc = props.get("description", "")
                st.caption(f"• `{item['sku_id']}` {desc} × {item['quantity_unplaced']} — `{item['reason']}`")
    
    # === Справка с адаптивным оформлением под тёмную тему ===
    with st.expander("🏷️ Расшифровка свойств"):
        st.markdown("""
        <div style='background:#3a3a3a; padding:15px; border-radius:8px; border-left:4px solid #3498db; color:#eee'>
        <table style='width:100%; border-collapse:collapse'>
            <tr style='background:#444'>
                <th style='padding:8px; text-align:left; border:1px solid #555'>Свойство</th>
                <th style='padding:8px; text-align:left; border:1px solid #555'>Значение</th>
                <th style='padding:8px; text-align:left; border:1px solid #555'>Поле в JSON</th>
            </tr>
            <tr>
                <td style='padding:8px; border:1px solid #555'>🍷</td>
                <td style='padding:8px; border:1px solid #555'>Хрупкий груз</td>
                <td style='padding:8px; border:1px solid #555'><code>fragile: true</code></td>
            </tr>
            <tr>
                <td style='padding:8px; border:1px solid #555'>⬆️</td>
                <td style='padding:8px; border:1px solid #555'>Строго вертикально</td>
                <td style='padding:8px; border:1px solid #555'><code>strict_upright: true</code></td>
            </tr>
            <tr>
                <td style='padding:8px; border:1px solid #555'>🚫</td>
                <td style='padding:8px; border:1px solid #555'>Не ставить сверху</td>
                <td style='padding:8px; border:1px solid #555'><code>stackable: false</code></td>
            </tr>
        </table>
        <div style='margin-top:10px; font-size:0.9em; color:#aaa'>
        📁 Данные: <code>test_data.json</code> (свойства) + <code>result.json</code> (размещение)
        </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.caption(f"📄 Файлы: `{TEST_DATA_FILE}` + `{RESULT_FILE}`")


if __name__ == "__main__":
    main()