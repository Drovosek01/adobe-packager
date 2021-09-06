#!/bin/bash

CYAN="$(tput bold; tput setaf 6)"
RESET="$(tput sgr0)"

# clear

if command -v python3 > /dev/null 2>&1; then
	if [ $(python3 -c "print('ye')") = "ye" ]; then
		# clear
		echo "${CYAN}python3 found!${RESET}"
	else
		# clear
		echo "python3 found but non-functional" # probably xcode-select stub on Catalina+
		echo "${CYAN}If you received a popup asking to install some tools, please accept.${RESET}"
		read -n1 -r -p "Press [SPACE] when installation is complete, or any other key to abort." key
		echo ""
		if [ "$key" != '' ]; then
			exit 1
		fi
	fi
else
	echo "${CYAN}installing python3...${RESET}"
	if ! command -v brew > /dev/null 2>&1; then
		echo | /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
	fi
	brew install python
fi

python3 -c 'import requests' > /dev/null 2>&1
if [ $? == 0 ]; then
	echo "${CYAN}requests found!${RESET}"
else
	echo "${CYAN}installing requests...${RESET}"
	python3 -m pip install requests --user
fi
python3 -c "import tqdm" || pip3 install --user tqdm 
# clear

echo "${CYAN}starting ccdl${RESET}"
cd "$(dirname "$0")"
python3 "./ccdl.py"
