#!/usr/bin/env python2
import os
import sys
import subprocess
import json
import platform
import re
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2
import zipfile
import shutil
import tempfile
import ssl

CONFIG_FILE = 'plugins_config.json'
STATE_FILE = 'dump_state.json'
RESULTS_DIR = os.path.join(os.path.expanduser("~"), "VolatiliX_Results")

def print_banner():
    print("\n" + "="*50)
    print("                VolatiliX 2")
    print("        Automated DFIR Memory Analysis")
    print("           (Python 2 & Volatility 2)")
    print("="*50 + "\n")

def resolve_vol_path(vol_path):
    """
    Intelligently identifies the correct execution command from a path.
    Handles directory inputs and python scripts.
    """
    if not vol_path:
        return None
        
    vol_path = os.path.abspath(vol_path.strip('\'"'))
    
    if os.path.isdir(vol_path):
        # Look for executable or script inside directory
        patterns = ['volatility.exe', 'vol.py', 'volatility.py', 'vol']
        for pattern in patterns:
            potential = os.path.join(vol_path, pattern)
            if os.path.isfile(potential):
                return resolve_vol_path(potential)
        return None # Could not find executable in directory

    if vol_path.lower().endswith('.py'):
        # Return a list [python_executable, script_path]
        return [sys.executable, vol_path]
        
    return vol_path

def download_volatility():
    """Downloads and extracts Volatility 2 standalone for Windows."""
    print("[*] Downloading Volatility 2.6 (Windows Standalone)...")
    url = "https://github.com/volatilityfoundation/volatility/releases/download/2.6/volatility_2.6_win64_standalone.zip"
    
    # Target directory in user home
    install_dir = os.path.join(os.path.expanduser("~"), "Volatility2")
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)
        
    zip_path = os.path.join(tempfile.gettempdir(), "volatility.zip")
    
    # SSL context to handle verification issues in older Python installs
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib2.Request(url, headers=headers)
        response = urllib2.urlopen(req, context=ctx)
        
        with open(zip_path, 'wb') as f:
            f.write(response.read())
            
        print("[*] Extracting to {0}...".format(install_dir))
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(install_dir)
            
        # The zip contains a folder, let's find the .exe
        exe_path = None
        for root, dirs, files in os.walk(install_dir):
            for file in files:
                if file.lower() == 'volatility_2.6_win64_standalone.exe':
                    exe_path = os.path.join(root, file)
                    break
        
        if exe_path:
            print("[+] Volatility 2.6 downloaded successfully.")
            return os.path.dirname(exe_path)
    except Exception as e:
        print("[-] Download failed: {0}".format(e))
    return None

def update_path(new_dir):
    """Adds a directory to the system/user PATH."""
    os_type = platform.system()
    if os_type == 'Windows':
        print("[*] Adding {0} to User PATH using setx...".format(new_dir))
        try:
            # Get current PATH to avoid duplicates
            current_path = os.environ.get('PATH', '')
            if new_dir.lower() not in current_path.lower():
                # setx path "%path%;C:\new\path"
                cmd = 'setx PATH "%PATH%;{0}"'.format(new_dir)
                subprocess.call(cmd, shell=True)
                print("[!] PATH updated. PLEASE RESTART YOUR TERMINAL for changes to take effect.")
                return True
            else:
                print("[*] Directory already in PATH.")
                return True
        except Exception as e:
            print("[-] Failed to update PATH: {0}".format(e))
    elif os_type == 'Linux':
        print("[*] Please add the following to your ~/.bashrc or ~/.zshrc:")
        print("export PATH=$PATH:{0}".format(new_dir))
    return False

def setup_volatility():
    """Handles the full setup process if Volatility is missing."""
    print("[!] Volatility 2 not found. Starting automatic setup...")
    os_type = platform.system()
    
    if os_type == 'Windows':
        vol_dir = download_volatility()
        if vol_dir:
            update_path(vol_dir)
            # Try to return the absolute path for immediate use even if PATH hasn't refreshed
            standalone_exe = os.path.join(vol_dir, 'volatility_2.6_win64_standalone.exe')
            if os.path.exists(standalone_exe):
                return standalone_exe
    else:
        print("[*] On Linux/macOS, please install Volatility 2 manually:")
        print("git clone https://github.com/volatilityfoundation/volatility.git")
        print("cd volatility && sudo python setup.py install")
        
    return None

def check_environment():
    """Detects OS and Volatility 2 installation."""
    os_type = platform.system()
    print("[*] Detected OS: {0}".format(os_type))

    # Common commands for calling volatility
    commands = ['volatility', 'vol.py', 'vol']
    if os_type == 'Windows':
        commands = ['volatility.exe', 'vol.exe'] + commands

    vol_cmd = None

    for cmd in commands:
        try:
            # Use check_output and decode for compatibility
            output = subprocess.check_output([cmd, '-h'], stderr=subprocess.STDOUT)
            # Handle bytes in Py3 and str in Py2
            if hasattr(output, 'decode'):
                output = output.decode('utf-8', 'ignore')
            
            if 'Volatility Foundation' in output or 'Volatility Framework' in output:
                vol_cmd = cmd
                break
        except (os.error, subprocess.CalledProcessError, OSError):
            continue

    if not vol_cmd:
        print("[-] Error: Volatility 2 is not installed or not in your system PATH.")
        print("[*] Searching for common standalone Volatility 2 executables...")
        
        # Additional common Windows standalone names
        extra_cmds = [
            'volatility_2.6_win64_standalone.exe',
            'volatility_2.6_win32_standalone.exe',
            'volatility-2.6.exe',
            'vol2.exe'
        ]
        
        for cmd in extra_cmds:
            try:
                output = subprocess.check_output([cmd, '-h'], stderr=subprocess.STDOUT)
                if hasattr(output, 'decode'):
                    output = output.decode('utf-8', 'ignore')
                if 'Volatility Foundation' in output or 'Volatility Framework' in output:
                    vol_cmd = cmd
                    break
            except:
                continue
                
    if not vol_cmd:
        vol_cmd = setup_volatility()
                
    if not vol_cmd:
        print("[!] Volatility 2 still not found automatically.")
        manual_path = raw_input("[?] Please enter the full path to your Volatility 2 executable or its directory (or 'q' to quit): ").strip()
        manual_path = manual_path.strip('\'"')
        if manual_path.lower() == 'q':
            sys.exit(0)
            
        vol_cmd = resolve_vol_path(manual_path)
        if not vol_cmd:
            sys.exit("[-] Error: Provided path does not point to a valid Volatility 2 executable or directory containing one.")

    # Ensure vol_cmd is correctly resolved if it was found automatically but is a directory or script
    vol_cmd = resolve_vol_path(vol_cmd)
    
    print("[*] Using Volatility 2: {0}".format(vol_cmd))
    return vol_cmd

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
        path = raw_input("\n[?] Enter the full path of the memory dump: ").strip()
        # Remove extra quotes if dragged and dropped in terminal
        path = path.strip('\'"')
        if os.path.isfile(path):
            return path
        print("[-] File not found. Please check the path and try again.")

def get_output_dir(dump_path):
    """Creates and returns a dedicated output directory for the dump outside the repo."""
    dump_name = os.path.basename(dump_path)
    base_name = os.path.splitext(dump_name)[0]
    output_dir = os.path.join(RESULTS_DIR, base_name)
    
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        print("[*] Results will be saved to: {0}".format(output_dir))
        return output_dir
    except Exception as e:
        print("[-] Error creating output directory {0}: {1}".format(output_dir, e))
        fallback_dir = os.path.join(os.getcwd(), "results", base_name)
        if not os.path.exists(fallback_dir):
            os.makedirs(fallback_dir)
        print("[*] Falling back to: {0}".format(fallback_dir))
        return fallback_dir

def get_profile_vol2(vol_cmd, dump_path, state):
    """Retrieves saved profile or runs imageinfo to detect it."""
    dump_abs_path = os.path.abspath(dump_path)
    
    if dump_abs_path in state and "profile" in state[dump_abs_path]:
        saved_profile = state[dump_abs_path]["profile"]
        print("[*] Found saved profile in state file: {0}".format(saved_profile))
        use_saved = raw_input("[?] Use saved profile '{0}'? (y/n): ".format(saved_profile)).strip().lower()
        if use_saved == 'y' or use_saved == '':
            return saved_profile

    print("[*] Running 'imageinfo' to detect profile. This may take a few minutes...")
    try:
        # Prepare command list
        cmd = []
        if isinstance(vol_cmd, list):
            cmd.extend(vol_cmd)
        else:
            cmd.append(vol_cmd)
        cmd.extend(['-f', dump_path, 'imageinfo'])
        
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        if hasattr(output, 'decode'):
            output = output.decode('utf-8', 'ignore')
            
        match = re.search(r'Suggested Profile\(s\) : (.+)', output)
        if match:
            profiles = match.group(1).split(',')
            best_profile = profiles[0].strip().split(' ')[0]
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
    print("1) Basic plugins")
    print("2) Most plugins")
    print("3) All plugins")
    print("4) Specific plugin (Manual entry)")
    
    choice = raw_input("[?] Enter choice (1-4): ").strip()

    if choice == '1':
        return available_plugins.get("basic", [])
    elif choice == '2':
        return available_plugins.get("most", [])
    elif choice == '3':
        return available_plugins.get("all", [])
    elif choice == '4':
        plugin = raw_input("[?] Enter the exact plugin name: ").strip()
        return [plugin]
    else:
        print("[-] Invalid choice, defaulting to Basic.")
        return available_plugins.get("basic", [])

def run_plugins(vol_cmd, dump_path, profile, plugins, output_dir):
    print("\n[*] Starting execution of {0} plugins...".format(len(plugins)))
    
    dump_name = os.path.basename(dump_path)
    base_output_name = os.path.splitext(dump_name)[0]

    for i, plugin in enumerate(plugins, 1):
        plugin_parts = plugin.split()
        plugin_name = plugin_parts[0]
        
        output_file = os.path.join(output_dir, "{0}_{1}.txt".format(base_output_name, plugin_name))
        print("  -> Running {0} ({1}/{2})...".format(plugin_name, i, len(plugins)))
        
        # Prepare command list
        cmd = []
        if isinstance(vol_cmd, list):
            cmd.extend(vol_cmd)
        else:
            cmd.append(vol_cmd)
            
        cmd.extend(['-f', dump_path, '--profile', profile])
        cmd.extend(plugin_parts)

        try:
            with open(output_file, 'w') as f:
                # Use shell=False (default) for list commands on Windows
                return_code = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
                if return_code != 0:
                    print("     [!] Warning: {0} returned non-zero exit code: {1}".format(plugin_name, return_code))
            print("     Saved to: {0}".format(output_file))
        except Exception as e:
            print("     [-] Failed to execute {0}: {1}".format(plugin_name, e))

    print("\n[+] VolatiliX 2 execution completed successfully!")

def main():
    print_banner()
    
    vol_cmd = check_environment()
    
    config = load_json(CONFIG_FILE)
    if not config:
        sys.exit("[-] Error: Could not load {0}. Please ensure it exists.".format(CONFIG_FILE))
        
    state = load_json(STATE_FILE)
    dump_path = get_dump_path()
    profile = get_profile_vol2(vol_cmd, dump_path, state)
    plugins_to_run = select_plugins(config)

    if not plugins_to_run:
        sys.exit("[-] No plugins selected or configured. Exiting.")

    output_dir = get_output_dir(dump_path)
    run_plugins(vol_cmd, dump_path, profile, plugins_to_run, output_dir)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[-] Execution cancelled by user.")
        sys.exit(0)
