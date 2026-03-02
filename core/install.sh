#!/bin/bash

CYAN="$(tput bold; tput setaf 6)"
RESET="$(tput sgr0)"
srcfolder="$(cd "$(dirname "$0")" ; pwd)"
sed "s!./ccdl.py!$srcfolder/ccdl.py!" "$srcfolder/ccdl.command" > "/Applications/Adobe Packager.command"
chmod +x "/Applications/Adobe Packager.command"
# clear

echo "${CYAN}Done! You can now start /Applications/Adobe Packager.command to begin${RESET}"
exit
