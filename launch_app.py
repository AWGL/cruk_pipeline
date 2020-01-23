import requests
import json
import os
import datetime
import logging
from poll_appsession_status import PollAppsessionStatus
from config import v1_api
from config import v2_api

log = logging.getLogger("cruk_smp")


class LaunchApp:

    def __init__(self, auth, worksheet, project_id, app_name, app_version, sample_pairs, tst_170=None, smp=None):
        self.authorise = auth
        self.worksheet = worksheet
        self.project_id = project_id
        self.app_name = app_name
        self.app_version = app_version
        self.sample_pairs = sample_pairs
        self.tst_170 = tst_170
        self.smp = smp
        self.appresults_dict = {}
        self.app_group_id = None
        self.app_id = None

    def launch_tst170_pairs(self):
        '''
        :return:
        '''
        # Launch TST170 app for DNA, RNA pairs
        tst_170 = {}
        for dna_sample in self.sample_pairs.keys():
            tst_170_launch = self.launch_tst170_analysis(dna_sample)
            tst_170[dna_sample] = tst_170_launch
            # Write out to log file to provide data required to resume process from this point
            log.warning(f"{dna_sample}: {tst_170_launch}")
        return tst_170

    def launch_tst170_analysis(self, dna_sample):
        '''
        :param launch:
        :param worksheet_id:
        :param dna_sample:
        :param pairs_dict:
        :return:
        '''
        # Identify biosamples for upload
        dna_biosample_id = self.get_biosamples(f"{self.worksheet}-{dna_sample}")
        rna_sample = self.sample_pairs.get(dna_sample)
        rna_biosample_id = self.get_biosamples(f"{self.worksheet}-{rna_sample}")

        # Create configuration for TST 170 app launch
        app_config = self.generate_app_config(dna_sample, dna_biosample_id, rna_biosample_id)

        # Find specific application ID for application and version number of TST 170 app
        self.get_app_group_id()
        self.get_app_id()

        # Launch TST 170 application for DNA and RNA pair
        log.info(f"Launching {self.app_name} {self.app_version} for {dna_sample} and {rna_sample}")
        appsession = self.launch_application(app_config)
        tst_170_analysis = {"appsession": appsession, "dna_biosample_id": dna_biosample_id,
                                    "rna_biosample_id": rna_biosample_id}
        return tst_170_analysis

    def poll_tst170_launch_smp2(self):
        # Poll appsession status of launched TST 170 app- polling runs until appsession is complete then launch SMP2 v3 app
        smp_appsession = {}
        for dna_sample, tst_values in self.tst_170.items():
            rna_sample = self.sample_pairs.get(dna_sample)
            log.info(f"Polling status of TST 170 application, appsession {tst_values.get('appsession')}")
            polling = PollAppsessionStatus(self.authorise, tst_values.get("appsession"))
            poll_result = polling.poll()  # Poll status of appsession
            log.info(f" TST 170 appsession {tst_values.get('appsession')} for samples {dna_sample} and {rna_sample} "
                     f"has finished with status {poll_result}")
            if poll_result == "Fail":
                log.info(f"TST170 app for samples {dna_sample} and {rna_sample} has failed to"
                        f"complete. Investigate further through the BaseSpace website.")
                # Move on to the next pair's appsession
                continue
            # Launch SMP2v3 app as each pair completes analysis with the TST170 app
            # Find specific application ID for application and version number of SMP2 app
            self.get_app_group_id()
            self.get_app_id()
            log.info(f"Launching {self.app_name} {self.app_version} for {dna_sample} and "
                     f"{self.sample_pairs.get(dna_sample)}")
            smp_appsession[dna_sample] = self.launch_smp_analysis(dna_sample, tst_values)
            self.smp = smp_appsession
        return self.smp

    def launch_smp_analysis(self, dna_sample_id, tst_values):
        '''
        :param launch_smp:
        :param tst_values:
        :return:
        '''
        # Get dataset ids using TST 170 appsession id and nucleotide biosample id
        dna_dataset_id = self.get_datasets(tst_values.get("appsession"), tst_values.get("dna_biosample_id"))
        rna_dataset_id = self.get_datasets(tst_values.get("appsession"), tst_values.get("rna_biosample_id"))
        # Create configuration for SMP2 v3 app launch
        smp_app_config = self.generate_smp_app_config(dna_sample_id, dna_dataset_id, rna_dataset_id)

        # Launch SMP2 v3
        smp_appsession = self.launch_application(smp_app_config)
        return smp_appsession

    def poll_smp2(self):
        # Poll appsession status of launched SMP2 v3 app- polling runs until appsession is complete then download files
        for dna_sample, smp_appsession in self.smp.items():
            rna_sample = self.sample_pairs.get(dna_sample)
            log.info(f"Polling status of SMP2 v3 application, appsession {smp_appsession}")
            polling = PollAppsessionStatus(self.authorise, smp_appsession)
            poll_result = polling.poll()  # Poll status of appsession
            log.info(f" SMP2 v3 appsession {smp_appsession} for sample {dna_sample} and {rna_sample} has finished with "
                     f"status {poll_result}")
            appresults = polling.find_appresults()
            if len(appresults) != 1 and poll_result is not "Fail":
                raise Exception(f"Expected 1 appresult for successful appsession {smp_appsession}, dna sample "
                                f"{dna_sample} but found {len(appresults)}. File path to results could not be "
                                f"determined- please download files manually from BaseSpace")
            elif poll_result is not "Fail":
                self.appresults_dict[dna_sample] = {"appresults": appresults[0], "status": poll_result}
            elif poll_result == "Fail":
                self.appresults_dict[dna_sample] = {"appresults": None, "status": poll_result}
            else:
                raise Exception(f"Unexpected status {poll_result} returned by {smp_appsession} for dna sample "
                                f"{dna_sample}. Unable to handle this status appropriately.")
        return self.appresults_dict

    def get_biosamples(self, biosample_name):
        url = v2_api + "/biosamples"
        p = {"biosamplename": biosample_name, "projectid": self.project_id}
        head = {"Authorization": self.authorise, "Content-Type": "application/json"}
        response = requests.get(url, headers=head, params=p)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        if len(response.json().get("Items")) > 1:
            raise Exception(f"Multiple biosamples with name {biosample_name} in project {self.project_id}")
        if len(response.json().get("Items")) < 1:
            raise Exception(f"No biosample with name {biosample_name} in project {self.project_id}")
        try:
            response.json().get("Items")[0]
        except:
            raise Exception(f"Problem with finding biosample data in BaseSpace: {response.json()}")
        return response.json().get("Items")[0].get("Id")

    def generate_app_config(self, dna_sample_id, dna_biosample_id, rna_biosample_id):
        # Generate biosamples in correct format for application launch
        dna_libraryprep_id = self.get_biosample_info(dna_biosample_id)
        dna_config = f"biosamples/{dna_biosample_id}/librarypreps/{dna_libraryprep_id}"
        rna_libraryprep_id = self.get_biosample_info(rna_biosample_id)
        rna_config = f"biosamples/{rna_biosample_id}/librarypreps/{rna_libraryprep_id}"
        # Obtain date and time
        current_time = datetime.datetime.now()
        # remove seconds from date and time and create string
        date_time = ":".join(str(current_time).split(":")[:-1])
        # Obtain rna sample name for name of appsession
        rna_sample_id = self.sample_pairs.get(dna_sample_id)
        with open(os.path.join(os.getcwd(), "app.config.template.json")) as app_config_file:
            try:
                app_config = json.load(app_config_file)
                inp = app_config.get("InputParameters")
                inp["dna-sample-id"] = dna_config
                inp["project-id"] = f"projects/{self.project_id}"
                inp["rna-sample-id"] = rna_config
                app_config["Name"] = f"{dna_sample_id}-{rna_sample_id} TruSight Tumour 170 {date_time}"
            except json.decoder.JSONDecodeError:
                raise Exception("Config file is incorrectly formatted and does not contain valid json")
        return app_config

    def generate_smp_app_config(self, dna_sample_id, dna_dataset_id, rna_dataset_id):
        dna_config = f"datasets/{dna_dataset_id}"
        rna_config = f"datasets/{rna_dataset_id}"
        # Obtain date and time
        current_time = datetime.datetime.now()
        # remove seconds from date and time and create string
        date_time = ":".join(str(current_time).split(":")[:-1])
        # Obtain rna sample name for name of appsession
        rna_sample_id = self.sample_pairs.get(dna_sample_id)
        with open(os.path.join("smpapp.config.template.json")) as smpapp_config_file:
            try:
                app_config = json.load(smpapp_config_file)
                inp = app_config.get("InputParameters")
                inp["app-result-dna-id"] = dna_config
                inp["project-id"] = f"projects/{self.project_id}"
                inp["app-result-rna-id"] = rna_config
                app_config["Name"] = f"{dna_sample_id}-{rna_sample_id} SMP2 v3 {date_time}"
            except json.decoder.JSONDecodeError:
                raise Exception("SMP config file is incorrectly formatted and does not contain valid json")
        return app_config

    def get_app_group_id(self):
        url = v1_api + "/applications"
        p = {"Limit": 200, "Offset": 0}
        head = {"Authorization": self.authorise, "Content-Type": "application/json"}
        response = requests.get(url, headers=head, params=p)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        else:
            for i in response.json().get("Response").get("Items"):
                if i.get("Name") == self.app_name:
                    self.app_group_id = i.get("Id")
        return self.app_group_id

    def get_app_id(self):
        url = v1_api + "/applications/" + self.app_group_id + "/versions"
        p = {"Limit": 200, "Offset": 0}
        head = {"Authorization": self.authorise, "Content-Type": "application/json"}
        response = requests.get(url, headers=head, params=p)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        else:
            for i in response.json().get("Response").get("Items"):
                if i.get("VersionNumber") == self.app_version:
                    self.app_id = i.get("Id")
        return self.app_id

    def get_app_form(self):
        url = v1_api + "/applications/" + self.app_id + "/assets/forms"
        p = {"status": "active"}
        head = {"Authorization": self.authorise, "Content-Type": "application/json"}
        response = requests.get(url, headers=head, params=p)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        else:
            app_form_id = response.json().get("Response").get("Items")[0] #TODO Set this line raise exception if >1
        return str(app_form_id.get("Id"))

    def get_app_form_items(self, app_form_id):
        url = v1_api + "/applications/" + self.app_id + "/assets/Forms/" + app_form_id + "/items"
        head = {"Authorization": self.authorise, "Content-Type": "application/json"}
        response = requests.get(url, headers=head)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        else:
            response = response.json()
        return response

    def get_biosample_info(self, biosample_id):
        url = v2_api + "/biosamples/" + biosample_id + "/libraries"
        p = {"Limit": 200, "Offset": 0}
        head = {"Authorization": self.authorise, "Content-Type": "application/json"}
        response = requests.get(url, headers=head, params=p)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        if len(response.json().get("Items")) > 1:
            raise Exception(f"More than one library for biosample {biosample_id}")
        return response.json().get("Items")[0].get("LibraryPrep").get("Id")

    def get_datasets(self, appsession_id, biosample_id):
        dataset_id = ""
        url = v2_api + "/datasets"
        p = {"limit": "50", "inputbiosamples": biosample_id, "datasettypes": "common.files",
             "include": "AppSessionRoot"}
        head = {"Authorization": self.authorise, "Content-Type": "application/json"}
        response = requests.get(url, headers=head, params=p)
        if response.status_code != 200:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        else:
            if len(response.json().get("Items")) > 1:
                for dataset in (response.json().get("Items")):
                    if dataset.get("AppSession").get("AppSessionRoot").get("Id") == appsession_id:
                        dataset_id = dataset.get("Id")
                    else:
                        raise Exception(f"Could not determine dataset id required to launch SMP2 app.")
            else:
                dataset_id = response.json().get("Items")[0].get("Id")
        return dataset_id

    def launch_application(self, app_conf):
        url = v2_api + "/applications/" + self.app_id + "/launch/"
        d = json.dumps(app_conf)
        head = {"Content-Type": "application/json", "Authorization": self.authorise}
        response = requests.post(url, headers=head, data=d)
        if response.status_code != 201:
            raise Exception(f"BaseSpace error. Error code {response.status_code} message {response.text}")
        return response.json().get("Id")
