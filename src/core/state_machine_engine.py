import random
from typing import Dict, Any, List, Optional, Tuple
from palletizing_env import PalletizingEnv
from state_machine_gene import StateMachineGenome, StateRule


class StateMachineEngine:
    """
    Executes placement using state machine genome.
    State transitions based on environment conditions.
    Places ALL boxes by quantity.
    """
    
    def __init__(self, env: PalletizingEnv, genome: StateMachineGenome):
        self.env = env
        self.genome = genome
        self.boxes_meta = env.boxes_meta
        self.current_state = genome.start_state
        self.boxes_placed_in_state = 0
        self.attempted_skus: Dict[str, int] = {}
    
    def _get_box_queue(self, state_rule: StateRule) -> List[Dict[str, Any]]:
        """Create ordered queue of ALL boxes to place, filtered by state."""
        queue = []
        for sku_id, sku in self.boxes_meta.items():
            for _ in range(sku["quantity"]):
                box = {
                    "sku_id": sku_id,
                    "weight": sku["weight_kg"],
                    "fragile": sku["fragile"],
                    "strict_upright": sku["strict_upright"],
                    "length_mm": sku["length_mm"],
                    "width_mm": sku["width_mm"],
                    "height_mm": sku["height_mm"],
                    "volume": sku["length_mm"] * sku["width_mm"] * sku["height_mm"],
                    "area": sku["length_mm"] * sku["width_mm"]
                }
                
                # Apply state filter
                if state_rule.box_filter == "fragile_only" and not sku["fragile"]:
                    continue
                if state_rule.box_filter == "sturdy_only" and sku["fragile"]:
                    continue
                if state_rule.box_filter == "heavy_only" and sku["weight_kg"] <= 5.0:
                    continue
                if state_rule.box_filter == "light_only" and sku["weight_kg"] > 5.0:
                    continue
                
                queue.append(box)
        
        # Sort by state strategy
        key = state_rule.box_sort_key
        reverse = (state_rule.box_sort_order == "desc")
        
        if key == "volume":
            queue.sort(key=lambda b: b["volume"], reverse=reverse)
        elif key == "weight":
            queue.sort(key=lambda b: b["weight"], reverse=reverse)
        elif key == "height":
            queue.sort(key=lambda b: b["height_mm"], reverse=reverse)
        elif key == "fragile":
            queue.sort(key=lambda b: b["fragile"], reverse=reverse)
        elif key == "sturdy":
            queue.sort(key=lambda b: not b["fragile"], reverse=reverse)
        
        return queue
    
    def _select_pallet(self, state_rule: StateRule) -> int:
        """Select pallet based on state rule."""
        pallet_specs = self.env.get_pallet_specs()
        
        key = state_rule.pallet_select_key
        reverse = (state_rule.pallet_select_order == "desc")
        
        if key == "remaining_volume":
            pallet_specs.sort(key=lambda p: p["remaining_volume"], reverse=reverse)
        elif key == "remaining_height":
            pallet_specs.sort(key=lambda p: p["remaining_height"], reverse=reverse)
        elif key == "weight_capacity":
            pallet_specs.sort(key=lambda p: p["weight_remaining"], reverse=reverse)
        elif key == "index":
            pallet_specs.sort(key=lambda p: p["pallet_idx"], reverse=reverse)
        
        return pallet_specs[0]["pallet_idx"] if pallet_specs else 0
    
    def _get_orientations(self, box: Dict[str, Any], state_rule: StateRule) -> List[Tuple[float, float, float]]:
        """Get possible orientations based on state rule."""
        dims = [box["length_mm"], box["width_mm"], box["height_mm"]]
        
        if not state_rule.allow_rotation:
            return [(dims[0], dims[1], dims[2])]
        
        orientations = set()
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    if i != j and i != k and j != k:
                        orientations.add((dims[i], dims[j], dims[k]))
        
        orientations = list(orientations)
        
        if state_rule.orientation_priority == "original":
            orientations.sort(key=lambda o: abs(o[0] - dims[0]) + abs(o[1] - dims[1]) + abs(o[2] - dims[2]))
        elif state_rule.orientation_priority == "height_min":
            orientations.sort(key=lambda o: o[2])
        elif state_rule.orientation_priority == "volume_optimal":
            orientations.sort(key=lambda o: o[0] * o[1], reverse=True)
        elif state_rule.orientation_priority == "random":
            random.shuffle(orientations)
        
        return orientations
    
    def _find_valid_positions(self, pallet_idx: int, box: Dict[str, Any], 
                          l: float, w: float, h: float, 
                          state_rule: StateRule) -> List[Tuple[float, float, float]]:
        """
        Systematically calculate ALL valid positions with physics constraints.
        """
        pallet = self.env.pallets[pallet_idx]
        grid = state_rule.grid_size_mm

        valid_positions = []

        # ===== GROUND LEVEL POSITIONS (z = 0) =====
        for x in range(0, int(pallet["length_mm"] - l + 1), grid):
            for y in range(0, int(pallet["width_mm"] - w + 1), grid):
                if x + l > pallet["length_mm"] + 1e-6:
                    continue
                if y + w > pallet["width_mm"] + 1e-6:
                    continue
                
                # Check collisions
                collision = False
                for existing in pallet["placed_boxes"]:
                    if self._boxes_overlap_3d(x, y, 0, l, w, h, existing):
                        collision = True
                        break
                    
                if not collision:
                    valid_positions.append((x, y, 0))

        # ===== STACKED POSITIONS (on top of existing boxes) =====
        if pallet["placed_boxes"]:
            z_levels = sorted(set(b["z_max"] for b in pallet["placed_boxes"]))

            for z in z_levels:
                for x in range(0, int(pallet["length_mm"] - l + 1), grid):
                    for y in range(0, int(pallet["width_mm"] - w + 1), grid):
                        if x + l > pallet["length_mm"] + 1e-6:
                            continue
                        if y + w > pallet["width_mm"] + 1e-6:
                            continue
                        if z + h > pallet["max_height_mm"] + 1e-6:
                            continue
                        
                        # Check collisions
                        collision = False
                        for existing in pallet["placed_boxes"]:
                            if self._boxes_overlap_3d(x, y, z, l, w, h, existing):
                                collision = True
                                break
                            
                        if collision:
                            continue
                        
                        # ===== NEW: Check physics constraints =====
                        physics_valid, reason = self._check_physics_constraints(
                            x, y, z, l, w, h, pallet_idx, state_rule
                        )

                        if not physics_valid:
                            continue
                        
                        valid_positions.append((x, y, z))

        return valid_positions
    
    def _boxes_overlap_3d(self, x: float, y: float, z: float,
                           l: float, w: float, h: float,
                           existing: Dict[str, Any]) -> bool:
        """
        Check if a box at (x,y,z) with dimensions (l,w,h) overlaps with existing box.
        """
        x_min, x_max = x, x + l
        y_min, y_max = y, y + w
        z_min, z_max = z, z + h

        ox = max(0, min(x_max, existing["x_max"]) - max(x_min, existing["x_min"]))
        oy = max(0, min(y_max, existing["y_max"]) - max(y_min, existing["y_min"]))
        oz = max(0, min(z_max, existing["z_max"]) - max(z_min, existing["z_min"]))

        return ox > 0 and oy > 0 and oz > 0

    def _check_physics_constraints(self, x: float, y: float, z: float,
                                l: float, w: float, h: float,
                                pallet_idx: int,
                                state_rule: StateRule) -> Tuple[bool, str]:
        """
        Check all physics constraints for a placement.
        Returns (is_valid, rejection_reason).
        """
        pallet = self.env.pallets[pallet_idx]
        placed_boxes = pallet["placed_boxes"]

        # ===== 1. Ground Level (always valid if within bounds) =====
        if z < 1e-6:
            return True, "valid"

        # ===== 2. Support Ratio Check =====
        support_ratio, support_details = self._calculate_support_ratio(
            x, y, z, l, w, h, placed_boxes
        )

        if support_ratio < state_rule.min_support_ratio:
            return False, f"insufficient_support ({support_ratio:.2f} < {state_rule.min_support_ratio})"

        # ===== 3. Center of Mass Check (PREVENTS STAIRCASE) =====
        if not support_details["center_supported"]:
            return False, "center_of_mass_unsupported"

        # ===== 4. Edge Support Check (PREVENTS STAIRCASE) =====
        # Require at least 2 edges supported for stability
        if support_details["edges_supported"] < 2:
            return False, f"insufficient_edge_support ({support_details['edges_supported']}/4 edges)"

        # ===== 5. Overhang Check =====
        # Prevent severe overhang (more than 40% of dimension hanging)
        max_overhang_ratio = 0.4
        for existing in placed_boxes:
            if abs(existing["z_max"] - z) < 1e-6:
                # Check X overhang
                overlap_x = max(0, min(x + l, existing["x_max"]) - max(x, existing["x_min"]))
                if overlap_x > 0:
                    overhang_left = max(0, existing["x_min"] - x)
                    overhang_right = max(0, (x + l) - existing["x_max"])
                    if overhang_left > l * max_overhang_ratio or overhang_right > l * max_overhang_ratio:
                        return False, "excessive_overhang_x"

                # Check Y overhang
                overlap_y = max(0, min(y + w, existing["y_max"]) - max(y, existing["y_min"]))
                if overlap_y > 0:
                    overhang_front = max(0, existing["y_min"] - y)
                    overhang_back = max(0, (y + w) - existing["y_max"])
                    if overhang_front > w * max_overhang_ratio or overhang_back > w * max_overhang_ratio:
                        return False, "excessive_overhang_y"

        # ===== 6. Load Bearing Check (if available) =====
        sku = self.boxes_meta.get(list(self.boxes_meta.keys())[0], {})
        box_weight = sku.get("weight_kg", 0)

        for existing in placed_boxes:
            if abs(existing["z_max"] - z) < 1e-6:
                # Check if supporting box can handle the weight
                existing_load_bearing = existing.get("load_bearing_kg", float('inf'))
                if box_weight > existing_load_bearing:
                    return False, f"load_bearing_exceeded ({box_weight} > {existing_load_bearing})"

        # ===== 7. Stack Layer Limit Check =====
        # Count how many boxes are below this position
        layers_below = 0
        check_z = z - 0.1
        while check_z > 0:
            for existing in placed_boxes:
                if abs(existing["z_max"] - check_z) < 1.0:
                    if (existing["x_min"] <= x + l/2 <= existing["x_max"] and
                        existing["y_min"] <= y + w/2 <= existing["y_max"]):
                        layers_below += 1
                        check_z = existing["z_min"]
                        break
            else:
                break
            
        max_layers = sku.get("max_stack_layers", 10)
        if layers_below >= max_layers:
            return False, f"max_stack_layers_exceeded ({layers_below} >= {max_layers})"

        return True, "valid"

    def _calculate_support_ratio(self, x: float, y: float, z: float,
                              l: float, w: float, h: float,
                              placed_boxes: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate support ratio WITH physics boundary checks.
        Returns (support_ratio, support_details).
        """
        box_area = l * w
        if box_area == 0:
            return 0.0, {"support_area": 0, "support_boxes": [], "overhang": True, "center_supported": False}

        support_area = 0.0
        support_boxes = []
        z_tol = 1e-6

        # Box center for center-of-mass check
        box_center_x = x + l / 2
        box_center_y = y + w / 2

        for existing in placed_boxes:
            # Check if existing box top is at this box's bottom
            if abs(existing["z_max"] - z) < z_tol:
                # Calculate overlap area
                dx = max(0, min(x + l, existing["x_max"]) - max(x, existing["x_min"]))
                dy = max(0, min(y + w, existing["y_max"]) - max(y, existing["y_min"]))

                if dx > 0 and dy > 0:
                    support_area += dx * dy
                    support_boxes.append({
                        "sku_id": existing["sku_id"],
                        "overlap_area": dx * dy,
                        "overlap_dims": (dx, dy)
                    })

        # ===== NEW: Physics Boundary Checks =====

        # 1. Check for overhang (box extending beyond support on any edge)
        overhang_x_min = True
        overhang_x_max = True
        overhang_y_min = True
        overhang_y_max = True

        for existing in placed_boxes:
            if abs(existing["z_max"] - z) < z_tol:
                # Check if support exists at each edge
                if existing["x_min"] <= x + 10:  # Support at left edge (10mm tolerance)
                    overhang_x_min = False
                if existing["x_max"] >= (x + l) - 10:  # Support at right edge
                    overhang_x_max = False
                if existing["y_min"] <= y + 10:  # Support at front edge
                    overhang_y_min = False
                if existing["y_max"] >= (y + w) - 10:  # Support at back edge
                    overhang_y_max = False

        # Count how many edges have support
        edges_supported = sum([
            not overhang_x_min,
            not overhang_x_max,
            not overhang_y_min,
            not overhang_y_max
        ])

        # 2. Check if center of mass is supported
        center_supported = False
        for existing in placed_boxes:
            if abs(existing["z_max"] - z) < z_tol:
                if (existing["x_min"] <= box_center_x <= existing["x_max"] and
                    existing["y_min"] <= box_center_y <= existing["y_max"]):
                    center_supported = True
                    break
                
        support_ratio = support_area / box_area

        details = {
            "support_area": support_area,
            "support_boxes": support_boxes,
            "overhang_x_min": overhang_x_min,
            "overhang_x_max": overhang_x_max,
            "overhang_y_min": overhang_y_min,
            "overhang_y_max": overhang_y_max,
            "edges_supported": edges_supported,
            "center_supported": center_supported,
            "is_stable": support_ratio >= 0.6 and center_supported and edges_supported >= 2
        }

        return support_ratio, details

    def _get_all_valid_orientations(self, box: Dict[str, Any], 
                                     state_rule: StateRule) -> List[Tuple[float, float, float]]:
        """
        Generate all valid orientations for a box.
        Respects strict_upright constraint.
        """
        dims = [box["length_mm"], box["width_mm"], box["height_mm"]]
        sku = self.boxes_meta[box["sku_id"]]

        if not state_rule.allow_rotation:
            return [(dims[0], dims[1], dims[2])]

        # Generate all 6 possible orientations (permutations of 3 dimensions)
        orientations = set()
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    if i != j and i != k and j != k:
                        orientations.add((dims[i], dims[j], dims[k]))

        orientations = list(orientations)

        # Filter by strict_upright constraint
        if sku.get("strict_upright", False):
            orientations = [
                (l, w, h) for l, w, h in orientations
                if abs(h - sku["height_mm"]) < 1e-6
            ]

        # Sort by preference
        if state_rule.orientation_priority == "height_min":
            orientations.sort(key=lambda o: o[2])
        elif state_rule.orientation_priority == "volume_optimal":
            orientations.sort(key=lambda o: o[0] * o[1], reverse=True)
        elif state_rule.orientation_priority == "original":
            orientations.sort(key=lambda o: abs(o[0] - dims[0]) + abs(o[1] - dims[1]) + abs(o[2] - dims[2]))
        elif state_rule.orientation_priority == "random":
            random.shuffle(orientations)

        return orientations

    def _find_best_position(self, pallet_idx: int, box: Dict[str, Any],
                        state_rule: StateRule) -> Optional[Tuple[float, float, float, float, float, float]]:
        """
        Find the best valid position with physics stability scoring.
        """
        orientations = self._get_all_valid_orientations(box, state_rule)
        
        best_position = None
        best_score = -float('inf')
        
        for l, w, h in orientations:
            positions = self._find_valid_positions(pallet_idx, box, l, w, h, state_rule)
            
            for x, y, z in positions:
                score = 0.0
                
                # Z preference (lower is better for stability)
                if state_rule.prefer_lower_z:
                    score -= z * state_rule.position_score_z_weight
                
                # X, Y preference (fill from corner)
                score -= (x + y) * state_rule.position_score_xy_weight
                
                # ===== NEW: Physics Stability Scoring =====
                if z > 1e-6:
                    support_ratio, support_details = self._calculate_support_ratio(
                        x, y, z, l, w, h,
                        self.env.pallets[pallet_idx]["placed_boxes"]
                    )
                    
                    # Bonus for higher support ratio
                    score += support_ratio * 2000
                    
                    # Bonus for center support
                    if support_details["center_supported"]:
                        score += 1000
                    
                    # Bonus for more edges supported
                    score += support_details["edges_supported"] * 500
                    
                    # Penalty for any overhang
                    if support_details["overhang_x_min"]:
                        score -= 200
                    if support_details["overhang_x_max"]:
                        score -= 200
                    if support_details["overhang_y_min"]:
                        score -= 200
                    if support_details["overhang_y_max"]:
                        score -= 200
                
                if score > best_score:
                    best_score = score
                    best_position = (x, y, z, l, w, h)
        
        return best_position

    def _place_box_optimal(self, box: Dict[str, Any], state_rule: StateRule) -> bool:
        """
        Attempt to place a single box using calculated positions.
        Returns True if successfully placed.
        """
        sku_id = box["sku_id"]
        
        # Select pallet based on state rule
        pallet_idx = self._select_pallet(state_rule)
        
        # Find best position and orientation
        result = self._find_best_position(pallet_idx, box, state_rule)
        
        if result:
            x, y, z, l, w, h = result
            
            # Try to place
            placement_result = self.env.place_box(
                box["sku_id"], x, y, z, l, w, h,
                pallet_idx=pallet_idx
            )
            
            if placement_result["success"]:
                return True
            else:
                self.env.record_denial(
                    sku_id=sku_id,
                    reason=placement_result["error"],
                    attempted_pallets=[pallet_idx],
                    attempted_orientations=[]
                )
        else:
            self.env.record_denial(
                sku_id=sku_id,
                reason="no_valid_position",
                attempted_pallets=[pallet_idx],
                attempted_orientations=[]
            )
        return False
    
    def _try_placement(self, pallet_idx: int, sku_id: str, 
                       x: float, y: float, z: float,
                       l: float, w: float, h: float, state_rule: StateRule) -> bool:
        """Test if placement would be valid."""
        pallet = self.env.pallets[pallet_idx]
        sku = self.boxes_meta[sku_id]
        
        if x + l > pallet["length_mm"] + 1e-6:
            return False
        if y + w > pallet["width_mm"] + 1e-6:
            return False
        if z + h > pallet["max_height_mm"] + 1e-6:
            return False
        
        x_min, x_max = x, x + l
        y_min, y_max = y, y + w
        z_min, z_max = z, z + h
        
        for existing in pallet["placed_boxes"]:
            ox = max(0, min(x_max, existing["x_max"]) - max(x_min, existing["x_min"]))
            oy = max(0, min(y_max, existing["y_max"]) - max(y_min, existing["y_min"]))
            oz = max(0, min(z_max, existing["z_max"]) - max(z_min, existing["z_min"]))
            if ox > 0 and oy > 0 and oz > 0:
                return False
        
        if z > 1e-6:
            support_area = 0.0
            box_area = l * w
            for existing in pallet["placed_boxes"]:
                if abs(existing["z_max"] - z) < 1e-6:
                    dx = max(0, min(x_max, existing["x_max"]) - max(x_min, existing["x_min"]))
                    dy = max(0, min(y_max, existing["y_max"]) - max(y_min, existing["y_min"]))
                    support_area += dx * dy
            
            if box_area == 0 or support_area / box_area < state_rule.min_support_ratio:
                return False
        
        return True
    
    def _check_state_transition(self) -> Optional[str]:
        """Check if should transition to new state."""
        current_rule = self.genome.get_state_rule(self.current_state)
        if not current_rule:
            return None
        
        # Check box count limits
        if self.boxes_placed_in_state >= current_rule.max_boxes_in_state:
            if current_rule.transitions:
                return current_rule.transitions[0].target_state
        
        # Check transition conditions
        env_state = self.env.get_env_state()
        for transition in current_rule.transitions:
            if transition.evaluate(env_state):
                return transition.target_state
        
        return None
    
    def place_all_boxes(self) -> Dict[str, Any]:
        """
        Execute state machine to place ALL boxes by quantity.
        """
        self.env.reset()
        self.current_state = self.genome.start_state
        self.boxes_placed_in_state = 0
        
        placed_count = 0
        state_transitions = 0
        states_used = set()
        
        max_attempts_per_box = 3
        box_attempt_count = {}
        
        consecutive_failures = 0
        max_consecutive_failures = 100
        
        # max_transitions = 0
        # for sku in self.boxes_meta:
        #     max_transitions += sku["quantity"]
        # max_transitions *= max_attempts_per_box
        
        while state_transitions < max_consecutive_failures * max_attempts_per_box and consecutive_failures < max_consecutive_failures:
            # Check for state transition
            state_transitions += 1
            new_state = self._check_state_transition()
            if new_state and new_state != self.current_state:
                self.current_state = new_state
                self.boxes_placed_in_state = 0
            
            state_rule = self.genome.get_state_rule(self.current_state)
            if not state_rule:
                break
            
            states_used.add(self.current_state)
            box_queue = self._get_box_queue(state_rule)
            
            placed_this_iteration = False
            for box in box_queue:
                sku = self.boxes_meta[box["sku_id"]]
                sku_key = box["sku_id"]
                
                # Check if we've exceeded quantity
                if self.env.sku_usage[box["sku_id"]] >= sku["quantity"]:
                    continue
                
                # ← NEW: Track attempts per box type
                box_attempt_count[sku_key] = box_attempt_count.get(sku_key, 0) + 1
                if box_attempt_count[sku_key] > max_attempts_per_box:
                    continue
                
                # Try to place
                if self._place_box_optimal(box, state_rule):
                    placed_count += 1
                    self.boxes_placed_in_state += 1
                    placed_this_iteration = True
                    consecutive_failures = 0  # ← Reset on success
                    box_attempt_count[sku_key] = 0  # ← Reset attempts for this SKU
                    break  # Move to next iteration to re-evaluate state
                
            if not placed_this_iteration:
                consecutive_failures += 1
        
        return {
            "placed_count": placed_count,
            "failed_count": self.env.total_requested_items - placed_count,
            "total_requested": self.env.total_requested_items,
            "placement_rate": placed_count / self.env.total_requested_items if self.env.total_requested_items > 0 else 0,
            "state_transitions": state_transitions,
            "states_used": list(states_used),
            "final_state": self.current_state
        }