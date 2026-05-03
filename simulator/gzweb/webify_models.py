#!/usr/bin/python

# To be deprecated and replaced by webify_models_v2.py

# A script to update gazebo models to be web-friendly.
# It converts all textures to png format and make sure they are
# stored in the [model_name]/meshes/ directory alongside the
# dae files.

import os
import subprocess
import sys

print("**************************************")
print("* 'webify_models.py' is deprecated.  *")
print("* Use 'webify_models_v2.py' instead. *")
print("**************************************")

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
        # dest_dir = path.replace('materials/textures', 'meshes')
        dest_dir = path
        dest_path = f"{dest_dir}/{name}.png"
        if format.lower() in ["tif", "tga", "tiff", "jpeg", "jpg", "gif", "png"]:
            if dest_path != file:
                cmd = ["convert", file, dest_path]
                subprocess.check_call(cmd)

            mesh_dest_dir = path.replace("materials/textures", "meshes")
            if mesh_dest_dir != dest_dir:
                cmd = ["cp", dest_path, mesh_dest_dir]
                # if format.lower() == 'png':
                #  cmd = ['cp', file, mesh_dest_dir]
                print(cmd)
                subprocess.check_call(cmd)

        if format.lower() in ["dae"]:
            sed_cmd = [
                "sed",
                "-i",
                "-e",
                r"s/\.tga/\.png/g",
                "-e",
                r"s/\.tiff/\.png/g",
                "-e",
                r"s/\.tif/\.png/g",
                "-e",
                r"s/\.jpg/\.png/g",
                "-e",
                r"s/\.jpeg/\.png/g",
                "-e",
                r"s/\.gif/\.png/g",
                file,
            ]
            print(sed_cmd)
            subprocess.check_call(sed_cmd)
    except Exception as e:
        print(f"error {e}")
        raise
