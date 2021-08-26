#!/bin/bash

CYAN="$(tput bold; tput setaf 6)"
RESET="$(tput sgr0)"

curl https://gist.githubusercontent.com/ayyybe/a5f01c6f40020f9a7bc4939beeb2df1d/raw/ccdl.command -o "/Applications/Adobe Packager.command"
chmod +x "/Applications/Adobe Packager.command"

clear

echo "${CYAN}Done! You can now start /Applications/Adobe Packager.command to begin${RESET}"
exit