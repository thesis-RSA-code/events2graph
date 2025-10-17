import uproot
import awkward as ak
import numpy as np
import time
import argparse
import os
import psutil
from pathlib import Path

# Import des modules de construction de graphe (inchangé)
import graph_builders.knn as knn_builder
import graph_builders.delaunay as delaunay_builder
import graph_builders.radius as radius_builder
import graph_builders.knn_pyg as knn_pyg_builder

GRAPH_BUILDERS = {
    "knn": knn_builder.build_edges,
    "delaunay": delaunay_builder.build_edges,
    "radius": radius_builder.build_edges,
    "knn_pyg": knn_pyg_builder.build_edges,
}

def load_data(file_path, tree_name, feature_vars):
    """Charge les données depuis un fichier ROOT en utilisant uproot et awkward."""
    print(f"Chargement des données depuis '{file_path}' (tree: '{tree_name}')...")
    with uproot.open(file_path) as file:
        tree = file[tree_name]
        data = tree.arrays(feature_vars, library="ak")
    print(f"Chargement terminé. {len(data)} événements trouvés.")
    return data

def print_summary(results: dict):
    """Affiche un résumé des données de monitoring collectées."""
    print("\n" + "="*50)
    print("RÉSUMÉ DU MONITORING")
    print("="*50)

    # Section 1: Chargement des données
    ram_before = results.get('ram_before_load', 0)
    ram_after = results.get('ram_after_load', 0)
    print("\n--- Phase de Chargement ---")
    print(f"RAM avant chargement : {ram_before:.2f} Mo")
    print(f"RAM après chargement  : {ram_after:.2f} Mo")
    print(f"Delta                 : {ram_after - ram_before:+.2f} Mo")

    # Section 2: Boucle de traitement des événements
    loop_data = results.get('ram_during_loop', [])
    print("\n--- Phase de Traitement (Boucle) ---")
    if not loop_data:
        print("Aucune donnée de RAM n'a été collectée pendant la boucle.")
    else:
        num_samples = len(loop_data)
        # Extraire les valeurs de RAM
        ram_values = [ram for idx, ram in loop_data]
        
        print(f"Nombre d'échantillons de RAM pris : {num_samples}")
        print(f"RAM au début de la boucle        : {ram_values[0]:.2f} Mo (événement #{loop_data[0][0]})")
        print(f"RAM maximale atteinte            : {max(ram_values):.2f} Mo")
        print(f"RAM à la fin de la boucle          : {ram_values[-1]:.2f} Mo (événement #{loop_data[-1][0]})")

    print("\n" + "="*50)

def main(args):

    # Validation des arguments (inchangé)
    if not args.input_file.exists():
        raise FileNotFoundError(f"Le fichier d'entrée n'a pas été trouvé : {args.input_file}")
    if args.method not in GRAPH_BUILDERS:
        raise ValueError(f"Méthode '{args.method}' non reconnue.")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Initialisation du monitoring
    monitoring_results = {}
    process = psutil.Process(os.getpid()) if args.monitor_ram else None

    # --- Étape 1: Suivi du chargement des données ---
    if args.monitor_ram:
        monitoring_results['ram_before_load'] = process.memory_info().rss / 1024**2

    # On évite les doublons avec list(dict.fromkeys(...))
    all_vars_to_load = list(dict.fromkeys(args.node_features + args.edge_features + ["n_hits"]))
    events_data = load_data(args.input_file, args.tree_name, all_vars_to_load)
    
    if args.monitor_ram:
        monitoring_results['ram_after_load'] = process.memory_info().rss / 1024**2
        monitoring_results['ram_during_loop'] = []

    # --- Étape 2: Traitement et suivi en boucle ---
    print(f"\nDébut du traitement de {len(events_data)} événements...")
    
    edge_process_time_per_event = []
    for event_idx, event in enumerate(events_data):
        # Limiter le nombre d'événements pour les tests
        if event_idx % 100 == 0:
            print(f"--- Traitement de l'événement {event_idx} ---")
            
        # Suivi de la RAM à intervalle régulier
        if args.monitor_ram and event_idx % args.monitor_interval == 0:
            current_ram = process.memory_info().rss / 1024**2
            monitoring_results['ram_during_loop'].append((event_idx, current_ram))

        # Le reste du traitement est silencieux pour ne pas polluer la sortie
        if event["n_hits"] == 0:
            continue
            
        node_features = np.stack([ak.to_numpy(event[var]) for var in args.node_features], axis=-1)
        edge_coords = np.stack([ak.to_numpy(event[var]) for var in args.edge_features], axis=-1)
        
        build_edges_func = GRAPH_BUILDERS[args.method]
        
        start_time = time.time()
        method_params = {'k': args.k, 'r': args.r} 
        edge_index = build_edges_func(edge_coords, **method_params)
        end_time = time.time()

        if args.use_timeit:
            elapsed = end_time - start_time
            edge_process_time_per_event.append(elapsed)

        # Format attendu par PyG: [2, num_edges], type long
        output_data = {'x': node_features, 'edge_index': edge_index, 'pos': edge_coords, 'event_id': event_idx}
        output_filename = args.output_dir / f"event_{event_idx}_graph.npz"
        np.savez(output_filename, **output_data)
        
    print(f"\nTraitement terminé. {len(events_data)} événements traités et sauvegardés.")

    # --- Étape 3: Affichage du résumé final ---
    if args.monitor_ram:
        # S'assurer d'avoir un dernier point de mesure à la fin
        final_ram = process.memory_info().rss / 1024**2
        monitoring_results['ram_during_loop'].append((event_idx, final_ram))
        print_summary(monitoring_results)
        np.savez(args.output_dir / "monitoring_results.npz", **monitoring_results)

    if args.use_timeit:
        avg_time = np.mean(edge_process_time_per_event)
        print(f"[TimeIt] Informations : moy :{avg_time:.6f} secondes \n         std :{np.std(edge_process_time_per_event):.6f} secondes sur {len(edge_process_time_per_event)} événements.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construire des graphes à partir de données Cherenkov.")
    
    # Arguments I/O et sélection de données
    parser.add_argument("input_file", type=Path, help="Chemin vers le fichier .root d'entrée.")
    parser.add_argument("output_dir", type=Path, help="Chemin vers le répertoire de sauvegarde des graphes.")
    parser.add_argument("--tree-name", type=str, default="pure_root_tree", help="Nom de l'arbre (TTree) dans le fichier ROOT.")
    parser.add_argument("--node-features", nargs='+', default=['charge', 'time'], help="Features pour les noeuds.")
    parser.add_argument("--edge-features", nargs='+', default=['hitx', 'hity', 'hitz'], help="Coordonnées pour les arêtes.")

    # Arguments méthode
    parser.add_argument("--method", type=str, required=True, choices=GRAPH_BUILDERS.keys(), help="Méthode de construction des arêtes.")
    parser.add_argument("--k", type=int, default=10, help="Nombre de voisins pour la méthode KNN.")
    parser.add_argument("--r", type=float, default=1.0, help="Rayon pour la méthode Radius.")

    # Arguments monitoring
    parser.add_argument("--use-timeit", action='store_true', help="Activer la mesure du temps de calcul.")
    parser.add_argument("--monitor-ram", action='store_true', help="Activer le suivi global de la RAM.")
    parser.add_argument("--monitor-interval", type=int, default=10, 
                        help="Intervalle (en nombre d'événements) pour l'échantillonnage de la RAM pendant la boucle.")
    
    parsed_args = parser.parse_args()
    main(parsed_args)