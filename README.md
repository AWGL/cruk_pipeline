# CRUK Pipeline
***
## Introduction
Pipeline to support the analysis of SMP2v3 samples using apps in the Illumina BaseSpace environment.
### Overview of Steps:

* Identify fastqs for the samples on an Illumina SampleSheet.csv
* Pair samples according to the common identifier for DNA and RNA from the same source in the pairs variable 
* Launch the Illumina TruSight Tumor 170 app for each pair
* Poll the sessions for the Illumina TruSight Tumour 170 app for each pair and, once complete, launch the SMP2v3 app
* Poll the sessions for the SMP2v3 app for each pair and once all pairs are complete (or aborted) download the required files


***
## Installation
This software uses Python 3.7.

It has dependencies which are recommended to be installed using a Conda environment. 
Install Conda:

```
https://docs.conda.io/projects/conda/en/latest/user-guide/install/download.html
```

Clone the repository:

```
git clone https://github.com/AWGL/cruk_pipeline
```

Create Conda environment:

```
conda env create cruk_env.yml
```

If required edit the Python config file to launch the correct versions of the apps:


Edit ```config.py```

Set up the JSON config file with the correct authentication token:

Edit ```bs.config.json.example``` and save as ```bs.config.json```


The code can then be run after the Conda environment is activated:

```
bash 1_launch_SMP2v3.sh
```
***
## Usage
#### Notes on directory structure
The code is expecting a directory structure where fastqs and a variables file created by ```https://github.com/AWGL/MakeVariableFiles``` are located within directories named with the sample file name, and the sample sheet ```SampleSheet.csv``` is in the same directory as all of the scripts.

e.g.
![](dir.png)
### Default options
The pipeline should be automatically initiated after sequencing by IlluminaQC (see https://github.com/AWGL/IlluminaQC). This launches the script ```1_launch_SMP2v3.sh``` which aggregates QC data for all samples on the run and launches the script ```cruk_smp.py``` with the default location for the config file on the cluster cvx-gen01.

To run the pipeline independently of this process, it can be launched with
```
python cruk_smp.py -c /path/to/JSON/config/file/
```

### Other options
To resume the process for a partially complete process, for example due to loss of internet connectivity. There are the following options:

1. After all fastq files have been successfully uploaded- **Launch TST170 app for all DNA/RNA pairs**
	+ 	Command line option -t or --tst170

		e.g.
```
python cruk_smp.py -t -c /path/to/JSON/config/file/
```

2. After TST170 app has been launched for all sample pairs- **Poll status of TST170 app and once complete launch SMP2v3 app for all DNA/RNA pairs**
	+ 	Command line option -s or --smp2

		e.g.
```
python cruk_smp.py -s -c /path/to/JSON/config/file/
```

3. After the SMP2v3 app has been launched for all sample pairs- **Download required files**
	+ 	Command line option -d or --dl_files

		e.g.
```
python cruk_smp.py -d -c /path/to/JSON/config/file/
```

Note that this may require logging on to BaseSpace through the GUI to delete partially completed data depending on the current progress of the process.

***
## The BaseSpace GUI
To log in to the BaseSpace GUI:

Navigate to 
```
https://pmg.euc1.sh.basespace.illumina.com
```
and use the bioinformatics team email and transfer account password to log in.
***
## Notes
### Current known issues
* Multipart file upload is nbot supported on child nodes of the cluster. The request does not error out, but hangs indefinitely.
* Fastq upload is sequential and not parallelised, which causes a long run time.
* There is no way to easily upload fastqs for a subset of samples. A failure at this stage of the process requires all fastqs to be re-uploaded.
* Deletion of data through the BaseSpace GUI may require navigating to the biosamples tab and setting a new (different, existing) default project for biosamples before data can be deleted.
* Test data and a suite of tests has not yet been written.
* DNA samples without an RNA pair are not supported (this may be a future requirement).

### Dependency List
In case the Conda environment build fails.

* pandas
* numpy
* requests
* biopython
