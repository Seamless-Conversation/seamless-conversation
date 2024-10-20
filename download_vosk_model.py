import os
import urllib.request
import zipfile
import sys

def download_and_extract_model():
    model_url = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
    model_zip = "models/vosk-model-en-us-0.22.zip"
    model_dir = "models/vosk-model-en-us-0.22"

    if not os.path.exists(model_dir):
        if not os.path.exists('models'):
            os.makedirs('models')

        print("Downloading Vosk model...")

        def reporthook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = int(downloaded * 100 / total_size)
            sys.stdout.write(f"\rDownloading: {percent}%")
            sys.stdout.flush()
        urllib.request.urlretrieve(model_url, model_zip, reporthook)
        print("\nDownload completed.")

        print("Extracting the model...")

        with zipfile.ZipFile(model_zip, 'r') as zip_ref:
            total_files = len(zip_ref.infolist())
            for i, file in enumerate(zip_ref.infolist()):
                zip_ref.extract(file, "models")
                percent = int((i + 1) * 100 / total_files)
                sys.stdout.write(f"\rExtracting: {percent}%")
                sys.stdout.flush()
        print("\nExtraction completed.")

        os.remove(model_zip)
        print("Cleanup completed.")
    else:
        print("Model already exists. Skipping download.")

if __name__ == "__main__":
    download_and_extract_model()
