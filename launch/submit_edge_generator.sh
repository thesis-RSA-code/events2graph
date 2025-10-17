#!/bin/bash

# Wrapper script to submit edge generator jobs with proper output directory structure
# Usage: ./submit_edge_generator.sh <yaml_config_file>
#
# SLURM Configuration (edit these values as needed):
SLURM_TIME="0-00:15:00"      # Time limit
SLURM_MEM="2G"              # Memory limit
JOB_NAME="tv_mu-_st_knn"

# Directory Configuration (edit these paths as needed):
MINICONDA_DIR="/sps/t2k/eleblevec/miniconda3"                    # Miniconda installation path
JOBS_DIR="/sps/t2k/eleblevec/mini-Caverns-toolsbox/root2graph/jobs"  # Where job folders are created
ROOTGRAPH_DIR="/sps/t2k/eleblevec/mini-Caverns-toolsbox/root2graph"  # Main project directory

# Fixed SLURM parameters
SLURM_CPUS=1
SLURM_GPU=1
SLURM_PARTITION="gpu"


# --------- EXECUTED CODE --------- #
yaml_file=$1

# Check if yaml file is provided
if [ -z "$yaml_file" ]; then
    echo "Error: Please provide a yaml config file as argument"
    echo "Usage: $0 <yaml_config_file>"
    echo ""
    echo "To modify SLURM resources and paths, edit the variables at the top of this script:"
    echo ""
    echo "SLURM Configuration:"
    echo "  SLURM_TIME=\"0-00:20:00\"    # Time limit"
    echo "  SLURM_MEM=\"10G\"            # Memory limit"
    echo ""
    echo "Directory Configuration:"
    echo "  MINICONDA_DIR=\"...\"        # Miniconda installation path"
    echo "  JOBS_DIR=\"...\"             # Where job folders are created"
    echo "  ROOTGRAPH_DIR=\"...\"        # Main project directory"
    exit 1
fi

# Check if yaml file exists
if [ ! -f "$yaml_file" ]; then
    echo "Error: YAML file '$yaml_file' not found"
    exit 1
fi

# Generate job folder name using Python script
source "$MINICONDA_DIR/bin/activate" grant_cuda_12_1

JOB_FOLDER=$(python "$ROOTGRAPH_DIR/utils/generate_job_name.py" "$yaml_file")

# Create jobs directory and job-specific directory
JOB_DIR="$JOBS_DIR/$JOB_FOLDER"
mkdir -p "$JOB_DIR"

# Copy yaml file to job directory to prevent modifications during job execution
SED_YAML_FILE="$JOB_DIR/edge_config.yaml"
cp $yaml_file $SED_YAML_FILE

echo "Job directory: $JOB_DIR"
echo "Job folder name: $JOB_FOLDER"
echo "SLURM resources: Time=$SLURM_TIME, Memory=$SLURM_MEM"
echo "" 

# Submit the job with output files directed to the job directory
sbatch \
    --time="$SLURM_TIME" \
    --mem="$SLURM_MEM" \
    --cpus-per-task="$SLURM_CPUS" \
    --gres=gpu:"$SLURM_GPU" \
    --partition="$SLURM_PARTITION" \
    --output="$JOB_DIR/slurm_%x_%j.out" \
    --error="$JOB_DIR/slurm_%x_%j.err" \
    --job-name="$JOB_NAME" \
    --export=MINICONDA_DIR="$MINICONDA_DIR",JOBS_DIR="$JOBS_DIR",ROOTGRAPH_DIR="$ROOTGRAPH_DIR",JOB_DIR="$JOB_DIR" \
    "$ROOTGRAPH_DIR/launch/edge_generator_slurm.sh" \
    "$SED_YAML_FILE"

echo "Job submitted successfully!"
echo "SLURM output files will be in: $JOB_DIR"
