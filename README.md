# VolatiliX 🔍

An advanced, automated, and cross-platform Python wrapper for memory forensics using the Volatility Framework. VolatiliX streamlines the DFIR workflow by automatically detecting your operating system, Volatility version, and caching memory dump profiles to save valuable analysis time.

## ✨ Key Features
* **Cross-Platform**: Seamlessly works on both Linux and Windows environments.
* **Auto-Detection**: Dynamically detects whether Volatility 2 or Volatility 3 is installed and adjusts the command syntax accordingly.
* **State Persistence**: Memorizes the suggested profile (for Volatility 2) in a local `dump_state.json` file, avoiding repetitive and time-consuming profile scans on the same memory dump.
* **Customizable Plugins**: Uses an editable `plugins_config.json` file to map and group plugins into categories (Basic, Most, All) for both Vol 2 and Vol 3.
* **Clean Output**: Automatically executes selected plugins and saves each output into an organized, cleanly named text file.

## ⚙️ Prerequisites
* **Python 3.x**
* **Volatility 2** or **Volatility 3** installed and added to your system's PATH (accessible via commands like `volatility`, `vol.py`, `volatility.exe`, etc.).

## 🚀 Usage

**Clone the repository:**
```bash
git clone [https://github.com/RedHackJo/VolatiliX.git](https://github.com/RedHackJo/VolatiliX.git)
cd VolatiliX
