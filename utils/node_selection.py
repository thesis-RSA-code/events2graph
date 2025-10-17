"""
Simple node selection utility for filtering PMT hits based on time and charge criteria.
"""

import numpy as np
import h5py
from typing import Dict, Optional, Tuple
from scipy.optimize import curve_fit
from scipy.stats import moyal


def landau(x, amp, loc, scale):
    """Landau distribution (using Moyal approximation)."""
    return amp * moyal.pdf(x, loc, scale)


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
    
    def check_data_requirements(self, event_group: h5py.Group) -> bool:
        """Check if event has required data (time and charge)."""
        has_time = any(key in event_group for key in ['pmt_time', 'time'])
        has_charge = any(key in event_group for key in ['pmt_charge', 'charge'])
        return has_time and has_charge
    
    def get_mask(self, event_group: h5py.Group) -> np.ndarray:
        """
        Get boolean mask for filtering based on time and charge cuts.
        
        Args:
            event_group: HDF5 group containing event data
            
        Returns:
            Boolean mask [N] where True means keep the node
        """
        # Extract time and charge from event group
        time_key = 'pmt_time' if 'pmt_time' in event_group else 'time'
        charge_key = 'pmt_charge' if 'pmt_charge' in event_group else 'charge'
        
        time = event_group[time_key][:]
        charge = event_group[charge_key][:]
        
        mask = np.ones(len(time), dtype=bool)
        
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
        
        return mask


class PercentileTimeSelection:
    """
    Node selection based on percentile cuts on time data.
    Can use either raw data percentiles or fit a Landau distribution first.
    """
    
    def __init__(self,
                 lower_percentile: float = 5.0,
                 upper_percentile: float = 90.0,
                 use_landau_fit: bool = True):
        """
        Initialize percentile-based time selection.
        
        Args:
            lower_percentile: Lower percentile threshold (e.g., 5 for 5th percentile)
            upper_percentile: Upper percentile threshold (e.g., 90 for 90th percentile)
            use_landau_fit: If True, fit Landau to time distribution before computing percentiles.
                           If False, compute percentiles directly from raw data.
        """
        self.lower_percentile = lower_percentile
        self.upper_percentile = upper_percentile
        self.use_landau_fit = use_landau_fit
    
    def check_data_requirements(self, event_group: h5py.Group) -> bool:
        """Check if event has required data (time only)."""
        return any(key in event_group for key in ['pmt_time', 'time'])
    
    def get_mask(self, event_group: h5py.Group) -> np.ndarray:
        """
        Get boolean mask for filtering based on percentile time cuts.
        
        Args:
            event_group: HDF5 group containing event data
            
        Returns:
            Boolean mask [N] where True means keep the node
        """
        # Extract time from event group
        time_key = 'pmt_time' if 'pmt_time' in event_group else 'time'
        time = event_group[time_key][:]
        
        # Compute time cuts (from Landau fit or raw data)
        time_min, time_max = self.compute_percentile_cuts(time)
        
        if time_min is None or time_max is None:
            # Fitting failed, return all True (keep everything)
            print("Warning: Percentile computation failed, keeping all nodes")
            return np.ones(len(time), dtype=bool)
        
        # Create mask based on time cuts
        mask = (time >= time_min) & (time <= time_max)
        
        return mask
    
    def compute_percentile_cuts(self, time: np.ndarray) -> Tuple[Optional[float], Optional[float]]:
        """
        Compute percentile-based time cuts from either raw data or Landau fit.
        
        Args:
            time: Time values [N]
            
        Returns:
            Tuple of (time_min, time_max) based on percentiles, or (None, None) if failed
        """
        if not self.use_landau_fit:
            # Use raw data percentiles directly
            time_min = np.percentile(time, self.lower_percentile)
            time_max = np.percentile(time, self.upper_percentile)
            return time_min, time_max
        
        # Fit Landau to time distribution
        try:
            counts, bins = np.histogram(time, bins=100)
            bin_centers = (bins[:-1] + bins[1:]) / 2
            
            # Initial guess for Landau parameters
            p0 = [counts.max(), np.median(time), np.std(time)]
            params, _ = curve_fit(landau, bin_centers, counts, p0=p0, maxfev=5000)
            
            # Generate samples from fitted Landau distribution
            fitted_samples = moyal.rvs(loc=params[1], scale=params[2], size=10000)
            
            # Compute percentiles from fitted distribution
            time_min = np.percentile(fitted_samples, self.lower_percentile)
            time_max = np.percentile(fitted_samples, self.upper_percentile)
            
            return time_min, time_max

        except Exception as e:
            print(f"Warning: Landau fit failed ({e}), using raw percentiles")
            raise ValueError(f"Landau fit failed ({e})")
            # # Fall back to raw data percentiles
            # time_min = np.percentile(time, self.lower_percentile)
            # time_max = np.percentile(time, self.upper_percentile)
            # return time_min, time_max


