import shmooze.lib.cmdlog
import shmooze.lib.database as database
import shmooze.lib.service as service
import shmooze.settings as settings
import uuid

# A pool manages the life and death of modules, through tornado's IOLoop.

class Pool(service.JSONCommandProcessor, service.Service):
    port=settings.ports["pool"]

    def __init__(self,modules,logfilename=None):
        print "Pool started."
        # Create a UUID for this instance
        self.instance = str(uuid.uuid4())

        # Create lookup table of possible modules & backgrounds
        self.modules_available_dict = dict([(m.TYPE_STRING,m) for m in modules])

        # pool is the actual pool of modules
        self.pool=set()
        # pool is a synchronization object so that multiple clients don't try to alter the pool at the same time
        # (also includes background)
        self.pool_lock=service.Lock()

        # old_queue is used to take diffs of the pool (and from there, send appropriate messages to affected modules.)
        # whenever the pool is unlocked, it should equal the pool.
        self.old_pool=[]

        # When debugging, uids are assigned sequentially
        self.debug = False

        # Each module on the pool gets a unique ID, this variable allocates those
        self.last_uid=-1

        # Log important commands
        # (used in JSONCommandProcessor)
        if logfilename:
            self.logger = database.Database(log_table="pool_log")
        self.log_namespace = "client-pool"

        # JSONCommandService handles all of the low-level TCP connection stuff.
        super(Pool,self).__init__()

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
        d=dict(self.pool)
        if uid not in d:
            raise Exception("Module identifier not in queue")
        raise service.Return(d[uid].get_multiple_parameters(parameters))

    # Called from client
    # Retrieves names of possible modules that can be added to the pool
    @service.coroutine
    def modules_available(self):
        raise service.Return(self.modules_available_dict.keys())

    # Called from client
    # Retrieves the current pool, and info about modules on it
    @service.coroutine
    def get_pool(self,parameters={}):
        l=[]
        for (uid,obj) in self.pool:
            d={'uid':uid,'type':obj.TYPE_STRING}
            if obj.TYPE_STRING in parameters:
                d['parameters']=obj.get_multiple_parameters(parameters[obj.TYPE_STRING])
            l.append(d)
        raise service.Return(l)

    # Called from client
    # Issues a command to a module
    # Note that this involves a transaction between the pool and the module, and may take a while.
    # This is in contrast to ask_module which only retrieves cached information and does not create additional transactions.
    @service.coroutine
    def tell_module(self,uid,cmd,args={}):
        d=dict(self.pool)
        if uid not in d:
            raise Exception("Module identifier not in pool")
        result = yield d[uid].tell(cmd,args)
        raise service.Return(result)

    # Called from client
    # Create a new module and add it to the pool
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
        with (yield self.pool_lock.acquire()):
            self.pool.append((uid,mod_inst))
            yield self.pool_updated()
        raise service.Return({'uid':uid})

    # Called from client
    # Removes some modules from the pool
    # May take a little while as the modules are destroyed.
    @service.coroutine
    def rm(self,uids):
        with (yield self.pool_lock.acquire()):
            self.pool={(uid,obj) for (uid,obj) in self.pool if uid not in uids}
            if self.bg is not None and self.bg[0] in uids:
                self.bg=None
            yield self.pool_updated()

    # Take a diff of the pool, and issue appropriate commands to modules (start and rm) if necessary.
    # May take a little while as the commands are executed.
    # Commands are executed simultaneously.
    # Pool should be locked for this operation
    # TODO harden this
    @service.coroutine
    def pool_updated(self):
        again=True
        while again:
            again=False
            cur_uids=[uid for (uid,obj) in self.pool]
            to_remove=[((uid,obj),obj.remove) for (uid,obj) in self.old_pool if uid not in cur_uids and obj.alive]
            to_play=[]
            for (uid, obj) in self.pool:
                if not obj.is_on_top: # is_on_top is alias for 'is running'  in this case
                    to_play.append(((uid, obj), obj.play))

            to_suspend = [] # Nothing should be suspended

            self.old_pool=self.pool

            actions=to_remove+to_suspend+to_play
            try:
                if len(actions) > 0:
                    # Execute all operations simultaneously
                    actions=[(mod,future()) for mod,future in actions]
                    yield [future for uid,future in actions]
            except Exception as e:
                print "Errors trying to update poool:"
                for (uid,obj),f in actions:
                    if f.exception():
                        print "- {0} raised {1}".format(uid,f.exception())
                bad_modules=[mod for mod,f in actions if f.exception()]
                print "Removing bad modules:",bad_modules
                for uid,obj in bad_modules:
                    obj.terminate()
                self.pool={(uid,obj) for uid,obj in self.pool if uid not in [uid2 for uid2,obj2 in bad_modules]}
                again=True

    # Returns a coroutine that may be executed to remove the current module from the queue
    # Generally, the result of this function is passed into a newly constructed module, so that
    # it may gracefully remove itself if it terminates naturally.
    def get_remover(self,my_uid):
        @service.coroutine
        def remove_self():
            with (yield self.pool_lock.acquire()):
                self.pool={(uid,obj) for (uid,obj) in self.pool if uid != my_uid}
                yield self.pool_updated()
        return remove_self

    def shutdown(self):
        def shutdown_complete(f):
            service.ioloop.stop()
        service.ioloop.add_future(self.killall(),shutdown_complete)

    @service.coroutine
    def killall(self):
        with (yield self.pool_lock.acquire()):
            self.pool = set()
            yield self.pool_updated()

    commands = {
        'rm':rm,
        'add':add,
        'pool':get_pool,
        'modules_available':modules_available,
        'tell_module':tell_module,
        'ask_module':ask_module,
    }

    log_cmds = ['rm','add','tell_module']
