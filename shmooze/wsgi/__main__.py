import shmooze.wsgi
import shmooze.settings
import werkzeug.serving

werkzeug.serving.run_simple('',shmooze.settings.ports["wsgi"],shmooze.wsgi.application,use_reloader=False, use_debugger=False)
