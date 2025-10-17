"""
Edge index generator that creates HDF5 files containing only edge_index data
for different graph construction configurations.
"""

import h5py
import numpy as np
import argparse
import os
import psutil
from pathlib import Path
import yaml
import time
from tqdm import tqdm

import sys
sys.path.append(str(Path(__file__).parent / "utils"))
from edge_builder import EdgeBuilder
from node_selection import NodeSelection, PercentileTimeSelection
from selection_compose import SelectionCompose


def print_summary(results: dict):
    """Display a summary of collected monitoring data."""
    print("\n" + "="*50)
    print("MONITORING SUMMARY")
    print("="*50)

    # Section 1: Data loading
    ram_before = results.get('ram_before_load', 0)
    print("\n--- Loading Phase ---")
    print(f"RAM before loading : {ram_before:.2f} MB")

    # Section 2: Event processing loop
    loop_data = results.get('ram_during_loop', [])
    print("\n--- Processing Phase (Loop) ---")
    if not loop_data:
        print("No RAM data was collected during the loop.")
    else:
        num_samples = len(loop_data)
        # Extract RAM values
        ram_values = [ram for idx, ram in loop_data]
        
        print(f"Number of RAM samples taken : {num_samples}")
        print(f"RAM at start of loop        : {ram_values[0]:.2f} MB (event #{loop_data[0][0]})")
        print(f"Maximum RAM reached        : {max(ram_values):.2f} MB")
        print(f"RAM at end of loop         : {ram_values[-1]:.2f} MB (event #{loop_data[-1][0]})")
        
        print(f"Delta with max RAM      : {max(ram_values) - ram_before:+.2f} MB")  

    print("\n" + "="*50)


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def generate_edge_config_name(algorithm: str, algorithm_params: dict = None, pos_features: str = None, metric: str = None) -> str:
    """
    Generate a simple name for the edge_index dataset.
    Since each config gets its own file, we can keep it simple.
    """
    return "edge_index"


def main(args):
    if not args.h5_data_file.exists():
        raise FileNotFoundError(f"HDF5 file '{args.h5_data_file}' not found.")

    if 'pyg' in args.algorithm:
        import torch 

    # Monitoring setup
    monitoring_results = {}
    if args.monitor_ram:
        process = psutil.Process(os.getpid())
        monitoring_results['ram_before_load'] = process.memory_info().rss / 1024**2
            
    print(f"\nPreparing to generate edge indices...")
    print(f"Algorithm: {args.algorithm}")
    print(f"Using device {'cuda' if torch.cuda.is_available() else 'cpu'}")
    print(f"Metric: {args.metric}")
    print(f"Pos features: {args.pos_features}")
    print(f"Combine files: {args.combine_files}")
    print(f"Node selection: {args.node_selection}")
    edge_process_time_per_event = []
    
    # Create node selection compose if specified
    selection_compose = None
    if args.node_selection is not None:
        selections = []
        
        # Support both single selection and list of selections
        selection_configs = args.node_selection if isinstance(args.node_selection, list) else [args.node_selection]
        
        for sel_config in selection_configs:
            selection_type = sel_config.get('type', 'fixed')
            
            if selection_type == 'percentile':
                selection = PercentileTimeSelection(
                    lower_percentile=sel_config.get('lower_percentile', 5.0),
                    upper_percentile=sel_config.get('upper_percentile', 90.0),
                    use_landau_fit=sel_config.get('use_landau_fit', True)
                )
                print(f"Added PercentileTimeSelection: {sel_config.get('lower_percentile', 5.0)}-{sel_config.get('upper_percentile', 90.0)}%, Landau={sel_config.get('use_landau_fit', True)}")
            else:
                selection = NodeSelection(
                    time_cut=sel_config.get('time_cut'),
                    charge_cut=sel_config.get('charge_cut')
                )
                print(f"Added NodeSelection: time={sel_config.get('time_cut')}, charge={sel_config.get('charge_cut')}")
            
            selections.append(selection)
        
        selection_compose = SelectionCompose(selections)
        print(f"\nCreated SelectionCompose with {len(selections)} selection(s)")
    
    # Create edge builder
    edge_builder = EdgeBuilder(
        algorithm=args.algorithm,
        metric=args.metric,
        algorithm_params=args.algorithm_params,
        metric_params=args.metric_params
    )
    
    # Generate edge dataset name (simplified since each config gets its own file)
    print(f"Edges will be saved as direct event datasets: event_1, event_2, etc.")

    if args.combine_files:
        # Single file approach: modify the data file in place
        print(f"Using single file approach: modifying '{args.h5_data_file}'")
        target_file = args.h5_data_file
        file_mode = 'a'
    else:
        # Two file approach: create separate edge file
        print(f"Using two file approach: creating '{args.output_file}'")
        target_file = args.output_file
        file_mode = 'a' if args.output_file.exists() else 'w'

    # Open HDF5 files
    with h5py.File(args.h5_data_file, 'r', libver='latest', swmr=False) as data_file, \
         h5py.File(target_file, file_mode) as target_h5_file:
        

        # check if all the required features are present in the data file
        event_0 = data_file['event_0']
        for feature in args.pos_features:
            if feature not in event_0:
                raise ValueError(f"Feature '{feature}' not found in data file. Please check the data file and the config file.")
            
        if selection_compose is not None:
            if not selection_compose.check_data_requirements(event_0):
                raise ValueError(f"Required data not found in event_0. Please check the data file and the config file.")

        # Store configuration as file attributes
        target_h5_file.attrs['algorithm'] = args.algorithm
        target_h5_file.attrs['metric'] = str(args.metric) if args.metric is not None else "none"
        target_h5_file.attrs['algorithm_params'] = str(args.algorithm_params)
        target_h5_file.attrs['metric_params'] = str(args.metric_params)
        target_h5_file.attrs['pos_features'] = str(args.pos_features)
        target_h5_file.attrs['combine_files'] = args.combine_files
        target_h5_file.attrs['node_selection'] = str(args.node_selection) if args.node_selection is not None else "none"

        event_names = [name for name in data_file.keys() if name.startswith('event_')]
        event_names.sort(key=lambda x: int(x.split('_')[1]))
        total_events = len(event_names)

        for event_idx, event_name in enumerate(tqdm(event_names, desc="Generating edge indices")):
            
            # Monitor RAM if requested
            if args.monitor_ram and event_idx % args.monitor_interval == 0:
                current_ram = process.memory_info().rss / 1024**2
                monitoring_results['ram_during_loop'] = monitoring_results.get('ram_during_loop', [])
                monitoring_results['ram_during_loop'].append((event_idx, current_ram))

            data_event_group = data_file[event_name]

            # Check if this edge dataset already exists and skip if not overwriting
            if event_name in target_h5_file and not args.overwrite:
                continue

            # Extract raw edge coordinates from data file
            raw_edge_coords = []
            for feature in args.pos_features:
                raw_edge_coords.append(data_event_group[feature][:])
            
            # Stack all features together
            raw_edge_coords = np.stack(raw_edge_coords, axis=1)

            # Apply node selection filtering if specified
            if selection_compose is not None:
                filtered_coords = selection_compose(raw_edge_coords, data_event_group)
                selection_mask = selection_compose.last_mask  # Get the stored mask
                
                if len(filtered_coords) == 0:
                    print(f"Warning: No nodes remain after filtering in {event_name}. Event skipped.")
                    continue
            else:
                filtered_coords = raw_edge_coords
                selection_mask = None

            # Generate edge index using EdgeBuilder
            start_time = time.time()
            edge_index = edge_builder.compute_edge_index(filtered_coords)

            if args.use_timeit:
                edge_process_time_per_event.append(time.time() - start_time)

            # Remove existing datasets if overwriting
            if event_name in target_h5_file:
                del target_h5_file[event_name]
            mask_name = f"{event_name}_mask"
            if mask_name in target_h5_file:
                del target_h5_file[mask_name]
                
            # Save edge index
            target_h5_file.create_dataset(
                event_name, 
                data=edge_index, 
                compression=args.compression
            )
            
            # Save selection mask if selection was applied
            if selection_mask is not None:
                target_h5_file.create_dataset(
                    mask_name,
                    data=selection_mask.astype(np.uint8),  # Save as uint8 to save space
                    compression=args.compression
                )
            
    if args.combine_files:
        print(f"\nProcessing completed. File '{args.h5_data_file}' enriched with edge indices.")
    else:
        print(f"\nProcessing completed. Edge file '{args.output_file}' created with edge indices.")
    
    # Print monitoring summary if requested
    if args.monitor_ram:
        print_summary(monitoring_results)
    
    # Print timing summary if requested
    if args.use_timeit and edge_process_time_per_event:
        avg_time = np.mean(edge_process_time_per_event)
        print(f"\nAverage edge processing time per event: {avg_time:.4f} seconds")
        print(f"Total events processed: {len(edge_process_time_per_event)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate edge indices and save them in an HDF5 file.")
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML configuration file.")
    
    args = parser.parse_args()
    
    # Load YAML config
    config = load_config(args.config)
    
    # Create args object for main function
    class Args:
        def __init__(self, config_dict):
            self.h5_data_file = Path(config_dict['h5_data_file'])
            
            # Handle output file generation
            output_file_config = config_dict.get('output_file', '')
            if not output_file_config:
                # No output file specified, generate based on config
                self.output_file = self._generate_output_filename(config_dict)
            elif Path(output_file_config).is_dir():
                # Directory specified, generate filename in that directory
                self.output_file = Path(output_file_config) / self._generate_output_filename(config_dict).name
            else:
                # Full path specified
                self.output_file = Path(output_file_config)

            # Create output file directory if it doesn't exist
            if not self.output_file.exists():
                if not self.output_file.parent.exists():
                    self.output_file.parent.mkdir(parents=True, exist_ok=True)
            
            self.combine_files = config_dict.get('combine_files', False)
            self.algorithm = config_dict['algorithm']  # 'knn_pyg', 'knn_scipy', 'delaunay', 'radius'
            self.metric = config_dict.get('metric')  # 'spacetime', 'euclidean_3d', 'weighted_euclidean', or None
            self.algorithm_params = config_dict.get('algorithm_params', {})
            self.metric_params = config_dict.get('metric_params', {})
            self.pos_features = config_dict.get('pos_features', ['x', 'y', 'z'])
            self.compression = config_dict.get('compression', 'gzip')
            self.use_timeit = config_dict.get('use_timeit', False)
            self.monitor_ram = config_dict.get('monitor_ram', False)
            self.monitor_interval = config_dict.get('monitor_interval', 10)
            self.overwrite = config_dict.get('overwrite', False)
            self.node_selection = config_dict.get('node_selection', None)
        
        def _generate_output_filename(self, config_dict):
            """Generate output filename based on configuration parameters."""
            # Get base name from input file
            base_name = self.h5_data_file.stem
            
            # Generate edge config name (similar to generate_edge_config_name function)
            algorithm = config_dict['algorithm']
            algorithm_params = config_dict.get('algorithm_params', {})
            pos_features = config_dict.get('pos_features', ['x', 'y', 'z'])
            metric = config_dict.get('metric')
            
            config_name = f"edges_{algorithm}"
            
            # Add algorithm parameters
            if algorithm_params:
                for key, value in sorted(algorithm_params.items()):
                    value_str = int(value) if isinstance(value, float) and value.is_integer() else value
                    config_name += f"_{key}{value_str}"
            
            # Add position features
            if pos_features:
                config_name += "_posfeat_"
                for feature in pos_features:
                    config_name += f"{feature}"
            
            # Add metric
            if metric:
                config_name += f"_{metric}"
            
            # Add node selection parameters
            node_selection = config_dict.get('node_selection')
            if node_selection:
                config_name += "_nodesel"
                if node_selection.get('time_cut'):
                    time_cut = node_selection['time_cut']
                    if 'min' in time_cut:
                        config_name += f"_tmin{time_cut['min']}"
                    if 'max' in time_cut:
                        config_name += f"_tmax{time_cut['max']}"
                if node_selection.get('charge_cut'):
                    charge_cut = node_selection['charge_cut']
                    if 'min' in charge_cut:
                        config_name += f"_qmin{charge_cut['min']}"
                    if 'max' in charge_cut:
                        config_name += f"_qmax{charge_cut['max']}"
            
            # Create final filename
            filename = f"{base_name}_{config_name}.h5"
            return Path(filename)
    
    parsed_args = Args(config)
    main(parsed_args)