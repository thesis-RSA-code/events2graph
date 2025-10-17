import numpy as np
from scipy.spatial import Delaunay

"""
Explications Clés
Prérequis : La triangulation de Delaunay en 3D ne fonctionne que pour des données spécifiquement en 3 dimensions et nécessite au moins 4 points pour former le premier tétraèdre. Le code inclut des vérifications pour ces cas. Il gère également les cas "dégénérés" (par exemple, si tous vos points sont sur un même plan), où Qhull lèverait une erreur.

Delaunay(coords) : C'est l'appel principal. Il prend le nuage de points et calcule l'ensemble des tétraèdres qui constituent la triangulation.

Extraction des arêtes : La partie la plus importante est de comprendre que la triangulation ne donne pas directement les arêtes, mais les simplexes (des triangles en 2D, des tétraèdres en 3D). Un tétraèdre formé par les points p0, p1, p2, p3 a 6 arêtes : (p0,p1), (p0,p2), (p0,p3), (p1,p2), (p1,p3), (p2,p3).

Gestion des doublons : Une même arête est partagée par plusieurs tétraèdres voisins. Pour obtenir une liste unique d'arêtes, le code utilise un set. L'astuce tuple(sorted((i, j))) garantit que l'arête entre le point i et le point j est stockée de la même manière que l'arête entre j et i, évitant ainsi les doublons directionnels à ce stade.

Formatage pour PyG : Une fois la liste d'arêtes uniques (i, j) obtenue, elle est transformée au format edge_index de PyG. Comme les graphes dans PyG sont souvent traités comme des graphes dirigés, on ajoute explicitement les arêtes dans les deux sens (i, j) et (j, i) pour rendre le graphe non dirigé.
"""




def build_edges(coords: np.ndarray, **kwargs) -> np.ndarray:
    """
    Construit les arêtes d'un graphe en utilisant la triangulation de Delaunay 3D.
    Cette méthode connecte les noeuds qui sont des voisins "naturels" dans l'espace,
    formant des tétraèdres qui remplissent l'enveloppe convexe du nuage de points.

    Args:
        coords (np.ndarray): Tableau de forme [N, 3] contenant les coordonnées 3D
                             des N noeuds. La triangulation de Delaunay en 3D
                             nécessite explicitement 3 dimensions.
        **kwargs: Arguments supplémentaires (ignorés ici) pour maintenir une signature
                  de fonction cohérente.

    Returns:
        np.ndarray: Tableau de forme [2, num_edges] représentant la liste des arêtes
                    (edge_index) au format PyG. Le graphe est non dirigé.
    """
    # 1. Vérification des prérequis
    if coords.shape[0] < 4:
        # La triangulation 3D nécessite au moins 4 points non coplanaires
        print(f"Avertissement: Moins de 4 points ({coords.shape[0]}), impossible de construire un graphe Delaunay 3D. "
              "Retour d'un graphe vide.")
        return np.array([[], []], dtype=np.int64)

    if coords.shape[1] != 3:
        raise ValueError(f"La triangulation de Delaunay 3D requiert des coordonnées en 3D, "
                         f"mais les données fournies ont {coords.shape[1]} dimensions.")

    # 2. Calculer la triangulation de Delaunay
    # `scipy.spatial.Delaunay` est un wrapper de la bibliothèque Qhull, très performante.
    # L'objet `tri` contient toutes les informations sur les tétraèdres formés.
    try:
        tri = Delaunay(coords)
    except Exception as e:
        # Gérer les cas dégénérés (ex: tous les points sont coplanaires)
        print(f"Erreur lors du calcul de la triangulation de Delaunay: {e}")
        print("Cela peut arriver si tous les points sont coplanaires. Retour d'un graphe vide.")
        return np.array([[], []], dtype=np.int64)

    # 3. Extraire les arêtes à partir des simplexes (tétraèdres en 3D)
    # tri.simplices est un tableau de forme [num_tetrahedrons, 4].
    # Chaque ligne contient les 4 indices des points formant un tétraèdre.
    # Ex: [i, j, k, l]
    # Les arêtes de ce tétraèdre sont (i,j), (i,k), (i,l), (j,k), (j,l), (k,l).
    
    # On ajoute toutes les paires possibles pour chaque tétraèdre.
    # On utilise un set pour stocker les arêtes afin d'éviter les doublons,
    # car une même arête peut appartenir à plusieurs tétraèdres.
    # On normalise aussi l'arête (min(i,j), max(i,j)) pour que (i,j) et (j,i) soient identiques.
    edge_set = set()
    for simplex in tri.simplices:
        # Pour chaque tétraèdre [p0, p1, p2, p3]
        edge_set.add(tuple(sorted((simplex[0], simplex[1]))))
        edge_set.add(tuple(sorted((simplex[0], simplex[2]))))
        edge_set.add(tuple(sorted((simplex[0], simplex[3]))))
        edge_set.add(tuple(sorted((simplex[1], simplex[2]))))
        edge_set.add(tuple(sorted((simplex[1], simplex[3]))))
        edge_set.add(tuple(sorted((simplex[2], simplex[3]))))

    # 4. Convertir le set d'arêtes au format edge_index de PyG
    # Le set contient des arêtes uniques sous la forme (i, j)
    if not edge_set:
        return np.array([[], []], dtype=np.int64)

    # Convertir en tableau [num_edges, 2]
    unique_edges_array = np.array(list(edge_set))

    # Transposer pour obtenir la forme [2, num_edges]
    row = unique_edges_array[:, 0]
    col = unique_edges_array[:, 1]
    
    # Le graphe est déjà non dirigé par construction (car on a stocké (i, j) et (j, i)
    # de manière unique). Pour PyG, on a besoin des deux directions.
    undirected_edges = np.concatenate(
        [
            np.stack([row, col]),
            np.stack([col, row])
        ],
        axis=1
    )

    return undirected_edges.astype(np.int64)