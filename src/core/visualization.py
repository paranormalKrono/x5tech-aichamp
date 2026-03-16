from palletizing_env import PalletizingEnv

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def show_text(solver, best_genome, stats, score):
  print("\n" + "=" * 70)
  print("OPTIMIZED STATE MACHINE GENOME")
  print("=" * 70)

  print(f"\nStart State: {best_genome.start_state}")
  print(f"Number of States: {len(best_genome.states)}")
  print(f"Mutation Rate: {best_genome.mutation_rate:.2f}")

  print("\n--- States in Genome ---")
  for i, state in enumerate(best_genome.states):
      print(f"\nState {i+1}: {state.state_name}")
      print(f"  Box Sort: {state.box_sort_key} ({state.box_sort_order})")
      print(f"  Box Filter: {state.box_filter}")
      print(f"  Position Strategy: {state.position_strategy}")
      print(f"  Transitions: {len(state.transitions)}")
      for t in state.transitions:
          print(f"    → {t.target_state} when {t.condition_type} {t.operator} {t.threshold:.2f}")

  print(f"\n--- Placement Results ---")
  print(f"Total Requested: {stats['total_requested']}")
  print(f"Successfully Placed: {stats['placed_count']}")
  print(f"Placement Rate: {stats['placement_rate']:.2%}")
  print(f"State Transitions: {stats['state_transitions']}")
  print(f"States Used: {stats['states_used']}")
  print(f"Final State: {stats['final_state']}")
  print(f"\nFinal Score: {score:.4f}")

  print("\n--- Pallet Summary ---")
  for summary in solver.env.get_pallet_summary():
      print(f"{summary['pallet_id']}: {summary['boxes_count']} boxes, "
            f"{summary['total_weight']:.1f}/{summary['max_weight']} kg")
    

def visualize_3d(env: PalletizingEnv, pallet_idx: int = 0, show: bool = True):
    """
    Create 3D visualization of pallet with boxes.
    Requires matplotlib.
    """
    
    pallet = env.pallets[pallet_idx]
    boxes = pallet['placed_boxes']
    
    if not boxes:
        print("No boxes to visualize")
        return
    
    print("Boxes len ", len(boxes))
    
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Color map for different SKUs
    sku_colors = {}
    color_map = plt.cm.get_cmap('tab10', len(set(b['sku_id'] for b in boxes)))
    for i, sku_id in enumerate(set(b['sku_id'] for b in boxes)):
        sku_colors[sku_id] = color_map(i)
    
    # Draw pallet base
    pallet_vertices = [
        [(0, 0, 0), (pallet['length_mm'], 0, 0), 
         (pallet['length_mm'], pallet['width_mm'], 0), (0, pallet['width_mm'], 0)],
        [(0, 0, 0), (0, 0, pallet['max_height_mm']), 
         (pallet['length_mm'], 0, pallet['max_height_mm']), (pallet['length_mm'], 0, 0)],
        # Add more faces...
    ]
    
    # Draw pallet wireframe
    ax.plot([0, pallet['length_mm']], [0, 0], [0, 0], 'k-', linewidth=2)
    ax.plot([0, pallet['length_mm']], [pallet['width_mm'], pallet['width_mm']], [0, 0], 'k-', linewidth=2)
    ax.plot([0, 0], [0, pallet['width_mm']], [0, 0], 'k-', linewidth=2)
    ax.plot([pallet['length_mm'], pallet['length_mm']], [0, pallet['width_mm']], [0, 0], 'k-', linewidth=2)
    ax.plot([0, 0], [0, 0], [0, pallet['max_height_mm']], 'k-', linewidth=2)
    ax.plot([pallet['length_mm'], pallet['length_mm']], [0, 0], [0, pallet['max_height_mm']], 'k-', linewidth=2)
    ax.plot([0, 0], [pallet['width_mm'], pallet['width_mm']], [0, pallet['max_height_mm']], 'k-', linewidth=2)
    ax.plot([pallet['length_mm'], pallet['length_mm']], [pallet['width_mm'], pallet['width_mm']], [0, pallet['max_height_mm']], 'k-', linewidth=2)
    
    # Draw boxes
    for box in boxes:
        x, y, z = box['x_min'], box['y_min'], box['z_min']
        dx = box['x_max'] - box['x_min']
        dy = box['y_max'] - box['y_min']
        dz = box['z_max'] - box['z_min']
        
        # Create box vertices
        vertices = [
            [[x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z]],  # bottom
            [[x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]],  # top
            [[x, y, z], [x, y+dy, z], [x, y+dy, z+dz], [x, y, z+dz]],  # left
            [[x+dx, y, z], [x+dx, y+dy, z], [x+dx, y+dy, z+dz], [x+dx, y, z+dz]],  # right
            [[x, y, z], [x+dx, y, z], [x+dx, y, z+dz], [x, y, z+dz]],  # front
            [[x, y+dy, z], [x+dx, y+dy, z], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]],  # back
        ]
        
        color = sku_colors[box['sku_id']]
        alpha = 0.3 if box['fragile'] else 0.7
        edge_color = 'red' if box['fragile'] else 'blue'
        
        box_mesh = Poly3DCollection(vertices, 
                                    facecolor=color, 
                                    edgecolor=edge_color,
                                    alpha=alpha,
                                    linewidth=0.5)
        ax.add_collection(box_mesh)
    
    # Set labels and limits
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    
    ax.set_xlim(0, pallet['length_mm'])
    ax.set_ylim(0, pallet['width_mm'])
    
    ax.set_title(f"Pallet {pallet_idx}: {pallet['id']}\n{len(boxes)} boxes placed")
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=sku_colors[sku_id], edgecolor='black', alpha=0.7, label=sku_id)
        for sku_id in sku_colors.keys()
    ]
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.05, 1))
    
    plt.tight_layout()
    
    if show:
        plt.show()
    
    return fig, ax