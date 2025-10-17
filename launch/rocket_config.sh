#!/bin/bash

# Script to run all edge generation configs in config_rockets folder locally
# Usage: bash rocket_config.sh

MINICONDA_DIR=${MINICONDA_DIR:-"/home/amaterasu/miniconda3"}
ROOTGRAPH_DIR=${ROOTGRAPH_DIR:-"/home/amaterasu/work/mini-Caverns/root2graph"}
CONFIG_DIR="$ROOTGRAPH_DIR/config_rockets"
JOBS_DIR="$ROOTGRAPH_DIR/jobs"

# Activate conda environment
source $MINICONDA_DIR/bin/activate new_caverns

echo "=========================================="
echo "Running all configs in config_rockets"
echo "=========================================="

# Counter for tracking
total_configs=0
successful=0
failed=0

# Find all yaml files in config_rockets
for yaml_file in "$CONFIG_DIR"/*.yaml; do
    if [ -f "$yaml_file" ]; then
        total_configs=$((total_configs + 1))
        
        echo ""
        echo "=========================================="
        echo "Config $total_configs: $(basename $yaml_file)"
        echo "=========================================="
        
        # Generate job folder name
        JOB_FOLDER=$(python3 "$ROOTGRAPH_DIR/utils/generate_job_name.py" "$yaml_file" 2>/dev/null)
        
        if [ -z "$JOB_FOLDER" ]; then
            # Fallback if generate_job_name.py fails
            config_name=$(basename "$yaml_file" .yaml)
            timestamp=$(date +%y_%m_%d_%H_%M)
            JOB_FOLDER="${timestamp}_${config_name}"
        fi
        
        JOB_DIR="$JOBS_DIR/$JOB_FOLDER"
        mkdir -p "$JOB_DIR"
        
        # Copy config to job directory
        cp "$yaml_file" "$JOB_DIR/edge_config.yaml"
        local_yaml="$JOB_DIR/edge_config.yaml"
        
        echo "Job directory: $JOB_DIR"
        echo "Config file: $local_yaml"
        echo ""
        
        # Run edge generation
        python3 "$ROOTGRAPH_DIR/edge_index_generator.py" --config "$local_yaml"
        
        if [ $? -eq 0 ]; then
            echo "✓ Config $total_configs completed successfully"
            successful=$((successful + 1))
        else
            echo "✗ Config $total_configs failed"
            echo "  Job directory preserved: $JOB_DIR"
            failed=$((failed + 1))
        fi
    fi
done

echo ""
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo "Total configs: $total_configs"
echo "Successful: $successful"
echo "Failed: $failed"
echo "=========================================="

if [ $failed -gt 0 ]; then
    exit 1
fi
