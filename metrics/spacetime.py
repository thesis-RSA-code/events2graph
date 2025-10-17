
import numpy as np
from typing import Dict, Any, Optional
from sklearn.preprocessing import StandardScaler

from utils.physical_values import SPEED_OF_LIGHT, N_PURE_WATER, WCSIM_TRIGGER_TIME_OFFSET

SPEED_OF_LIGHT_IN_WATER_20degree_cm_per_ns = SPEED_OF_LIGHT * (1e2 / 1e9) / N_PURE_WATER


def process_coords_spacetime(coords: np.ndarray, use_std_scaler: bool = False, spatial_weight: float = 1.0, temporal_weight: float = 1.0) -> np.ndarray:
    """
    Process coordinates using spacetime metric combining spatial and temporal distances.
    
    Args:
        coords: Coordinate array [N, 4] (x, y, z, t)
        spatial_weight: Weight for spatial component
        temporal_weight: Weight for temporal component
        
    Returns:
        Processed coordinates [N, 3] with spacetime transformation
    """
    if coords.shape[1] != 4:
        raise ValueError("Spacetime metric requires 4D coordinates (x, y, z, t)")
    
    # Create a copy to avoid modifying the original
    coords_copy = coords.copy()
    
    # Convert time to spatial units using speed of light in water
    coords_copy[:, 3:4] = ( coords_copy[:, 3:4] - WCSIM_TRIGGER_TIME_OFFSET ) * SPEED_OF_LIGHT_IN_WATER_20degree_cm_per_ns
    if use_std_scaler:
        coords_copy = StandardScaler().fit_transform(coords_copy)
    else:
        coords_copy = coords_copy

    # Combine spatial and temporal components with weights
    spacetime_coords = spatial_weight * coords_copy[:, :3] + temporal_weight * coords_copy[:, 3:4]
    
    return spacetime_coords
