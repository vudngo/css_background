import sys
import pandas as pd
import time
from resemble import Resemble
from pathlib import Path
from pydub import AudioSegment
import json
import csv
from datetime import datetime
import zipfile
import subprocess
import boto3
import logging
import os
import requests


DEFAULT_PROJECT_UUID = 'cb1450c2'
OUTPUT_FILENAME =  datetime.now().strftime('%Y-%m-%d-%H-%M-%S') 
OUTPUT_FOLDER = '/cisco_tts_output/' +  OUTPUT_FILENAME
REMOTE_FILENAME =  OUTPUT_FOLDER + ".zip"
LOCAL_OUTPUT_FILE_PATH =  os.getcwd() + OUTPUT_FOLDER
LOGFILE_PATH =  os.getcwd() + OUTPUT_FOLDER +"/output.log"
project_uuid = ''
bucket_name = 'cisco-app'
public_url = ""


Resemble.syn_server_url('https://p6.cluster.resemble.ai/synthesize')

output_formats = {"sample_rate": 44100, "precision": "PCM_16", "output_path": "44.1khz_16bit_PCM"}



if not os.path.exists(LOCAL_OUTPUT_FILE_PATH):
            os.makedirs(LOCAL_OUTPUT_FILE_PATH)

def verify_inputs(project_uuid):
    response = Resemble.v2.projects.get(project_uuid)
    if response['success']:
        return True
    return False



def get_resemble_language_code(prompt_data):
    if prompt_data["language_code"].lower() == 'no-no':
        language_code = 'nb-no'
    elif prompt_data["language_code"].lower() == 'vi-vi':
        language_code = 'vi-vn'
    else: 
        language_code = prompt_data["language_code"].lower()
    return language_code

def get_voice_uuid(language_code):
    match language_code.lower():
        case "ar-sa":
            voice_uuid = '8bafb1a0'
        case _:
            voice_uuid = 'c464a8aa' #'c464a8aa' is original 37 language cisco, '9a97995e' is adobe enhanced version, '15e166c4' is 44 langauges adobe enhanced
    return voice_uuid    
  
def synthesize_tts_audio(prompt_data, output_format):
    resemble_language_code = get_resemble_language_code(prompt_data)
    project_uuid = sys.argv[3] if len(sys.argv[3]) > 0 else DEFAULT_PROJECT_UUID
    voice_uuid = get_voice_uuid(prompt_data["language_code"])
    body = f"<lang xml:lang=\"{resemble_language_code}\">{prompt_data['text']}</lang>"
    try:
        resemble_response = Resemble.v2.clips.create_sync(
            project_uuid, 
            voice_uuid, 
            body,
            title=prompt_data["filename"],
            sample_rate=output_format["sample_rate"],
            output_format='wav',
            precision=output_format["precision"]
            )
    except Exception as e:
        return str(e)
    return resemble_response

def get_output_path(prompt_data, output_format):
    return LOCAL_OUTPUT_FILE_PATH + '/' + prompt_data["Product"] + '/' + prompt_data["language_code"] + '/' + output_format["output_path"] + '/'

def download_sts_audio(prompt_data, resemble_response, output_format):
    #get the download link of the STS output file
    sts_audio_file_link = resemble_response['item']['audio_src']
    #download the STS output file
    sts_download_response = requests.get(sts_audio_file_link)

    if sts_download_response.status_code == 200:
        output_path = get_output_path(prompt_data, output_format)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        local_file_path =  output_path + prompt_data["filename"]
        if not os.path.exists(local_file_path):     
            with open(local_file_path, 'wb') as wav_file:
                wav_file.write(sts_download_response.content)
        return local_file_path
    else:
        print(f"Failed to download WAV file from Resemble. Status code: {sts_download_response.status_code}")
        return False
    
def zip_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))
    return True

def upload_file_to_s3(file_name, bucket, object_name=None):
    if object_name is None:
        object_name = file_name
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_name, bucket, object_name, ExtraArgs={'ACL': 'public-read'})
        return f"https://{bucket_name}.s3.amazonaws.com/{object_name}"
    except FileNotFoundError:
        print("The file was not found")
        return None
    except NoCredentialsError:
        print("Credentials not available")
        return None
    except PartialCredentialsError:
        print("Incomplete credentials")
        return None

def process_prompt(prompt_data):
    print(f"Processing: {prompt_data['Product']}/{prompt_data['language_code']}/{prompt_data['filename']}")

    if not prompt_data['filename'].endswith(".wav"):
        prompt_data['filename'] = prompt_data['filename'] + ".wav"
    start_time = time.time()
    resemble_response = synthesize_tts_audio(prompt_data, output_formats)
    if resemble_response['success']:
        local_file_path = download_sts_audio(prompt_data, resemble_response, output_formats)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print("Time taken:", elapsed_time, "seconds")
    else:
        print(f"Failed to synthesize: {prompt_data['filename']}")
        print(resemble_response)
    logging.info(f"Processing: {prompt_data['Product']}/{prompt_data['language_code']}/{prompt_data['filename']}")
    logging.info(f"Resemble API Response {resemble_response}")



if __name__ == '__main__':
    csv_file = sys.argv[1]
    csv_path = os.path.join(os.path.dirname(__file__), csv_file)

    api_key = sys.argv[2]
    project_uuid = sys.argv[3]
    df = pd.read_csv(csv_file)
    # Perform operations on the dataframe as needed
    Resemble.api_key(api_key)
    project_uuid = sys.argv[3] if len(sys.argv[3]) > 0 else DEFAULT_PROJECT_UUID
    #print(df)  # Example: Print the first few rows of the dataframe
    print(api_key)
    print(project_uuid)
    if verify_inputs(project_uuid):
        try:
            tts_prompt_data = []
            with open(csv_file, 'r', encoding='utf-8-sig') as file:    
                csv_reader = csv.DictReader(file)
                for row in csv_reader:          
                    tts_prompt_data.append(dict(row))
            print(tts_prompt_data)
            Resemble.api_key(api_key)
            logging.basicConfig(
                filename=LOGFILE_PATH,
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )
            for prompt_data in tts_prompt_data:
                #print(prompt_data)
                process_prompt(prompt_data)
                        
            output_zip_file = LOCAL_OUTPUT_FILE_PATH + ".zip"
            #print(f"zip folder path: {output_zip_file}")
            if zip_folder(LOCAL_OUTPUT_FILE_PATH, output_zip_file):
                object_name = OUTPUT_FILENAME+".zip"
                public_url = upload_file_to_s3(output_zip_file, bucket_name, object_name)
                if public_url:
                    html = '''<a href="{{ link_url }}" target="_blank">Download results</a>'''
                    print(public_url)
                    #return render_template_string(html, link_url=public_url)
                else:
                    print(f"try going to https://{bucket_name}.s3.amazonaws.com/{object_name}")
        except Exception as e:
            raise e
            #return str(e)
    else:
        print( f"The Project UUID '{project_uuid}' could not be found using the API Key you've provided")
