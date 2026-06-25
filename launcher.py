#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BlockSack Launcher Core
Downloads assets, libraries, and the client jar from Mojang's official servers,
constructs the classpath, and launches Minecraft.
"""

import json
import urllib.request
import os
import subprocess
import platform
import concurrent.futures
import time

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ASSET_URL_BASE = "https://resources.download.minecraft.net"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "username": "fitzypopper",
    "version": "1.21",
    "ram_max": "2G",
    "java_path": "java",
    "game_dir": "instances/main"
}

def load_config():
    """Loads configuration from file or creates a default one."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_CONFIG
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def download_file(url, path, retries=3):
    """Downloads a file with automatic retries and User-Agent spoofing."""
    if os.path.exists(path):
        return  # Skip if file already exists
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                with open(path, 'wb') as out_file:
                    out_file.write(response.read())
            return
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                print(f"[ERROR] Failed to download {url} after {retries} attempts: {e}")

def get_json(url):
    """Fetches and parses a JSON response from a given URL."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    })
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def is_allowed_on_os(rules):
    """Validates if a specific library should be downloaded for the current OS."""
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

def main():
    print("--- BlockSack Launcher CLI ---")
    config = load_config()
    target_version = config["version"]
    username = config["username"]
    game_dir = config.get("game_dir", "instances/main")

    print(f"[*] Fetching manifest for version {target_version}...")
    manifest = get_json(MANIFEST_URL)
    version_entry = next((v for v in manifest["versions"] if v["id"] == target_version), None)

    if not version_entry:
        print(f"[!] Could not find version {target_version} in the manifest.")
        return

    print(f"[*] Downloading package data for {target_version}...")
    version_data = get_json(version_entry["url"])

    # 1. Download Client .jar
    client_url = version_data["downloads"]["client"]["url"]
    client_jar = os.path.join("versions", target_version, f"{target_version}.jar")
    print("[*] Verifying client.jar...")
    download_file(client_url, client_jar)

    # 2. Download Libraries
    print("[*] Analyzing and downloading libraries...")
    libraries = []
    download_tasks = []
    
    for lib in version_data.get("libraries", []):
        if not is_allowed_on_os(lib.get("rules")):
            continue
            
        downloads = lib.get("downloads", {})
        if "artifact" in downloads:
            artifact = downloads["artifact"]
            path = os.path.join("libraries", artifact["path"])
            libraries.append(path)
            download_tasks.append((artifact["url"], path))

    # 3. Download Assets
    asset_index_info = version_data.get("assetIndex", {})
    asset_index_id = asset_index_info.get("id", target_version)
    asset_index_url = asset_index_info.get("url")
    asset_index_path = os.path.join("assets", "indexes", f"{asset_index_id}.json")

    if asset_index_url:
        print("[*] Fetching asset index...")
        download_file(asset_index_url, asset_index_path)
        
        with open(asset_index_path, "r", encoding="utf-8") as f:
            asset_index = json.load(f)
            
        print("[*] Preparing asset downloads...")
        for key, obj in asset_index.get("objects", {}).items():
            hash_val = obj["hash"]
            sub_hash = hash_val[:2]
            asset_url = f"{ASSET_URL_BASE}/{sub_hash}/{hash_val}"
            asset_path = os.path.join("assets", "objects", sub_hash, hash_val)
            download_tasks.append((asset_url, asset_path))

    # Execute downloads in parallel (limited to 5 threads to avoid rate limits)
    total_tasks = len(download_tasks)
    if total_tasks > 0:
        print(f"[*] Processing {total_tasks} files. Please wait...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(download_file, url, path) for url, path in download_tasks]
            concurrent.futures.wait(futures)

    # 4. Build Classpath and Launch
    print("[*] Downloads complete. Building launch parameters...")
    
    cp_separator = ":" if platform.system() != "Windows" else ";"
    classpath = cp_separator.join(libraries + [client_jar])

    main_class = version_data.get("mainClass", "net.minecraft.client.Main")
    
    mc_args = [
        config["java_path"],
        f"-Xmx{config['ram_max']}",
        "-cp", classpath,
        main_class,
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
