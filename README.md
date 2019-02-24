# Blender remote script execution (UNIX)
This single-file add-on allows you to reload and execute python scripts and
addons by writing appropriate lines into a unix pipe.

## Installation
Download the [remote\_script\_run.py](remote_script_run.py) python script.
Install it by clicking `Install Add-on from File...` in the
`Add-ons` settings (`File` -> `User Preferences...` -> `Add-ons`)
and selecting the script.

![Preferences](https://salatfreak.github.io/images/remote_script_run/preferences.jpg)

You can start and stop the remote operation by clicking the `Start/Stop remote`
button in a Text Editor area.

![Start/Stop remote button](https://salatfreak.github.io/images/remote_script_run/text_editor.jpg)

## Settings
The add-on works by creating and reading from a named unix pipe.
You can specify the directory to create the pipe in in the add-ons settings.
By default the temporary directory of the running blender instance is used.
It's usually something like /tmp/blender\_\*\*\*\*\*/.

![Add-on Preference](https://salatfreak.github.io/images/remote_script_run/addon_preference.jpg)

## Usage
The add-on provides 3 functions:

1. Reload a text file by writing `reload_script PATH` into the pipe 
(replace `PATH` with the absolute path to the file).
2. Run a text file with python by writing `run_script PATH` into the pipe.
3. Reload and enable an add-on by writing `reload_addon MODULE_NAME` into the
pipe (replace MODULE\_NAME with the module name of the add-on, e. g.
remote\_script\_run for this add-on).

For security reasons, these functions only work for text files and add-ons that
are already opened/imported in Blender.

For an example and simple client, see the [client.sh](client.sh) file.
