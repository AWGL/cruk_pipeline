# cron job that takes CRUK runs that have demultiplexed successfully and completes basesapce section:
# - upload FASTQs to basespace, 
# - kick off TST170 app, 
# - wait for TST app completion and kick off SMP2 app, 
# - wait for SMP2 app completion and download files

version=master

# activate conda env
module purge
module load anaconda
. ~/.bashrc
conda activate cruk


# find runs with bs_required file (bs_required is produced at the end of 1_launchSMP2v3.sh)
for run in $(find /Output/results/ -type f -name bs_required); do

    run_dir=$(dirname $run)
    echo $run_dir
    cd $run_dir

    # make file to stop run being kicked off while another cron is running
    mv bs_required bs_started

    # all basespace stuff is dealt with from python script
    python cruk_smp.py -c /data/diagnostics/pipelines/CRUK/CRUK-"$version"/access/

    mv bs_started bs_complete

done

conda deactivate

