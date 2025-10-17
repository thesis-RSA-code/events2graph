"""
Simple node selection utility for filtering PMT hits based on time and charge criteria.
"""

import numpy as np
from typing import Dict, Optional


class NodeSelection:
    """
    Simple node selection class that filters PMT hits based on time and charge criteria.
    """
    
    def __init__(self, 
                 time_cut: Optional[Dict[str, float]] = None,
                 charge_cut: Optional[Dict[str, float]] = None):
        """
        Initialize the node selection filter.
        
        Args:
            time_cut: Time filtering criteria {'min': float, 'max': float}
            charge_cut: Charge filtering criteria {'min': float, 'max': float}
        """
        self.time_cut = time_cut
        self.charge_cut = charge_cut
    
    def apply_selection(self, coordinates: np.ndarray, time: np.ndarray, charge: np.ndarray) -> np.ndarray:
        """
        Apply filtering and return filtered coordinates.
        
        Args:
            coordinates: Node coordinates [N, D]
            time: Time values [N] 
            charge: Charge values [N]
            
        Returns:
            Filtered coordinates [M, D] where M <= N
        """
        mask = np.ones(len(coordinates), dtype=bool)
        
        # Apply time cut
        if self.time_cut is not None:
            if 'min' in self.time_cut:
                mask &= (time >= self.time_cut['min'])
            if 'max' in self.time_cut:
                mask &= (time <= self.time_cut['max'])
        
        # Apply charge cut  
        if self.charge_cut is not None:
            if 'min' in self.charge_cut:
                mask &= (charge >= self.charge_cut['min'])
            if 'max' in self.charge_cut:
                mask &= (charge <= self.charge_cut['max'])
        
        return coordinates[mask]
    
    def __call__(self, coordinates: np.ndarray, time: np.ndarray, charge: np.ndarray) -> np.ndarray:
        """Alias for apply_selection for backward compatibility."""
        return self.apply_selection(coordinates, time, charge)
