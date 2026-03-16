import json
import random
from typing import Dict, Any, List, Optional, Tuple
from copy import deepcopy

# ==============================================================================
# Helper Functions (Copied from original logic to ensure consistency)
# ==============================================================================

def calc_overlap_2d(b1: Dict[str, Any], b2: Dict[str, Any]) -> float:
    """Площадь пересечения проекций на XY."""
    dx = max(0, min(b1["x_max"], b2["x_max"]) - max(b1["x_min"], b2["x_min"]))
    dy = max(0, min(b1["y_max"], b2["y_max"]) - max(b1["y_min"], b2["y_min"]))
    return dx * dy

def check_3d_collision(b1: Dict[str, Any], b2: Dict[str, Any]) -> bool:
    """AABB-коллизия: строгое пересечение по всем осям."""
    ox = max(0, min(b1["x_max"], b2["x_max"]) - max(b1["x_min"], b2["x_min"]))
    oy = max(0, min(b1["y_max"], b2["y_max"]) - max(b1["y_min"], b2["y_min"]))
    oz = max(0, min(b1["z_max"], b2["z_max"]) - max(b1["z_min"], b2["z_min"]))
    return ox > 0 and oy > 0 and oz > 0

# ==============================================================================
# Incremental Environment
# ==============================================================================

class PalletizingEnv:
    def __init__(self, request: Dict[str, Any]):
        """
        Initialize the environment with the task request.
        """
        self.request = request
        self.pallet = request["pallet"]
        self.boxes_meta = {b["sku_id"]: dict(b) for b in request["boxes"]}
        
        # State
        self.placed_boxes: List[Dict[str, Any]] = []
        self.sku_usage: Dict[str, int] = {sku_id: 0 for sku_id in self.boxes_meta}
        self.total_weight_placed = 0.0
        self.fragility_violations = 0
        
        # Constants for scoring
        self.total_requested_items = sum(b["quantity"] for b in request["boxes"])
        self.pallet_vol = (
            self.pallet["length_mm"] * 
            self.pallet["width_mm"] * 
            self.pallet["max_height_mm"]
        )

    def reset(self):
        """Reset the environment to initial state."""
        self.placed_boxes = []
        self.sku_usage = {sku_id: 0 for sku_id in self.boxes_meta}
        self.total_weight_placed = 0.0
        self.fragility_violations = 0

    def get_state(self) -> Dict[str, Any]:
        """Return current environment state."""
        return {
            "placed_count": len(self.placed_boxes),
            "total_weight": self.total_weight_placed,
            "sku_usage": dict(self.sku_usage),
            "current_score": self.calculate_score().get("final_score", 0.0)
        }

    def _create_box_record(self, sku_id: str, pos: Dict[str, float], dims: Dict[str, float]) -> Dict[str, Any]:
        """Internal helper to create the standard box dict used in validation."""
        sku = self.boxes_meta[sku_id]
        x_min = pos["x_mm"]
        y_min = pos["y_mm"]
        z_min = pos["z_mm"]
        x_max = x_min + dims["length_mm"]
        y_max = y_min + dims["width_mm"]
        z_max = z_min + dims["height_mm"]

        return {
            "sku_id": sku_id,
            "weight": sku["weight_kg"],
            "fragile": sku["fragile"],
            "strict_upright": sku["strict_upright"],
            "orig_height": sku["height_mm"],
            "x_min": x_min, "x_max": x_max,
            "y_min": y_min, "y_max": y_max,
            "z_min": z_min, "z_max": z_max,
            "area": dims["length_mm"] * dims["width_mm"],
            "volume": dims["length_mm"] * dims["width_mm"] * dims["height_mm"],
        }

    def place_box(self, sku_id: str, x: float, y: float, z: float, 
                  l: float, w: float, h: float) -> Dict[str, Any]:
        """
        Task 2: Function to place a box at a specific place.
        Validates constraints before adding to state.
        """
        # 1. Basic SKU Validation
        if sku_id not in self.boxes_meta:
            return {"success": False, "error": f"Unknown SKU: {sku_id}"}
        
        sku = self.boxes_meta[sku_id]
        
        # 2. Quantity Check
        if self.sku_usage[sku_id] >= sku["quantity"]:
            return {"success": False, "error": f"Max quantity reached for {sku_id}"}

        # 3. Dimension Cheat Check (Must be permutation of original)
        orig_dims_sorted = sorted([sku["length_mm"], sku["width_mm"], sku["height_mm"]])
        placed_dims_sorted = sorted([l, w, h])
        # Allow small floating point tolerance
        if not all(abs(a - b) < 1e-6 for a, b in zip(orig_dims_sorted, placed_dims_sorted)):
            return {
                "success": False, 
                "error": f"Dimensions mismatch. Orig: {orig_dims_sorted}, Placed: {placed_dims_sorted}"
            }

        # Prepare temporary box object for validation
        pos = {"x_mm": x, "y_mm": y, "z_mm": z}
        dims = {"length_mm": l, "width_mm": w, "height_mm": h}
        new_box = self._create_box_record(sku_id, pos, dims)

        # 4. Hard Constraints Validation
        
        # 4.1 Weight Limit
        if (self.total_weight_placed + sku["weight_kg"]) > self.pallet["max_weight_kg"] + 1e-6:
            return {"success": False, "error": "Pallet overweight"}

        # 4.2 Pallet Bounds
        if (
            new_box["x_min"] < -1e-6 or new_box["y_min"] < -1e-6 or new_box["z_min"] < -1e-6 or
            new_box["x_max"] > self.pallet["length_mm"] + 1e-6 or
            new_box["y_max"] > self.pallet["width_mm"] + 1e-6 or
            new_box["z_max"] > self.pallet["max_height_mm"] + 1e-6
        ):
            return {"success": False, "error": "Box out of pallet bounds"}

        # 4.3 Strict Upright
        if sku["strict_upright"]:
            height_placed = new_box["z_max"] - new_box["z_min"]
            if abs(height_placed - sku["height_mm"]) > 1e-6:
                return {"success": False, "error": "Strict upright violation"}

        # 4.4 Collisions (Check against all existing)
        for existing in self.placed_boxes:
            if check_3d_collision(new_box, existing):
                return {"success": False, "error": f"Collision with {existing['sku_id']}"}

        # 4.5 Gravity Support (60% rule)
        if new_box["z_min"] > 1e-6:  # Not on ground
            support_area = 0.0
            for existing in self.placed_boxes:
                # Check if existing box top is at new box bottom
                if abs(existing["z_max"] - new_box["z_min"]) < 1e-6:
                    support_area += calc_overlap_2d(new_box, existing)
            
            if new_box["area"] == 0 or support_area / new_box["area"] < 0.6:
                return {
                    "success": False, 
                    "error": f"Insufficient support ({support_area:.1f}/{new_box['area']:.1f})"
                }

        # 4.6 Fragility (Check interaction with existing boxes)
        # We need to check if this new box violates fragility rules with existing ones
        # Case A: New box is ON TOP of existing fragile box (and New is heavy)
        # Case B: Existing box is ON TOP of new fragile box (and Existing is heavy)
        # Note: In incremental build, Case B is unlikely if building bottom-up, 
        # but we check to ensure score consistency with batch evaluator.
        
        temp_placements = self.placed_boxes + [new_box]
        new_violations = 0
        
        # Check New vs Existing
        for existing in self.placed_boxes:
            # Check if New is on Top of Existing
            if abs(existing["z_max"] - new_box["z_min"]) < 1e-6 and calc_overlap_2d(new_box, existing) > 0:
                if new_box["weight"] > 2.0 and existing["fragile"]:
                    new_violations += 1
            # Check if Existing is on Top of New
            if abs(new_box["z_max"] - existing["z_min"]) < 1e-6 and calc_overlap_2d(existing, new_box) > 0:
                if existing["weight"] > 2.0 and new_box["fragile"]:
                    new_violations += 1
        
        # If adding this box increases violations, we might want to warn or block.
        # The original evaluator counts total violations. 
        # To be strict, we could block, but usually, we allow placement and penalize score.
        # Here we allow placement but track the violation for scoring.
        
        # --- COMMIT PLACEMENT ---
        self.placed_boxes.append(new_box)
        self.sku_usage[sku_id] += 1
        self.total_weight_placed += sku["weight_kg"]
        self.fragility_violations += new_violations

        return {
            "success": True, 
            "message": "Box placed successfully",
            "current_score": self.calculate_score()["final_score"]
        }

    def calculate_score(self, time_ms: int = 1000) -> Dict[str, Any]:
        """
        Task 1: Calculate the score incrementally using the same logic as evaluate_solution.
        """
        # 1. Volume Utilization
        vol_util = sum(b["volume"] for b in self.placed_boxes) / self.pallet_vol if self.pallet_vol > 0 else 0.0

        # 2. Item Coverage
        placed_items = len(self.placed_boxes)
        item_coverage = placed_items / self.total_requested_items if self.total_requested_items > 0 else 0.0

        # 3. Fragility Score
        # We track violations incrementally, but to be 100% safe against drift, 
        # we can recalculate from scratch on the current list (O(N^2) but accurate)
        # For performance in incremental, we used self.fragility_violations above.
        # Let's recalculate to ensure exact match with original function logic.
        calc_violations = 0
        for top in self.placed_boxes:
            if top["weight"] <= 2.0:
                continue
            for bottom in self.placed_boxes:
                if not bottom["fragile"]:
                    continue
                if abs(top["z_min"] - bottom["z_max"]) < 1e-6 and calc_overlap_2d(top, bottom) > 0:
                    calc_violations += 1
        
        fragility_score = max(0.0, 1.0 - 0.05 * calc_violations)

        # 4. Time Score
        if time_ms <= 1000:
            time_score = 1.0
        elif time_ms <= 5000:
            time_score = 0.7
        elif time_ms <= 30000:
            time_score = 0.3
        else:
            time_score = 0.0

        # 5. Final Weighted Score
        final_score = (
            0.50 * vol_util +
            0.30 * item_coverage +
            0.10 * fragility_score +
            0.10 * time_score
        )

        return {
            "valid": True, # Assuming we only place valid boxes in Env
            "metrics": {
                "volume_utilization": round(vol_util, 4),
                "item_coverage": round(item_coverage, 4),
                "fragility_score": round(fragility_score, 4),
                "time_score": round(time_score, 4),
            },
            "final_score": round(final_score, 4),
        }

# ==============================================================================
# Example Usage
# ==============================================================================

if __name__ == "__main__":
    # 1. Mock Request Data (Matching your original structure)
    mock_request = {
        "pallet": {
            "id": "P-001",
            "length_mm": 1200,
            "width_mm": 1000,
            "max_height_mm": 1500,
            "max_weight_kg": 1000.0
        },
        "boxes": [
            {
                "sku_id": "SKU-A-1234",
                "length_mm": 400,
                "width_mm": 300,
                "height_mm": 200,
                "weight_kg": 5.0,
                "quantity": 10,
                "strict_upright": False,
                "fragile": False
            },
            {
                "sku_id": "SKU-B-5678",
                "length_mm": 400,
                "width_mm": 300,
                "height_mm": 200,
                "weight_kg": 10.0, # Heavy
                "quantity": 5,
                "strict_upright": True,
                "fragile": True # Fragile
            }
        ]
    }

    # 2. Initialize Environment
    env = PalletizingEnv(mock_request)
    env.reset()

    print("--- Starting Incremental Palletizing ---")

    # 3. Place Box 1 (Ground level, valid)
    res1 = env.place_box(
        sku_id="SKU-A-1234", 
        x=0, y=0, z=0, 
        l=400, w=300, h=200
    )
    print(f"Step 1: {res1['message']} | Score: {res1.get('current_score', 0)}")

    # 4. Place Box 2 (On top of Box 1, valid support)
    res2 = env.place_box(
        sku_id="SKU-A-1234", 
        x=0, y=0, z=200, 
        l=400, w=300, h=200
    )
    print(f"Step 2: {res2['message']} | Score: {res2.get('current_score', 0)}")

    # 5. Place Box 3 (Heavy on Fragile - Should trigger fragility penalty in score)
    # Note: In this mock, SKU-B is fragile AND heavy. 
    # If we put it on ground, it's fine. If we put something heavy on IT, it's violation.
    # Let's place SKU-B on ground.
    res3 = env.place_box(
        sku_id="SKU-B-5678", 
        x=400, y=0, z=0, 
        l=400, w=300, h=200
    )
    print(f"Step 3: {res3['message']} | Score: {res3.get('current_score', 0)}")

    # 6. Try Invalid Placement (Out of bounds)
    res4 = env.place_box(
        sku_id="SKU-A-1234", 
        x=2000, y=0, z=0, 
        l=400, w=300, h=200
    )
    print(f"Step 4 (Invalid): {res4['error']}")

    # 7. Get Final Detailed Metrics
    final_metrics = env.calculate_score()
    print("\n--- Final Metrics ---")
    print(json.dumps(final_metrics, indent=2))