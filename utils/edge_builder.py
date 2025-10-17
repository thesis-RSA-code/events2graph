"""
Edge builder utility class that handles metric transformation and graph building.
"""

import numpy as np
import sys
from pathlib import Path

from graph_builders import knn_scipy, delaunay, radius, knn_pyg

from metrics.spacetime import process_coords_spacetime
from metrics.weighted_euclidian import process_coords_weighted_euclidean



# Graph builder registry
GRAPH_BUILDERS = {
    "knn_scipy": knn_scipy.build_edges,
    "delaunay": delaunay.build_edges,
    "radius": radius.build_edges,
    "knn_pyg": knn_pyg.build_edges,
}

# Registry of available metrics
METRIC_REGISTRY = {
    'spacetime': process_coords_spacetime,
    'weighted_euclidean': process_coords_weighted_euclidean,
}


class EdgeBuilder:
    """
    Edge builder class that handles metric transformation and graph building.
    """
    
    def __init__(self, algorithm: str, metric: str = None, algorithm_params: dict = None, metric_params: dict = None):
        """
        Initialize the edge builder.
        
        Args:
            algorithm: Graph building algorithm ('knn_pyg', 'knn_scipy', 'delaunay', 'radius')
            metric: Metric transformation ('spacetime', 'euclidean_3d', etc.) or None for no transformation
            algorithm_params: Parameters for the algorithm (e.g., {'k': 5})
            metric_params: Parameters for the metric transformation
        """
        self.algorithm = algorithm
        self.metric = metric
        self.algorithm_params = algorithm_params or {}
        self.metric_params = metric_params or {}
        
        # Get graph builder function
        self.graph_builder = GRAPH_BUILDERS.get(algorithm)
        if self.graph_builder is None:
            raise ValueError(f"Unknown algorithm '{algorithm}'. Available algorithms: {list(GRAPH_BUILDERS.keys())}")
        
        # Get metric function (if specified)
        self.metric_func = None
        if metric is not None:
            self.metric_func = METRIC_REGISTRY.get(metric)
            if self.metric_func is None:
                raise ValueError(f"Unknown metric '{metric}'. Available metrics: {list(METRIC_REGISTRY.keys())}")
    
    def compute_edge_index(self, raw_edge_coords: np.ndarray) -> np.ndarray:
        """
        Compute edge index from raw coordinates.
        
        Args:
            raw_edge_coords: Raw coordinate data [N, D] from H5 file
            
        Returns:
            Edge index array [2, num_edges]
        """
        # Apply metric transformation if specified
        if self.metric_func is not None:
            edge_coords = self.metric_func(raw_edge_coords, **self.metric_params)
        else:
            # No metric transformation - use raw coordinates
            edge_coords = raw_edge_coords
        
        # Generate edge index using the graph builder
        edge_index = self.graph_builder(edge_coords, **self.algorithm_params)
        
        return edge_index
