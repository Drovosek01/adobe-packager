#!/bin/bash

CYAN="$(tput bold; tput setaf 6)"
RESET="$(tput sgr0)"
PYTHON_PATH="$(command -v python3)"

if [ -z "$PYTHON_PATH" ]; then
    echo "python3 not found!"
    echo "You need download and install Python 3 manually"
    open "https://www.python.org/downloads/"
    exit 0
    # echo "${CYAN}installing python3...${RESET}"
    # if ! command -v brew > /dev/null 2>&1; then
    # 	echo | /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
    # fi
    # brew install python
else
    # Checking the python3 binary
    # If the python3 binary is located in the Frameworks folder, it means that it is most likely a full-fledged python3 binary.
    # Otherwise, we check the digital signature of the binary, and if it is signed by Apple, then it is a stub binary for installing Xcode CLT.
    # All these checks are done so as not to try to execute any code using the python3 binary, which will open the Xcode CLT installation prompt window and this will confuse inexperienced users, as well as downloading and installing Xcode CLT longer than downloading and installing only the Python package from the official website.
    
    if [[ "$PYTHON_PATH" == /Library/Frameworks/Python.framework/* ]]; then
        echo "${CYAN}python3 found!${RESET}"
    else
        SIGNATURE_INFO="$(codesign -dv --verbose=4 "$PYTHON_PATH" 2>&1)"

        if echo "$SIGNATURE_INFO" | grep -q "Authority=Software Signing" && \
            echo "$SIGNATURE_INFO" | grep -q "Authority=Apple Code Signing Certification Authority"; then
            
            echo "python3 found but non-functional" # probably xcode-select stub on Catalina+
            echo "You need download and install Python 3"
            open "https://www.python.org/downloads/"
            exit 0
        else
            echo "${CYAN}python3 found!${RESET}"
        fi
    fi
fi

python3 -c 'import requests' > /dev/null 2>&1
if [[ $? == 0 && $(python3 -c 'import requests;print(requests.__version__)') == "2.28.2" ]]; then
    echo "${CYAN}requests 2.28.2 found!${RESET}"
else
    echo "${CYAN}installing requests 2.28.2...${RESET}"
    python3 -m pip install requests==2.28.2 --user
fi
python3 -c "import tqdm" || pip3 install --user tqdm 

echo "${CYAN}starting ccdl${RESET}"
cd "$(dirname "$0")/core"
python3 "./ccdl.py" "$@"
