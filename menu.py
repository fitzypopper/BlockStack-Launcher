#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BlockSack Launcher GUI
A lightweight Tkinter interface to manage profiles, instances, and trigger the core launcher.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import subprocess
import threading

# === BRANDING & TEXTS ===
APP_NAME = "BlockSack Launcher"
APP_SUBTITLE = "Manage your profiles and instances"
START_BUTTON_TEXT = "▶ START GAME"
AUTHOR_TEXT = "Developed by fitzypopper"
# ========================

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "username": "Steve",
    "version": "1.21",
    "ram_max": "2G",
    "java_path": "java",
    "game_dir": "instances/main"
}

def load_config():
    """Reads config data or generates a fallback if missing."""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Inject missing keys from default config
            for key, value in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = value
            return data
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(data):
    """Saves the current state to the configuration file."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

class LauncherMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("450x400")
        self.resizable(False, False)
        
        self.config_data = load_config()
        
        self.create_header()
        self.create_tabs()
        self.create_footer()

    def create_header(self):
        header_frame = tk.Frame(self, pady=10)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text=APP_NAME, font=("Helvetica", 18, "bold")).pack()
        tk.Label(header_frame, text=APP_SUBTITLE, font=("Helvetica", 10)).pack()

    def create_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=5)
        
        # Tab 1: Play (Profile & Version)
        self.play_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.play_tab, text="Play")
        
        ttk.Label(self.play_tab, text="Username (Skin/Profile):").pack(anchor="w", padx=10, pady=(15, 2))
        self.entry_username = ttk.Entry(self.play_tab, font=("Helvetica", 12))
        self.entry_username.insert(0, self.config_data.get("username", ""))
        self.entry_username.pack(fill="x", padx=10)

        ttk.Label(self.play_tab, text="Minecraft Version (e.g., 1.21, 1.20.4):").pack(anchor="w", padx=10, pady=(15, 2))
        self.entry_version = ttk.Entry(self.play_tab, font=("Helvetica", 12))
        self.entry_version.insert(0, self.config_data.get("version", ""))
        self.entry_version.pack(fill="x", padx=10)

        # Tab 2: Settings & Instances
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Settings")
        
        ttk.Label(self.settings_tab, text="Max RAM (e.g., 2G, 4G, 8000M):").pack(anchor="w", padx=10, pady=(15, 2))
        self.entry_ram = ttk.Entry(self.settings_tab)
        self.entry_ram.insert(0, self.config_data.get("ram_max", ""))
        self.entry_ram.pack(fill="x", padx=10)

        ttk.Label(self.settings_tab, text="Instance Directory (Save worlds separately):").pack(anchor="w", padx=10, pady=(15, 2))
        self.entry_gamedir = ttk.Entry(self.settings_tab)
        self.entry_gamedir.insert(0, self.config_data.get("game_dir", "instances/main"))
        self.entry_gamedir.pack(fill="x", padx=10)
        
        ttk.Label(self.settings_tab, text="Java Path (Default: java):").pack(anchor="w", padx=10, pady=(15, 2))
        self.entry_java = ttk.Entry(self.settings_tab)
        self.entry_java.insert(0, self.config_data.get("java_path", "java"))
        self.entry_java.pack(fill="x", padx=10)

    def create_footer(self):
        footer_frame = tk.Frame(self, pady=10)
        footer_frame.pack(fill="x", side="bottom")
        
        tk.Label(footer_frame, text=AUTHOR_TEXT, font=("Helvetica", 8, "italic"), fg="gray").pack(side="left", padx=15)
        
        self.btn_start = tk.Button(footer_frame, text=START_BUTTON_TEXT, font=("Helvetica", 12, "bold"), 
                                   bg="#238636", fg="white", activebackground="#2ea043", 
                                   command=self.launch_game, width=15)
        self.btn_start.pack(side="right", padx=15)

    def save_current_state(self):
        self.config_data["username"] = self.entry_username.get().strip()
        self.config_data["version"] = self.entry_version.get().strip()
        self.config_data["ram_max"] = self.entry_ram.get().strip()
        self.config_data["game_dir"] = self.entry_gamedir.get().strip()
        self.config_data["java_path"] = self.entry_java.get().strip()
        save_config(self.config_data)

    def launch_game(self):
        self.save_current_state()
        self.btn_start.config(text="LAUNCHING...", state="disabled")
        
        # Start core logic in a daemon thread to keep UI responsive
        threading.Thread(target=self.run_launcher_script, daemon=True).start()

    def run_launcher_script(self):
        try:
            subprocess.run(["python3", "launcher.py"])
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to start the game:\n{e}")
        finally:
            # Restore button state when game closes
            self.btn_start.config(text=START_BUTTON_TEXT, state="normal")

if __name__ == "__main__":
    app = LauncherMenu()
    app.mainloop()
