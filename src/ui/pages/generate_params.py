import streamlit as st
import json
import os
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import traceback

# ==========================================
# 1. НАСТРОЙКА ПУТЕЙ И ИМПОРТ
# ==========================================

src_dir = Path(__file__).parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    from generator.data_gen import (
        PalletScenarioGenerator, 
        GenerationConfig, 
        ComplexityLevel, 
        FOOD_RETAIL_ARCHETYPES, 
        PALLETS,
        save_scenario
    )
except ImportError as e:
    st.error(f"❌ Ошибка импорта: {e}")
    st.stop()

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, 'x'.join(map(str, v)) if all(isinstance(i, int) for i in v) else v))
        else:
            items.append((new_key, v))
    return dict(items)

def load_request_json(filepath: Path) -> Optional[dict]:
    if not filepath.exists():
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

# ==========================================
# 3. STREAMLIT UI
# ==========================================

st.set_page_config(page_title="Генератор Паллет", layout="wide")
st.title("📦 Генератор сценариев размещения")

# --- Session State ---
if 'config' not in st.session_state:
    cfg = GenerationConfig()
    cfg.apply_complexity_profile()
    st.session_state.config = cfg

if 'preset_mode' not in st.session_state:
    st.session_state.preset_mode = "Medium"

# --- Пресеты ---
def apply_preset(preset_name):
    cfg = GenerationConfig()
    cfg.complexity = ComplexityLevel[preset_name.upper()]
    cfg.apply_complexity_profile()
    st.session_state.config = cfg
    st.session_state.preset_mode = preset_name

# --- Sidebar ---
with st.sidebar:
    st.header("🎛 Профиль сложности")
    preset_options = ["Easy", "Medium", "Hard", "Chaos", "Custom"]
    current_idx = preset_options.index(st.session_state.preset_mode.capitalize()) if st.session_state.preset_mode.capitalize() in preset_options else 4
    selected = st.selectbox("Пресет", options=preset_options, index=current_idx)
    
    if selected != "Custom" and selected.lower() != st.session_state.preset_mode.lower():
        apply_preset(selected)
        st.rerun()
    else:
        st.session_state.preset_mode = "Custom"
    
    st.divider()
    st.session_state.config.seed = st.number_input("Seed", value=st.session_state.config.seed)
    task_id = st.text_input("ID задачи", value=f"task_{datetime.now().strftime('%H%M%S')}")

# --- Параметры ---
st.subheader("Параметры")
cfg = st.session_state.config
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 📦 Паллеты")
    c1, c2 = st.columns(2)
    cfg.pallet_count_min = c1.number_input("Мин", 1, 100, cfg.pallet_count_min, key="p_min")
    cfg.pallet_count_max = c2.number_input("Макс", 1, 100, cfg.pallet_count_max, key="p_max")
    cfg.pallet_type_ids = st.multiselect("Типы", [p["id"] for p in PALLETS], default=cfg.pallet_type_ids or [p["id"] for p in PALLETS])

with col2:
    st.markdown("#### 🧱 SKU")
    c1, c2 = st.columns(2)
    cfg.sku_count_min = c1.number_input("Мин", 1, 50, cfg.sku_count_min, key="s_min")
    cfg.sku_count_max = c2.number_input("Макс", 1, 50, cfg.sku_count_max, key="s_max")
    c3, c4 = st.columns(2)
    cfg.quantity_per_sku_min = c3.number_input("Кол-во Мин", 1, 500, cfg.quantity_per_sku_min, key="q_min")
    cfg.quantity_per_sku_max = c4.number_input("Кол-во Макс", 1, 500, cfg.quantity_per_sku_max, key="q_max")

with col3:
    st.markdown("#### 🎲 Параметры")
    cfg.dimension_noise_ratio = st.slider("Шум размеров", 0.0, 0.5, cfg.dimension_noise_ratio, format="%.2f")
    cfg.weight_noise_ratio = st.slider("Шум веса", 0.0, 0.5, cfg.weight_noise_ratio, format="%.2f")
    cfg.force_fragile_ratio = st.slider("Хрупкость", 0.0, 1.0, cfg.force_fragile_ratio, format="%.2f")
    cfg.force_upright_ratio = st.slider("Вертикально", 0.0, 1.0, cfg.force_upright_ratio, format="%.2f")
    cfg.enable_load_bearing = st.checkbox("Несущая способность", value=cfg.enable_load_bearing)

st.divider()
st.subheader("Архетипы")
archetype_keys = list(FOOD_RETAIL_ARCHETYPES.keys())
c1, c2 = st.columns(2)
cfg.include_archetypes = c1.multiselect("Включить", archetype_keys, default=cfg.include_archetypes or [])
cfg.exclude_archetypes = c2.multiselect("Исключить", archetype_keys, default=cfg.exclude_archetypes or [])

# ==========================================
# 4. КНОПКА ГЕНЕРАЦИИ
# ==========================================

st.divider()
if st.button("🚀 Сгенерировать", type="primary", use_container_width=True):
    # Создаём директорию
    data_dir = src_dir / "generator" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Запускаем генератор
    generator = PalletScenarioGenerator(cfg)
    scenario = generator.generate(task_id)
    
    # Сохраняем в request.json
    request_path = data_dir / "request.json"
    with open(request_path, 'w', encoding='utf-8') as f:
        json.dump(scenario, f, indent=2, ensure_ascii=False)
    
    # Сразу показываем результаты
    st.session_state.last_request_path = str(request_path)
    st.session_state.last_data = scenario
    st.rerun()

# ==========================================
# 5. ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ
# ==========================================

if st.session_state.get('last_data'):
    data = st.session_state.last_data
    
    st.divider()
    st.header("📊 Результаты")
    
    info = data.get('shipment_info', {})
    m1, m2, m3 = st.columns(3)
    m1.metric("Паллет", info.get('total_pallets', 0))
    m2.metric("SKU типов", info.get('total_sku_types', 0))
    m3.metric("Коробок всего", info.get('total_boxes_estimated', 0))
    
    tabs = st.tabs(["📦 Паллеты", "🧱 Коробки", "📄 JSON"])
    
    with tabs[0]:
        pallets = data.get('pallets', [])
        if pallets:
            df = pd.DataFrame([flatten_dict(p) for p in pallets])
            df.columns = [c.replace('_', ' ').title() for c in df.columns]
            st.dataframe(df, use_container_width=True, hide_index=True)
    
    with tabs[1]:
        boxes = data.get('boxes', [])
        if boxes:
            df = pd.DataFrame([flatten_dict(b) for b in boxes])
            df.columns = [c.replace('_', ' ').title() for c in df.columns]
            st.dataframe(df, use_container_width=True, hide_index=True)
    
    with tabs[2]:
        st.json(data)
    
    # Кнопка скачивания
    st.divider()
    with open(st.session_state.last_request_path, 'r', encoding='utf-8') as f:
        content = f.read()
    st.download_button("💾 Скачать request.json", content, file_name="request.json", mime="application/json")
    
    # Кнопка перехода к визуализации
    st.divider()
    if st.button("👁️ Показать 3D размещение", type="secondary", use_container_width=True):
        st.switch_page("pages/visualization.py")