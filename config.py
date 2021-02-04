'''Variables that I may find handy to change on the fly via the server are loaded here.
This can also be thought of as a config file.'''
import json

with open('config.json','r') as f:
    vars = json.load(f)


TYPE_RESOLUTION = {'image_download_interval': int,
                   'flip_frequency': int}

def save_config():
    with open('config.json','w') as f:
        json.dump(vars)
