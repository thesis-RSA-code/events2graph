import numpy as np

try:
    import torch
    import torch_geometric.nn as pyg_nn
except ImportError:
    # Si les bibliothèques ne sont pas installées, l'appel à la fonction plantera,
    # ce qui est le comportement attendu.
    # On pourrait aussi lever une erreur ici, mais c'est plus propre de le faire
    # dans la fonction elle-même.
    pass

def build_edges(coords: np.ndarray, k: int, **kwargs) -> np.ndarray: # kwargs are passed to knn_graph
    """
    Construit les arêtes d'un graphe en utilisant l'algorithme des K plus proches voisins (KNN)
    avec l'implémentation de PyTorch Geometric (knn_graph).

    Cette fonction est conçue pour être appelée depuis un script qui utilise NumPy.
    Elle gère la conversion vers des tenseurs PyTorch et inversement.

    Args:
        coords (np.ndarray): Tableau de forme [N, D] contenant les coordonnées des N noeuds
                             dans un espace à D dimensions.
        k (int): Le nombre de plus proches voisins à trouver pour chaque noeud.
        **kwargs: Arguments supplémentaires (ignorés ici) pour maintenir une signature
                  de fonction cohérente.

    Returns:
        np.ndarray: Tableau de forme [2, num_edges] représentant la liste des arêtes
                    (edge_index) au format PyG. Le graphe retourné est dirigé.
    """
    try:
        # 1. Convertir les données NumPy en tenseurs PyTorch
        # .contiguous() garantit que le tenseur est stocké dans un bloc de mémoire
        # contigu, ce qui peut être nécessaire pour certaines opérations de bas niveau.
        pos_tensor = torch.from_numpy(coords).float().contiguous()

        # 2. Déterminer le device (CPU dans ce cas, car c'est le but de la comparaison)
        # Bien que le code puisse utiliser le GPU s'il est disponible, on peut forcer le CPU
        # pour une comparaison équitable. Pour une utilisation en production,
        # on utiliserait `torch.device('cuda' if torch.cuda.is_available() else 'cpu')`.
        # device = torch.device('cpu')
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        # print(f"Using device: {device}")
        pos_tensor = pos_tensor.to(device)
        
        # 3. Appeler la fonction `knn_graph` de PyG
        # `knn_graph` est une fonction optimisée qui retourne directement un `edge_index`
        # de forme [2, N*k].
        # - loop=False : n'inclut pas les arêtes auto-bouclantes (i, i).
        # - batch=None : indique qu'on traite un seul graphe et non un batch de graphes.
        edge_index_tensor = pyg_nn.knn_graph(pos_tensor, k=k, loop=False, batch=None, **kwargs)

        # 4. Reconvertir le tenseur résultat en tableau NumPy
        # Le script principal s'attend à recevoir un ndarray.
        # .cpu() est nécessaire si le calcul a été fait sur GPU pour le ramener en RAM.
        edge_index_numpy = edge_index_tensor.cpu().numpy()

        return edge_index_numpy.astype(np.int64)

    except NameError:
        raise ImportError(
            "PyTorch ou Torch Geometric ne sont pas installés. "
            "Veuillez les installer pour utiliser ce constructeur de graphe: "
        )