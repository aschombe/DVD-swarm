#!/usr/bin/python

# A script to update gazebo models to be web-friendly.
# It converts all textures to png format and make sure they are
# stored in the [model_name]/materials/textures/ directory.
# Texture references in the collada dae files are also updated
# to have the correct path.

# Usage: ./webify_models_v2.py path_to_model_directory

import os
import subprocess
import sys

# explicitly set encoding in osx otherwise sometimes sed throws
# an illegal byte sequence error
if sys.platform == "darwin":
    os.environ["LANG"] = "C"

path = sys.argv[1]

files = os.listdir(path)

find_cmd = ["find", path, "-name", "*"]
files = subprocess.check_output(find_cmd, text=True).split()

for file in files:
    try:
        path, filename = os.path.split(file)
        name, format = filename.split(".")[-2:]
    except ValueError:
        continue  # not a texture

    try:
        dest_dir = path
        dest_path = f"{dest_dir}/{name}.png"

        # convert texture files to png
        if format.lower() in ["tif", "tga", "tiff", "jpeg", "jpg", "gif", "png"]:
            if dest_path != file:
                cmd = ["convert", file, dest_path]
                subprocess.check_call(cmd)
                cmd = ["rm", file]
                subprocess.check_call(cmd)

            # make sure texture files only exist in materials/textures dir
            texture_dir = path
            if texture_dir.find("materials/textures") == -1 and texture_dir.find("meshes") != -1:
                model_path, other = texture_dir.split("meshes")
                texture_dir = os.path.join(model_path, "materials/textures")
                cmd = ["mkdir", "-p", texture_dir]
                subprocess.check_call(cmd)

            if texture_dir != dest_dir:
                cmd = ["mv", dest_path, texture_dir]
                print(cmd)
                subprocess.check_call(cmd)

        # update texture path in dae files
        if format.lower() in ["dae"]:
            sed_cmd = [
                "sed",
                "-i",
                "-e",
                r"s/\(\.tga\|\.tiff\|\.tif\|\.jpg\|\.jpeg\|\.gif\)/\.png/g",
                file,
            ]
            print(sed_cmd)
            subprocess.check_call(sed_cmd)

            # find relative path to texture dir
            texture_dir = path
            if texture_dir.find("materials/textures") == -1 and texture_dir.find("meshes") != -1:
                model_path, other = texture_dir.split("meshes")
                subdir_count = len(other.split("/"))
                relative_path = ""
                for _ in range(0, subdir_count):
                    relative_path = relative_path + r"\.\.\/"

                # replace dae file png references to texture path
                sed_cmd = [
                    "sed",
                    "-i",
                    "-e",
                    r"s/\(>\)\(.*\/\)\(.*\.png\)/\\1"
                    + relative_path
                    + r"materials\/textures\/\\3/g",
                    file,
                ]
                print(sed_cmd)
                subprocess.check_call(sed_cmd)

                sed_cmd = [
                    "sed",
                    "-i",
                    "-e",
                    r"/[a-zA-Z0-9_\.\/\-]\+materials\/textures/!"
                    + r"s/\([a-zA-Z0-9_\-]\+\)\(\.png\W\)/"
                    + relative_path
                    + r"materials\/textures\/\\1\\2/g",
                    file,
                ]

                print(sed_cmd)
                subprocess.check_call(sed_cmd)

        if format.lower() in ["material", "txt", "sdf"]:
            sed_cmd = [
                "sed",
                "-i",
                "-e",
                r"s/\(\.tga\|\.tiff\|\.tif\|\.jpg\|\.jpeg\|\.gif\)/\.png/g",
                file,
            ]
            print(sed_cmd)
            subprocess.check_call(sed_cmd)

    except Exception as e:
        print(f"error {e}")
        raise
