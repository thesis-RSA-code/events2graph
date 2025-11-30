#!/bin/bash

# Script to launch edge generation jobs for all config files in config_rockets
# Usage: ./launch_all_configs.sh

# Configuration
CONFIGS_DIR="/sps/t2k/eleblevec/mini-Caverns-toolsbox/events2graph/config_rockets"
SUBMIT_SCRIPT="/sps/t2k/eleblevec/mini-Caverns-toolsbox/events2graph/launch/submit_edge_generator.sh"

echo "=========================================="
echo "Launching Edge Generation Jobs"
echo "=========================================="
echo "Configs directory: $CONFIGS_DIR"
echo ""

# Check if submit script exists
if [ ! -f "$SUBMIT_SCRIPT" ]; then
    echo "Error: Submit script not found at $SUBMIT_SCRIPT"
    exit 1
fi

# Counters
total_configs=0
launched_jobs=0
failed_jobs=0

# Loop through all YAML config files
for config_file in "$CONFIGS_DIR"/*.yaml; do
    if [ ! -f "$config_file" ]; then
        continue
    fi
    
    total_configs=$((total_configs + 1))
    config_name=$(basename "$config_file")
    
    echo "[$total_configs] Processing: $config_name"
    
    # Launch the job
    if bash "$SUBMIT_SCRIPT" "$config_file"; then
        echo "    ✅ Job launched successfully"
        launched_jobs=$((launched_jobs + 1))
    else
        echo "    ❌ Failed to launch job"
        failed_jobs=$((failed_jobs + 1))
    fi
    
    echo ""
    
    # Small delay to avoid overwhelming the scheduler
    sleep 1
done

echo "=========================================="
echo "Job Launch Summary:"
echo "  Total configs found: $total_configs"
echo "  Jobs launched: $launched_jobs"
echo "  Jobs failed: $failed_jobs"
echo "=========================================="

if [ $failed_jobs -eq 0 ]; then
    echo "🎉 All jobs launched successfully!"
    exit 0
else
    echo "⚠️  Some jobs failed to launch"
    exit 1
fi

