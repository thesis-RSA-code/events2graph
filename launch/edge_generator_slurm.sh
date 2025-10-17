#!/bin/bash

#SBATCH --job-name=edge_gen
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1        # Nombre de GPU
#SBATCH --time=0-00:20:00
#SBATCH --mem=10G

# Script: edge_generator_slurm.sh
# SLURM version of edge generator that creates job-specific directories
# Usage: sbatch edge_generator_slurm.sh <yaml_config_file>

MINICONDA_DIR=${MINICONDA_DIR:-"/home/amaterasu/miniconda3"}
JOBS_DIR=${JOBS_DIR:-"/home/amaterasu/work/mini-Caverns/root2graph/jobs"}
ROOTGRAPH_DIR=${ROOTGRAPH_DIR:-"/home/amaterasu/work/mini-Caverns/root2graph"}
JOB_DIR=${JOB_DIR:-""}

yaml_file=$1

# Check if yaml file is provided
if [ -z "$yaml_file" ]; then
    echo "Error: Please provide a yaml config file as argument"
    echo "Usage: sbatch edge_generator_slurm.sh <yaml_config_file>"
    exit 1
fi

# Check if yaml file exists
if [ ! -f "$yaml_file" ]; then
    echo "Error: YAML file '$yaml_file' not found"
    exit 1
fi

# Check if h5_data_file exists in yaml (only uncommented lines)
if ! grep -q "^h5_data_file:" $yaml_file; then
    echo "Error: h5_data_file not found in $yaml_file"
    exit 1
fi

# Use job directory passed from submit script, or create one if not provided
if [ -n "$JOB_DIR" ]; then
    # Job directory was passed from submit script
    echo "Using provided job directory: $JOB_DIR"
else
    # Fallback: create job directory (for direct execution)
    echo "No job directory provided, creating one..."
    
    # Generate job folder name using Python script
    JOB_FOLDER=$(python "$ROOTGRAPH_DIR/utils/generate_job_name.py" "$yaml_file")
    JOB_DIR="$JOBS_DIR/$JOB_FOLDER" # mind the "s" in JOBS
    mkdir -p "$JOB_DIR"
    echo "Created job directory: $JOB_DIR"
    
    # if there are no JOB_DIR it means the yaml file wasn't already copied so we do it here
    echo "Making a copy of the yaml file in the job directory: $JOB_DIR"
    cp $yaml_file $JOB_DIR/edge_config.yaml
    yaml_file=$JOB_DIR/edge_config.yaml
fi

echo "Starting edge generation..."
echo "Working directory: $(pwd)"
echo "Python script: $ROOTGRAPH_DIR/edge_index_generator.py"
echo "Config file: $yaml_file"

# Run the edge generation
source $MINICONDA_DIR/bin/activate new_caverns
python $ROOTGRAPH_DIR/edge_index_generator.py --config $yaml_file

if [ $? -eq 0 ]; then
    echo "Edge generation completed successfully"
else
    echo "**********************************************************************"
    echo "* Error: Edge generation failed                                    *"
    echo "* Job directory with intermediate files preserved: $JOB_DIR"
    echo "**********************************************************************"
    exit 1
fi
