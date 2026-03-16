import random
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

class PlacementState(Enum):
    """Possible states in the placement state machine."""
    INIT = "init"
    FILL_BOTTOM = "fill_bottom"      # Place boxes at lowest Z first
    BUILD_LAYER = "build_layer"      # Complete layers before moving up
    PLACE_FRAGILE = "place_fragile"  # Handle fragile boxes specially
    PLACE_HEAVY = "place_heavy"      # Handle heavy boxes specially
    FILL_GAPS = "fill_gaps"          # Fill remaining gaps
    SWITCH_PALLET = "switch_pallet"  # Move to next pallet
    FINALIZE = "finalize"            # Final optimization pass
    # REMOVED: No need for corner/center/random strategies

@dataclass
class StateTransition:
    """
    Defines when to transition from one state to another.
    Condition is evaluated against current environment state.
    """
    condition_type: str  # pallet_fill_ratio, weight_ratio, height_ratio, boxes_remaining, fragile_remaining
    operator: str  # gt, lt, gte, lte, eq
    threshold: float
    target_state: str
    
    def evaluate(self, env_state: Dict[str, Any]) -> bool:
        """Check if transition condition is met."""
        value = env_state.get(self.condition_type, 0.0)
        
        if self.operator == "gt":
            return value > self.threshold
        elif self.operator == "lt":
            return value < self.threshold
        elif self.operator == "gte":
            return value >= self.threshold
        elif self.operator == "lte":
            return value <= self.threshold
        elif self.operator == "eq":
            return abs(value - self.threshold) < 0.01
        return False
@dataclass
class StateRule:
    """
    A single state in the state machine genome.
    Defines WHAT to do when in this state.
    """
    state_name: str
    
    # ===== BOX SELECTION =====
    box_sort_key: str = "volume"  # volume, weight, height, area, fragile, sturdy
    box_sort_order: str = "desc"  # asc, desc
    box_filter: str = "all"  # all, fragile_only, sturdy_only, heavy_only, light_only
    
    # ===== PALLET SELECTION =====
    pallet_select_key: str = "remaining_volume"
    pallet_select_order: str = "desc"
    
    # ===== POSITION CALCULATION (REPLACES position_strategy) =====
    grid_size_mm: int = 50
    prefer_lower_z: bool = True  # Prefer placing boxes lower (gravity-first)
    prefer_more_support: bool = True  # Prefer positions with higher support ratio
    position_score_z_weight: float = 10000.0  # Weight for Z in position scoring
    position_score_xy_weight: float = 100.0  # Weight for X,Y in position scoring
    
    # ===== ORIENTATION =====
    orientation_priority: str = "original"  # original, volume_optimal, height_min, stable, random
    allow_rotation: bool = True
    respect_strict_upright: bool = False  # Enforce strict_upright constraint
    
    # ===== SUPPORT REQUIREMENTS =====
    min_support_ratio: float = 0.6
    check_support_on_ground: bool = False  # Skip support check for ground-level boxes
    
    # ===== STATE TRANSITIONS =====
    transitions: List[StateTransition] = field(default_factory=list)
    min_boxes_in_state: int = 1
    max_boxes_in_state: int = 100
    
    # ===== PALLET SWITCHING =====
    switch_pallet_on_full: bool = True
    pallet_fill_threshold: float = 0.8  # Switch when pallet is this % full
    
    # ===== Physics Constraints =====
    min_support_ratio: float = 0.6
    require_center_support: bool = True  # Center of mass must be supported
    min_edges_supported: int = 2  # Minimum edges that need support (0-4)
    max_overhang_ratio: float = 0.4  # Max 40% overhang allowed
    check_load_bearing: bool = True  # Enforce load bearing limits
    check_stack_layers: bool = True  # Enforce max stack layers
    ground_level_only: bool = False  # Only place on ground (no stacking)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_name": self.state_name,
            "box_sort_key": self.box_sort_key,
            "box_sort_order": self.box_sort_order,
            "box_filter": self.box_filter,
            "pallet_select_key": self.pallet_select_key,
            "pallet_select_order": self.pallet_select_order,
            "grid_size_mm": self.grid_size_mm,
            "prefer_lower_z": self.prefer_lower_z,
            "prefer_more_support": self.prefer_more_support,
            "position_score_z_weight": self.position_score_z_weight,
            "position_score_xy_weight": self.position_score_xy_weight,
            "orientation_priority": self.orientation_priority,
            "allow_rotation": self.allow_rotation,
            "respect_strict_upright": self.respect_strict_upright,
            "min_support_ratio": self.min_support_ratio,
            "check_support_on_ground": self.check_support_on_ground,
            "min_boxes_in_state": self.min_boxes_in_state,
            "max_boxes_in_state": self.max_boxes_in_state,
            "switch_pallet_on_full": self.switch_pallet_on_full,
            "pallet_fill_threshold": self.pallet_fill_threshold,
            "transitions": [
                {
                    "condition_type": t.condition_type,
                    "operator": t.operator,
                    "threshold": t.threshold,
                    "target_state": t.target_state
                }
                for t in self.transitions
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateRule':
        transitions = [
            StateTransition(
                condition_type=t["condition_type"],
                operator=t["operator"],
                threshold=t["threshold"],
                target_state=t["target_state"]
            )
            for t in data.get("transitions", [])
        ]
        return cls(
            state_name=data["state_name"],
            box_sort_key=data.get("box_sort_key", "volume"),
            box_sort_order=data.get("box_sort_order", "desc"),
            box_filter=data.get("box_filter", "all"),
            pallet_select_key=data.get("pallet_select_key", "remaining_volume"),
            pallet_select_order=data.get("pallet_select_order", "desc"),
            grid_size_mm=data.get("grid_size_mm", 50),
            prefer_lower_z=data.get("prefer_lower_z", True),
            prefer_more_support=data.get("prefer_more_support", True),
            position_score_z_weight=data.get("position_score_z_weight", 10000.0),
            position_score_xy_weight=data.get("position_score_xy_weight", 100.0),
            orientation_priority=data.get("orientation_priority", "original"),
            allow_rotation=data.get("allow_rotation", True),
            respect_strict_upright=data.get("respect_strict_upright", True),
            min_support_ratio=data.get("min_support_ratio", 0.6),
            check_support_on_ground=data.get("check_support_on_ground", False),
            min_boxes_in_state=data.get("min_boxes_in_state", 1),
            max_boxes_in_state=data.get("max_boxes_in_state", 100),
            switch_pallet_on_full=data.get("switch_pallet_on_full", True),
            pallet_fill_threshold=data.get("pallet_fill_threshold", 0.8),
            transitions=transitions
        )

    @classmethod
    def random(cls, state_name: str = "") -> 'StateRule':
        """Generate random state rule."""
        if state_name == "":
            state_name = random.choice([s.value for s in PlacementState])

        num_transitions = random.randint(1, 3)
        transitions = []
        for _ in range(num_transitions):
            transitions.append(StateTransition(
                condition_type=random.choice([
                    "pallet_fill_ratio", "weight_ratio", "height_ratio",
                    "boxes_remaining", "fragile_remaining"
                ]),
                operator=random.choice(["gt", "lt", "gte", "lte"]),
                threshold=random.uniform(0.3, 0.9),
                target_state=random.choice([s.value for s in PlacementState])
            ))

        return cls(
            state_name=state_name,
            box_sort_key=random.choice(["volume", "weight", "height", "area", "fragile", "sturdy"]),
            box_sort_order=random.choice(["asc", "desc"]),
            box_filter=random.choice(["all", "fragile_only", "sturdy_only", "heavy_only", "light_only"]),
            pallet_select_key=random.choice(["remaining_volume", "remaining_height", "weight_capacity", "index"]),
            pallet_select_order=random.choice(["asc", "desc"]),
            grid_size_mm=random.choice([25, 50, 75, 100]),
            prefer_lower_z=random.choice([True, False]),
            prefer_more_support=random.choice([True, False]),
            position_score_z_weight=random.uniform(5000.0, 20000.0),
            position_score_xy_weight=random.uniform(50.0, 200.0),
            orientation_priority=random.choice(["original", "volume_optimal", "height_min", "stable", "random"]),
            allow_rotation=random.choice([True, False]),
            respect_strict_upright=random.choice([True, False]),
            min_support_ratio=random.uniform(0.3, 0.5),
            check_support_on_ground=random.choice([True, False]),
            min_boxes_in_state=random.randint(1, 5),
            max_boxes_in_state=random.randint(10, 50),
            switch_pallet_on_full=random.choice([True, False]),
            pallet_fill_threshold=random.uniform(0.6, 0.9),
            transitions=transitions
        )
    
@dataclass
class StateMachineGenome:
    """
    Complete genome: A state machine with multiple states and transitions.
    This is what evolves - not individual placements, but decision logic.
    """
    states: List[StateRule]
    start_state: str
    mutation_rate: float = 0.3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "states": [s.to_dict() for s in self.states],
            "start_state": self.start_state,
            "mutation_rate": self.mutation_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateMachineGenome':
        states = [StateRule.from_dict(s) for s in data["states"]]
        return cls(
            states=states,
            start_state=data["start_state"],
            mutation_rate=data.get("mutation_rate", 0.3)
        )
    
    @classmethod
    def random(cls, num_states: int = 0) -> 'StateMachineGenome':
        """Generate random state machine genome."""
        if num_states == 0:
            num_states = random.randint(3, 6)
        
        # Create diverse states
        available_states = [s.value for s in PlacementState]
        selected_states = random.sample(available_states, min(num_states, len(available_states)))
        
        states = [StateRule.random(state_name=name) for name in selected_states]
        
        # Ensure start state exists
        start_state = states[0].state_name if states else "init"
        
        return cls(
            states=states,
            start_state=start_state,
            mutation_rate=random.uniform(0.2, 0.6)
        )
    
    def get_state_rule(self, state_name: str) -> Optional[StateRule]:
        """Get rule for a specific state."""
        for state in self.states:
            if state.state_name == state_name:
                return state
        return None