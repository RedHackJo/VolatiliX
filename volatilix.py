#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import platform
import re

CONFIG_FILE = 'plugins_config.json'
STATE_FILE = 'dump_state.json'

def print_banner():
    print("\n" + "="*50)
    print("                VolatiliX")
    print("        Automated DFIR Memory Analysis")
    print("="*50 + "\n")

def check_environment():
    """Detects OS, Python version, and Volatility installation/version."""
    if sys.version_info[0] < 3:
        sys.exit("[-] Error: VolatiliX requires Python 3.")

    os_type = platform.system()
    print(f"[*] Detected OS: {os_type}")

    # Common commands for calling volatility
    commands = ['volatility', 'vol.py', 'vol']
    if os_type == 'Windows':
        commands = ['volatility.exe', 'vol.exe'] + commands

    vol_cmd = None
    vol_version = None

    for cmd in commands:
        try:
            result = subprocess.run([cmd, '-h'], capture_output=True, text=True)
            output = result.stdout + result.stderr
            if 'Volatility 3' in output:
                vol_cmd = cmd
                vol_version = 3
                break
            elif 'Volatility Foundation' in output or 'Volatility Framework' in output:
                vol_cmd = cmd
                vol_version = 2
                break
        except FileNotFoundError:
            continue

    if not vol_cmd:
        sys.exit("[-] Error: Volatility is not installed or not in your system PATH.")

    print(f"[*] Detected Volatility Version: {vol_version} (Command: {vol_cmd})")
    return vol_cmd, vol_version

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def get_dump_path():
    while True:
        path = input("\n[?] Enter the full path of the memory dump: ").strip()
        # Remove extra quotes if dragged and dropped in terminal
        path = path.strip('\'"')
        if os.path.isfile(path):
            return path
        print("[-] File not found. Please check the path and try again.")

def get_profile_vol2(vol_cmd, dump_path, state):
    """Retrieves saved profile or runs imageinfo to detect it."""
    dump_abs_path = os.path.abspath(dump_path)
    
    if dump_abs_path in state and "profile" in state[dump_abs_path]:
        saved_profile = state[dump_abs_path]["profile"]
        print(f"[*] Found saved profile in state file: {saved_profile}")
        use_saved = input(f"[?] Use saved profile '{saved_profile}'? (y/n): ").strip().lower()
        if use_saved == 'y' or use_saved == '':
            return saved_profile

    print("[*] Running 'imageinfo' to detect profile. This may take a few minutes...")
    result = subprocess.run([vol_cmd, '-f', dump_path, 'imageinfo'], capture_output=True, text=True)
    
    # Simple regex to extract suggested profile
    match = re.search(r'Suggested Profile\(s\) : (.+)', result.stdout)
    if match:
        profiles = match.group(1).split(',')
        best_profile = profiles[0].strip().split(' ')[0] # Take first suggestion and clean it
        print(f"[+] Suggested Profile: {best_profile}")
        
        # Save state
        if dump_abs_path not in state:
            state[dump_abs_path] = {}
        state[dump_abs_path]["profile"] = best_profile
        save_json(STATE_FILE, state)
        
        return best_profile
    else:
        print("[-] Could not automatically detect profile.")
        return input("[?] Please enter the profile name manually: ").strip()

def select_plugins(config, vol_version):
    ver_key = "volatility_2" if vol_version == 2 else "volatility_3"
    available_plugins = config.get(ver_key, {})

    print("\nSelect Plugin Execution Mode:")
    print("1) Basic plugins")
    print("2) Most plugins")
    print("3) All plugins")
    print("4) Specific plugin (Manual entry)")
    
    choice = input("[?] Enter choice (1-4): ").strip()

    if choice == '1':
        return available_plugins.get("basic", [])
    elif choice == '2':
        return available_plugins.get("most", [])
    elif choice == '3':
        return available_plugins.get("all", [])
    elif choice == '4':
        plugin = input("[?] Enter the exact plugin name: ").strip()
        return [plugin]
    else:
        print("[-] Invalid choice, defaulting to Basic.")
        return available_plugins.get("basic", [])

def run_plugins(vol_cmd, vol_version, dump_path, profile, plugins):
    print(f"\n[*] Starting execution of {len(plugins)} plugins...")
    
    dump_name = os.path.basename(dump_path)
    base_output_name = os.path.splitext(dump_name)[0]

    for i, plugin in enumerate(plugins, 1):
        # Handle arguments like 'psxview --apply-rules'
        plugin_parts = plugin.split()
        plugin_name = plugin_parts[0]
        
        output_file = f"{base_output_name}_{plugin_name}.txt"
        print(f"  -> Running {plugin_name} ({i}/{len(plugins)})...")
        
        cmd = [vol_cmd, '-f', dump_path]
        if vol_version == 2 and profile:
            cmd.extend(['--profile', profile])
            
        cmd.extend(plugin_parts)

        # Run and save to text file
        try:
            with open(output_file, 'w') as f:
                subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
            print(f"     Saved to: {output_file}")
        except Exception as e:
            print(f"     [-] Failed to execute {plugin_name}: {e}")

    print("\n[+] VolatiliX execution completed successfully!")

def main():
    print_banner()
    
    # 1 & 2 & 3. Env Check and Volatility Version
    vol_cmd, vol_version = check_environment()
    
    config = load_json(CONFIG_FILE)
    if not config:
        sys.exit(f"[-] Error: Could not load {CONFIG_FILE}. Please ensure it exists.")
        
    state = load_json(STATE_FILE)

    # 4. Get Dump Path
    dump_path = get_dump_path()

    # 5 & 6. Handle Profile (Vol 2 vs Vol 3) and State Persistence
    profile = None
    if vol_version == 2:
        profile = get_profile_vol2(vol_cmd, dump_path, state)

    # 7. Interactive Selection
    plugins_to_run = select_plugins(config, vol_version)
    if not plugins_to_run:
        sys.exit("[-] No plugins selected or configured. Exiting.")

    # 8. Execution and Output
    run_plugins(vol_cmd, vol_version, dump_path, profile, plugins_to_run)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[-] Execution cancelled by user.")
        sys.exit(0)
