import logging
from identify_files_to_download import IdentifyFiles
from config import download_file_extensions

log = logging.getLogger("cruk_smp")


class FileDownloader:
    def __init__(self, auth, appresults, worksheet):
        self.auth = auth
        self.appresults = appresults
        self.worksheet = worksheet
        # Adds the leading . for the first extension
        download_file_extensions[0] = f".{download_file_extensions[0]}"
        self.download_file_extensions = download_file_extensions

    def download_files(self):
        # Download files within appresults for which the SMP2 app successfully completed
        # Iterate over all appresults- one per dna sample successfully completed
        for dna_sample, appresult_dict in self.appresults.items():
            appresult = appresult_dict.get("appresults")
            if appresult_dict.get("status") == "Fail":
                log.info(f"SMP2 v3 app for dna sample {dna_sample} has failed to "
                         f"complete. Investigate further through the BaseSpace website.")
                # Failure means no appresults so this causes a pipeline fail
                #identify_files = IdentifyFiles(self.auth, self.worksheet, dna_sample, appresult, [".log"])
                #identify_files.download_sample_files()
            else:
                log.info(f"Downloading results for sample {dna_sample}")
                identify_files = IdentifyFiles(self.auth, self.worksheet, dna_sample, appresult,
                                           ",.".join(self.download_file_extensions))
                log.info(identify_files.download_sample_files())
        return "Files downloaded for all samples and appresults"
