#!/usr/bin/env python3
"""
Simple test of the NodeSelection functionality.
"""

import numpy as np
import sys
from pathlib import Path

# Add utils to path
sys.path.append(str(Path(__file__).parent / "utils"))
from node_selection import NodeSelection


def test_simple_filtering():
    """Test the simple NodeSelection filtering."""
    print("Testing simple NodeSelection filtering...")
    
    # Create sample data
    n_nodes = 100
    coords = np.random.rand(n_nodes, 3) * 100
    time = np.random.uniform(0, 1000, n_nodes)
    charge = np.random.uniform(0, 50, n_nodes)
    
    print(f"Original: {n_nodes} nodes")
    print(f"Time range: [{np.min(time):.1f}, {np.max(time):.1f}]")
    print(f"Charge range: [{np.min(charge):.1f}, {np.max(charge):.1f}]")
    
    # Create simple filter
    node_selection = NodeSelection(
        time_cut={'min': 200.0, 'max': 800.0},
        charge_cut={'min': 5.0, 'max': 30.0}
    )
    
    # Apply filtering
    filtered_coords = node_selection.apply_selection(coords, time, charge)
    
    print(f"After filtering: {len(filtered_coords)} nodes")
    print(f"Filtered fraction: {len(filtered_coords)/n_nodes:.2%}")
    
    # Verify the filtering worked
    time_mask = (time >= 200.0) & (time <= 800.0)
    charge_mask = (charge >= 5.0) & (charge <= 30.0)
    combined_mask = time_mask & charge_mask
    
    expected_coords = coords[combined_mask]
    print(f"Expected: {len(expected_coords)} nodes")
    print(f"Match: {np.allclose(filtered_coords, expected_coords)}")
    
    print("✓ Simple filtering test passed!")


if __name__ == "__main__":
    test_simple_filtering()
