import util
import pkg_resources
import shmooze.settings as settings

static_endpoints = {
    '/': settings.static_path
}

wsgi_endpoints = {}

for service, portnum in settings.ports.items():
    if service != "wsgi":
        wsgi_endpoints["/{}".format(service)] = util.wsgi_control("localhost", portnum)
