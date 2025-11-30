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

MINICONDA_DIR=${MINICONDA_DIR:-"/sps/t2k/eleblevec/miniconda3"}
JOBS_DIR=${JOBS_DIR:-"/sps/t2k/eleblevec/mini-Caverns-toolsbox/events2graph/jobs"}
ROOTGRAPH_DIR=${ROOTGRAPH_DIR:-"/sps/t2k/eleblevec/mini-Caverns-toolsbox/events2graph"}
PYTHON_ENV_NAME=${PYTHON_ENV_NAME:-"grant_cuda_12_1"}
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

# Extract h5_data_file path from YAML and copy to TMPDIR for faster I/O
h5_file=$(grep "^h5_data_file:" $yaml_file | sed 's/h5_data_file://g' | tr -d ' "' | tr -d "'")

if [ -z "$h5_file" ]; then
    echo "Error: Could not extract h5_data_file from config"
    exit 1
fi

echo "Original H5 file: $h5_file"

# Extract output_file path from YAML and clean it if exists
output_file=$(grep "^output_file:" $yaml_file | sed 's/output_file://g' | tr -d ' "' | tr -d "'")

if [ -n "$output_file" ]; then
    echo "Output file path: $output_file"
    
    # Check if output file exists from previous run
    if [ -f "$output_file" ]; then
        echo "Warning: Output file already exists from previous run: $output_file"
        
        # Extract directory, basename, and extension
        output_dir=$(dirname "$output_file")
        output_basename=$(basename "$output_file")
        output_extension="${output_basename##*.}"
        output_name="${output_basename%.*}"
        
        # Create new filename with _v2 suffix
        new_output_file="${output_dir}/${output_name}_v2.${output_extension}"
        
        echo "Creating new output file to avoid overwriting: $new_output_file"
        
        # Update the yaml file with the new output path
        sed -i "s|output_file:.*|output_file: $new_output_file|g" $yaml_file
        echo "Updated config file with new output path"
        
        output_file="$new_output_file"
    fi
else
    echo "No output_file specified in config, will be auto-generated"
fi

# Check if TMPDIR is available (SLURM provides this)
if [ -n "$TMPDIR" ] && [ -d "$TMPDIR" ]; then
    echo "Copying H5 file to scratch directory ($TMPDIR) for faster I/O..."
    h5_basename=$(basename "$h5_file")
    
    # Add SLURM_JOB_ID to filename to avoid conflicts when multiple jobs run in parallel
    h5_tmpdir="$TMPDIR/${h5_basename%.h5}_job${SLURM_JOB_ID}.h5"
    echo "Unique temp file: $h5_tmpdir"
    
    # Copy with progress
    time cp "$h5_file" "$h5_tmpdir"
    
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to copy H5 file to TMPDIR, using original path"
        h5_tmpdir="$h5_file"
    else
        echo "Successfully copied to: $h5_tmpdir"
        
        # Update the yaml file with the new path
        sed -i "s|h5_data_file:.*|h5_data_file: $h5_tmpdir|g" $yaml_file
        echo "Updated config file with scratch directory path"
    fi
else
    echo "TMPDIR not available, using original H5 file path"
    h5_tmpdir="$h5_file"
fi

# Run the edge generation
source $MINICONDA_DIR/bin/activate $PYTHON_ENV_NAME
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
