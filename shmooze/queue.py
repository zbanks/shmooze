import shmooze.lib.cmdlog
import shmooze.lib.database as database
import shmooze.lib.service as service
import shmooze.settings as settings
import uuid

# A queue manages the life and death of modules, through tornado's IOLoop.

class Queue(service.JSONCommandProcessor, service.Service):
    port=settings.ports["queue"]

    def __init__(self,modules,backgrounds,logfilename=None):
        print "Queue started."
        # Create a UUID for this instance
        self.instance = str(uuid.uuid4())

        # Create lookup table of possible modules & backgrounds
        self.modules_available_dict = dict([(m.TYPE_STRING,m) for m in modules])
        self.backgrounds_available_dict = dict([(b.TYPE_STRING,b) for b in backgrounds])

        # queue is the actual queue of modules
        self.queue=[]
        # bg is the module running in the background
        self.bg = None
        # queue_lock is a synchronization object so that multiple clients don't try to alter the queue at the same time
        # (also includes background)
        self.queue_lock=service.Lock()

        # old_queue is used to take diffs of the queue (and from there, send appropriate messages to affected modules.)
        # whenever the queue is unlocked, it should equal the queue.
        self.old_queue=[]
        # Same with old_bg
        self.old_bg=None

        # When debugging, uids are assigned sequentially
        self.debug = False

        # Each module on the queue gets a unique ID, this variable allocates those
        self.last_uid=-1

        # Log important commands
        # (used in JSONCommandProcessor)
        if logfilename:
            self.logger = database.Database(log_table="queue_log")
        self.log_namespace = "client-queue"

        # JSONCommandService handles all of the low-level TCP connection stuff.
        super(Queue,self).__init__()

    # Get a new UID for a module.
    def get_uid(self):
        if self.debug:
            self.last_uid += 1
            return self.last_uid
        return str(uuid.uuid4())

    # Called from client
    # Retrieves given parameters from the module
    @service.coroutine
    def ask_module(self,uid,parameters):
        d=dict(self.queue)
        if uid not in d:
            raise Exception("Module identifier not in queue")
        raise service.Return(d[uid].get_multiple_parameters(parameters))

    # Called fom client
    # Retrieves given parameters from the background
    @service.coroutine
    def ask_background(self,uid,parameters):
        if self.bg is None:
            raise Exception("No background")
        (bg_uid,bg_obj)=self.bg
        if bg_uid != uid:
            raise Exception("Background identifier doesn't match current background")
        raise service.Return(bg_obj.get_multiple_parameters(parameters))

    # Called from client
    # Retrieves names of possible modules that can be added to the queue
    @service.coroutine
    def modules_available(self):
        raise service.Return(self.modules_available_dict.keys())

    # Called from client
    # Retrieves names of possible backgrounds
    @service.coroutine
    def backgrounds_available(self):
        raise service.Return(self.backgrounds_available_dict.keys())

    # Called from client
    # Retrieves the current queue, and info about modules on it
    @service.coroutine
    def get_queue(self,parameters={}):
        l=[]
        for (uid,obj) in self.queue:
            d={'uid':uid,'type':obj.TYPE_STRING}
            if obj.TYPE_STRING in parameters:
                d['parameters']=obj.get_multiple_parameters(parameters[obj.TYPE_STRING])
            l.append(d)
        raise service.Return(l)

    # Called from client
    # Retrieves the current background, and info about it
    @service.coroutine
    def get_bg(self,parameters={}):
        if self.bg is None:
            return None
        (uid,obj)=self.bg

        d={'uid':uid,'type':obj.TYPE_STRING}
        if obj.TYPE_STRING in parameters:
            d['parameters']=obj.get_multiple_parameters(parameters[obj.TYPE_STRING])
        raise service.Return(d)

    # Called from client
    # Issues a command to a module
    # Note that this involves a transaction between the queue and the module, and may take a while.
    # This is in contrast to ask_module which only retrieves cached information and does not create additional transactions.
    @service.coroutine
    def tell_module(self,uid,cmd,args={}):
        d=dict(self.queue)
        if uid not in d:
            raise Exception("Module identifier not in queue")
        result = yield d[uid].tell(cmd,args)
        raise service.Return(result)

    # Called from client
    # Issues a command to the background (see tell_module)
    @service.coroutine
    def tell_background(self,uid,cmd,args={}):
        if self.bg is None:
            raise Exception("No background")
        (bg_uid,bg_obj)=self.bg
        if bg_uid != uid:
            raise Exception("Background identifier doesn't match current background")
        result = yield bg_obj.tell(cmd,args)
        raise service.Return(result)

    # Called from client
    # Create a new module and add it to the queue
    # May take a little while as module is spawned and constructed.
    @service.coroutine
    def add(self,type,args={}):
        uid=self.get_uid()
        if type not in self.modules_available_dict:
            raise Exception("Unrecognized module name")
        mod_inst=self.modules_available_dict[type](self.get_remover(uid))
        mod_inst.logger = self.logger
        mod_inst.uid = uid 
        mod_inst.log_uid = uid 
        mod_inst.log_namespace = "module-instance" 
        yield mod_inst.new(args)
        with (yield self.queue_lock.acquire()):
            self.queue.append((uid,mod_inst))
            yield self.queue_updated()
        raise service.Return({'uid':uid})

    # Called from client
    # Create a new background and add it to the queue
    # May take a little while as background is spawned and constructed.
    @service.coroutine
    def set_bg(self,type,args={}):
        uid=self.get_uid()
        if type not in self.backgrounds_available_dict:
            raise Exception("Unrecognized module name")
        bg_inst=self.backgrounds_available_dict[type](self.get_remover(uid))
        yield bg_inst.new(args)
        with (yield self.queue_lock.acquire()):
            self.bg=(uid,bg_inst)
            yield self.queue_updated()
        raise service.Return({'uid':uid})

    # Called from client
    # Removes some modules from the queue
    # May take a little while as the modules are destroyed.
    @service.coroutine
    def rm(self,uids):
        with (yield self.queue_lock.acquire()):
            self.queue=[(uid,obj) for (uid,obj) in self.queue if uid not in uids]
            if self.bg is not None and self.bg[0] in uids:
                self.bg=None
            yield self.queue_updated()

    # Called from client
    # Reorders modules on the queue
    # May take a little while if the top (playing) module is moved down (suspended).
    @service.coroutine
    def mv(self,uids):
        with (yield self.queue_lock.acquire()):
            newqueue=[]
            oldqueue=[uid for (uid,obj) in self.queue]
            d=dict(self.queue)
            for uid in uids:
                if uid in oldqueue:
                    oldqueue.remove(uid)
                    newqueue.append(uid)
            newqueue+=oldqueue
            self.queue=[(uid,d[uid]) for uid in newqueue]
            yield self.queue_updated()

    # Take a diff of the queue, and issue appropriate commands to modules (play, suspend, and rm) if necessary.
    # May take a little while as the commands are executed.
    # Commands are executed simultaneously.
    # Queue should be locked for this operation
    # TODO harden this
    @service.coroutine
    def queue_updated(self):
        again=True
        while again:
            again=False
            cur_uids=[uid for (uid,obj) in self.queue]
            to_remove=[((uid,obj),obj.remove) for (uid,obj) in self.old_queue if uid not in cur_uids and obj.alive]
            if self.bg:
                bg_uid,bg_obj=self.bg
            if self.old_bg:
                old_bg_uid,old_bg_obj=self.old_bg
            if self.old_bg is not None and (self.bg is None or bg_uid != old_bg_uid) and old_bg_obj.alive:
                to_remove.append(((old_bg_uid,old_bg_obj),old_bg_obj.remove))
            to_play=[]
            if len(self.queue) > 0:
                uid,obj=self.queue[0]
                if not obj.is_on_top:
                    to_play=[((uid,obj),obj.play)]
            elif self.bg:
                if not bg_obj.is_on_top:
                    to_play=[((bg_uid,bg_obj),bg_obj.play)]

            to_suspend=[((uid,obj),obj.suspend) for (uid,obj) in self.queue[1:] if obj.is_on_top]
            if len(self.queue) > 0 and self.bg:
                to_suspend.append(((bg_uid,bg_obj),bg_obj.suspend))

            self.old_queue=self.queue
            self.old_bg=self.bg

            actions=to_remove+to_suspend+to_play
            try:
                if len(actions) > 0:
                    # Execute all operations simultaneously
                    actions=[(mod,future()) for mod,future in actions]
                    yield [future for uid,future in actions]
            except Exception as e:
                print "Errors trying to update queue:"
                for (uid,obj),f in actions:
                    if f.exception():
                        print "- {0} raised {1}".format(uid,f.exception())
                bad_modules=[mod for mod,f in actions if f.exception()]
                print "Removing bad modules:",bad_modules
                for uid,obj in bad_modules:
                    obj.terminate()
                self.queue=[(uid,obj) for uid,obj in self.queue if uid not in [uid2 for uid2,obj2 in bad_modules]]
                if self.bg is not None and self.bg[0] in [uid for uid,obj in bad_modules]:
                    self.bg=None
                again=True

    # Returns a coroutine that may be executed to remove the current module from the queue
    # Generally, the result of this function is passed into a newly constructed module, so that
    # it may gracefully remove itself if it terminates naturally.
    def get_remover(self,my_uid):
        @service.coroutine
        def remove_self():
            with (yield self.queue_lock.acquire()):
                self.queue=[(uid,obj) for (uid,obj) in self.queue if uid != my_uid]
                if self.bg is not None and self.bg[0] == my_uid:
                    self.bg=None
                yield self.queue_updated()
        return remove_self

    def shutdown(self):
        def shutdown_complete(f):
            service.ioloop.stop()
        service.ioloop.add_future(self.killall(),shutdown_complete)

    @service.coroutine
    def killall(self):
        with (yield self.queue_lock.acquire()):
            self.queue=[]
            self.bg=None
            yield self.queue_updated()

    commands = {
        'rm':rm,
        'mv':mv,
        'add':add,
        'queue':get_queue,
        'bg':get_bg,
        'set_bg':set_bg,
        'modules_available':modules_available,
        'backgrounds_available':backgrounds_available,
        'tell_module':tell_module,
        'tell_background':tell_background,
        'ask_module':ask_module,
        'ask_background':ask_background,
    }

    log_cmds = ['rm','mv','add','set_bg','tell_module','tell_background']
