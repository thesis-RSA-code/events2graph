"""
Selection composition utility for chaining multiple node selection filters.
Similar to torchvision.transforms.Compose or torch_geometric.transforms.Compose.
"""

import h5py
import numpy as np
from typing import List, Optional


class SelectionCompose:
    """
    Composes several selection transforms together.
    Each selection is applied sequentially: coords -> selection1 -> selection2 -> ... -> final_coords
    """
    
    def __init__(self, selections: List):
        """
        Initialize composition of selections.
        
        Args:
            selections: List of selection objects (NodeSelection, PercentileTimeSelection, etc.)
        """
        self.selections = selections
        self.last_mask = None  # Store the last computed mask
    
    def check_data_requirements(self, event_group: h5py.Group) -> bool:
        """
        Check if the event group has all required data for all selections.
        
        Args:
            event_group: HDF5 group containing event data
            
        Returns:
            True if all requirements are met, False otherwise
        """
        for selection in self.selections:
            if hasattr(selection, 'check_data_requirements'):
                if not selection.check_data_requirements(event_group):
                    return False
        return True
    
    def get_combined_mask(self, event_group: h5py.Group, n_nodes: int) -> np.ndarray:
        """
        Get the combined mask from all selections.
        
        Args:
            event_group: HDF5 group containing event data
            n_nodes: Number of nodes in the original data
            
        Returns:
            Boolean mask [N] combining all selections
        """
        cumulative_mask = np.ones(n_nodes, dtype=bool)
        
        # Apply each selection and build cumulative mask
        for selection in self.selections:
            mask = selection.get_mask(event_group)
            cumulative_mask &= mask
        
        self.last_mask = cumulative_mask  # Store for later access
        return cumulative_mask
    
    def __call__(self, coordinates, event_group: h5py.Group):
        """
        Apply all selections sequentially using cumulative masking.
        Each selection creates a mask based on ORIGINAL event_group data,
        then we combine all masks and apply once at the end.
        
        Args:
            coordinates: Initial node coordinates [N, D]
            event_group: HDF5 group containing event data (for extracting time, charge, etc.)
            
        Returns:
            Filtered coordinates after all selections [M, D] where M <= N
        """
        n_nodes = len(coordinates)
        cumulative_mask = self.get_combined_mask(event_group, n_nodes)
        
        return coordinates[cumulative_mask]
    
    def __repr__(self):
        format_string = self.__class__.__name__ + '('
        for selection in self.selections:
            format_string += '\n'
            format_string += f'    {selection}'
        format_string += '\n)'
        return format_string

