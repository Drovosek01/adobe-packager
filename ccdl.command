#!/bin/bash

CYAN="$(tput bold; tput setaf 6)"
RESET="$(tput sgr0)"

if command -v python3 > /dev/null 2>&1; then
    PYTEST=$(python3 -c "print('ye')" 2>/dev/null)

    if [ "$PYTEST" = "ye" ]; then
        echo "${CYAN}python3 found!${RESET}"
    else
        echo "python3 found but non-functional" # probably xcode-select stub on Catalina+
        echo "You need download and install Python 3"
        open "https://www.python.org/downloads/"
        exit 0
        # echo "${CYAN}If you received a popup asking to install some tools, please accept.${RESET}"
        # read -n1 -r -p "Press [SPACE] when installation is complete, or any other key to abort." key
        # echo ""
        # if [ "$key" != '' ]; then
        # 	exit 1
        # fi
    fi
else
    echo "You need download and install Python 3"
    open "https://www.python.org/downloads/"
    exit 0
    # echo "${CYAN}installing python3...${RESET}"
    # if ! command -v brew > /dev/null 2>&1; then
    # 	echo | /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
    # fi
    # brew install python
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
