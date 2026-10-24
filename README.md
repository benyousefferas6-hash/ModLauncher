# ModLauncher

A Modrinth-style Minecraft launcher for Linux and Windows (Python + PyQt6).

## Get it
- **Linux:** `./install.sh` (adds it to your app menu), or `./run.sh` to try it. Arch: `sudo pacman -S python xdg-utils nss xcb-util-cursor` first.
- **Windows:** `run-windows.bat`, or build `ModLauncher.exe` with `build-windows.bat`.
- **Downloads for everyone:** push the folder to GitHub and push a tag (`git tag v1.1.0 && git push --tags`); the workflow builds the Windows .exe and the Linux file
  and attaches them to the release. The tag becomes the app version, and older versions show an "Update available" button.

## Sign in
Account page > **Sign in with Microsoft**: a short code appears, you enter it on the Microsoft page, done. The Account page then shows
"You are signed in" with your name and skin face, plus **Change account** and **Log out**. The launcher needs a Microsoft account that owns Minecraft: Java Edition.

For the developer (not shown in the app): the sign-in uses the Azure app ID set as `DEFAULT_CLIENT_ID` in `core.py` (public client, "Allow public client flows" on).
Mojang must approve that app ID for other people's accounts: https://aka.ms/mce-reviewappid

## Features
- **Library** of instances and modpacks as cards (icons, search, sort, filter, right-click menu). Import `.mrpack` / CurseForge `.zip` modpacks, mods (`.jar`), resource packs and shaders
  with **Import file...** or drag and drop. Mods can be disabled/enabled without deleting them.
- **Browse Modrinth** for mods, modpacks, resource packs and shaders: icons, pages, **Install** or **Versions...**, parallel downloads.
- **Skins**: front-view preview of your skin; change it from a PNG or copy another player's skin.
- **Performance**: smart RAM (Auto), Java profiles, GameMode / priority, quiet launcher while playing, one-click FPS mods for Fabric/Quilt, in-game video presets.
- **Crash report** window after a crash (and for hangs while closing), with safe settings in one click. The last run's log is `launcher-log.txt` in the instance folder.
- **Backgrounds** that cross-fade (or your own images), Discord "Playing" status (Account > Discord app ID), update check on start.

Data lives in `~/.local/share/modlauncher` (Linux) or `%APPDATA%\modlauncher` (Windows).
