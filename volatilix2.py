#!/usr/bin/env python2
import os
import sys
import subprocess
import json
import platform
import re
import glob

try:
    raw_input
except NameError:
    raw_input = input

CONFIG_FILE = 'plugins_config.json'
STATE_FILE = 'dump_state.json'
RESULTS_DIR = os.path.join(os.path.expanduser("~"), "VolatiliX_Results")

def print_banner():
    """Prints a block ASCII banner matching the requested style."""
    print(r"""
 __      __   _      _   _ _ _ __  __ ___  
 \ \    / /  | |    | | (_) | |\ \/ /|__ \ 
  \ \  / /__ | | __ | |_ _| | | \  /    ) |
   \ \/ / _ \| |/ _`| __| | | | /  \   / / 
    \  / (_) | | (_|| |_| | | |/ /\ \ / /_ 
     \/ \___/|_|\__,_\__|_|_|_/_/  \_\____|

    Automated Volatility 2 Wrapper
    Author: Morad Rawashdeh | v2.0
    """)
    print("="*55)

def install_local_resources():
    """Attempts to install Python 2 and VC from local MSIs on Windows."""
    msi_py = os.path.join("volatility2-resources", "python-2.7.16.msi")
    msi_vc = os.path.join("volatility2-resources", "VCForPython27.msi")
    
    if not os.path.exists(msi_py) or not os.path.exists(msi_vc):
        sys.exit("[-] Missing installers in 'volatility2-resources' folder.")
        
    print("[*] Installing Python 2.7.16 from local resources...")
    subprocess.call(['msiexec', '/i', msi_py, '/passive'])
    
    print("[*] Installing Visual C++ for Python 2.7...")
    subprocess.call(['msiexec', '/i', msi_vc, '/passive'])
    
    # Add to system PATH using setx
    try:
        subprocess.call('setx PATH "%PATH%;C:\\Python27;C:\\Python27\\Scripts"', shell=True)
        print("[+] Python 2.7 installed and added to PATH.")
        print("[!] PLEASE RESTART YOUR TERMINAL for PATH changes to take effect.")
        sys.exit(0)
    except Exception as e:
        print("[-] Failed to update PATH automatically: {0}".format(e))

def check_python_env():
    """Checks if Python 2 is installed and handles missing installations."""
    os_type = platform.system()
    
    if os_type == 'Windows':
        # Check standard and custom paths
        paths_to_check = [
            sys.executable,
            r"C:\Python27\python.exe",
            r"C:\python.exe"
        ]
        
        for p in paths_to_check:
            if os.path.exists(p):
                try:
                    output = subprocess.check_output([p, "-V"], stderr=subprocess.STDOUT)
                    if "2.7" in output.decode('utf-8', 'ignore'):
                        print("[+] Python 2 detected at: {0}".format(p))
                        return p
                except Exception:
                    pass
                
        print("[-] Python 2 not detected on the system.")
        install_local_resources()
    else:
        if sys.version_info[0] != 2:
            sys.exit("[-] On Linux, please run this script explicitly with python2 (e.g., `python2 volatilix2.py`).")
        print("[+] Python 2 environment verified.")
        return sys.executable

def find_local_volatility(python_exe):
    """Locates the vol.py script inside the local volatility2 directory."""
    vol_path = os.path.join("volatility2", "vol.py")
    
    if os.path.exists(vol_path):
        print("[+] Found local Volatility 2 package: {0}".format(vol_path))
        return [python_exe, vol_path]
    
    sys.exit("[-] Error: 'vol.py' not found inside the 'volatility2' directory. Ensure the folder is present.")

def detect_memory_dump():
    """Scans the current directory for memory dumps before prompting."""
    extensions = ['*.raw', '*.mem', '*.vmem', '*.dmp', '*.img']
    found_dumps = []
    
    for ext in extensions:
        found_dumps.extend(glob.glob(ext))
        
    if found_dumps:
        print("\n[*] Detected memory dump(s) in the current folder:")
        for i, dump in enumerate(found_dumps):
            print("  {0}) {1}".format(i+1, dump))
        
        choice = raw_input("[?] Select a dump (1-{0}) or press Enter to specify a custom path: ".format(len(found_dumps))).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(found_dumps):
            return os.path.abspath(found_dumps[int(choice)-1])
            
    # Fallback to manual path entry
    while True:
        path = raw_input("\n[?] Enter the full path of the memory dump: ").strip().strip('\'"')
        if os.path.isfile(path):
            return os.path.abspath(path)
        print("[-] File not found.")

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def get_output_dir(dump_path):
    dump_name = os.path.basename(dump_path)
    base_name = os.path.splitext(dump_name)[0]
    output_dir = os.path.join(RESULTS_DIR, base_name)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print("[*] Results will be saved to: {0}".format(output_dir))
    return output_dir

def get_profile_vol2(vol_cmd, dump_path, state):
    dump_abs_path = os.path.abspath(dump_path)
    
    if dump_abs_path in state and "profile" in state[dump_abs_path]:
        saved_profile = state[dump_abs_path]["profile"]
        print("[*] Found saved profile in state file: {0}".format(saved_profile))
        use_saved = raw_input("[?] Use saved profile '{0}'? (y/n): ".format(saved_profile)).strip().lower()
        if use_saved == 'y' or use_saved == '':
            return saved_profile

    print("[*] Running 'imageinfo' to detect profile. This may take a few minutes...")
    cmd = list(vol_cmd) + ['-f', dump_path, 'imageinfo']
    
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        output_str = output.decode('utf-8', 'ignore')
        match = re.search(r'Suggested Profile\(s\) : (.+)', output_str)
        if match:
            best_profile = match.group(1).split(',')[0].strip().split(' ')[0]
            print("[+] Suggested Profile: {0}".format(best_profile))
            
            if dump_abs_path not in state:
                state[dump_abs_path] = {}
            state[dump_abs_path]["profile"] = best_profile
            save_json(STATE_FILE, state)
            return best_profile
    except Exception as e:
        print("[-] Error detecting profile: {0}".format(e))
    
    return raw_input("[?] Please enter the profile name manually: ").strip()

def select_plugins(config):
    available_plugins = config.get("volatility_2", {})
    print("\nSelect Plugin Execution Mode:")
    print("1) Basic plugins\n2) Most plugins\n3) All plugins\n4) Specific plugin")
    choice = raw_input("[?] Enter choice (1-4): ").strip()

    if choice == '1': return available_plugins.get("basic", [])
    if choice == '2': return available_plugins.get("most", [])
    if choice == '3': return available_plugins.get("all", [])
    if choice == '4': return [raw_input("[?] Enter exact plugin name: ").strip()]
    return available_plugins.get("basic", [])

def run_plugins(vol_cmd, dump_path, profile, plugins, output_dir):
    print("\n[*] Starting execution of {0} plugins...".format(len(plugins)))
    base_output_name = os.path.splitext(os.path.basename(dump_path))[0]

    for i, plugin in enumerate(plugins, 1):
        plugin_parts = plugin.split()
        output_file = os.path.join(output_dir, "{0}_{1}.txt".format(base_output_name, plugin_parts[0]))
        print("  -> Running {0} ({1}/{2})...".format(plugin_parts[0], i, len(plugins)))
        
        cmd = list(vol_cmd) + ['-f', dump_path, '--profile', profile] + plugin_parts

        try:
            with open(output_file, 'w') as f:
                subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
            print("     Saved to: {0}".format(output_file))
        except Exception as e:
            print("     [-] Failed to execute {0}: {1}".format(plugin_parts[0], e))

def main():
    print_banner()
    python_exe = check_python_env()
    vol_cmd = find_local_volatility(python_exe)
    
    config = load_json(CONFIG_FILE)
    if not config:
        sys.exit("[-] Error: {0} missing.".format(CONFIG_FILE))
        
    state = load_json(STATE_FILE)
    dump_path = detect_memory_dump()
    profile = get_profile_vol2(vol_cmd, dump_path, state)
    
    plugins_to_run = select_plugins(config)
    if not plugins_to_run:
        sys.exit("[-] No plugins selected.")

    output_dir = get_output_dir(dump_path)
    run_plugins(vol_cmd, dump_path, profile, plugins_to_run, output_dir)
    print("\n[+] VolatiliX 2 execution completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[-] Execution cancelled by user.")
        sys.exit(0)