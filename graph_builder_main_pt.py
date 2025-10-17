#!/usr/bin/env python3
import math
import os
import uproot

from multiprocessing import current_process
import threading
from concurrent.futures import ThreadPoolExecutor

import hydra
from omegaconf import DictConfig, OmegaConf
from datetime import datetime
import pprint

import psutil
import numpy as np

from src.root_to_graph import RootToGraph
from src.in_memory_dataset_light_version import EasyInMemoryDataset


def worker_slice(args):
    file_path, start, stop, cfg = args
    worker = current_process().name; pid = os.getpid()
    tname = threading.current_thread().name; tid = threading.get_native_id()
    print(f"[Worker {worker} PID {pid} | Thread {tname} (id={tid})] processing slice {start} – {stop}")
    cfg['t_id'] = tid; cfg['t_subid'] = tname[-1]
    root_to_graph = RootToGraph(file_path=file_path, start=start, stop=stop, **cfg)  
    data_list, pos_data_list, meta_data_list = root_to_graph.process()
    return data_list, pos_data_list, meta_data_list

def process_in_parallel(file_path, nb_datapoints, root_to_graph_config, n_workers):
    tree_name = root_to_graph_config['tree_name']
    tree = uproot.open(file_path)[tree_name]
    total_entries = tree.num_entries
    tree.file.close()
    total_entries = min(nb_datapoints, total_entries)
    n_workers = n_workers or min(os.cpu_count(), nb_datapoints)
    chunk_size = math.ceil(total_entries / n_workers)
    print(f"Chunk size : {chunk_size}. Total processed : {chunk_size * n_workers}/{total_entries}")
    args_list = []
    for w in range(n_workers):
        start = w * chunk_size
        stop  = min((w + 1) * chunk_size, total_entries)
        if start < stop:
            args_list.append((file_path, start, stop, root_to_graph_config))
    all_data_graphs, all_pos_graphs, all_meta_graphs = [], [], []
    with ThreadPoolExecutor(max_workers=n_workers) as exe:
        for data_list, pos_list, meta_list in exe.map(worker_slice, args_list):
            all_data_graphs.extend(data_list)
            all_pos_graphs .extend(pos_list)
            all_meta_graphs.extend(meta_list)
    return all_data_graphs, all_pos_graphs, all_meta_graphs

# --- RAM MONITORING: Fonction pour afficher le résumé ---
def print_ram_summary(results: dict):
    print("\n" + "="*50)
    print("RÉSUMÉ DU MONITORING DE LA RAM")
    print("="*50)

    initial = results.get('initial_ram', 0)
    after_creation = results.get('ram_after_graph_creation', initial)
    after_saving = results.get('ram_after_saving', after_creation)

    print(f"\nRAM Initiale               : {initial:.2f} Mo")
    
    print("\n--- Phase de Création des Graphes ---")
    print(f"RAM après création         : {after_creation:.2f} Mo")
    print(f"Delta pour la création     : {after_creation - initial:+.2f} Mo")
    
    creation_steps = results.get('ram_during_creation', [])
    if creation_steps:
        print("Évolution pendant la création (après chaque fichier .root):")
        for i, (file_name, ram) in enumerate(creation_steps):
            print(f"  - Après fichier {i+1} ('{os.path.basename(file_name)}'): {ram:.2f} Mo")
        peak_ram = max(ram for _, ram in creation_steps)
        print(f"Pic de RAM atteint         : {peak_ram:.2f} Mo")

    print("\n--- Phase de Sauvegarde ---")
    print(f"RAM après sauvegarde       : {after_saving:.2f} Mo")
    print(f"Delta pour la sauvegarde   : {after_saving - after_creation:+.2f} Mo")

    print("\n" + "="*50)


@hydra.main(config_path="custom_configs", config_name="classification", version_base="1.3")
def main(config: DictConfig):
    start_time = datetime.now()
    print(f"\n\n--- Global program starting at {start_time} ---\n")

    # 1) Dump the resolved config
    cfg = OmegaConf.to_container(config, resolve=True)
    print(pprint.pformat(cfg, indent=2), end="\n\n")

    # --- RAM MONITORING: Initialisation ---
    monitoring_results = {}
    if cfg.get('monitor_ram', False):
        process = psutil.Process(os.getpid())
        monitoring_results['initial_ram'] = process.memory_info().rss / 1024**2
        monitoring_results['ram_during_creation'] = []

    # 2) Build inputs from the config
    n_workers = cfg.get('n_threads', 1)
    root_to_graph_cfg = cfg['root_to_graph']
    root_to_graph_cfg['pre_transform'] = cfg['pre_transform']
    nb_datapoints_per_file = 100_000_000 if cfg.get('nb_datapoints') is None else cfg['nb_datapoints']

    # 3) Start making the graphs for each root file
    graph_making_startime = datetime.now()
    print(f"\n--- Making the graphs : starting at {graph_making_startime} ---\n")

    all_data_graphs, all_pos_data_graphs, all_meta_data_graphs = [], [], []

    for file_name in cfg['root_file_names']:
        file_path = os.path.join(cfg['root_folder_path'], file_name)

        data_graphs, pos_data_graphs, meta_data_graphs = process_in_parallel(
            file_path=file_path,
            nb_datapoints=nb_datapoints_per_file,
            n_workers=n_workers,
            root_to_graph_config=root_to_graph_cfg,
        )

        print(f"\n\n  File {file_name}")
        print(f"  --- Len of Data & Pos Graphs created : {len(data_graphs)} | {len(pos_data_graphs)}")
        print(f"  --- Len of meta data graphs created  : {len(meta_data_graphs)}")
        
        all_data_graphs      += data_graphs
        all_pos_data_graphs  += pos_data_graphs
        all_meta_data_graphs += meta_data_graphs

        # --- RAM MONITORING: Enregistrement après chaque fichier ---
        if cfg.get('monitor_ram', False):
            current_ram = process.memory_info().rss / 1024**2
            monitoring_results['ram_during_creation'].append((file_name, current_ram))
            
    # --- RAM MONITORING: Enregistrement après la fin de la création ---
    if cfg.get('monitor_ram', False):
        monitoring_results['ram_after_graph_creation'] = process.memory_info().rss / 1024**2
            
    print(f"Total graphs created (data, pos, meta): {len(all_data_graphs), len(all_pos_data_graphs), len(meta_data_graphs)}")
    print(f"\nDone in {datetime.now() - graph_making_startime}\n")

    saving_data_startime = datetime.now()
    print(f"\n--- Saving the lists : starting at {saving_data_startime}\n")

    dataset = EasyInMemoryDataset(
        data_list=all_data_graphs,
        pos_data_list=all_pos_data_graphs,
        meta_data_list=all_meta_data_graphs,
        pre_transform=cfg['pre_transform'],
        **cfg['in_memory_dataset']
    )

    if cfg['in_memory_dataset']['load_after_process']:
        dataset.print_summary()

    # --- RAM MONITORING: Enregistrement après la sauvegarde ---
    if cfg.get('monitor_ram', False):
        monitoring_results['ram_after_saving'] = process.memory_info().rss / 1024**2

    print(f"Finished.")
    print(f"\nDone in {datetime.now() - saving_data_startime}")
    print(f"Global program runtime : {datetime.now() - start_time}")

    # --- RAM MONITORING: Affichage du rapport final ---
    if cfg.get('monitor_ram', False):
        print_ram_summary(monitoring_results)


if __name__ == "__main__":
    main()