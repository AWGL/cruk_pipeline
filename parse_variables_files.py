import glob
import os


def identify_samples():
    # All samples have a directory containing a variables file
    sample_ids = [x for x in os.listdir(os.path.curdir)
                  if os.path.isdir(x) and glob.glob(os.path.join(x, "*.variables"))]
    return sample_ids


def identify_worksheet(variables):
    worksheets = [(v.get('worklistId')).strip('"') for k, v in variables.items()]  # Remove quotes in variables file
    worksheets = list(set(worksheets))
    if len(worksheets) > 1:
        raise Exception("More than one worksheet id present on this run. Not sure what to call the project in "
                        "BaseSpace.")
    else:
        try:
            worksheet_id = worksheets[0]
        except IndexError as e:
            raise IndexError("No worksheet id for this run. Not sure what to call the project in BaseSpace")
    return worksheet_id


def locate_all_fastqs(samples, results_dir):
    # Create list for error handling when there are no fastqs found for a sample
    no_fastqs = []
    # Create dictionary to hold information about fastqs
    sample_fastqs_dict = {}
    # Iterate over all sample identifiers
    for sample in samples:
        # Create list of all fastqs matching sample id- all for upload into <sample>- pre-requisite to app launch
        sample_fastqs_list = (glob.glob(os.path.join(results_dir, sample, sample) + '*' + 'fastq.gz'))
        sample_fastqs_dict[sample] = sample_fastqs_list
        if not sample_fastqs_list:
            no_fastqs.append(sample)
    if no_fastqs:
        raise Exception(f"No fastqs found for sample or samples: {no_fastqs}")
    return sample_fastqs_dict


def load_all_variables(samples, results_dir):
    # Create dictionary to hold variables data
    sample_variables_dict = {}
    for sample in samples:
        # Create dictionary to hold key-value pairs
        variables_dict = {}
        with open(os.path.join(results_dir, sample, sample) + ".variables") as vf:
            for line in vf:
                split_line = line.split("=")
                try:
                    variables_dict[split_line[0]] = split_line[1].rstrip()
                except IndexError:
                    # Skip lines where there is no '='
                    pass
            sample_variables_dict[sample] = variables_dict
    return sample_variables_dict


def create_sample_pairs(variables):
    dna_dict = {}
    rna_dict = {}
    for k, v in variables.items():
        if v.get("sampleType") == "DNA":
            dna_dict[v.get("pairs")] = v.get("sampleId")
        elif v.get("sampleType") == "RNA":
            rna_dict[v.get("pairs")] = v.get("sampleId")
    pairs_dict = {}
    for patient_name in dna_dict.keys():
        if not patient_name == "null":
            pairs_dict[dna_dict.get(patient_name)] = rna_dict.get(patient_name, None)
    return pairs_dict


def find_samples_to_pair(variables):
    pairs_or_dna = {}
    to_pair = {}
    dna_only = {}
    for s, p in variables.items():
        if p.get('dna') == '0':
            to_pair[s] = p
        elif p.get('dna') == '1':
            dna_only[s] = p
    pairs_or_dna['dnas'] = dna_only
    pairs_or_dna['pairs'] = to_pair
    return pairs_or_dna





