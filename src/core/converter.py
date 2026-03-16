from typing import Dict, Any, List
from datetime import datetime
from palletizing_env import PalletizingEnv

def transform_env_to_output(
    env: PalletizingEnv,
    task_id: str = "task_001",
    solver_version: str = "1.2.3",
    solve_time_ms: int = 0
) -> Dict[str, Any]:
    """
    Convert PalletizingEnv state to standardized output format.
    
    Args:
        env: The environment with placed boxes
        task_id: Task identifier
        solver_version: Version string
        solve_time_ms: Time taken to solve in milliseconds
    
    Returns:
        Dict in the required output format
    """
    placements = []
    instance_index = 0
    
    # Track SKU instance counts for instance_index
    sku_instance_counts: Dict[str, int] = {}
    
    # Iterate through all pallets and their placed boxes
    for pallet_idx, pallet in enumerate(env.pallets):
        for box in pallet["placed_boxes"]:
            sku_id = box["sku_id"]
            
            # Get instance index for this SKU
            if sku_id not in sku_instance_counts:
                sku_instance_counts[sku_id] = 0
            instance_idx_for_sku = sku_instance_counts[sku_id]
            sku_instance_counts[sku_id] += 1
            
            # Calculate placed dimensions
            length_placed = box["x_max"] - box["x_min"]
            width_placed = box["y_max"] - box["y_min"]
            height_placed = box["z_max"] - box["z_min"]
            
            # Determine rotation code
            rotation_code = _get_rotation_code(box, env.boxes_meta[sku_id])
            
            placements.append({
                "sku_id": sku_id,
                "instance_index": instance_index,
                "pallet_index": pallet_idx,  # Optional: which pallet
                "position": {
                    "x_mm": box["x_min"],
                    "y_mm": box["y_min"],
                    "z_mm": box["z_min"]
                },
                "dimensions_placed": {
                    "length_mm": length_placed,
                    "width_mm": width_placed,
                    "height_mm": height_placed
                },
                "rotation_code": rotation_code
            })
            
            instance_index += 1
    
    # Build unplaced list from denial tracking
    unplaced = []
    if hasattr(env, 'denied_boxes') and env.denied_boxes:
        # Group denials by SKU
        unplaced_by_sku: Dict[str, Dict[str, Any]] = {}
        for denial in env.denied_boxes:
            sku_id = denial["sku_id"]
            if sku_id not in unplaced_by_sku:
                unplaced_by_sku[sku_id] = {
                    "sku_id": sku_id,
                    "quantity_unplaced": 0,
                    "reasons": []
                }
            unplaced_by_sku[sku_id]["quantity_unplaced"] += 1
            if denial["reason"] not in unplaced_by_sku[sku_id]["reasons"]:
                unplaced_by_sku[sku_id]["reasons"].append(denial["reason"])
        
        # Convert to output format
        for sku_id, info in unplaced_by_sku.items():
            # Use most common reason
            primary_reason = info["reasons"][0] if info["reasons"] else "unknown"
            unplaced.append({
                "sku_id": sku_id,
                "quantity_unplaced": info["quantity_unplaced"],
                "reason": primary_reason
            })
    
    # Calculate stats
    total_boxes = len(placements) + sum(u["quantity_unplaced"] for u in unplaced)
    
    output = {
        "task_id": task_id,
        "solver_version": solver_version,
        "solve_time_ms": solve_time_ms,
        "placements": placements,
        "unplaced": unplaced,
        "stats": {
            "total_boxes": total_boxes,
            "placed": len(placements),
            "unplaced": sum(u["quantity_unplaced"] for u in unplaced)
        }
    }
    
    return output


def _get_rotation_code(placed_box: Dict[str, Any], original_box: Dict[str, Any]) -> str:
    """
    Determine rotation code based on how box was oriented.
    
    Rotation codes:
    - LWH: Length along X, Width along Y, Height along Z (no rotation)
    - LHW: Length along X, Height along Y, Width along Z
    - WLH: Width along X, Length along Y, Height along Z
    - WHL: Width along X, Height along Y, Length along Z
    - HLW: Height along X, Length along Y, Width along Z
    - HWL: Height along X, Width along Y, Length along Z
    """
    # Get placed dimensions
    placed_l = placed_box["x_max"] - placed_box["x_min"]
    placed_w = placed_box["y_max"] - placed_box["y_min"]
    placed_h = placed_box["z_max"] - placed_box["z_min"]
    
    # Get original dimensions
    orig_l = original_box["length_mm"]
    orig_w = original_box["width_mm"]
    orig_h = original_box["height_mm"]
    
    # Create tolerance for floating point comparison
    tol = 1.0  # 1mm tolerance
    
    # Determine which original dimension maps to which axis
    x_dim = None
    y_dim = None
    z_dim = None
    
    # Check X axis
    if abs(placed_l - orig_l) < tol:
        x_dim = 'L'
    elif abs(placed_l - orig_w) < tol:
        x_dim = 'W'
    elif abs(placed_l - orig_h) < tol:
        x_dim = 'H'
    
    # Check Y axis
    if abs(placed_w - orig_l) < tol:
        y_dim = 'L'
    elif abs(placed_w - orig_w) < tol:
        y_dim = 'W'
    elif abs(placed_w - orig_h) < tol:
        y_dim = 'H'
    
    # Check Z axis
    if abs(placed_h - orig_l) < tol:
        z_dim = 'L'
    elif abs(placed_h - orig_w) < tol:
        z_dim = 'W'
    elif abs(placed_h - orig_h) < tol:
        z_dim = 'H'
    
    # Build rotation code
    if x_dim and y_dim and z_dim:
        return f"{x_dim}{y_dim}{z_dim}"
    else:
        return "LWH"  # Default


def save_output_to_json(output: Dict[str, Any], filepath: str):
    """
    Save output dict to JSON file.
    """
    import json
    from pathlib import Path
    
    # Ensure directory exists
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Output saved to: {filepath}")


def load_output_from_json(filepath: str) -> Dict[str, Any]:
    """
    Load output dict from JSON file.
    """
    import json
    
    with open(filepath, 'r') as f:
        return json.load(f)