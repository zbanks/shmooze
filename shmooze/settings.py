import json
import os
import pkg_resources

json_path = os.environ.get("SHMOOZE_SETTINGS")
if json_path is None:
    json_path = pkg_resources.resource_filename("shmooze", '../settings.json')

print "Using shmooze settings file: '{}'".format(json_path)

settings_file=open(json_path)

settings = json.load(settings_file)

if 'static_path' not in settings:
    settings['static_path'] = pkg_resources.resource_filename("shmooze", '../static')

for key, value in settings.items():
    if key.endswith("_path"):
        settings[key] = os.path.expandvars(value)

globals().update(settings)
