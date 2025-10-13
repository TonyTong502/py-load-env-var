import base64
import io
import os.path
import json
import shutil
import zipfile
import requests
from datetime import datetime
import xml.etree.ElementTree as ET

def get_token(config):
    payload = f"client_id={config["clientid"]}&client_secret={config["clientsecret"]}&grant_type=client_credentials"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(config["tokenurl"], headers= headers, data= payload)
    data = json.loads(response.content)
    return data["access_token"]

def get_list_packages_url(config):
    return f"{config['url']}/api/v1/IntegrationPackages"

def list_packages(list_package_url, headers):
    response = requests.get(list_package_url, headers=headers)
    data = json.loads(response.text)
    result = []
    for item in data["d"]["results"]:
        result.append({
            "id": item["Id"],
            "name": item["Name"],
            "url": item["__metadata"]["media_src"],
            "artifacts": {
                "integration_flow": item["IntegrationDesigntimeArtifacts"]["__deferred"]["uri"],
                "value_mapping": item["ValueMappingDesigntimeArtifacts"]["__deferred"]["uri"],
                "message_mapping": item["MessageMappingDesigntimeArtifacts"]["__deferred"]["uri"],
                "script_collection": item["ScriptCollectionDesigntimeArtifacts"]["__deferred"]["uri"]
            }
        })
    return result

def include_packages(packages_all, package_ids_to_be_downloaded):
    result = []
    for item in packages_all:
        pkg_id = str(item["id"]).strip()
        if pkg_id in package_ids_to_be_downloaded:
            result.append(item)
    if len(result) == 0:
        return packages_all
    else:
        return result

def download_package(package_url, headers):
    response = requests.get(package_url, headers=headers)
    status = "success" if response.status_code == 200 else "error"
    return {
        "status": status,
        "data": response.content
    }

def list_artifacts(list_artifact_url, headers):
    response = requests.get(list_artifact_url, headers=headers)
    data = json.loads(response.text)
    result = []
    for item in data["d"]["results"]:
        name = str(item["Name"])
        print(name)
        result.append({
            "id": item["Id"],
            "name": name,
            "url": item["__metadata"]["media_src"]
        })
    return result

def get_dict_from_entry_node(entry: ET.Element):
    return {
        "agency": entry.find("agency").text,
        "key": entry.find("schema").text,
        "value": entry.find("value").text
    }

def convert_value_mapping(xml_text: str):
    root = ET.fromstring(xml_text)
    group_elements = root.findall("group")
    data = {}
    for group in group_elements:
        first_entry = group.find("./entry[1]")
        source_dict = get_dict_from_entry_node(first_entry)
        second_entry = group.find("./entry[2]")
        target_dict = get_dict_from_entry_node(second_entry)
        #,source_a1|source_id1,target_a1|target_id1
        key = f",{source_dict["agency"]}|{source_dict["key"]},{target_dict["agency"]}|{target_dict["key"]}"
        #,k1|,v1
        value = f",{source_dict["value"]}|,{target_dict["value"]}"
        if key not in data.keys():
            data[key] = [value]
        else:
            data[key].append(value)
    lines = []
    sorted_keys = sorted(data.keys())
    for k in sorted_keys:
        lines.append(k)
        sorted_items = sorted(data.get(k))
        for i in sorted_items:
            lines.append(i)
    return "\n".join(lines)

def download_artifacts(package_artifacts, headers):
    integration_flow_link = package_artifacts["integration_flow"]
    integration_flow_list = list_artifacts(integration_flow_link, headers)
    value_mapping_link = package_artifacts["value_mapping"]
    value_mapping_list = list_artifacts(value_mapping_link, headers)
    message_mapping_link = package_artifacts["message_mapping"]
    message_mapping_list = list_artifacts(message_mapping_link, headers)
    script_collection_link = package_artifacts["script_collection"]
    script_collection_list = list_artifacts(script_collection_link, headers)

    all_artifacts_list = integration_flow_list + value_mapping_list + message_mapping_list + script_collection_list
    result = []
    for artifact in all_artifacts_list:
        download_url = str(artifact['url']).replace("Version='Draft'", "Version='Active'")
        artifact_dl = download_package(download_url, headers)
        result.append({"id": artifact["id"], "status": artifact_dl["status"], "data": artifact_dl["data"]})
    return result

def unzip_artifact(artifact_id: str, artifact_data: bytes, parent: str, package_name: str):
    with zipfile.ZipFile(io.BytesIO(artifact_data)) as azip:
        if "value_mapping.xml" in azip.namelist():
            vm_xml = azip.read("value_mapping.xml").decode()
            vm_csv = convert_value_mapping(vm_xml)
            with open(f"{parent}/{package_name}/{artifact_id}.csv", "w") as wf:
                wf.write(vm_csv)
        else:
            azip.extractall(f"\\\\?\\{parent}/{package_name}/{artifact_id}")

def unzip_package(package_name: str, package_data: bytes, parent: str):
    # unzip
    zf = zipfile.ZipFile(io.BytesIO(package_data))

    # create package folder
    os.mkdir(f"{parent}/{package_name}")

    content = base64.b64decode(zf.read("resources.cnt"))
    data = json.loads(content)

    for resource in data['resources']:
        name = str(resource['name'])
        if name.endswith(".zip"):
            rid = str(resource['id'])
            uid = str(resource['uniqueId'])
            rtype = str(resource['resourceType'])
            artifact_bs = zf.read(f"{rid}_content")
            with zipfile.ZipFile(io.BytesIO(artifact_bs)) as azip:
                if rtype == "ValueMapping":
                    vm_xml = azip.read("value_mapping.xml").decode()
                    vm_csv = convert_value_mapping(vm_xml)
                    with open(f"{parent}/{package_name}/{uid}.csv", "w") as wf:
                        wf.write(vm_csv)
                else:
                    azip.extractall(f"{parent}/{package_name}/{uid}")

def download_packages():
    target_dir = "."
    service_key_text = os.environ.get("service_key")
    package_list_text = os.environ.get("package_ids_to_be_downloaded")
    oauth = json.loads(service_key_text)
    config = oauth["oauth"]
    print(f"get packages list url")
    list_packages_url = get_list_packages_url(config)
    access_token = get_token(config)
    headers = {"Authorization": f"Bearer {access_token}", "accept": "application/json" }
    print("get packages info")
    packages = list_packages(list_packages_url, headers)
    if os.path.exists("packages_to_be_downloaded.txt"):
        lines = package_list_text.splitlines()
        packages = include_packages(packages, lines)
    logs = []
    for package in packages:
        package_id = package["id"]
        package_url = package["url"]
        print(f"going to download package by id {package_id}")
        data = download_package(package_url, headers)
        print(f"package: {package_id} download complete, status:{data["status"]}")
        if data["status"] == "error":
            print(f"download package: {package_id} failed, going to download artifacts instead.")
            logs.append(f"download package: {package_id} failed, going to download artifacts instead.\n")
            package_artifacts = download_artifacts(package["artifacts"], headers)
            package_folder = f"{target_dir}/{package_id}"
            if os.path.exists(package_folder):
                shutil.rmtree(package_folder)
            os.mkdir(package_folder)
            for artifact in package_artifacts:
                artifact_id = artifact["id"]
                artifact_status = artifact["status"]
                artifact_data = artifact["data"]
                if artifact_status == "error":
                    logs.append(f"download package: {package_id} failed, error details: {artifact_data}\n")
                else:
                    unzip_artifact(artifact_id, artifact_data, target_dir, package_id)
        else:
            print(f"download package: {package_id} succeeded, going to unzip package zip.")
            logs.append(f"download package: {package_id} succeeded, going to unzip package zip.\n")
            unzip_package(package_id, data["data"], target_dir)
    if len(logs) > 0:
        with open(f"log_{datetime.now().strftime('%Y%m%d%H%M%S')}.log", "w") as lf:
            lf.writelines(logs)

if __name__ == "__main__":
    download_packages()
