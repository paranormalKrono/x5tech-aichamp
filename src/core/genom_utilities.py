import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
from state_machine_gene import StateMachineGenome


def save_genome(genome: StateMachineGenome, filepath: str, stats: Dict[str, Any],
                score: float = 0.0):
    """
    Save genome to JSON file with metadata.
    """
    data = {
        "genome": genome.to_dict(),
        "score": score,
        "stats": stats,
        "saved_at": datetime.now().isoformat(),
        "version": "1.0"
    }
    
    # Ensure directory exists
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Genome saved to: {filepath}")
    return filepath

def load_genome(filepath: str) -> Tuple[StateMachineGenome, Dict[str, Any]]:
    """
    Load genome from JSON file.
    Returns genome and metadata.
    """
    
    path = Path(filepath)
    if (path.exists()):
      with open(filepath, 'r') as f:
          data = json.load(f)
    
      genome = StateMachineGenome.from_dict(data["genome"])
      metadata = {
          "score": data.get("score"),
          "stats": data.get("stats"),
          "saved_at": data.get("saved_at"),
          "version": data.get("version")
      }
    else:
      genome = StateMachineGenome(list(),"")
      metadata = {}
    
    print(f"Genome loaded from: {filepath}")
    return genome, metadata

def save_population(population: List[StateMachineGenome], 
                   scores: List[float], 
                   filepath: str):
    """
    Save entire population for later analysis or continuation.
    """
    data = {
        "population": [g.to_dict() for g in population],
        "scores": scores,
        "population_size": len(population),
        "saved_at": datetime.now().isoformat()
    }
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Population saved to: {filepath}")

def load_population(filepath: str) -> Tuple[List[StateMachineGenome], List[float]]:
    """
    Load population for continuing evolution.
    """
    
    path = Path(filepath)
    if (path.exists()):
      with open(filepath, 'r') as f:
          data = json.load(f)
          population = [StateMachineGenome.from_dict(g) for g in data["population"]]
          scores = data["scores"]
    else:
      population = []
      scores = []
      print("Population wasn't found")
    
    
    print(f"Population loaded from: {filepath}")
    return population, scores