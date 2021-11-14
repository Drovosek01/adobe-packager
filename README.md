## What is this and for what

This is a script that allows you to download portable installers of programs from Adobe for macOS with different versions and different or all languages. This can help system administrators who need to install the same program from Adobe on several computers, as well as those people who do not want to use the latest version of programs from Creative Cloud or install the application on an officially unsupported version of macOS (see [instructions](#instructions) partition here).

## How to use it

1. For the script to work, the Creative Cloud application must be installed.

   - [here](https://helpx.adobe.com/download-install/kb/creative-cloud-desktop-app-download.html) for "offline" installer of Creative Cloud under "macOS | Alternative downloads"

2. For the script to work, Python 3 and XCode (or XCode components) must be installed

   - just run this command `xcode-select --install` in terminal to install it

3. Clone the repository `git clone https://github.com/Drovosek01/adobe-packager` or download files via your browser (and of course unpack archive with files)

4. In the Finder double click on the `ccdl.command` file and follow the prompts in the terminal. You can also run the installer in the terminal to have it install into `/Applications/Adobe\ Packager.command`. Note that it needs the folder from github to remain on your system when you installed it.

   - You also can type `python3` in terminal and type path to `ccdl.py` file or just drop it to terminal window and press Enter. You can add attributes for launch `ccdl.py` file for specific work.

5. Be sure to keep your script updated by running `git pull` in the terminal where you have this cloned to.

## Donate

[Sponsor the project](https://donatty.com/drovosek)

You can support this repository at the link above.

P.S.

Yes, I am not the original creator of this script and so far I have only formatted this code, but I will try to share the donation among everyone who took part in writing and correcting this script.

## Known issues

- Unable to download the Adobe Acrobat installer
- When using a link to download a v5 xml file the script crashes
- Postfix `macarm64` can mean `macuniversal` architecture

## Resolved issues

- For Photoshop (and possibly some other applications), only the Intel version of the application installer is downloaded

## To Do

- [ ] Find a way to download Adobe Acrobat
- [ ] Fix the script for downloading applications via xml v5
- [ ] Find the difference between xml v5 and v4
- [ ] Refactoring the script - split it into different files
- [ ] Make the script fully or partially cross-platform
- [ ] Make interactive examples of requests for downloading an xml file in the browser
- [ ] Make it possible to select the language of the program in installer GUI
- [x] Make it possible to download all the language packs
- [x] Find a way to download Photoshop native for ARM

P.S.
At the moment, I do not know the Python language, but I will learn it sometime and maybe do scheduled tasks. Help is always welcome.

## Instructions

### How to install an application with all languages or choose a specific application language if all language packs are downloaded

Firstly, you should take into account that Adobe applications are quite specific and although they are made in approximately the same style, they often differ greatly in the implementation of the interface. For example, whichever language you choose when downloading Lightroom Classic or Media Encoder (tested on versions 10.4 and CC 2021, respectively), after installation they will have the same interface language as the system language and in the application settings you can change the interface language and it will change after restarting the application. Alas, this does not work with Photoshop, Illustrator (it was tested on CC 2021) and many other Adobe applications, and in order to change their interface language, you will have to reinstall the application after downloading it with the necessary language using our Adobe Packager or change the system interface language in the system settings and in the Creative Cloud settings in the "Apps" item to change the language to the same, restart the computer and only then install the application from Creative Cloud with the desired language.

Our Adobe Packager from a certain commit allows you to download the installer of your chosen application with all the languages available for the selected application (for this, at the language selection stage, you need to enter the word "ALL"), but this does not guarantee that in the installed application it will be possible to change the interface language to any available one. It all depends on the specific application.

For example, as already mentioned here, Lightroom Classic and Media Encoder, regardless of the language selected when downloading, will be installed with all languages and they can be easily switched in the application settings. Adobe XD application (tested on version 44.0.12) if you download (by selecting "ALL") and install with all languages, then after installation, you can select any interface language in the application settings and it will be applied after restarting the application. If you select one language during the Adobe XD download, then after installing the application, only this selected language will be present in its settings. With Illustrator (tested on CC 2021 v25.4.1) the situation is slightly different. If you download (by selecting "ALL") and install Illustrator with all languages, then after installation it will have the interface language "en_US" and all interface languages will be available for selection in the application settings, but after selecting the desired language and restarting the application, the interface language will not change.

I repeat, the interface language settings are specific to each Adobe program and therefore it is more convenient to have 1 installer with all languages and, if necessary, choose which interface language to install the application with.

If you downloaded the application with all the language packs (by selecting "ALL"), then you can set which interface language to install this application by changing in the file `driver.xml` the text between the "InstallLanguage" tags to one of the available language interface codes available for this application. You can view them in the `application.json` file (I recommend using some JSON beautifier to make it easier to read this JSON file). If you leave the word "ALL" between these tags, then the application will be installed either with the language "en_US" and in its settings it will not be possible to change the interface language, or it will be installed with the interface language of your system and in its settings it will be possible to change the interface language.

File `driver.xml` located on the path `<create_package>.app/Contents/Resouces/products`

The `application.json` file is located at `<create_package>.app/Contents/Resouces/products/<application_sapcode>`

P.S.

To be sure that the application will install exactly with the selected language after changing the text between the "InstallLanguage" tags, you can also delete all language packs except the one selected from the `application.json` folder

### How to install an application on an unsupported version of macOS

If you don't have the most up-to-date version of macOS (for example, macOS Mojave 10.14.6) if you try to download the latest version of the application from Creative Cloud (for example Adobe InDesign CC 2022 v17.0), then Creative Cloud will give
an error that the requested version of the application is incompatible with your version of macOS and you need to upgrade (in this situation to macOS 10.15 or newer macOS).

If you want to try your luck and find out if the version of the application you requested really can't work on the current version of macOS, you can download the installer with the version of the application you need using our Adobe Packager script. If you then run the installer, you will most likely immediately see error 192 and to install the downloaded version of the application on your macOS, you will need to open the `application.json` file and there, in the file search, enter "macOS 10." and see what minimum version of macOS Adobe wants for this application to work (for InDesign 2022 v17.0 it was macOS 10.15) and then in the entire `application.json` file replace this version (in my case it is "10.15") with the macOS version that you have now (in my case it is "10.14") and start the installation again.

After the installation is complete, open the Application folder and there is a folder with the installed application and if there is no crossed-out circle on the application icons, then it will start without problems and most likely will also work without problems.
So on macOS Mojave I managed to work in InDesign CC 2022 v17.0, but Photoshop CC 2022 installed on macOS Mojave was displayed with a crossed circle and even changing the requirements of the minimum version of macOS in the Info.plist file inside Adobe Photoshop 2022 did not help to launch it, because, as I understand, it is compiled specifically for macOS 10.15 and newer.

## Used code

As far as I know, this script was started by the user "ayyybe" on github gist, but then he stopped supporting the script and then the script stopped working and it was fixed by the user "thpryrchn". You can see this in the commit history.

Here are the links to the used sources:

- https://gist.github.com/ayyybe/a5f01c6f40020f9a7bc4939beeb2df1d
- https://gist.github.com/thpryrchn/c0ea1b6793117b00494af5f05959d526
- https://gist.github.com/SaadBazaz/37f41fffc66efea798f19582174e654c
