#!/bin/bash
#PBS -l walltime=12:00:00
#PBS -l ncpus=12
set -euo pipefail
PBS_O_WORKDIR=(`echo $PBS_O_WORKDIR | sed "s/^\/state\/partition1//" `)
cd $PBS_O_WORKDIR

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
# Script 1 runs in sample folder, requires fastq files split by lane

countQCFlagFails() {
    #count how many core FASTQC tests failed
    grep -E "Basic Statistics|Per base sequence quality|Per tile sequence quality|Per sequence quality scores|Per base N content" "$1" | \
    grep -v ^PASS | \
    grep -v ^WARN | \
    wc -l | \
    sed 's/^[[:space:]]*//g'
}

#load sample & pipeline variables
. *.variables
. /data/diagnostics/pipelines/CRUK/CRUK-"$version"/"$panel"/CRUK-"$version"_"$panel".variables

### Preprocessing ###

#record FASTQC pass/fail
rawSequenceQuality=PASS

# Extract QC data
for fastqPair in $(ls "$sampleId"_S*.fastq.gz | cut -d_ -f1-3 | sort | uniq); do

    #parse fastq filenames
    laneId=$(echo "$fastqPair" | cut -d_ -f3)
    read1Fastq=$(ls "$fastqPair"_R1_*fastq.gz)
    read2Fastq=$(ls "$fastqPair"_R2_*fastq.gz)
    unzippedRead1Fastq=${read1Fastq%%.*}
    unzippedRead2Fastq=${read2Fastq%%.*}

    #fastqc
    /share/apps/fastqc-distros/fastqc_v0.11.5/fastqc -d /state/partition1/tmpdir --threads 12 --extract "$read1Fastq"
    /share/apps/fastqc-distros/fastqc_v0.11.5/fastqc -d /state/partition1/tmpdir --threads 12 --extract "$read2Fastq"

    mv "$unzippedRead1Fastq"_fastqc/summary.txt "$unzippedRead1Fastq"_fastqc.txt
    mv "$unzippedRead2Fastq"_fastqc/summary.txt "$unzippedRead2Fastq"_fastqc.txt

    #check FASTQC output
    if [ $(countQCFlagFails "$unzippedRead1Fastq"_fastqc.txt) -gt 0 ] || [ $(countQCFlagFails "$unzippedRead2Fastq"_fastqc.txt) -gt 0 ]; then
        rawSequenceQuality=FAIL
    fi

    #clean up
    rm *_fastqc.zip
    rm -r "$unzippedRead1Fastq"_fastqc "$unzippedRead2Fastq"_fastqc

done

#Now that fastqs have been processed add the sample to a list
echo -e $(ls *.fastq.gz | cut -d'_' -f1-2 | uniq) >> ../FASTQs.list

#Print QC metrics
echo -e "RawSequenceQuality" > "$seqId"_"$sampleId"_QC.txt
echo -e "$rawSequenceQuality" >> "$seqId"_"$sampleId"_QC.txt

# Create variables to check if all samples are written
numSamplesWithFqs=$(sort ../FASTQs.list | uniq | wc -l | sed 's/^[[:space:]]*//g')
numSamplesInProject=$(find .. -maxdepth 1 -mindepth 1 -type d | wc -l | sed 's/^[[:space:]]*//g')

#check if all samples are written
if [ $numSamplesInProject -eq $numSamplesWithFqs ]; then

    # Return to run level directory
    cd ..

    # Copy pipeline scripts to results folder of runs
    cp "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/app.config.template.json" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/config.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/cruk_smp.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/download_files.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/file_downloader.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/file_upload.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/identify_files_to_download.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/launch_app.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/load_configuration.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/parse_variables_files.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/poll_appsession_status.py" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/smpapp.config.template.json" \
    "/data/diagnostics/pipelines/CRUK/CRUK-"$version"/split_file.py" .

    # Launch script 2 in run folder, which will run python scripts for pipeline
    bash 2_*.sh > "2_launch_SMP2v3.out" 2> "2_launch_SMP2v3.err"

fi
