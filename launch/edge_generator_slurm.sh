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
JOBS_DIR=${JOBS_DIR:-"/sps/t2k/eleblevec/mini-Caverns-toolsbox/root2graph/jobs"}
ROOTGRAPH_DIR=${ROOTGRAPH_DIR:-"/sps/t2k/eleblevec/mini-Caverns-toolsbox/root2graph"}
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

# Extract filenames from the original paths in config
H5_FILE_PATH=$(grep "^h5_data_file:" $yaml_file | sed 's/h5_data_file: *"//' | sed 's/".*//')
H5_FILENAME=$(grep "^h5_data_file:" $yaml_file | sed 's/.*\///' | sed 's/"//')
EDGE_FILE_PATH=$(grep "^output_file:" $yaml_file | sed 's/output_file: "//' | sed 's/"//')
EDGE_FILENAME=$(grep "^output_file:" $yaml_file | sed 's/.*\///' | sed 's/"//')

# Use tmp for fast I/O
TMP_DIR=${TMP_DIR:-"/tmp"}
TMP_EDGE_FILE="$TMP_DIR/$EDGE_FILENAME"
TMP_H5_FILE="$TMP_DIR/$H5_FILENAME"

# Modify yaml file in job directory
# and change the h5_data_file and output_file to the tmp files
sed -i "s|^h5_data_file: \".*\"|h5_data_file: \"$TMP_H5_FILE\"|" $yaml_file
sed -i "s|^output_file: \".*\"|output_file: \"$TMP_EDGE_FILE\"|" $yaml_file


echo "Using H5 file: $H5_FILE_PATH"
echo "Using Edge file: $EDGE_FILE_PATH"
echo "Copying H5 file to: $TMP_H5_FILE"
time cp $H5_FILE_PATH "$TMP_H5_FILE"

echo "Starting edge generation..."
echo "Working directory: $(pwd)"
echo "Python script: $ROOTGRAPH_DIR/edge_index_generator.py"
echo "Config file: $yaml_file"

# Run the edge generation
source $MINICONDA_DIR/bin/activate grant_cuda_12_1
python $ROOTGRAPH_DIR/edge_index_generator.py --config $yaml_file

if [ $? -eq 0 ]; then
    echo "Edge generation completed successfully"
    
    # Copy result back to original location
    echo "Copying edge file back to: $EDGE_FILE_PATH"
    mkdir -p $(dirname "$EDGE_FILE_PATH")
    time cp "$TMP_EDGE_FILE" "$EDGE_FILE_PATH"
    
    # Clean up temporary files but keep the job directory for inspection
    rm -f "$TMP_H5_FILE" "$TMP_EDGE_FILE"
    echo "Temporary files cleaned up, job directory preserved: $JOB_DIR"
else
    echo "**********************************************************************"
    echo "* Error: Edge generation failed                                    *"
    echo "* Job directory with intermediate files preserved: $JOB_DIR"
    echo "**********************************************************************"
    exit 1
fi
