from typing import Dict, Any, List, Tuple

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

class PalletizingEnv:
    def __init__(self, request: Dict[str, Any]):
        self.request = request
        self.boxes_meta = {}
        for b in request["boxes"]:
            sku_id = b["sku_id"]
            d1, d2, d3 = b["dimensions_mm"]

            self.boxes_meta[sku_id] = {
                "sku_id": sku_id,
                "description": b.get("description", ""),
                "length_mm": d1,
                "width_mm": d2,
                "height_mm": d3,
                "weight_kg": b["weight_kg"],
                "quantity": b["quantity"],
                "strict_upright": b["strict_upright"],
                "fragile": b["fragile"],
                "stackable": b.get("stackable", True),
                "load_bearing_kg": b.get("load_bearing_kg", 0),
                "max_stack_layers": b.get("max_stack_layers", 1)
            }
        if "pallets" in request:
            self.pallets: List[Dict[str, Any]] = []
            for i, pallet_spec in enumerate(request["pallets"]):
                d1, d2 = pallet_spec["dimensions_mm"]
                self.pallets.append({
                    "id": pallet_spec.get("pallet_index", f"P-{i:03d}"),
                    "length_mm": d1,
                    "width_mm": d2,
                    "max_height_mm": pallet_spec["max_height_mm"],
                    "max_weight_kg": pallet_spec["max_weight_kg"],
                    "placed_boxes": [],
                    "total_weight": 0.0,
                    "fragility_violations": 0
                })
        else:
            pallet_spec = request["pallets"]
            d1, d2 = pallet_spec["dimensions_mm"]
            self.pallets = [{
                "id": pallet_spec.get("id", "P-000"),
                "length_mm": d1,
                "width_mm": d2,
                "max_height_mm": pallet_spec["max_height_mm"],
                "max_weight_kg": pallet_spec["max_weight_kg"],
                "placed_boxes": [],
                "total_weight": 0.0,
                "fragility_violations": 0
            }]
        
        self.num_pallets = len(self.pallets)
        self.sku_usage: Dict[str, int] = {sku_id: 0 for sku_id in self.boxes_meta}
        self.action_history: List[Dict[str, Any]] = []
        
        self.total_requested_items = sum(b["quantity"] for b in request["boxes"])
        self.total_pallet_vol = sum(
            p["length_mm"] * p["width_mm"] * p["max_height_mm"] 
            for p in self.pallets
        )
        
        self.denied_boxes: List[Dict[str, Any]] = []

    def reset(self):
        for pallet in self.pallets:
            pallet["placed_boxes"] = []
            pallet["total_weight"] = 0.0
            pallet["fragility_violations"] = 0
        self.sku_usage = {sku_id: 0 for sku_id in self.boxes_meta}
        self.action_history = []
        self.denied_boxes = []  # Clear denial history on reset
        
    def record_denial(self, sku_id: str, reason: str, 
                  attempted_pallets: List[int],
                  attempted_orientations: List[Tuple]):
        """
        Record a box that could not be placed.
        """
        self.denied_boxes.append({
                "sku_id": sku_id,
                "reason": reason,
                "attempted_pallets": attempted_pallets or [],
                "attempted_orientations": attempted_orientations or [],
                "timestamp": len(self.action_history)  # Placement attempt number
            })
    
    def get_denial_summary(self) -> Dict[str, Any]:
        """
        Get summary of all denied boxes.
        """
        if not self.denied_boxes:
            return {
                "total_denied": 0,
                "by_reason": {},
                "by_sku": {}
            }
        
        # Count by reason
        by_reason = {}
        for d in self.denied_boxes:
            reason = d["reason"]
            by_reason[reason] = by_reason.get(reason, 0) + 1
        
        # Count by SKU
        by_sku = {}
        for d in self.denied_boxes:
            sku = d["sku_id"]
            if sku not in by_sku:
                by_sku[sku] = {"count": 0, "reasons": []}
            by_sku[sku]["count"] += 1
            if d["reason"] not in by_sku[sku]["reasons"]:
                by_sku[sku]["reasons"].append(d["reason"])
        
        return {
            "total_denied": len(self.denied_boxes),
            "by_reason": by_reason,
            "by_sku": by_sku,
            "details": self.denied_boxes
        }

    def get_env_state(self) -> Dict[str, Any]:
        """
        Get current environment state for state machine evaluation.
        This is what transition conditions check against.
        """
        total_placed = sum(len(p["placed_boxes"]) for p in self.pallets)
        total_weight = sum(p["total_weight"] for p in self.pallets)
        total_vol_used = sum(sum(b["volume"] for b in p["placed_boxes"]) for p in self.pallets)
        
        # Count remaining boxes by type
        fragile_remaining = 0
        heavy_remaining = 0
        for sku_id, sku in self.boxes_meta.items():
            remaining = sku["quantity"] - self.sku_usage[sku_id]
            if sku["fragile"]:
                fragile_remaining += remaining
            if sku["weight_kg"] > 2.0:
                heavy_remaining += remaining
        
        # Pallet metrics (use first pallet for simplicity, or average)
        pallet_fill_ratio = 0.0
        weight_ratio = 0.0
        height_ratio = 0.0
        if self.pallets:
            p = self.pallets[0]
            pallet_fill_ratio = total_vol_used / self.total_pallet_vol if self.total_pallet_vol > 0 else 0
            weight_ratio = total_weight / p["max_weight_kg"] if p["max_weight_kg"] > 0 else 0
            max_height_used = max((b["z_max"] for b in p["placed_boxes"]), default=0)
            height_ratio = max_height_used / p["max_height_mm"] if p["max_height_mm"] > 0 else 0
        
        return {
            "pallet_fill_ratio": pallet_fill_ratio,
            "weight_ratio": weight_ratio,
            "height_ratio": height_ratio,
            "boxes_remaining": self.total_requested_items - total_placed,
            "fragile_remaining": fragile_remaining,
            "heavy_remaining": heavy_remaining,
            "total_placed": total_placed,
            "total_weight": total_weight,
            "current_pallet_idx": 0  # Could track active pallet
        }

    def get_pallet_specs(self) -> List[Dict[str, Any]]:
        return [
            {
                "pallet_idx": i,
                "id": p["id"],
                "length_mm": p["length_mm"],
                "width_mm": p["width_mm"],
                "max_height_mm": p["max_height_mm"],
                "max_weight_kg": p["max_weight_kg"],
                "remaining_volume": p["length_mm"] * p["width_mm"] * p["max_height_mm"] - 
                                   sum(b["volume"] for b in p["placed_boxes"]),
                "remaining_height": p["max_height_mm"] - (
                    max((b["z_max"] for b in p["placed_boxes"]), default=0)
                ),
                "weight_remaining": p["max_weight_kg"] - p["total_weight"]
            }
            for i, p in enumerate(self.pallets)
        ]

    def _create_box_record(self, sku_id: str, pos: Dict[str, float], 
                           dims: Dict[str, float]) -> Dict[str, Any]:
        sku = self.boxes_meta[sku_id]
        x_min, y_min, z_min = pos["x_mm"], pos["y_mm"], pos["z_mm"]
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
                  l: float, w: float, h: float, 
                  pallet_idx: int = 0) -> Dict[str, Any]:
        if pallet_idx < 0 or pallet_idx >= self.num_pallets:
            return {"success": False, "error": f"Invalid pallet index: {pallet_idx}"}
        
        pallet = self.pallets[pallet_idx]
        
        if sku_id not in self.boxes_meta:
            return {"success": False, "error": f"Unknown SKU: {sku_id}"}
        
        sku = self.boxes_meta[sku_id]
        
        if self.sku_usage[sku_id] >= sku["quantity"]:
            return {"success": False, "error": f"Max quantity reached for {sku_id}"}


        orig_dims_sorted = sorted([sku["length_mm"], sku["width_mm"], sku["height_mm"]])
        placed_dims_sorted = sorted([l, w, h])
        if not all(abs(a - b) < 1e-6 for a, b in zip(orig_dims_sorted, placed_dims_sorted)):
            return {"success": False, "error": "Dimensions mismatch"}

        pos = {"x_mm": x, "y_mm": y, "z_mm": z}
        dims = {"length_mm": l, "width_mm": w, "height_mm": h}
        new_box = self._create_box_record(sku_id, pos, dims)

        if (pallet["total_weight"] + sku["weight_kg"]) > pallet["max_weight_kg"] + 1e-6:
            return {"success": False, "error": f"Pallet {pallet_idx} overweight"}

        if (
            new_box["x_min"] < -1e-6 or new_box["y_min"] < -1e-6 or new_box["z_min"] < -1e-6 or
            new_box["x_max"] > pallet["length_mm"] + 1e-6 or
            new_box["y_max"] > pallet["width_mm"] + 1e-6 or
            new_box["z_max"] > pallet["max_height_mm"] + 1e-6
        ):
            return {"success": False, "error": f"Box out of pallet {pallet_idx} bounds"}

        if sku["strict_upright"]:
            height_placed = new_box["z_max"] - new_box["z_min"]
            if abs(height_placed - sku["height_mm"]) > 1e-6:
                return {"success": False, "error": "Strict upright violation"}

        for existing in pallet["placed_boxes"]:
            if check_3d_collision(new_box, existing):
                return {"success": False, "error": f"Collision with {existing['sku_id']}"}

        if new_box["z_min"] > 1e-6:
            support_area = 0.0
            for existing in pallet["placed_boxes"]:
                if abs(existing["z_max"] - new_box["z_min"]) < 1e-6:
                    support_area += calc_overlap_2d(new_box, existing)
            
            if new_box["area"] == 0 or support_area / new_box["area"] < 0.6:
                return {"success": False, "error": "Insufficient support"}

        new_violations = 0
        for existing in pallet["placed_boxes"]:
            if abs(existing["z_max"] - new_box["z_min"]) < 1e-6 and calc_overlap_2d(new_box, existing) > 0:
                if new_box["weight"] > 2.0 and existing["fragile"]:
                    new_violations += 1
            if abs(new_box["z_max"] - existing["z_min"]) < 1e-6 and calc_overlap_2d(existing, new_box) > 0:
                if existing["weight"] > 2.0 and new_box["fragile"]:
                    new_violations += 1

        pallet["placed_boxes"].append(new_box)
        pallet["total_weight"] += sku["weight_kg"]
        pallet["fragility_violations"] += new_violations
        self.sku_usage[sku_id] += 1
        
        self.action_history.append({
            "pallet_idx": pallet_idx,
            "sku_id": sku_id,
            "weight": sku["weight_kg"],
            "violations": new_violations
        })

        return {"success": True, "pallet_idx": pallet_idx}

    def undo_last_placement(self) -> Dict[str, Any]:
        if not self.action_history:
            return {"success": False, "error": "No actions to undo"}
        
        last_action = self.action_history.pop()
        pallet_idx = last_action["pallet_idx"]
        pallet = self.pallets[pallet_idx]
        
        if pallet["placed_boxes"]:
            pallet["placed_boxes"].pop()
        else:
            return {"success": False, "error": "Pallet box list inconsistent"}
        
        pallet["total_weight"] -= last_action["weight"]
        pallet["fragility_violations"] -= last_action["violations"]
        self.sku_usage[last_action["sku_id"]] -= 1
        
        return {"success": True, "current_score": self.calculate_score()["final_score"]}

    def undo_multiple(self, count: int) -> Dict[str, Any]:
        undone = 0
        for _ in range(min(count, len(self.action_history))):
            result = self.undo_last_placement()
            if result["success"]:
                undone += 1
            else:
                break
        
        return {"success": undone > 0, "undone_count": undone, "current_score": self.calculate_score()["final_score"]}

    def calculate_score(self, time_ms: int = 0) -> Dict[str, Any]:
        """
        Calculate score across ALL pallets.
        Volume utilization only counts USED pallets to encourage better packing.
        """
        # ===== 1. VOLUME UTILIZATION (Used Pallets Only) =====
        total_vol_used = sum(
            sum(b["volume"] for b in p["placed_boxes"])
            for p in self.pallets
        )
        
        # Count only pallets that have at least one box
        used_pallets = [p for p in self.pallets if len(p["placed_boxes"]) > 0]
        num_used_pallets = len(used_pallets)
        
        # Volume of only used pallets (not all available pallets)
        used_pallet_vol = sum(
            p["length_mm"] * p["width_mm"] * p["max_height_mm"]
            for p in used_pallets
        ) if used_pallets else 0
        
        # Volume utilization based on used pallets only
        vol_util = total_vol_used / used_pallet_vol if used_pallet_vol > 0 else 0.0
        
        # Penalty for using more pallets than necessary
        total_pallets = len(self.pallets)
        pallet_efficiency_penalty = 0.0
        if num_used_pallets > 0:
            # Penalty increases with more pallets used
            pallet_efficiency_penalty = 0.05 * (num_used_pallets - 1) / max(1, total_pallets - 1)
    
        # ===== 2. ITEM COVERAGE =====
        placed_items = sum(len(p["placed_boxes"]) for p in self.pallets)
        item_coverage = placed_items / self.total_requested_items if self.total_requested_items > 0 else 0.0
        
        # Penalty for unplaced items
        unplaced_penalty = 0.0
        if self.total_requested_items > 0:
            unplaced_ratio = (self.total_requested_items - placed_items) / self.total_requested_items
            unplaced_penalty = 0.1 * unplaced_ratio  # Up to 0.1 penalty
    
        # ===== 3. FRAGILITY SCORE =====
        total_violations = 0
        for pallet in self.pallets:
            for top in pallet["placed_boxes"]:
                if top["weight"] <= 2.0:
                    continue
                for bottom in pallet["placed_boxes"]:
                    if not bottom["fragile"]:
                        continue
                    if abs(top["z_min"] - bottom["z_max"]) < 1e-6 and calc_overlap_2d(top, bottom) > 0:
                        total_violations += 1
        
        fragility_score = max(0.0, 1.0 - 0.05 * total_violations)
        
        # Additional fragility penalty (per violation)
        fragility_penalty = 0.02 * total_violations
    
        # ===== 4. WEIGHT DISTRIBUTION SCORE (NEW) =====
        # Penalize uneven weight distribution across pallets
        weight_distribution_score = 1.0
        if num_used_pallets > 1:
            weights = [p["total_weight"] / p["max_weight_kg"] if p["max_weight_kg"] > 0 else 0 
                       for p in used_pallets]
            weight_variance = sum((w - sum(weights)/len(weights))**2 for w in weights) / len(weights)
            weight_distribution_score = max(0.0, 1.0 - weight_variance)
    
        # ===== 5. SPACE EFFICIENCY SCORE (NEW) =====
        # Penalize large empty gaps within used pallets
        space_efficiency_score = 1.0
        for pallet in used_pallets:
            pallet_vol = pallet["length_mm"] * pallet["width_mm"] * pallet["max_height_mm"]
            if pallet_vol > 0:
                fill_ratio = sum(b["volume"] for b in pallet["placed_boxes"]) / pallet_vol
                # Penalty for partially filled pallets
                if fill_ratio < 0.5:
                    space_efficiency_score -= 0.05 * (0.5 - fill_ratio)
        space_efficiency_score = max(0.0, space_efficiency_score)
    
        # ===== 6. TIME SCORE =====
        if time_ms <= 1000:
            time_score = 1.0
        elif time_ms <= 5000:
            time_score = 0.7
        elif time_ms <= 30000:
            time_score = 0.3
        else:
            time_score = 0.0
    
        # ===== 7. FINAL WEIGHTED SCORE WITH PENALTIES =====
        base_score = (
            0.5 * vol_util +                    
            0.3 * item_coverage +               
            0.05 * fragility_score +
            0.05 * weight_distribution_score +   
            0.01 * space_efficiency_score +      
            0.1 * time_score
        )
        
        # Apply penalties
        total_penalties = pallet_efficiency_penalty + unplaced_penalty + fragility_penalty
        
        final_score = max(0.0, base_score - total_penalties)
            
        return {
            "valid": True,
            "metrics": {
                "volume_utilization": round(vol_util, 4),
                "item_coverage": round(item_coverage, 4),
                "fragility_score": round(fragility_score, 4),
                "time_score": round(time_score, 4),
                "weight_distribution_score": round(weight_distribution_score, 4),
                "space_efficiency_score": round(space_efficiency_score, 4),
                "total_boxes_placed": placed_items,
                "total_violations": total_violations,
                "num_pallets_used": num_used_pallets,
                "total_pallets_available": total_pallets,
                "pallet_efficiency_penalty": round(pallet_efficiency_penalty, 4),
                "unplaced_penalty": round(unplaced_penalty, 4),
                "fragility_penalty": round(fragility_penalty, 4),
                "total_penalties": round(total_penalties, 4)
            },
            "final_score": round(final_score, 4),
            "base_score": round(base_score, 4),
        }

    def get_pallet_summary(self) -> List[Dict[str, Any]]:
        return [
            {
                "pallet_id": p["id"],
                "length_mm": p["length_mm"],
                "width_mm": p["width_mm"],
                "max_height_mm": p["max_height_mm"],
                "boxes_count": len(p["placed_boxes"]),
                "total_weight": p["total_weight"],
                "max_weight": p["max_weight_kg"],
                "weight_utilization": p["total_weight"] / p["max_weight_kg"] if p["max_weight_kg"] > 0 else 0,
                "fragility_violations": p["fragility_violations"]
            }
            for p in self.pallets
        ]