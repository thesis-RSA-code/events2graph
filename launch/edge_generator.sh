#!/bin/bash

yaml_file=$1

# Check if yaml file is provided
if [ -z "$yaml_file" ]; then
    echo "Error: Please provide a yaml config file as argument"
    echo "Usage: $0 <yaml_config_file>"
    exit 1
fi

# Check if yaml file exists
if [ ! -f "$yaml_file" ]; then
    echo "Error: YAML file '$yaml_file' not found"
    exit 1
fi

# ------------ EXECUTED CODE ------------ #
# Set TMPDIR if not already set
export TMPDIR=${TMPDIR:-/tmp}

# Create job directory for local execution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOTGRAPH_DIR="$(dirname "$SCRIPT_DIR")"
JOBS_DIR="$ROOTGRAPH_DIR/jobs"

# Generate job folder name using Python script
JOB_FOLDER=$(python "$SCRIPT_DIR/generate_job_name.py" "$yaml_file")
JOB_DIR="$JOBS_DIR/$JOB_FOLDER"
mkdir -p "$JOB_DIR"

echo "Local execution - Job directory: $JOB_DIR"

# Check if h5_data_file exists in yaml (only uncommented lines)
if ! grep -q "^h5_data_file:" $yaml_file; then
    echo "Error: h5_data_file not found in $yaml_file"
    exit 1
fi

# Extract filenames from the original paths in config (only uncommented lines)
H5_FILE_PATH=$(grep "^h5_data_file:" $yaml_file | sed 's/h5_data_file: "//' | sed 's/"//')
H5_FILENAME=$(grep "^h5_data_file:" $yaml_file | sed 's/.*\///' | sed 's/"//')

EDGE_FILE_PATH=$(grep "^output_file:" $yaml_file | sed 's/output_file: "//' | sed 's/"//')
EDGE_FILENAME=$(grep "^output_file:" $yaml_file | sed 's/.*\///' | sed 's/"//')

# Use job directory instead of /tmp
TMP_EDGE_FILE="$JOB_DIR/$EDGE_FILENAME"
TMP_H5_FILE="$JOB_DIR/$H5_FILENAME"
TMP_YAML_FILE="$JOB_DIR/edge_config.yaml"

cp $yaml_file $TMP_YAML_FILE
sed -i "s|^h5_data_file: \".*\"|h5_data_file: \"$TMP_H5_FILE\"|" $TMP_YAML_FILE
sed -i "s|^output_file: \".*\"|output_file: \"$TMP_EDGE_FILE\"|" $TMP_YAML_FILE

echo "Copying H5 file to: $TMP_H5_FILE"
time cp $H5_FILE_PATH "$TMP_H5_FILE"

echo "Starting edge generation..."
python "$ROOTGRAPH_DIR/edge_index_generator.py" --config $TMP_YAML_FILE

if [ $? -eq 0 ]; then
    echo "Edge generation completed successfully"
    
    # Copy result back to original location
    echo "Copying edge file back to: $EDGE_FILE_PATH"
    time cp "$TMP_EDGE_FILE" "$EDGE_FILE_PATH"
    
    # Clean up temporary files but keep the job directory for inspection
    rm -f "$TMP_H5_FILE" "$TMP_EDGE_FILE"
    echo "Temporary files cleaned up, job directory preserved: $JOB_DIR"
else
    echo "Error: Edge generation failed"
    echo "Job directory with intermediate files preserved: $JOB_DIR"
    exit 1
fi