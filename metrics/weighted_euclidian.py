
import numpy as np
from typing import Dict, Any, Optional


def process_coords_weighted_euclidean(coords: np.ndarray, weights: np.ndarray = None) -> np.ndarray:
    """Weighted Euclidean distance with different weights for each dimension."""
    if weights is None:
        weights = np.ones(coords.shape[1])
    
    if len(weights) != coords.shape[1]:
        raise ValueError(f"Weights length {len(weights)} doesn't match coordinate dimensions {coords.shape[1]}")
    
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    weighted_diff = diff * weights
    return np.sqrt(np.sum(weighted_diff**2, axis=2))
