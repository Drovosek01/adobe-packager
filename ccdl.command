#!/bin/bash

CYAN="$(tput bold; tput setaf 6)"
RESET="$(tput sgr0)"
PYTHON_PATH="$(command -v python3)"
PYTHON_DOWNLOAD_WEBPAGE="https://www.python.org/downloads/"
PYTHON_INSTALLER_PATH="/tmp/python_installer.pkg"

IS_PIPED=false
# Check whether the code is running via pipe, stdin or bash -c
if [ -p /dev/stdin ] || [ ! -t 0 ] || [[ "$0" == *"bash"* ]]; then
    IS_PIPED=true
fi

if [ "$IS_PIPED" = true ]; then
    echo "${CYAN}Script is running directly from code string/url (piped/evaluated)${RESET}"
    # If run from the network, the working directory for ccdl will be a temporary folder
    BASE_DIR="/tmp/ccdl_tmp"
    CORE_DIR="${BASE_DIR}/core"
    SCRIPT_LAUNCH_METHOD="piped"
else
    # If run as a file, we take the native folder of this file
    BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
    CORE_DIR="${BASE_DIR}/core"
    SCRIPT_LAUNCH_METHOD="file"
fi

PY_TARGET_FILE="${CORE_DIR}/ccdl.py"

# Function for downloading ccdl.py if it doesn't exist
ensure_ccdl_py_exists() {
    if [ ! -f "$PY_TARGET_FILE" ]; then
        echo "${CYAN}ccdl.py not found locally. Preparing download...${RESET}"
        
        # Create folder structure if it doesn't exist (especially important for /tmp)
        mkdir -p "$CORE_DIR"
        
        local download_url="https://github.com/Drovosek01/adobe-packager/raw/refs/heads/develop/core/ccdl.py"
        echo "Downloading ccdl.py into ${CORE_DIR}..."
        
        if ! curl -L -# -o "$PY_TARGET_FILE" "$download_url"; then
            echo "Error: Failed to download ccdl.py from GitHub."
            exit 1
        fi
    fi
}

need_manually_download_python() {
    echo "Open download page manually and download and install Python 3 manually."
    echo "$PYTHON_DOWNLOAD_WEBPAGE"
    open "$PYTHON_DOWNLOAD_WEBPAGE"
}

# Function for installing .pkg via a graphical rights query (AppleScript / Touch ID)
install_pkg_with_gui_privileges() {
    local pkg_path="$1"
    
    if [ ! -f "$pkg_path" ]; then
        echo "Error: Package file $pkg_path not found."
        return 1
    fi

    echo "${CYAN}Requesting administrator privileges via macOS prompt...${RESET}"

    # TODO: maybe need create installer choicechanges to customize the install https://docs.python.org/3/using/mac.html#installing-using-the-command-line
    
    # Forming a command to execute via osascript with administrator rights
    local osascript_cmd="do shell script \"sudo installer -pkg '${pkg_path}' -target /\" with administrator privileges"
    
    if osascript -e "$osascript_cmd" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function for determining the macOS version, downloading and installing Python
download_python_auto() {
    echo "${CYAN}Checking macOS version to select compatible Python...${RESET}"
    
    # Get current macOS version (for example, 14.5, 10.14.6 etc)
    local os_version=$(sw_vers -productVersion)
    local major=$(echo "$os_version" | cut -d. -f1)
    local minor=$(echo "$os_version" | cut -d. -f2)
    
    local url=""
    
    # The logic of choosing a macOS-based version
    if [ "$major" -eq 10 ]; then
        if [ "$minor" -ge 15 ]; then
            # for macOS 10.15+
            url="https://www.python.org/ftp/python/3.14.7/python-3.14.7-macos11.pkg"
        elif [ "$minor" -ge 13 ]; then
            # for macOS 10.13+
            url="https://www.python.org/ftp/python/3.13.14/python-3.13.14-macos11.pkg"
        elif [ "$minor" -ge 9 ]; then
            # for OS X 10.9+
            url="https://www.python.org/ftp/python/3.12.5/python-3.12.5-macos11.pkg"
        fi
    elif [ "$major" -ge 11 ]; then
        # for macOS 11+
        url="https://www.python.org/ftp/python/3.14.7/python-3.14.7-macos11.pkg"
    fi

    # If the macOS version is too old (older than 10.9)
    if [ -z "$url" ]; then
        echo "Your macOS version ($os_version) is too old or not supported automatically."
        need_manually_download_python
        exit 1
    fi

    # local filename="python_installer.pkg"
    local filename="$PYTHON_INSTALLER_PATH"
    echo "${CYAN}Detected current macOS $os_version. Downloading compatible Python...${RESET}"
    echo "URL: $url"
    echo "To: $PYTHON_INSTALLER_PATH"
    
    # Downloading a file with a progress indicator (-#)
    if ! curl -L -# -o "$filename" "$url"; then
        echo "Failed to download Python installer."
        need_manually_download_python
        exit 1
    fi
}

download_then_install_python() {
    download_python_auto

    local filename="$PYTHON_INSTALLER_PATH"

    if install_pkg_with_gui_privileges "$filename"; then
        echo "${CYAN}Python installed successfully!${RESET}"
        rm -f "$filename"
        
        # Adjusting the path to the newly installed Python
        PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
        if [ ! -f "$PYTHON_PATH" ]; then
            PYTHON_PATH="$(command -v python3)"
        fi
    else
        echo "Installation failed or cancelled by user."
        rm -f "$filename"
        need_manually_download_python
        exit 1
    fi
}

# Diagnostics of the existence of a working Python3
is_stub_python() {
    local py_bin="$1"
    
    # 1. If the path doesn't exist, it's not a valid Python
    if [ -z "$py_bin" ] || [ ! -x "$py_bin" ]; then
        return 0 # is stub / missing
    fi
    
    # 2. If Python is located in /Library/Frameworks/ or /usr/local/ or Homebrew, it's a 100% legitimate Python
    if [[ "$py_bin" == /Library/Frameworks/Python.framework/* ]] || [[ "$py_bin" == /opt/homebrew/* ]] || [[ "$py_bin" == /usr/local/* ]]; then
        return 1 # NOT a stub
    fi

    # 3. Check if the Python is located in /usr/bin/python3, which is a stub on macOS
    if [[ "$py_bin" == "/usr/bin/python3" ]]; then
        # If xcode-select is not configured to point to a full Xcode / CLT path, then this is a stub
        if ! xcode-select -p >/dev/null 2>&1; then
            return 0 # is stub
        fi
        
        # Additional check of Apple Mac OS Component signature (characteristic of /usr/bin stubs)
        local sig="$(codesign -dv --verbose=4 "$py_bin" 2>&1)"
        if echo "$sig" | grep -q "Apple Mac OS Component" || echo "$sig" | grep -q "Software Signing"; then
            return 0 # is stub
        fi
    fi

    return 1 # NOT a stub
}

if is_stub_python "$PYTHON_PATH"; then
    echo "${CYAN}Functional python3 not found (or stub detected). Installing official Python PKG...${RESET}"
            download_then_install_python
        else
    echo "${CYAN}python3 found: $PYTHON_PATH${RESET}"
fi

PYTHON_EXEC="${PYTHON_PATH:-/Library/Frameworks/Python.framework/Versions/Current/bin/python3}"

# --- DEPENDENCY CHECKING ---
$PYTHON_EXEC -c 'import requests' > /dev/null 2>&1
if [[ $? == 0 && $($PYTHON_EXEC -c 'import requests;print(requests.__version__)') == "2.28.2" ]]; then
    echo "${CYAN}requests 2.28.2 found!${RESET}"
else
    echo "${CYAN}installing requests 2.28.2...${RESET}"
    $PYTHON_EXEC -m pip install requests==2.28.2 --user
fi

$PYTHON_EXEC -c "import tqdm" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "${CYAN}installing tqdm...${RESET}"
    $PYTHON_EXEC -m pip install tqdm --user
fi

# --- CHECKING THE AVAILABILITY AND LAUNCHING OF THE CCDL STRUCTURE ---
ensure_ccdl_py_exists

echo "${CYAN}starting ccdl (${SCRIPT_LAUNCH_METHOD} mode)...${RESET}"
cd "$CORE_DIR" || exit 1
$PYTHON_EXEC "./ccdl.py" "$@"
