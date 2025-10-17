#!/usr/bin/env python3
"""
Generate job folder name from YAML config file.
Usage: python generate_job_name.py <yaml_file>
"""

import sys
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

def generate_job_name(yaml_file):
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
        
        # Generate date prefix
        date_prefix = datetime.now().strftime("%y_%m_%d_%H_%M")
        
        # Build job folder name
        # Format: date_algorithm_params_posfeatures_metric_particle_energy
        job_parts = [date_prefix, f"{algorithm}{algorithm_params}", pos_features]
        
        if metric_info:
            job_parts.append(metric_info[1:])  # Remove leading underscore
        
        job_parts.append(particle_type)
        
        if energy_range:
            job_parts.append(energy_range)
        
        job_name = "_".join(job_parts)
        
        return job_name
        
    except Exception as e:
        print(f"Error processing YAML file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_job_name.py <yaml_file>", file=sys.stderr)
        sys.exit(1)
    
    yaml_file = sys.argv[1]
    job_name = generate_job_name(yaml_file)
    print(job_name)