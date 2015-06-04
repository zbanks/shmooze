import util
import pkg_resources
import shmooze.settings as settings

prefix = settings.get("wsgi_prefix", "/")

static_endpoints = {
    prefix: settings.static_path,
}

wsgi_endpoints = {
    prefix + "settings.json": util.wsgi_settings_json(settings.public_settings),
}

for service, portnum in settings.ports.items():
    if service != "wsgi":
        wsgi_endpoints[prefix + service] = util.wsgi_control("localhost", portnum)

