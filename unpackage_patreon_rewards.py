# Example commands:
# 7z x 'Patreon Campaign - info.7z' -oCampaign/
# unzip 'Patreon Campaign - info.zip' -d 'Campaign/'
# unrar x 'Patreon Campaign - info.rar' 'Campaign/'

# Short Comings:
# - Passworded files are not auto handled (might cause problems)
# - Archives with duplicate file names from other archives are not auto handled
# - Pre-existing folders before unpackaging will get renamed as well
# - 7zip files with spaces in the name may break; current patch untested

# Standard imports
import os
import subprocess


VERSION = "v1.0.0"

for _, _, files in os.walk("."):
    for file_name in files:
        output_folder = file_name.split(" - ")[0]
        if ".zip" in file_name:
            subprocess.call(
                "unzip '{}' -d '{}/'".format(
                    file_name, output_folder
                ),
                shell=True,
            )
        elif ".rar" in file_name:
            subprocess.call(
                "unrar x '{}' '{}/'".format(
                    file_name, output_folder
                ),
                shell=True,
            )
        elif ".7z" in file_name:
            subprocess.call(
                "7z x '{}' -o'{}/'".format(file_name, output_folder),
                shell=True,
            )

for folder_name, _, files in os.walk("."):
    if len(folder_name.split("/")) <= 1:
        continue  # Ignore root

    artist = folder_name.split("/")[1]
    for file_name in files:
        os.rename(
            "{}/{}".format(folder_name, file_name),
            "{}/{} - {}".format(folder_name, artist, file_name),
        )
