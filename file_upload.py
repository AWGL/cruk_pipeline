import requests
import os
import gzip
import time
import logging
import numpy as np
from Bio.SeqIO.QualityIO import FastqGeneralIterator
from split_file import SplitFile
from config import v1_api
from config import v2_api

log = logging.getLogger("cruk_smp")


class FileUpload:

    def __init__(self, auth, project_name, samples, fastqs):
        self.authorise = auth
        self.project_name = project_name
        self.project_id = None
        self.samples_to_upload = samples
        self.all_fastqs = fastqs

    def create_basespace_project(self):
        '''
        :param project_name: Worksheet id from the sample sheet, which will be the project name in BaseSpace
        :param authorise:
        :return:
        '''
        response = requests.post(f"{v1_api}/projects", data={"name": self.project_name},
                                 headers={"Authorization": self.authorise},
                                 allow_redirects=True)
        if response.status_code != 200 and response.status_code != 201:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        elif response.status_code == 200:
            # Update project id inside object if project already exists
            self.project_id = response.json().get("Response").get("Id")
        elif response.status_code == 201:
            # Update project id inside object
            self.project_id = response.json().get("Response").get("Id")
        return self.project_id

    def upload_files(self):
        # For each sample on worksheet
        for sample_num, sample in enumerate(self.samples_to_upload, 1):
            log.info(f"Uploading sample {sample}")
            sample_data = self.upload_sample_files(sample, self.all_fastqs)
            # Update sample metadata
            self.update_sample_metadata(sample, sample_num, sample_data.get("sample_id"),
                                               sample_data.get("len_reads"), sample_data.get("read_num"))
            # Mark file upload appsession as complete
            self.finalise_appsession(sample_data.get("appsession_id"), sample)

        # Wait to allow biosample indexes to update (5 seconds)
        time.sleep(5)

    def upload_sample_files(self, sample, all_fastqs):
        # Files associated with each sample here
        '''
        :param upload_file:
        :param sample:
        :param all_fastqs:
        :return:
        '''
        file_upload_info = {}
        read_num = 0  # Cumulative tally
        len_reads = 0  # Same across all fastqs on the run
        # Create a sample inside the project in BaseSpace
        sample_metadata = self.make_sample(sample)
        sample_id = sample_metadata.get("sample_id")
        appsession_id = sample_metadata.get("appsession_id")
        file_upload_info["sample_id"] = sample_id
        file_upload_info["appsession_id"] = appsession_id
        # Pull out files associated with that particular sample
        fastq_files = all_fastqs.get(sample)
        # For each file associated with that sample
        for f in fastq_files:
            log.info(f"Uploading fastq {f}")
            # Identify if read 1 or read 2
            match_read = f.split("_")
            read = match_read[:][-2] # Requires no underscores in file name, SMP2 v3 app also requires this
            # Extract required fastq information from R1- assume R2 is the same- paired end
            if read == "R1":
                fq_metadata = self.get_fastq_metadata(f)  # Returns (max read length, number of reads in fastq)
                if len_reads < fq_metadata.get("len_reads"):
                    len_reads = fq_metadata.get("len_reads")
                num_reads = fq_metadata.get("num_reads")
                # Cumulative tally of read numbers for this sample
                read_num += num_reads
            # Create a file inside the sample in BaseSpace
            file_id = self.make_file(f, sample_id)
            # Split the file into chunks for upload
            file_splitting = SplitFile(os.path.join(os.getcwd(), sample, f))
            chunks = file_splitting.get_file_chunk_size()
            file_chunks_created = file_splitting.split_file(chunks)
            num_chunks_uploaded = 0
            for i, f_chunk in enumerate(file_chunks_created):
                # Calculate hash for file chunk
                md5_b64 = file_splitting.calc_md5_b64(f_chunk)
                md5_hex = file_splitting.calc_md5_hex(f_chunk)
                # Populate sample with file chunks
                chunk_num = i + 1
                file_part_uploaded_md5 = self.upload_into_file(f_chunk, file_id, chunk_num, md5_b64)
                # Check MD5s match before and after upload
                if md5_hex != file_part_uploaded_md5:
                    raise Exception(f"MD5s do not match before and after file upload for file chunk {f_chunk}")
                # Delete file chunk after upload successful
                os.remove(f_chunk)
                num_chunks_uploaded += 1
            # Check all file parts uploaded
            if len(file_chunks_created) != num_chunks_uploaded:
                raise Exception(f"Not all file chunks successfully uploaded for file {f}")
            file_upload_info["len_reads"] = len_reads
            file_upload_info["read_num"] = read_num
            # Set file status to complete
            log.info(self.set_file_upload_status(file_id, "complete"))
        return file_upload_info

    def make_sample(self, file_to_upload):
        sample_metadata = {}
        file_name = os.path.basename(file_to_upload)
        url = f"{v1_api}/projects/{self.project_id}/samples"
        data = {"Name": f"{self.project_name}-{file_name}", "SampleId": f"{self.project_name}-{file_name}",
                "SampleNumber": 0, "Read1": "101", "Read2": "101", "IsPairedEnd": "true"}
        head = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": self.authorise,
                "User-Agent": "/python-requests/2.22.0"}
        response = requests.post(url, headers=head, data=data, allow_redirects=True)
        if response.status_code != 201:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        sample_metadata["sample_id"] = response.json().get("Response").get("Id")
        sample_metadata["appsession_id"] = response.json().get("Response").get("AppSession").get("Id")
        return sample_metadata

    def get_read_length_one_fq(self, fq_file):
        with gzip.open(fq_file, "rt") as fh:
            fq = FastqGeneralIterator(fh)
            for fq_id, fq_seq, fq_qual in fq:
                # Read length
                len_reads = len(fq_seq)
                return len_reads

    def get_fastq_metadata(self, fastq):
        read_metadata = {}
        # Open fastq
        with gzip.open(fastq, "rt") as fh_r1:
            fq_r1 = FastqGeneralIterator(fh_r1)
            fq_r1_array = np.array([len(fq_seq.strip()) for (fq_id, fq_seq, fq_qual) in fq_r1])
        read_metadata["len_reads"] = np.amax(fq_r1_array)
        read_metadata["num_reads"] = fq_r1_array.size
        return read_metadata

    def make_file(self, file_to_upload, sample_id):
        file_name = os.path.basename(file_to_upload)
        url = f"{v1_api}/samples/{sample_id}/files"
        p = {"name": file_name, "multipart": "true"}
        head = {"Content-Type": "json/application", "Authorization": self.authorise,
                "User-Agent": "/python-requests/2.22.0"}
        response = requests.post(url, headers=head, params=p, allow_redirects=True)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        return response.json().get("Response").get("Id")

    def upload_into_file(self, upload_file, file_id, file_chunk_num, hash):
        part_num = file_chunk_num
        url = f"{v1_api}/files/{file_id}/parts/{part_num}"
        head = {"Authorization": self.authorise, "Content-MD5": hash}
        file = {"fn": open(upload_file, 'rb')}
        response = requests.put(url, headers=head, files=file, allow_redirects=True)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        return response.json().get("Response").get("ETag")

    def set_file_upload_status(self, file_id, file_status):
        url = f"{v1_api}/files/{file_id}"
        p = {"uploadstatus": file_status}
        head = {"Authorization": self.authorise}
        response = requests.post(url, headers=head, params=p, allow_redirects=True)
        if response.status_code != 201:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        return f"{response.json().get('Response').get('Name')} set to status {file_status}"

    def update_sample_metadata(self, file_to_upload, sample_number, sample_id, r_len, num_reads):
        sample_metadata = {}
        file_name = os.path.basename(file_to_upload)
        url = f"{v1_api}/samples/{sample_id}"
        data = {"Name": f"{self.project_name}-{file_name}", "SampleId": f"{self.project_name}-{file_name}",
                "SampleNumber": sample_number, "Read1": r_len, "Read2": r_len, "IsPairedEnd": "true",
                "NumReadsRaw": num_reads, "NumReadsPF": num_reads}
        head = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": self.authorise,
                "User-Agent": "/python-requests/2.22.0"}
        response = requests.post(url, headers=head, data=data, allow_redirects=True)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        sample_metadata["sample_id"] = response.json().get("Response").get("Id")
        sample_metadata["appsession_id"] = response.json().get("Response").get("AppSession").get("Id")
        return sample_metadata

    def finalise_appsession(self, appsession_id, file_name):
        url = f"{v2_api}/appsessions/{appsession_id}"
        d = {"ExecutionStatus": "Complete", "StatusSummary": f"Finished uploading {file_name}"}
        head = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": self.authorise,
                "User-Agent": "/python-requests/2.22.0"}
        response = requests.post(url, headers=head, data=d, allow_redirects=True)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        return f"AppSession {appsession_id} for file {self.project_name}-{file_name} set to status Complete"


