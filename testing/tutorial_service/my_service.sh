#!/bin/bash
set -x

# Look up the git commit hash of the service RegistrationExample (third word in output)
GITHASH=$(itksnap-wt -P -dssp-services-list | grep RegistrationExample | awk '{print $3}')

# Temporary directory for this script
if [[ ! $TMPDIR ]]; then
  TMPDIR=/tmp/service_${GITHASH}
  mkdir -p $TMPDIR
fi

# Run in an infinite loop
while [[ true ]]; do

  # Claim a ticket
  itksnap-wt -dssp-services-claim $GITHASH testlab instance_1 > $TMPDIR/claim.txt

  # If return code is non-zero we sleep and continue
  if [[ $? -ne 0 ]]; then
    sleep 10
    continue
  fi

  # Get the ticket id (second word in line starting with '1>')
  TICKET_ID=$(cat $TMPDIR/claim.txt | grep '^1>' | awk '{print $2}')

  # Create work dir
  WORKDIR=$TMPDIR/dss_work/ticket_${TICKET_ID}
  mkdir -p $WORKDIR

  # Download the ticket
  itksnap-wt -dssp-tickets-download $TICKET_ID $WORKDIR > $TMPDIR/download.txt

  # If return code is non-zero we mark the ticket as failed
  if [[ $? -ne 0 ]]; then
    itksnap-wt -dssp-tickets-fail $TICKET_ID "Failed to download ticket"
    continue
  fi

  # Inform the user
  itksnap-wt -dssp-tickets-log $TICKET_ID info "Ticket successfully downloaded"

  # Find the workspace file in the download
  INPUT_WSP=$(cat $TMPDIR/download.txt | grep '^1>.*itksnap$' | sed -e "s/^1> //")

  # Get the necessary layers
  TARGET_IMG=$(itksnap-wt -P -i $INPUT_WSP -llf Target)
  SOURCE_IMG=$(itksnap-wt -P -i $INPUT_WSP -llf Source)
  SOURCE_SEG=$(itksnap-wt -P -i $INPUT_WSP -llf SourceSeg)

  # Extract the affine transformation from the input workspace
  INIT_AFFINE=$WORKDIR/init_affine.mat
  itksnap-wt -i $INPUT_WSP -layers-pick-by-tag Source -props-get-transform \
    | grep '^3>' | sed -e "s/^3> //" > $INIT_AFFINE

  # Perform affine registration
  AFFINE_MAT=$WORKDIR/affine.mat
  AFFINE_OUTPUT=$WORKDIR/affine_reg_output.txt
  greedy -d 3 -m NCC 8x8x8 -n 40x40x20 -a \
    -i $TARGET_IMG $SOURCE_IMG -o $AFFINE_MAT -ia $INIT_AFFINE \
    > $AFFINE_OUTPUT 2>&1

  # Attach the output to the log
  itksnap-wt -dssp-tickets-attach $TICKET_ID "AffineReg output" $AFFINE_OUTPUT text/plain

  # Check that registration succeeded
  if [[ ! -f $AFFINE_MAT ]]; then
    itksnap-wt -dssp-tickets-fail $TICKET_ID "Affine registration failed"
    continue
  fi

  # Attach affine result to the log and send update
  itksnap-wt -dssp-tickets-attach $TICKET_ID "Affine matrix" $AFFINE_MAT text/plain
  itksnap-wt -dssp-tickets-log $TICKET_ID info "Affine registration successful"
  itksnap-wt -dssp-tickets-set-progress $TICKET_ID 0 1 0.4

  # Perform deformable registration
  WARP=$WORKDIR/warp.nii.gz
  DEFORMABLE_OUTPUT=$WORKDIR/deformable_reg_output.txt
  greedy -d 3 -m NCC 8x8x8 -n 40x40x20 -i $TARGET_IMG $SOURCE_IMG -it $AFFINE_MAT -o $WARP \
    > $DEFORMABLE_OUTPUT 2>&1

  # Attach the output to the log
  itksnap-wt -dssp-tickets-attach $TICKET_ID "Deformable output" $DEFORMABLE_OUTPUT text/plain

  # Check that registration succeeded
  if [[ ! -f $AFFINE_MAT ]]; then
    itksnap-wt -dssp-tickets-fail $TICKET_ID "Deformable registration failed"
    continue
  fi

  itksnap-wt -dssp-tickets-log $TICKET_ID info "Deformable registration successful"
  itksnap-wt -dssp-tickets-set-progress $TICKET_ID 0 1 0.8

  # Perform the final reslice step
  RESLICE_SOURCE_IMG=$WORKDIR/reslice_source_img.nii.gz
  RESLICE_SOURCE_SEG=$WORKDIR/reslice_source_seg.nii.gz
  COMBINED_WARP=$WORKDIR/warp_combined.nii.gz
  greedy -d 3 -rf $TARGET_IMG \
    -rm $SOURCE_IMG $RESLICE_SOURCE_IMG \
    -ri LABEL 0.2vox -rm $SOURCE_SEG $RESLICE_SOURCE_SEG \
    -rc $COMBINED_WARP \
    -r $WARP $AFFINE_MAT

  # Package up the workspace
  RESULT_WSP=$WORKDIR/result.itksnap
  itksnap-wt -i $INPUT_WSP \
    -layers-add-anat $RESLICE_SOURCE_IMG -props-set-nickname "Resliced Source Image" \
    -layers-add-anat $COMBINED_WARP -props-set-nickname "Deformation Field" -props-set-colormap jet \
    -layers-add-seg $RESLICE_SOURCE_SEG -props-set-nickname "Resliced Segmentation" \
    -layers-list -o $RESULT_WSP

  # Upload the workspace
  itksnap-wt -i $RESULT_WSP -dssp-tickets-upload $TICKET_ID

  # If return code is non-zero we mark the ticket as failed
  if [[ $? -ne 0 ]]; then
    itksnap-wt -dssp-tickets-fail $TICKET_ID "Failed to upload ticket"
    continue
  fi

  # Set progress and mark ticket as success
  itksnap-wt -dssp-tickets-set-progress $TICKET_ID 0 1 1 
  itksnap-wt -dssp-tickets-success $TICKET_ID

done
