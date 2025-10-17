import numpy as np
from scipy.spatial import cKDTree

def build_edges(coords: np.ndarray, k: int, **kwargs) -> np.ndarray:
    """
    Construit les arêtes d'un graphe en utilisant l'algorithme des K plus proches voisins (KNN)
    avec l'implémentation cKDTree de SciPy.

    Args:
        coords (np.ndarray): Tableau de forme [N, D] contenant les coordonnées des N noeuds
                             dans un espace à D dimensions.
        k (int): Le nombre de plus proches voisins à trouver pour chaque noeud.
        **kwargs: Arguments supplémentaires (ignorés ici) pour maintenir une signature
                  de fonction cohérente avec les autres méthodes.

    Returns:
        np.ndarray: Tableau de forme [2, num_edges] représentant la liste des arêtes
                    (edge_index) au format PyG. Les arêtes sont non dirigées (symétriques).
    """
    # 1. Construire la structure de données KD-Tree
    # C'est une étape rapide et efficace en O(N log N)
    tree = cKDTree(coords)

    # 2. Trouver les k+1 plus proches voisins pour chaque point.
    # On demande k+1 car le premier voisin d'un point est toujours lui-même.
    # La distance au (k+1)-ième voisin est une borne pour `query_ball_point`.
    # `query_pairs` est plus efficace pour trouver toutes les paires uniques.
    # On trouve la distance maximale au k-ième voisin pour définir un rayon de recherche.
    distances, _ = tree.query(coords, k=k + 1, workers=1) # workers=-1 utilise tous les coeurs CPU
    
    # Prendre la distance du k-ième voisin (index k) pour chaque point. On ignore le point lui-même (index 0).
    # On prend la distance maximale parmi tous ces k-ièmes voisins pour s'assurer
    # que chaque point aura au moins k voisins dans la recherche par rayon.
    # C'est une heuristique robuste pour rendre la recherche efficace.
    max_radius = np.max(distances[:, k])

    # 3. Trouver toutes les paires de points dont la distance est inférieure à ce rayon.
    # `query_pairs` est très optimisé. Il retourne un set de tuples (i, j) avec i < j.
    edge_set = tree.query_pairs(r=max_radius, output_type='set')

    # 4. Filtrer pour ne garder que les K plus proches voisins
    # L'étape précédente peut retourner plus de k voisins pour certains points.
    # Nous devons maintenant raffiner ce résultat.
    
    # `query` nous donne directement les k voisins pour chaque point.
    # C'est souvent plus direct.
    _, indices = tree.query(coords, k=k + 1, workers=-1)
    
    # indices a la forme [N, k+1]. L'index 0 est le point lui-même, on l'ignore.
    k_nearest_indices = indices[:, 1:]

    # Créer la liste des arêtes au format PyG
    num_nodes = coords.shape[0]
    row = np.repeat(np.arange(num_nodes), k) # Le noeud source, répété k fois
    col = k_nearest_indices.flatten()       # Les noeuds destination

    # Combiner pour obtenir un edge_index dirigé
    directed_edge_index = np.stack([row, col], axis=0)

    # 5. Rendre le graphe non dirigé (symétrique)
    # On ajoute l'arête inverse (j, i) pour chaque arête (i, j)
    # Et on supprime les doublons.
    # NOTE: PyG a une fonction `to_undirected` pour ça, mais il est bon de savoir le faire en NumPy.
    
    # Inverser les arêtes
    reversed_edge_index = np.stack([directed_edge_index[1], directed_edge_index[0]], axis=0)
    
    # Concaténer et supprimer les doublons
    full_edge_index = np.concatenate([directed_edge_index, reversed_edge_index], axis=1)
    
    # Utiliser `np.unique` est une façon de supprimer les doublons
    unique_edges = np.unique(full_edge_index, axis=1)

    return unique_edges.astype(np.int64) # PyG attend des entiers de 64 bits (long)