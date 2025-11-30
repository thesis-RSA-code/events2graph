#!/usr/bin/env python3
"""
Generate job folder name from YAML config file.
Usage: python generate_job_name.py <yaml_file> [job_id]
"""

import sys
import os
import yaml
import re
from datetime import datetime

def simplify_features(pos_features):
    """Simplify position features with comprehensive mapping."""
    feature_map = {
        "hitx": "x",
        "hity": "y", 
        "hitz": "z",
        "hitt": "t",
        "charge": "q",
        "time": "t",
        "energy": "E",
    }
    
    result = []
    for feature in pos_features:
        feature = feature.strip()
        
        if feature in feature_map:
            result.append(feature_map[feature])
        elif feature.startswith("hit") and len(feature) == 4:
            # Extract letter from hitX pattern
            result.append(feature[3])
        else:
            # For unmapped features, use the original
            result.append(feature)
    
    return "".join(result)

def extract_algorithm_params(config):
    """Extract algorithm parameters for naming."""
    params = []
    
    if "algorithm_params" in config:
        alg_params = config["algorithm_params"]
        if "k" in alg_params:
            params.append(f"k{alg_params['k']}")
        elif "r" in alg_params:
            params.append(f"r{alg_params['r']}")
        # Add more parameter types as needed
    
    return "_" + "_".join(params) if params else ""

def extract_metric_info(config):
    """Extract metric information for naming."""
    metric_parts = []
    
    if "metric" in config and config["metric"] is not None:
        metric = config["metric"]
        if metric == "spacetime":
            metric_parts.append("st")
        elif metric == "euclidean_3d":
            metric_parts.append("e3d")
        elif metric == "weighted_euclidean":
            metric_parts.append("we")
        else:
            metric_parts.append(metric)
    
    # Add metric parameters if any
    if "metric_params" in config and config["metric_params"] is not None:
        metric_params = config["metric_params"]
        # Add specific metric parameter handling here
    
    return "_" + "_".join(metric_parts) if metric_parts else ""

def extract_particle_info(h5_file_path):
    """Extract particle type and energy range from H5 file path."""
    # Extract particle type from path like: .../Datasets/custom_dataset/e-/50-1500MeV/...
    particle_match = re.search(r'Datasets/custom_dataset/([^/]+)/', h5_file_path)
    particle_type = particle_match.group(1) if particle_match else "unknown"
    
    # Extract energy range like: 50-1500MeV
    energy_match = re.search(r'(\d+-\d+MeV)', h5_file_path)
    energy_range = energy_match.group(1) if energy_match else None
    
    return particle_type, energy_range

def extract_cuts_info(config):
    """Extract cut information from node_selection."""
    cuts = []
    
    if "node_selection" in config and config["node_selection"] is not None:
        node_sel = config["node_selection"]
        
        # Extract time cut
        if "time_cut" in node_sel and node_sel["time_cut"] is not None:
            time_cut = node_sel["time_cut"]
            if "min" in time_cut and "max" in time_cut:
                min_val = int(time_cut["min"]) if isinstance(time_cut["min"], (int, float)) else time_cut["min"]
                max_val = int(time_cut["max"]) if isinstance(time_cut["max"], (int, float)) else time_cut["max"]
                cuts.append(f"t{min_val}-{max_val}")
        
        # Extract charge cut
        if "charge_cut" in node_sel and node_sel["charge_cut"] is not None:
            charge_cut = node_sel["charge_cut"]
            if "min" in charge_cut and "max" in charge_cut:
                # Format charge values without decimal points (0.3 -> 03, 1.5 -> 15)
                min_val = charge_cut["min"]
                max_val = charge_cut["max"]
                
                # Convert to string and remove decimal point
                min_str = str(min_val).replace(".", "")
                max_str = str(int(max_val)) if isinstance(max_val, (int, float)) and max_val == int(max_val) else str(max_val).replace(".", "")
                
                cuts.append(f"q{min_str}-{max_str}")
    
    return "_" + "_".join(cuts) if cuts else ""

def generate_job_name(yaml_file, job_id=None):
    """Generate job folder name from YAML config."""
    try:
        with open(yaml_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Extract basic info
        algorithm = config.get("algorithm", "unknown")
        pos_features_raw = config.get("pos_features", [])
        h5_file_path = config.get("h5_data_file", "")
        
        # Simplify position features
        pos_features = simplify_features(pos_features_raw)
        
        # Extract algorithm parameters
        algorithm_params = extract_algorithm_params(config)
        
        # Extract metric information
        metric_info = extract_metric_info(config)
        
        # Extract particle info
        particle_type, energy_range = extract_particle_info(h5_file_path)
        
        # Extract cuts info
        cuts_info = extract_cuts_info(config)
        
        # Generate date and time with milliseconds (YYMMDD_HHMM_ms_XXX format)
        now = datetime.now()
        date_part = now.strftime("%y%m%d")  # 251019
        time_part = now.strftime("%H%M")    # 1430
        milliseconds = now.microsecond // 1000  # Convert microseconds to milliseconds (0-999)
        
        # Build job folder name
        # Format: YYMMDD_HHMM_ms_XXX_algorithm_params_posfeatures_metric_particle_energy_cuts
        job_parts = [f"{date_part}_{time_part}_ms_{milliseconds:03d}"]

        job_parts.append(f"{algorithm}{algorithm_params}")
        job_parts.append(pos_features)
        
        if metric_info:
            job_parts.append(metric_info[1:])  # Remove leading underscore
        
        job_parts.append(particle_type)
        
        if energy_range:
            job_parts.append(energy_range)
        
        if cuts_info:
            job_parts.append(cuts_info[1:])  # Remove leading underscore
        
        job_name = "_".join(job_parts)
        
        return job_name
        
    except Exception as e:
        print(f"Error processing YAML file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python generate_job_name.py <yaml_file> [job_id]", file=sys.stderr)
        sys.exit(1)
    
    yaml_file = sys.argv[1]
    job_id = sys.argv[2] if len(sys.argv) == 3 else None
    
    job_name = generate_job_name(yaml_file, job_id)
    print(job_name)