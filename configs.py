try:
    # support for comments in json file
    import commentjson as json
except ImportError:
    import json
import typing


def load_config(filename: str) -> typing.Dict[str, str]:
    try:
        with open(f'configurations/{filename}.json', 'r') as config:
            return json.load(config)
    except FileNotFoundError:
        with open(f'configurations/{filename}.json', 'w') as config:
            config.write('{}')


camera_config = load_config('camera')
