from pydub import AudioSegment
import os
import requests
import time
from dotenv import load_dotenv

## This function to convert from mp4 and m4a to mp3 which is a lighter format
## compatible with whispers.

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
API_VERSION = os.getenv("API_VERSION")

def convert_media_to_mp3(directory):
    """
    Converts all .m4a and .mp4 files in the specified directory to .mp3 format and saves them in a subdirectory named 'mp3'.

    Parameters:
    directory (str): The path to the directory containing .m4a and .mp4 files.
    """
    mp3_directory = os.path.join(directory, 'mp3')

    #
    if not os.path.exists(mp3_directory):
        os.makedirs(mp3_directory)

    for filename in os.listdir(directory):
        if filename.endswith('.m4a') or filename.endswith('.mp4'):
            file_path = os.path.join(directory, filename)
            mp3_filename = os.path.splitext(filename)[0] + '.mp3'
            mp3_path = os.path.join(mp3_directory, mp3_filename)


            audio = AudioSegment.from_file(file_path, format="mp4" if filename.endswith('.mp4') else "m4a")
            audio.export(mp3_path, format="mp3")
            print(f"Converted {filename} to MP3 and saved in 'mp3' subdirectory")

## This function cuts anything bigger than 25 mb (the limit of the api) into
## two files, returning them with the original name 1 and 2.
def cut_large_mp3_files(directory):
    """
    Cuts .mp3 files larger than 25 MB in the specified directory into two halves.

    Parameters:
    directory (str): The path to the directory containing .mp3 files.
    """
    for filename in os.listdir(directory):
        if filename.endswith('.mp3'):
            file_path = os.path.join(directory, filename)
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # size in MB

            if file_size > 25:
                audio = AudioSegment.from_file(file_path)

                # Cutting the file in half
                half_way_point = len(audio) // 2
                audio_part1 = audio[:half_way_point]
                audio_part2 = audio[half_way_point:]

                # Exporting the two halves
                base_filename = filename.replace('.mp3', '')
                audio_part1.export(os.path.join(directory, f"{base_filename} 1.mp3"), format="mp3")
                audio_part2.export(os.path.join(directory, f"{base_filename} 2.mp3"), format="mp3")

                print(f"Processed {filename}")


## Variation of the previous one to clean up resources after doing it, this way
## the original file is removed.
def process_and_cleanup_mp3_files(directory):
    """
    Processes .mp3 files larger than 25 MB by cutting them into two halves and deletes the original file.

    Parameters:
    directory (str): The path to the directory containing .mp3 files.
    """
    for filename in os.listdir(directory):
        if filename.endswith('.mp3'):
            file_path = os.path.join(directory, filename)
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # size in MB

            if file_size > 24:
                audio = AudioSegment.from_file(file_path)

                # Cutting the file in half
                half_way_point = len(audio) // 2
                audio_part1 = audio[:half_way_point]
                audio_part2 = audio[half_way_point:]

                # Exporting the two halves
                base_filename = filename.replace('.mp3', '')
                audio_part1.export(os.path.join(directory, f"{base_filename} 1.mp3"), format="mp3")
                audio_part2.export(os.path.join(directory, f"{base_filename} 2.mp3"), format="mp3")

                # Deleting the original file
                os.remove(file_path)

                print(f"Processed and deleted {filename}")


## Core function transcribes audio to text, might make some mistakes confusing
## Galician with Portuguese but changing the prompt helps improving it

def transcribe_audio_to_text(audio_file_path, save_path=None):



    headers = {
        "api-key": AZURE_OPENAI_KEY
    }
    files = {
        "file": open(audio_file_path, "rb")
    }
    params = {
        "api-version": API_VERSION,
        "language": "es",
        "prompt": "You are going to be provided audio of interviews in Spanish, help transcribe them returning the text in Spanish",
        "temperature":0
    }


    response = requests.post(AZURE_OPENAI_ENDPOINT, headers=headers, files=files, params=params)

    files["file"].close()


    if response.status_code == 200:
        transcription = response.json().get('text')
        if transcription:

            save_path = save_path or os.path.splitext(audio_file_path)[0] + '.txt'
            with open(save_path, 'w') as text_file:
                text_file.write(transcription)
            print(f"Transcription saved to {save_path}")
        else:
            print("Transcription received but was empty.")
    else:
        print("Error:", response.status_code, response.text)



## A wrapper function to transcribe everything within a directory.

def transcribe_all_mp3_in_directory(directory, retry_delay=60, max_retries=3):
    """
    Processes all .mp3 files in the specified directory for transcription, skipping files already transcribed.

    Parameters:
    directory (str): The path to the directory containing .mp3 files.
    retry_delay (int): Time in seconds to wait before retrying after a 503 error.
    max_retries (int): Maximum number of retries for each file in case of 503 errors.
    """
    for filename in os.listdir(directory):
        if filename.endswith('.mp3'):
            audio_file_path = os.path.join(directory, filename)
            transcription_save_path = os.path.splitext(audio_file_path)[0] + '.txt'


            if os.path.exists(transcription_save_path):
                print(f"Skipping {filename}, transcription already exists.")
                continue

            
            retries = 0
            while retries < max_retries:
                try:
                    transcribe_audio_to_text(audio_file_path, save_path=transcription_save_path)
                    break  # Break the loop if transcription is successful
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 503:
                        print(f"503 Service Unavailable error for {filename}. Retrying in {retry_delay} seconds.")
                        time.sleep(retry_delay)
                        retries += 1
                    else:
                        print(f"Error transcribing {filename}: {e}")
                        break
                except Exception as e:
                    print(f"An error occurred while transcribing {filename}: {e}")
                    break
