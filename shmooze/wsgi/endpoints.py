import util
import pkg_resources
import shmooze.settings as settings

static_endpoints = {
    '/': settings.static_path,
}

wsgi_endpoints = {
    "/settings.json": util.wsgi_settings_json(settings.public_settings),
}

for service, portnum in settings.ports.items():
    if service != "wsgi":
        wsgi_endpoints["/{}".format(service)] = util.wsgi_control("localhost", portnum)

