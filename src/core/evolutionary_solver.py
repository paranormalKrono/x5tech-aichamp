import random
from typing import Dict, Any, List, Tuple
from copy import deepcopy
from palletizing_env import PalletizingEnv
from state_machine_gene import StateMachineGenome, StateRule
from state_machine_engine import StateMachineEngine
from datetime import datetime
from genom_utilities import save_genome


class EvolutionarySolver:
    def __init__(self, request: Dict[str, Any], pop_size: int = 20):
        self.request = request
        self.pop_size = pop_size
        self.elite_size = max(2, pop_size // 5)  # ← Keep top 20%
        self.tournament_size = 5  # ← Increased from 3 for stronger selection
        self.env = PalletizingEnv(request)
        
        self.population: List[StateMachineGenome] = []
        self.scores: List[float] = []
        self.best_genome = None
        self.best_score = -1.0
        self.best_stats = None
        self.best_denial_summary = {}

    def initialize_population(self):
        self.population = [StateMachineGenome.random() for _ in range(self.pop_size)]
        self.scores = [0.0] * self.pop_size

    def evaluate_genome(self, genome: StateMachineGenome) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
        try:
            engine = StateMachineEngine(self.env, genome)
            stats = engine.place_all_boxes()
            score = self.env.calculate_score()["final_score"]
            denial_summary = self.env.get_denial_summary()
            return score, stats, denial_summary
        except Exception as e:
            print(f"Evaluation error - {e}")
            return 0.0, {
                "placed_count": 0,
                "failed_count": self.env.total_requested_items,
                "total_requested": self.env.total_requested_items,
                "placement_rate": 0.0,
                "state_transitions": 0,
                "states_used": [],
                "final_state": "error"
            }, {}

    def evaluate_population(self):
        self.best_score = 0.0
        for i, genome in enumerate(self.population):
            score, stats, denial_summary = self.evaluate_genome(genome)
            self.scores[i] = score
            
            if score > self.best_score or self.best_stats is None:
                self.best_score = score
                self.best_genome = deepcopy(genome)
                self.best_stats = stats
                self.best_denial_summary = denial_summary

    def select_parent(self) -> StateMachineGenome:
        """Tournament selection with larger tournament."""
        participants = random.sample(range(self.pop_size), self.tournament_size)
        best_idx = max(participants, key=lambda i: self.scores[i])
        return deepcopy(self.population[best_idx])

    def crossover(self, p1: StateMachineGenome, p2: StateMachineGenome) -> StateMachineGenome:
        """Crossover state machines - merge states from both parents."""
        # Combine states from both parents
        all_states = p1.states + p2.states
        
        # Select subset for child
        num_states = random.randint(len(all_states) // 2, len(all_states))
        child_states = random.sample(all_states, min(num_states, len(all_states)))
        
        # Inherit start state from one parent
        start_state = random.choice([p1.start_state, p2.start_state])
        
        # Inherit mutation rate
        mutation_rate = random.uniform(
            min(p1.mutation_rate, p2.mutation_rate),
            max(p1.mutation_rate, p2.mutation_rate)
        )
        
        return StateMachineGenome(
            states=child_states,
            start_state=start_state,
            mutation_rate=mutation_rate
        )

    def mutate(self, genome: StateMachineGenome) -> StateMachineGenome:
        """Mutate state machine genome."""
        genome_dict = genome.to_dict()
        
        # Mutate states
        for i, state_dict in enumerate(genome_dict["states"]):
            if random.random() < genome.mutation_rate:
                # Mutate state parameters
                state_dict["box_sort_key"] = random.choice(["volume", "weight", "height", "fragile", "sturdy"])
                state_dict["position_strategy"] = random.choice(["corner", "center", "random", "support_max", "layer_complete"])
                state_dict["orientation_priority"] = random.choice(["original", "volume_optimal", "height_min", "stable", "random"])
                state_dict["min_support_ratio"] = random.uniform(0.4, 0.8)
                state_dict["grid_size_mm"] = random.choice([25,50,75,100])
            
            if random.random() < genome.mutation_rate:
                # Add/remove transition
                if state_dict["transitions"] and random.random() > 0.5:
                    state_dict["transitions"].pop()
                else:
                    state_dict["transitions"].append({
                        "condition_type": random.choice(["pallet_fill_ratio", "weight_ratio", "boxes_remaining"]),
                        "operator": random.choice(["gt", "lt", "gte", "lte"]),
                        "threshold": random.uniform(0.3, 0.9),
                        "target_state": random.choice([s["state_name"] for s in genome_dict["states"]])
                    })
        
        # Add/remove state
        if random.random() < genome.mutation_rate and len(genome_dict["states"]) < 8:
            genome_dict["states"].append(StateRule.random().to_dict())
        elif random.random() < genome.mutation_rate and len(genome_dict["states"]) > 2:
            genome_dict["states"].pop()
        
        # Mutate start state
        if random.random() < genome.mutation_rate and genome_dict["states"]:
            genome_dict["start_state"] = random.choice([s["state_name"] for s in genome_dict["states"]])
        
        return StateMachineGenome.from_dict(genome_dict)

    def run(self, generations: int = 50, verbose: bool = True,
            save_best: bool = True, save_dir: str = "./saved_genomes") -> Tuple[StateMachineGenome, Dict[str, Any], float, Dict[str, Any]]:
        """
        Run evolution with optional auto-save.
        """
        if verbose:
            print(f"Starting State Machine Evolutionary Solver")
            print(f"  Generations: {generations}")
            print(f"  Population: {self.pop_size}")
            print(f"  Pallets: {self.env.num_pallets}")
            print(f"  Total Boxes to Place: {self.env.total_requested_items}")
            print(f"  Save Directory: {save_dir if save_best else 'None'}")
            print("-" * 60)
        
        self.initialize_population()
        self.evaluate_population()
        
        for gen in range(generations):
            new_pop = []
            
            # ← Elitism: Keep top performers
            elite_indices = sorted(range(len(self.scores)), key=lambda i: self.scores[i], reverse=True)[:self.elite_size]
            for idx in elite_indices:
                new_pop.append(deepcopy(self.population[idx]))
            
            # Fill rest with offspring
            while len(new_pop) < self.pop_size:
                p1 = self.select_parent()
                p2 = self.select_parent()
                child = self.crossover(p1, p2)
                child = self.mutate(child)
                new_pop.append(child)
            
            self.population = new_pop
            self.evaluate_population()
            
            # ← NEW: Print more detailed progress
            if verbose and gen % 5 == 0:  # Every 5 generations
                if self.best_stats:
                    print(f"Gen {gen:3d}: Score = {self.best_score:.4f}, "
                          f"Placed = {self.best_stats['placed_count']}/{self.best_stats['total_requested']}, "
                          f"States = {len(self.best_stats['states_used'])}, "
                          f"Pallets Used = {sum(1 for p in self.env.pallets if p['placed_boxes'])}")

        if verbose:
            print("-" * 60)
            print(f"Optimization Complete. Final Score: {self.best_score:.4f}")
        
        # Ensure best_stats is never None
        if self.best_stats is None:
            self.best_stats = {
                "placed_count": 0,
                "failed_count": self.env.total_requested_items,
                "total_requested": self.env.total_requested_items,
                "placement_rate": 0.0,
                "state_transitions": 0,
                "states_used": [],
                "final_state": "none"
            }
        if self.best_genome is None:
            self.best_genome = StateMachineGenome(list(), "", 0.0)
        
        # Auto-save best genome
        if save_best:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"{save_dir}/best_genome_{timestamp}.json"
            save_genome(self.best_genome, filepath, self.best_stats, self.best_score)
        
        return self.best_genome, self.best_denial_summary, self.best_score, self.best_stats