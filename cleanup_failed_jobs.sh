#!/bin/bash

# Script: cleanup_failed_jobs.sh
# Purpose: Parse jobs directory and remove folders for failed/incomplete SLURM jobs
# Usage: ./cleanup_failed_jobs.sh [--dry-run]

JOBS_DIR="/sps/t2k/eleblevec/mini-Caverns-toolsbox/events2graph/jobs"
DRY_RUN=false

# Check for dry-run flag
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "========================================"
    echo "   DRY RUN MODE - No files will be deleted"
    echo "========================================"
fi

echo "Scanning jobs directory: $JOBS_DIR"
echo "----------------------------------------"

# Statistics counters
total_jobs=0
successful_jobs=0
failed_jobs=0
removed_jobs=0

# Loop through each job folder
for job_folder in "$JOBS_DIR"/*/; do
    # Skip if not a directory
    [[ ! -d "$job_folder" ]] && continue
    
    total_jobs=$((total_jobs + 1))
    job_name=$(basename "$job_folder")
    
    # Find SLURM output file (*.out)
    slurm_out=$(find "$job_folder" -maxdepth 1 -name "slurm_*.out" | head -1)
    slurm_err=$(find "$job_folder" -maxdepth 1 -name "slurm_*.err" | head -1)
    
    # If no SLURM files found, mark for removal (incomplete job)
    if [[ -z "$slurm_out" ]]; then
        failed_jobs=$((failed_jobs + 1))
        echo "✗  [$job_name] No SLURM output file found - incomplete job"
        
        if [[ "$DRY_RUN" == true ]]; then
            echo "   [DRY-RUN] Would remove: $job_folder"
        else
            echo "   Removing folder: $job_folder"
            rm -rf "$job_folder"
            if [[ $? -eq 0 ]]; then
                removed_jobs=$((removed_jobs + 1))
                echo "   ✓ Successfully removed"
            else
                echo "   ✗ Failed to remove folder"
            fi
        fi
        continue
    fi
    
    # Extract SLURM job ID from filename
    job_id=$(basename "$slurm_out" | grep -oP '\d+(?=\.out$)')
    
    if [[ -z "$job_id" ]]; then
        echo "⚠️  [$job_name] Could not extract job ID - SKIPPING"
        continue
    fi
    
    # Initialize status flags
    should_remove=false
    reason=""
    
    # Method 1: Check output file for success/failure messages
    if grep -q "Edge generation completed successfully" "$slurm_out" 2>/dev/null; then
        echo "✓  [$job_name] Job $job_id: SUCCESS"
        successful_jobs=$((successful_jobs + 1))
        continue
    elif grep -q "Error: Edge generation failed" "$slurm_out" 2>/dev/null; then
        should_remove=true
        reason="Edge generation failed (explicit error)"
    fi
    
    # Method 2: Check SLURM job status using sacct
    if [[ "$should_remove" == false ]]; then
        slurm_state=$(sacct -j "$job_id" --format=State --noheader | head -1 | tr -d '[:space:]')
        
        # Remove trailing + from status (e.g., CANCELLED+ -> CANCELLED)
        slurm_state="${slurm_state%+}"
        
        case "$slurm_state" in
            COMPLETED)
                # Job completed but no success message - check for errors
                if [[ -f "$slurm_err" ]]; then
                    # Check if error file has significant content (more than just warnings)
                    err_lines=$(grep -vE "^$|UserWarning|FutureWarning|DeprecationWarning" "$slurm_err" | wc -l)
                    if [[ $err_lines -gt 10 ]]; then
                        should_remove=true
                        reason="COMPLETED status but significant errors in .err file ($err_lines error lines)"
                    else
                        echo "⚠️  [$job_name] Job $job_id: COMPLETED (no success message, minimal errors)"
                        successful_jobs=$((successful_jobs + 1))
                        continue
                    fi
                else
                    echo "⚠️  [$job_name] Job $job_id: COMPLETED (no success message)"
                    successful_jobs=$((successful_jobs + 1))
                    continue
                fi
                ;;
            FAILED|CANCELLED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL)
                should_remove=true
                reason="SLURM status: $slurm_state"
                ;;
            RUNNING|PENDING)
                echo "⏳ [$job_name] Job $job_id: Still $slurm_state - SKIPPING"
                continue
                ;;
            "")
                # Job not found in sacct (might be too old)
                should_remove=true
                reason="Job not found in SLURM accounting (old job or crashed)"
                ;;
            *)
                echo "❓ [$job_name] Job $job_id: Unknown status '$slurm_state' - SKIPPING"
                continue
                ;;
        esac
    fi
    
    # Method 3: Check error file for critical errors
    if [[ "$should_remove" == false ]] && [[ -f "$slurm_err" ]]; then
        # Check for common critical errors
        if grep -qE "Traceback|Error:|Exception:|Segmentation fault|core dumped" "$slurm_err" 2>/dev/null; then
            # Count non-warning error lines
            critical_errors=$(grep -E "Traceback|Error:|Exception:|Segmentation fault|core dumped" "$slurm_err" | grep -vE "UserWarning|FutureWarning|DeprecationWarning" | wc -l)
            if [[ $critical_errors -gt 0 ]]; then
                should_remove=true
                reason="Critical errors found in .err file ($critical_errors errors)"
            fi
        fi
    fi
    
    # Decide whether to remove
    if [[ "$should_remove" == true ]]; then
        failed_jobs=$((failed_jobs + 1))
        echo "✗  [$job_name] Job $job_id: FAILED - $reason"
        
        if [[ "$DRY_RUN" == true ]]; then
            echo "   [DRY-RUN] Would remove: $job_folder"
        else
            echo "   Removing folder: $job_folder"
            rm -rf "$job_folder"
            if [[ $? -eq 0 ]]; then
                removed_jobs=$((removed_jobs + 1))
                echo "   ✓ Successfully removed"
            else
                echo "   ✗ Failed to remove folder"
            fi
        fi
    fi
done

# Print summary
echo ""
echo "========================================"
echo "         CLEANUP SUMMARY"
echo "========================================"
echo "Total jobs scanned:        $total_jobs"
echo "Successful jobs:           $successful_jobs"
echo "Failed jobs detected:      $failed_jobs"

if [[ "$DRY_RUN" == true ]]; then
    echo "Jobs that would be removed: $failed_jobs"
    echo ""
    echo "Run without --dry-run to actually remove folders"
else
    echo "Jobs removed:              $removed_jobs"
fi
echo "========================================"

