# cron job that takes CRUK runs that have demultiplexed successfully and completes basesapce section:
# - upload FASTQs to basespace, 
# - kick off TST170 app, 
# - wait for TST app completion and kick off SMP2 app, 
# - wait for SMP2 app completion and download files

version=master

conda activate cruk

python cruk_smp.py -c /data/diagnostics/pipelines/CRUK/CRUK-"$version"/access/

conda deactivate

