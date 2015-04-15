import shmooze.queue
import shmooze.settings as settings
import shmooze.lib.service as service
from shmooze.module import Module
import os
import signal

class Youtube(Module):
    TYPE_STRING='youtube'
    process = ['python','-m','musicazoo.queue.modules.youtube']

class Problem(Module):
    TYPE_STRING='problem'
    process = ['python','-m','musicazoo.queue.modules.problem']

class Text(Module):
    TYPE_STRING='text'
    process = ['python','-m','musicazoo.queue.modules.text']

class TextBG(Module):
    TYPE_STRING='text_bg'
    process = ['python','-m','musicazoo.queue.modules.text_bg']

class Image(Module):
    TYPE_STRING='image'
    process = ['python','-m','musicazoo.queue.modules.image']

modules = [Youtube, Text]
backgrounds = [TextBG, Image]

q=shmooze.queue.Queue(modules, backgrounds, settings.log_database)

def shutdown_handler(signum,frame):
    print
    print "Received signal, attempting graceful shutdown..."
    service.ioloop.add_callback_from_signal(q.shutdown)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

service.ioloop.start()
