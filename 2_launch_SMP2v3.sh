#!/bin/bash
#PBS -l walltime=120:00:00
#PBS -l ncpus=12
set -euo pipefail
#PBS_O_WORKDIR=(`echo $PBS_O_WORKDIR | sed "s/^\/state\/partition1//" `)
#cd $PBS_O_WORKDIR

#Description: CRUK SMP2v3 Illumina TST170 Pipeline (Illumina paired-end). Not for use with other library preps/ experimental conditions.
#Author: Sara Rey, All Wales Medical Genetics Lab
#Mode: BY_SAMPLE
version="2.0.0"

# Directory structure required for pipeline
#
# /data
# â””â”€â”€ results
#     â””â”€â”€ seqId
#         â”œâ”€â”€ panel1
#         â”‚Â Â  â”œâ”€â”€ sample1
#         â”‚Â Â  â”œâ”€â”€ sample2
#         â”‚Â Â  â””â”€â”€ sample3
#         â””â”€â”€ panel2
#             â”œâ”€â”€ sample1
#             â”œâ”€â”€ sample2
#             â””â”€â”€ sample3
#
# Script 2 runs in run folder

# Log into head node, Activate Conda environment, launch python pipeline, deactivate conda environment


# Run CRUK SMP2v3 pipeline
ssh transfer@cvx-gen01 "cd '$wd' \
&& source /home/transfer/miniconda3/bin/activate cruk \
&& python cruk_smp.py -c /data/diagnostics/pipelines/CRUK/CRUK-"$version"/access/ \
&& source /home/transfer/miniconda3/bin/deactivate"

### Generate Combined QC File ###
python /data/diagnostics/scripts/merge_qc_files.py .