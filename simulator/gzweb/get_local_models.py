#!/usr/bin/python

import os
import shutil
import sys

import distutils.core


def copy_models(src, dst):

    list_dir = [os.path.join(src, x) for x in os.listdir(src)]
    sub_dirs = [x for x in list_dir if os.path.isdir(x)]
    for model_path in sub_dirs:
        if "model.config" in os.listdir(model_path):
            # sys.stdout.write(" copying %s" % model_path)
            print(".", end="")
            dest_dir = os.path.join(dst, os.path.split(model_path)[1])
            if os.path.isdir(dest_dir):
                shutil.rmtree(dest_dir)
                print(f"overriding model {model_path}")
            shutil.copytree(model_path, dest_dir)
        else:
            print(f" {model_path} ignored")


dest_dir = sys.argv[1]


print(f"copying local models to {dest_dir}")

unique_paths = None
try:
    gazebo_path = os.environ["GAZEBO_MODEL_PATH"].split(":")

    model_paths = [x for x in gazebo_path if os.path.isdir(x)]
    unique_paths = list(set(model_paths))
except KeyError:
    print("No local models.")
#    exit(0)

if unique_paths is not None:
    for path in unique_paths:
        print(f"\nmodel path: [{path}]")
        copy_models(path, dest_dir)

    print("local models transfered")


print(f"copying local resources to {dest_dir}")


def copy_resources(src, dst):
    media_path = os.path.join(src, "media")
    if os.path.exists(media_path) and os.path.isdir(media_path):
        dest_dir = os.path.join(dst, "media")
        distutils.dir_util.copy_tree(media_path, dest_dir)


unique_paths = None
try:
    resource_path = os.environ["GAZEBO_RESOURCE_PATH"].split(":")

    resource_paths = [x for x in resource_path if os.path.isdir(x)]
    unique_paths = list(set(resource_paths))
except KeyError:
    print("No local resources")
    exit(0)

if unique_paths is not None:
    for path in unique_paths:
        print(f"\nresource path: [{path}]")
        copy_resources(path, dest_dir)

print("local resources transfered")
