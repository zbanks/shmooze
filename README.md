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

Application-level configuration is done via a JSON settings file. The settings are loaded into python and available to all running shmooze services.

The `settings.json` file is configured by setting the `SHMOOZE_SETTINGS` environmental variable. 

For example:
```
export SHMOOZE_SETTINGS=/etc/myapp/settings.json
python -m myapp
```
There are a few settings that are 

#### ports
The `ports` field is a dictionary mapping shmooze services to TCP ports. Each shmooze service should expose a HTTP/JSON endpoint on its given port for control.

Although *locally* shmooze services can connect to each other directly, external connections to shmooze services should be proxied through `shmooze.wsgi`. For example, the `pool` service should be accessible through POST requests to `http://localhost/pool`. 

Only the WSGI port needs to be accept incoming connections, but it's not an inherent security risk to allow clients to connect to shmooze services directly.

#### public
The `public` field is a list of other attributes, represented as strings.

The `shmooze.wsgi` service serves a subset of the `settings.json` file on `http://localhost/settings.json`, which allows you to configure end-clients and UIs. It only shows keys that are in the `public` list, which allows you to put *e.g.* API keys in `settings.json` without making them publicly visible.

#### *_path
Fields which end in `_path` can use environmental variables, which are then expanded when `settings.json` is loaded.

This allows you to have, for example: `"log_database_path": "$HOME/shmooze.db"`, and `$HOME` will be expanded.

#### Using settings
From within a shmooze service, you can access these settings by importing the `shmooze.settings` module. 

The settings can be accessed directly through `shmooze.settings.name` or with `shmooze.settings.get("name", default=None)`.

### Supervisord

Although shmooze does not require supervisord, usually projects want to run multiple daemonized shmooze services. There is an example `supervisord.conf` for reference.

Apps
----
A shmooze project consists of several services. An service is a daemonized process which responds to a HTTP/JSON endpoint.

Shmooze comes with the following services:

#### shmooze.wsgi
The `shmooze.wsgi` service creates HTTP endpoints all on the same port for other running services based on the `ports` configuration.

Additionally, it serves static content out of `static_path`.

It can be started directly with `python -m shmooze.wsgi` (with `SHMOOZE_SETTINGS` configured).

#### shmooze.queue & shmooze.pool
Both `shmooze.queue` and `shmooze.pool` are designed for running a set of *modules*: 

- *Queue* keeps an ordered list of modules, running one at a time and defaulting to a *background module* when the queue is empty. 
- *Pool* has all of the modules running concurrently.

These two services need additional configuration and cannot be started directly. See `examples/example_queue.py` or [musicazoo.queue](https://github.com/zbanks/musicazoo/blob/master/musicazoo/queue.py) for an example of how its used.

Modules
-------
Modules are ephemeral processes that are controlled and brokered by a *queue* or *pool*.

The queue/pool keeps track of a JSON dict of *parameters*. These are updated with push notifications from the modules (see below). This dict can then be requested by other services, etc. via the queue/pool's HTTP/JSON endpoint.

Modules can theoretically be written in any language, not just python. In python, `pymodule`/`shmooze.modules` contains the `ParentConnection` and `JSONParentPoller` classes which provide a framework for modules.

### Communication

Modules communicate with their controlling queue or pool over a pair of TCP/JSON streams which each follow a request-response pattern.
- The *command stream* allows the queue to send or forward commands to the running module instance.
- The *update stream* allows the module to push updates about its state back to the queue.

The ports of these streams are passed in to the module as arguments.

#### Command Stream Methods
The following methods **must** be implemented in a *module*. The queue/pool will initiate these commands over the command stream.

- `init` - called shortly after the module is spawned, and contains arguments to the module. The module should not start performing any action until it receives `init`.
- `rm` - called right before the module is terminated. The module should clean itself up and terminate gracefully.
- `suspend` - called to "pause" the module's action, e.g. pause a playing video. This is called when the queue wants to play something instead.
- `play` - called to "unpause" the module.

Modules are also free to implement any additional methods. Other services can access these methods through the queue/pool. (See: `tell_module`)

#### Update Stream Methods
The follow methods are implemented by the *queue*/*pool*. The module can send these commands to the queue/pool over the update stream.

- `rm` - used to let the queue/pool know if the module terminates gracefully on its own
- `set_parameters` - update a JSON dict of *parameters* related to the module.
- `unset_parameters` - remove the given parameters from the module's *parameters* dict.

### Termination

If modules that are requested to terminate with `rm` do not exit within a timeout (1-3 seconds), the `SIGTERM` signal will be sent, followed by `SIGKILL` if they continue to run. This is to prevent "zombie" processes from being abandoned and running in the background. This mechanism is a key part of shmooze.

Modules can also terminate on their own, by sending an `rm` command to the queue/pool over the update stream.

Javascript
----------

Shmooze is intended to build web applications. A library `shmooze.js` is provided which provides the basics of connecting to *endpoints* (services) and sending commands. It also loads global settings from `./settings.json`.

- `settings_data` - object of settings from `./settings.json`
- `endpoints` - objects of `Endpoint` objects 
- `Endpoint` - object for communicating with a single service
    - `endpoint.deferQuery` - Send a command to a service, but try to batch requests.
    - `endpoint.forceQuery` - Send a command to a service immediately

When connection to the shmooze server is lost, HTML tags with the class `.disconnect-hide` will be hidden, and tags with `.disconnect-show` will be shown.

Scripts
-------
### shmz
`shmz` is an example of a simple a command-line interface to a shmooze module with no external dependencies. This is a good template to use if you want an external system to send commands to a shmooze service. 

A more complete example (from musicazoo) is the [mz](https://github.com/zbanks/musicazoo/blob/master/musicazoo/cli.py) script. Musicazoo has an `nlp` service which is designed to parse simple string inputs.

### run_shmooze.sh
`run_shmooze.sh` is an example on how to run a shmooze system for debugging. 

Gritty Details
--------------

The following are details of internals and shouldn't be necessary to understand to develop with shmooze.

### JSON Commands

The standard format for commands is JSON, escaped and serialized into a string,  and terminated with a trailing newline (`\n`).

