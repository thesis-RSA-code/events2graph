# !/bin/bash

# debug events
# /sps/t2k/eleblevec/Datasets/custom_dataset/e-/50-1500MeV/test/merged_e-_50-1500MeV_folder1_a2.root

# Note : (E - 25/09/2025)
# For now in addition there are 
# ["n_hits", "energy", "eventType", "towall", "dwall", "trigger_time", "vertex"]
# also stored in the hdf5 file.

python graph_builder_main_hdf5.py \
    /sps/t2k/eleblevec/Datasets/custom_dataset/pi0/50-1500MeV/train_val_400_a1000/merged_pi0_50-1500MeV_folder400_a1000.root \
    /sps/t2k/eleblevec/Datasets/custom_dataset/pi0/50-1500MeV/train_val_400_a1000/h5/hierar_knn_k5_x_tq_edges_xyz_pi0_folder400_a1000.h5 \
    --method knn_pyg \
    --k 5 \
    --storage-mode hierarchical \
    --node-features charge time \
    --edge-features hitx hity hitz \
    --use-timeit \
    --monitor-ram \
    --monitor-interval 500 

# # Utiliser Delaunay (qui n'a pas besoin de k ou r)
# python main.py /path/to/my/data.root /path/to/output_dir \
#     --method delaunay \
#     --node-features charge \
#     --edge-features hitx hity

# # Utiliser Radius avec un rayon de 150.5 (les unités dépendent de vos données)
# python main.py /path/to/my/data.root /path/to/output_dir \
#     --method radius \
#     --r 150.5