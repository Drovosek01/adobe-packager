## What is this and for what

This is a script that allows you to download portable installers of programs from Adobe for macOS with different versions. This can help system administrators who need to install the same program from Adobe on several computers, as well as those people who do not want to use the latest version of programs from Creative Cloud

## How to use it

1. For the script to work, the Creative Cloud application must be installed

   - [here](https://helpx.adobe.com/download-install/kb/creative-cloud-desktop-app-download.html) you can find "offline" installers Creative Cloud

2. For the script works Python 3 and XCode (or XCode components) mist be installed

   - just run this command `xcode-select --install` in terminal to install it

3. Clone the repository or download files via your browser (and of course unpack archive with files)

4. Make the `ccdl.command` file executable

   - to do this, go to the repository folder in the terminal and run this command `chmod +x ccdl.command`

5. In the Finder click 2 times on the `ccdl.command` file and follow the prompts in the terminal

## Known issues

- Unable to download the Adobe Acrobat installer
- For Photoshop (and possibly some other applications), only the Intel version of the application installer is downloaded
- When using a link to download a v5 xml file the script crashes

## To Do

- [ ] Find a way to download Adobe Acrobat
- [ ] Find a way to download Photoshop native for ARM
- [ ] Fix the script for downloading applications via xml v5
- [ ] Find the difference between xml v5 and v4
- [ ] Refactoring the script - split it into different files
- [ ] Make the script fully or partially cross-platform
- [ ] Make it possible to download all the language packs and select the language of the program during installation
- [ ] Make interactive examples of requests for downloading an xml file in the browser

P.S.
At the moment, I do not know the Python language, but I will learn it sometime and maybe do scheduled tasks. Help is always welcome.

## Used code

As far as I know, this script was started by the user "ayyybe" on github gist, but then he stopped supporting the script and then the script stopped working and it was fixed by the user "thpryrchn". You can see this in the commit history.

Here are the links to the used sources:

- https://gist.github.com/ayyybe/a5f01c6f40020f9a7bc4939beeb2df1d
- https://gist.github.com/thpryrchn/c0ea1b6793117b00494af5f05959d526
- https://gist.github.com/SaadBazaz/37f41fffc66efea798f19582174e654c
