"""
Description here
Default behaviour is to run the entire pipeline after launch from 1_IlluminaQC.sh via 1_launch_SMP2v3.sh without manual
intervention
Options provided to manually launch and resume the pipeline from various stages if required

"""
import os
import logging
import argparse
import textwrap
import json
from parse_variables_files import *
from file_upload import FileUpload
from launch_app import LaunchApp
from file_downloader import FileDownloader
from load_configuration import get_authentication_token
from config import app_name
from config import app_version
from config import smp2_app_name
from config import smp2_app_version


# Class to filter logging to restrict to one level only
class MyFilter(object):
    def __init__(self, level):
        self.__level = level

    def filter(self, log_record):
        return log_record.levelno <= self.__level


def get_args():
    '''
    :return:
    '''
    argument_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent(
            '''
            summary:
            Uploads fastqs for the CRUK project to BaseSpace, launches two applications and downloads the required
            results for analysis and reporting
            '''))

    # Adds version and date updated
    argument_parser.add_argument(
        '-v', '--version', action='version',
        version=f"version: {__version__} updated on: {__updated__}")

    # Add arguments
    # REQUIRED: Path to config file containing authorisation information
    argument_parser.add_argument(
        '-c', '--path_to_config_file', action='store',
        help=textwrap.dedent(
            '''
            File path to config file location containing authentication credentials. Set up according to template
            in bs.config.json.example. Config file must be named bs.config.json. REQUIRED.
            '''))

    # OPTIONAL: choices for resuming part way through the pipeline
    resuming_options = argument_parser.add_mutually_exclusive_group()
    resuming_options.add_argument(
        '-t', '--tst170', action='store_true', default=False,
        help=textwrap.dedent(
            '''
            Set this flag to start pipeline from the launch of the TST170 app (post upload of all files). OPTIONAL.
            '''))
    resuming_options.add_argument(
        '-s', '--smp2', action='store_true', default=False,
        help=textwrap.dedent(
            '''
            Set this flag to start pipeline from the launch of the SMP2v3 app (post completion of TST170 app). OPTIONAL.
            '''))
    resuming_options.add_argument(
        '-d', '--dl_files', action='store_true', default=False,
        help=textwrap.dedent(
            '''
            Set this flag to download required files for all DNA samples (will include RNA sample data paired with
            DNA sample where applicable) (post completion of SMP2v3 app). OPTIONAL.
            '''))

    return argument_parser.parse_args()


class CrukSmp:
    def __init__(self):
        #  Load the config file containing user-specific information and obtain the authentication token
        self.authentication_token = get_authentication_token(args.path_to_config_file)
        self.worksheet = ""
        self.sample_pairs = ""

    def main(self):
        '''
        :return:
        '''
        # Always do these steps regardless of option
        # Parse variables files to extract relevant sample information
        # Identify samples to upload to BaseSpace
        samples_to_upload = identify_samples()

        # Load and parse out variables from variables files associated with each sample
        all_variables = load_all_variables(samples_to_upload, os.getcwd())

        # Identify the worksheet number which will be used as the project name in BaseSpace
        worksheet = identify_worksheet(all_variables)

        # Pair samples- DNA sample is key, RNA sample to look up- if No RNA sample, it is None
        sample_pairs = create_sample_pairs(all_variables)
        # Write out sample pairs to log file for checking if needed
        log.warning(f"sample pairs are {sample_pairs}")

        # Locate the fastqs associated with all samples
        all_fastqs = locate_all_fastqs(samples_to_upload, os.getcwd())

        # Create a project in BaseSpace- will not create if it already exists, but will still return project id
        upload = FileUpload(self.authentication_token, worksheet, samples_to_upload, all_fastqs)
        project = upload.create_basespace_project()
        log.info(f"Project {worksheet} created")
        log.warning(f"Project id for project name {worksheet} is {project}")

        # If whole pipeline required then upload fastq files
        if not args.tst170 and not args.smp2 and not args.dl_files:
            # Upload fastq files
            print(f"uploading fastq files for all samples")
            upload.upload_files()

        # Create launch app object for TST170 app
        launch_tst = LaunchApp(self.authentication_token, worksheet, project, app_name,
                               app_version, sample_pairs)

        # If resuming from TST170 required or full pipeline- launch the TST170 app
        if not args.smp2 and not args.dl_files:
            # Launch TST170 application for each pair in turn
            # IMPORTANT NOTE: Only processes paired data
            tst_170 = launch_tst.launch_tst170_pairs()

            # Dump data to file
            with open(os.path.join(os.getcwd(), "tst_170.json"), 'w') as t:
                json.dump(tst_170, t)

        # If resuming from SMP2v3 launch load in required TST170 data from file
        elif args.smp2:
            try:
                with open(os.path.join(os.getcwd(), "tst_170.json")) as ts:
                    tst_170 = json.load(ts)
            except FileNotFoundError:
                raise FileNotFoundError(f"Could not find file tst_170.json. Cannot resume pipeline from SMP2 step."
                                        f"Please delete TST170 analysis in BaseSpace and resume pipeline from"
                                        f"TST170 stage.")

        # If resuming from SMP2v3 required, resuming from TST170 required or full pipeline- launch the SMP2 app
        if not args.dl_files:
            # Create launch app object for SMP2 v3 if not just downloading files- poll TST170 and when complete
            # launch SMP2
            launch_smp = LaunchApp(self.authentication_token, worksheet, project, smp2_app_name,
                                   smp2_app_version, sample_pairs, tst_170)
            # Poll the tst 170 appsessions until completion, then launch smp2 app
            smp_appsession = launch_smp.poll_tst170_launch_smp2()

            # Dump data to file
            with open(os.path.join(os.getcwd(), "smp.json"), 'w') as s:
                json.dump(smp_appsession, s)

        # If downloading files from a completed SMP2 app required
        # Create a LaunchApp object for smp2 app if flag to only download files is set- allows for polling of SMP2
        if args.dl_files:
            # Load data in required smp2 data from file
            try:
                with open(os.path.join(os.getcwd(), "smp.json")) as sm:
                    smp = json.load(sm)
            except FileNotFoundError:
                raise FileNotFoundError(f"Could not find file smp.json. Cannot resume pipeline from download step."
                                        f"Please delete SMP2 analysis in BaseSpace and resume pipeline from"
                                        f"SMP2 stage.")
            launch_smp = LaunchApp(self.authentication_token, worksheet, project, smp2_app_name,
                                   smp2_app_version, sample_pairs, None, smp)  # None as tst170 app data not required


        # Poll the smp appsessions until completion
        smp_appresults = launch_smp.poll_smp2()

        # Download all required files- every step requires this
        file_download = FileDownloader(self.authentication_token, smp_appresults, worksheet)
        file_download.download_files()
        log.info(f"CRUK workflow completed")


if __name__ == '__main__':

    __version__ = '2.0.0'
    __updated__ = "14/11/2019"

    # Set up logger
    log = logging.getLogger("cruk_smp")
    log.setLevel(logging.DEBUG)
    #handler_out = logging.StreamHandler(sys.stdout)
    handler_out = logging.FileHandler(os.path.join(os.getcwd(), "cruk_smp.out"))
    handler_out.setLevel(logging.INFO)
    handler_out.addFilter(MyFilter(logging.INFO))
    #handler_err = logging.StreamHandler(sys.stderr)
    handler_dbg = logging.FileHandler(os.path.join(os.getcwd(), "cruk_smp.dbg"))
    handler_dbg.setLevel(logging.WARNING)
    handler_dbg.addFilter(MyFilter(logging.WARNING))
    handler_err = logging.FileHandler(os.path.join(os.getcwd(), "cruk_smp.err"))
    handler_err.setLevel(logging.ERROR)
    log.addHandler(handler_out)
    log.addHandler(handler_dbg)
    log.addHandler(handler_err)

    # Load command line arguments
    args = get_args()
    cr = CrukSmp()
    cr.main()
