import os
import shutil
from datetime import datetime

def move_file_with_timestamp(source_path):

    if not os.path.isfile(source_path):
       print("file does not exist - nothing moved")
       return
     
    # Get the current timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Split the path into directory and filename
    directory, filename = os.path.split(source_path)

    # Create the new filename with timestamp
    new_filename = f"{filename}.{timestamp}"

    # Combine the directory and new filename
    destination_path = os.path.join(directory, new_filename)

    # Move the file
    shutil.move(source_path, destination_path)

    print(f"File moved from {source_path} to {destination_path}")
