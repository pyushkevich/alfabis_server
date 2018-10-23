#!/bin/bash
#!/bin/bash

# ------------------------------------
# Trim whitespace and lower resolution
# ------------------------------------

# Path to C3D
PATH=/data/picsl/pauly/bin:$PATH

# Print usage by default
if [[ $# -lt 1 || $1 == "-h" || $1 == "-help" || $1 == "--help" ]]; then
  cat <<USAGETEXT
  trim_neck_rf: Brain MRI neck removal tool
  usage:
    trim_neck_rf [options] input_image output_image
  options:
    -l <mm>        : Length (sup-inf) of the head that should be captured [180].
    -c <mm>        : Clearance above head that should be captured [10].
    -m <file>      : Location to save mask used for the computation.
    -w <dir>       : Location to store intermediate files. Default: [$TMPDIR]
    -d             : Verbose/debug mode
USAGETEXT
  exit 0
fi

# Default parameter values
HEADLEN=180
CLEARANCE=10
unset WORKDIR MASKOUT DEBUG

# Read the options
while getopts "l:c:m:w:d" opt; do
  case $opt in

    l) HEADLEN=$OPTARG;;
    c) CLEARANCE=$OPTARG;;
    m) MASKOUT=$OPTARG;;
    w) WORKDIR=$OPTARG;;
    d) DEBUG=1;;
    \?) echo "Unknown option $OPTARG"; exit 2;;
    :) echo "Option $OPTARG requires an argument"; exit 2;;

  esac
done

shift $((OPTIND-1))

# Debugging
if [[ $DEBUG ]]; then
  set -x -e
  VERBOSE="-verbose"
fi

# Read script parameters
SOURCE=${1?}
TARGET=${2?}

# Create a temporary directory
if [[ ! $WORKDIR ]]; then
  if [[ ! $TMPDIR ]]; then
    TMPDIR=$(mktemp -d)
  fi
  WORKDIR=$TMPDIR
else
  mkdir -p $WORKDIR
fi

# Create a landmark file for background / foreground segmentation
cat > $WORKDIR/landmarks.txt << 'LANDMARKS'
40x40x40% 1
60x40x40% 1
40x60x40% 1
40x40x60% 1
60x60x40% 1
60x40x60% 1
40x60x60% 1
60x60x60% 1
3x3x3% 2
97x3x3% 2
3x97x3% 2
3x3x97% 2
97x97x3% 2
97x3x97% 2
3x97x97% 2
97x97x97% 2
LANDMARKS

# Intermediate images
RAS_TRIMMED=$WORKDIR/trimmed_ras.nii.gz
RAS_RESULT=$WORKDIR/result_ras.nii.gz
RFMAP=$WORKDIR/rfmap.nii.gz
LEVELSET=$WORKDIR/levelset.nii.gz
MASK=$WORKDIR/mask.nii.gz
SLAB=$WORKDIR/slab.nii.gz

# Quick trim of the image
c3d $VERBOSE \
  $SOURCE -swapdim RAS \
  -smooth-fast 1vox -resample-mm 2x2x2mm -o $WORKDIR/dsample_ras.nii.gz -as T1 \
  -dup -steig 2.0 4x4x4 \
  -push T1 -dup -scale 0 -lts $WORKDIR/landmarks.txt 15 -o $WORKDIR/samples.nii.gz \
  -rf-param-patch 1x1x1 -rf-train /tmp/myforest.rf -pop -rf-apply /tmp/myforest.rf \
  -o $RFMAP

# Quick level set of the image
c3d $VERBOSE \
  $RFMAP -as R -smooth-fast 1vox -resample 50% -stretch 0 1 -1 1 -dup \
  $WORKDIR/samples.nii.gz -thresh 1 1 1 -1 -reslice-identity \
  -levelset-curvature 5.0 -levelset 300 -o $LEVELSET \
  -insert R 1 -reslice-identity -thresh 0 inf 1 0 -o $MASK

# Get the dimensions of the image and the trim amount
DIM=($(c3d $MASK -info-full | grep 'Dimen' | sed -e "s/.*\[//g" -e "s/,/ /g" -e "s/\].*//g"))
DIMX=${DIM[0]}
DIMY=${DIM[1]}
DIMZ=${DIM[2]}

# Amount to trim: 18cm = 90vox
REGZ=$((HEADLEN / 2 + CLEARANCE / 2))
TRIM=$((CLEARANCE / 2))

# Translate the RAI code into a region specification
REGCMD="0x0x0vox ${DIMX}x${DIMY}x${REGZ}vox"

# Perform the trimming
c3d $VERBOSE $MASK \
  -dilate 1 ${DIMX}x${DIMY}x0vox -trim 0x0x${TRIM}vox \
  -region $REGCMD -thresh -inf inf 1 0 -o $SLAB -popas S \
  $SOURCE -as I -int 0 -push S -reslice-identity -trim 0vox -as SS -o $WORKDIR/slab_src.nii.gz \
  -push I -reslice-identity -o $TARGET

# If mask requested, reslice mask to target space
if [[ $MASKOUT ]]; then
  c3d $SOURCE $LEVELSET -reslice-identity -thresh 0 inf 1 0 -o $MASKOUT
fi


