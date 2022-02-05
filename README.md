# webcam-filters

This project is an API for custom real-time filters for webcam.
(This is mostly used to annoy teachers in online classes)

## Installation

Follow pyvirtualcam installation instructions [here](https://github.com/letmaik/pyvirtualcam#installation)

Install python 3 if you haven't already installed it. And install libs for it:
`$ pip install -r requirements.txt`

## Configuration

There are three files which will help you to set up your perfect webcam filter system, which are located in the "configuration" folder.
"camera.json" is used only to set an id for your camera, while "gui.json" is used to configure your interface.
If you want to change style of the interface, you can do so in the "style.css".

## Custom filters

You can remove pre-created filters as well as create new ones in the "filters.py" file.
