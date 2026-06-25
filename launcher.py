#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BlockStack Launcher Core
Downloads assets, libraries, and the client jar from Mojang's official servers.
Automatically manages and downloads correct portable Java versions.
"""

import json
import urllib.request
import os
import subprocess
import platform
import concurrent.futures
import time
import tarfile
import zipfile

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ASSET_URL_BASE = "https://resources.download.minecraft.net"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "username": "Steve",
    "version": "26.2",
    "ram_max": "2G",
    "java_path": "auto",  # 'auto' triggers portable Java downloads
    "game_dir": "instances/main"
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_CONFIG
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in data:
                data[k] = v
        return data

def download_file(url, path, retries=3, show_errors=True):
    if os.path.exists(path):
        return
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    })

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                with open(path, 'wb') as out_file:
                    out_file.write(response.read())
            return
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            elif show_errors:
                print(f"[ERROR] Failed to download {url}: {e}")

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def is_allowed_on_os(rules):
    if not rules:
        return True
    
    current_os = "linux" if platform.system() == "Linux" else ("osx" if platform.system() == "Darwin" else "windows")
    allowed = False

    for rule in rules:
        action = rule.get("action")
        os_match = rule.get("os", {}).get("name")
        if action == "allow":
            if not os_match or os_match == current_os:
                allowed = True
        elif action == "disallow":
            if os_match == current_os:
                allowed = False
    return allowed

def get_portable_java(major_version):
    """Downloads and extracts the required Java runtime for the OS."""
    os_name = platform.system().lower()
    if os_name == "darwin":
        adoptium_os = "mac"
    elif os_name == "windows":
        adoptium_os = "windows"
    else:
        adoptium_os = "linux"

    arch = platform.machine().lower()
    if arch in ['x86_64', 'amd64']:
        adoptium_arch = "x64"
    elif arch in ['aarch64', 'arm64']:
        adoptium_arch = "aarch64"
    else:
        adoptium_arch = "x32"

    ext = "zip" if adoptium_os == "windows" else "tar.gz"
    runtime_dir = os.path.join("runtimes", f"jre-{major_version}")
    java_exe = "java.exe" if adoptium_os == "windows" else "java"

    # Kolla om Java redan är nedladdat och uppackat
    if os.path.exists(runtime_dir):
        for root, dirs, files in os.walk(runtime_dir):
            if java_exe in files and "bin" in root.split(os.sep):
                return os.path.join(root, java_exe)

    print(f"[*] Downloading portable Java {major_version} (This only happens once)...")
    os.makedirs("runtimes", exist_ok=True)
    
    # Ladda ner JRE från Eclipse Temurin (Adoptium)
    api_url = f"https://api.adoptium.net/v3/binary/latest/{major_version}/ga/{adoptium_os}/{adoptium_arch}/jre/hotspot/normal/eclipse"
    archive_path = os.path.join("runtimes", f"jre-{major_version}.{ext}")
    
    download_file(api_url, archive_path, retries=2)

    if not os.path.exists(archive_path):
        print(f"[!] Could not download Java {major_version}. Falling back to system 'java'.")
        return "java"

    print(f"[*] Extracting Java {major_version}...")
    if ext == "tar.gz":
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=runtime_dir)
    else:
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(runtime_dir)

    os.remove(archive_path) # Städa upp

    # Hitta och ge exekveringsrättigheter (för Linux/Mac)
    for root, dirs, files in os.walk(runtime_dir):
        if java_exe in files and "bin" in root.split(os.sep):
            executable = os.path.join(root, java_exe)
            if adoptium_os != "windows":
                os.chmod(executable, 0o755)
            return executable

    return "java"

def main():
    print("--- HangryLauncher CLI ---")
    config = load_config()
    target_version = config["version"]
    username = config["username"]
    game_dir = config.get("game_dir", "instances/main")

    print(f"[*] Fetching manifest for version {target_version}...")
    manifest = get_json(MANIFEST_URL)
    version_entry = next((v for v in manifest["versions"] if v["id"] == target_version), None)

    if not version_entry:
        print(f"[!] Could not find version {target_version}.")
        return

    print(f"[*] Downloading package data for {target_version}...")
    version_data = get_json(version_entry["url"])

    # --- Hämta rätt Java ---
    java_path = config.get("java_path", "auto")
    if java_path.lower() == "auto":
        # Kolla vilken version Mojang rekommenderar, annars fallback till Java 8 för gamla versioner
        required_java = version_data.get("javaVersion", {}).get("majorVersion", 8)
        java_path = get_portable_java(required_java)

    # 1. Download Client
    client_jar = os.path.join("versions", target_version, f"{target_version}.jar")
    print("[*] Verifying client.jar...")
    download_file(version_data["downloads"]["client"]["url"], client_jar)

    # 2. Download Libraries
    print("[*] Analyzing and downloading libraries...")
    libraries = []
    download_tasks = []
    
    for lib in version_data.get("libraries", []):
        if not is_allowed_on_os(lib.get("rules")):
            continue
        if "artifact" in lib.get("downloads", {}):
            artifact = lib["downloads"]["artifact"]
            path = os.path.join("libraries", artifact["path"])
            libraries.append(path)
            download_tasks.append((artifact["url"], path))

    # 3. Download Assets
    asset_index_id = version_data.get("assetIndex", {}).get("id", target_version)
    asset_index_url = version_data.get("assetIndex", {}).get("url")
    asset_index_path = os.path.join("assets", "indexes", f"{asset_index_id}.json")

    if asset_index_url:
        print("[*] Fetching asset index...")
        download_file(asset_index_url, asset_index_path)
        with open(asset_index_path, "r", encoding="utf-8") as f:
            asset_index = json.load(f)
            
        print("[*] Preparing asset downloads...")
        for obj in asset_index.get("objects", {}).values():
            hash_val = obj["hash"]
            asset_url = f"{ASSET_URL_BASE}/{hash_val[:2]}/{hash_val}"
            download_tasks.append((asset_url, os.path.join("assets", "objects", hash_val[:2], hash_val)))

    if download_tasks:
        print(f"[*] Processing files. Please wait...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(download_file, url, path, 3, False) for url, path in download_tasks]
            concurrent.futures.wait(futures)

    # 4. Launch
    print("[*] Downloads complete. Building launch parameters...")
    cp_separator = ":" if platform.system() != "Windows" else ";"
    classpath = cp_separator.join(libraries + [client_jar])

    mc_args = [
        java_path,
        f"-Xmx{config['ram_max']}",
        "-cp", classpath,
        version_data.get("mainClass", "net.minecraft.client.Main"),
        "--username", username,
        "--version", target_version,
        "--gameDir", game_dir,
        "--assetsDir", "assets",
        "--assetIndex", asset_index_id,
        "--uuid", "00000000-0000-0000-0000-000000000000",
        "--accessToken", "0",
        "--userType", "mojang",
        "--versionType", "release"
    ]

    print(f"\n[+] Launching Minecraft {target_version} as {username}...")
    subprocess.run(mc_args)

if __name__ == "__main__":
    main()
