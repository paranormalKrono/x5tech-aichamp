from evolutionary_solver import EvolutionarySolver
import json
import random
from genom_utilities import load_genome, load_population, save_population
from glob import glob
from visualization import visualize_3d, show_text
from state_machine_engine import StateMachineEngine
import time
from converter import transform_env_to_output

GLOBAL_SEED = 42

def set_seed(seed: int = GLOBAL_SEED):
    random.seed(seed)

if __name__ == "__main__":
    set_seed(42)
    
    sc_name = "task_demo_hard"
    filename = f"data/request_{sc_name}.json"
    
    with open(filename, 'r') as f:
        env_cfg = json.load(f)
    
    fn = "best_genome"
    # loaded_genome, metadata = load_genome(f"./best_genomes/{fn}.json")
    # if not load_genome is None:
    #   print(f"Loaded score: {metadata['score']}")
    #   print(f"Saved at: {metadata['saved_at']}")
      
    # Later: Load and continue evolution
    solver = EvolutionarySolver(env_cfg, pop_size=20)
    # engine = StateMachineEngine(solver.env, loaded_genome)
    start = time.perf_counter()
    # results = engine.place_all_boxes()
    end = time.perf_counter()
    print("Time ", end - start)
    # print(f"Placement rate: {results['placement_rate']:.2%}")
    
    # solver.population, solver.scores = load_population("./my_solutions/population_checkpoint.json")
    # if len(solver.population) > 0:
    #   solver.best_genome = solver.population[0]  # Set best from loaded
    
    start = time.perf_counter()
    best_genome, denial_summary, score, stats = solver.run(
        generations=40,
        verbose=True,
        save_best=True,
        save_dir="./best_genomes"
    )
    end = time.perf_counter()
    print("Fit time ", end - start)
    print(solver.env.get_denial_summary())
    
    # Save entire population mid-evolution
    # save_population(solver.population, solver.scores, "./my_solutions/population_checkpoint.json")
    
    # saved_files = glob("./my_solutions/best_genome_*.json")
    # print(f"Found {len(saved_files)} saved genomes\n")
    # 
    # for filepath in sorted(saved_files)[-5:]:  # Show last 5
    #     genome, meta = load_genome(filepath)
    #     print(f"{filepath}")
    #     print(f"  Score: {meta['score']:.4f}")
    #     print(f"  States: {len(genome.states)}")
    #     print(f"  Saved: {meta['saved_at']}")
    #     print()
    
    # Set best!
    # print(solver.env.pallets)
    # engine = StateMachineEngine(solver.env, best_genome)
    # results = engine.place_all_boxes()
    # print(f"Placement rate: {results['placement_rate']:.2%}")
    # print(solver.env.pallets)
    
    for i in range(len(solver.env.pallets)):
        visualize_3d(solver.env, pallet_idx=i, show=True)
    
    show_text(solver, best_genome, stats, score)
    
    new_data = transform_env_to_output(solver.env)
    
    path = "result.json"
    with open(path, 'w') as file:
        json.dump(new_data, file, indent=4)