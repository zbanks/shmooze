shmooze
=======

"libmz" -- A framework for building process-backed web applications

Installation
------------
From pip/PyPI:
```
pip install shmooze
```

From source:
```
git clone https://github.com/zbanks/shmooze.git
cd shmooze
python setup.py install
```

Configuration
-------------
### settings.json

Application-level configuration is done via a JSON settings file. The settings are loaded into python and available to all running shmooze apps.

The `settings.json` file is configured by setting the `SHMOOZE_SETTINGS` environmental variable. 

For example:
```
export SHMOOZE_SETTINGS=/etc/myapp/settings.json
python -m myapp
```
There are a few settings that are 

#### ports
The `ports` field is a dictionary mapping shmooze services to TCP ports. Each shmooze app should expose a HTTP/JSON endpoint on its given port for control.

Although *locally* shmooze apps can connect to each other directly, external connections to shmooze apps should be proxied through `shmooze.wsgi`. For example, the `pool` app should be accessible through `http://localhost/pool`. 

Only the WSGI port needs to be accept incoming connections, but it's not an inherent security risk to allow clients to connect to shmooze apps directly.

#### public
The `public` field is a list of other attributes, represented as strings.

The `shmooze.wsgi` app serves a subset of the `settings.json` file on `http://localhost/settings.json`, which allows you to configure end-clients and UIs. It only shows keys that are in the `public` list, which allows you to put *e.g.* API keys in `settings.json` without making them publicly visible.

#### *_path
Fields which end in `_path` can use environmental variables, which are then expanded when `settings.json` is loaded.

This allows you to have, for example: `"log_database_path": "$HOME/shmooze.db"`, and `$HOME` will be expanded.

#### Using settings
From within a shmooze app, you can access these settings by importing the `shmooze.settings` module. 

The settings can be accessed directly through `shmooze.settings.name` or with `shmooze.settings.get("name", default=None)`.

### Supervisord

Although shmooze does not require supervisord, usually projects want to run multiple daemonized shmooze apps. There is an example `supervisord.conf` for reference.
