# coding=utf-8
# Copyright 2021 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import yaml
from packaging import version as package_version


def update_versions_file(build_path, version):
    """
    Insert new version into _versions.yml file of the library
    Assumes that _versions.yml exists and has its first entry as master version
    """
    if version == "master":
        return
    with open(f"{build_path}/_versions.yml", "r") as versions_file:
        versions = yaml.load(versions_file, yaml.FullLoader)

        if versions[0]["version"] != "master":
            raise ValueError(f"{build_path}/_versions.yml does not contain master version")

        master_version, sem_versions = versions[0], versions[1:]
        new_version = {"version": version}
        did_insert = False
        for i, value in enumerate(sem_versions):
            if package_version.parse(new_version["version"]) > package_version.parse(value["version"]):
                sem_versions.insert(i, new_version)
                did_insert = True
                break
        if not did_insert:
            sem_versions.append(new_version)

    with open(f"{build_path}/_versions.yml", "w") as versions_file:
        versions_updated = [master_version] + sem_versions
        yaml.dump(versions_updated, versions_file)