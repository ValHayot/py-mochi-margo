# (C) 2018 The University of Chicago
# See COPYRIGHT in top-level directory.
import _pymargo
import json
from .bulk import Bulk
from .logging import Logger


"""
Tags to indicate whether an Engine runs as a server
(can receive RPC requests) or as a client (cannot).
"""
client = _pymargo.mode.client
server = _pymargo.mode.server

"""
Definition of an RPC handle. This class is fully defined
in the C++ side of the library.
"""
Handle = _pymargo.Handle

"""
Exception raised by most of the pymargo C++ functions.
"""
MargoException = _pymargo.MargoException


class Address:
    """
    Address class, represents the network address of an Engine.
    """

    def __init__(self, mid, hg_addr, need_del=True):
        """
        Constructor. This method is not supposed to be called
        directly by users. Users need to call the Engine.lookup
        method to lookup a remote Engine.
        """
        self._mid = mid
        self._hg_addr = hg_addr
        self._need_del = need_del

    def __del__(self):
        """
        Destructor. This method will free the underlying hg_addr_t object.
        """
        if self._need_del:
            _pymargo.addr_free(self._mid, self._hg_addr)

    def __str__(self):
        """
        Converts the address into a string. Note that this is only allowed
        on addresses returned by Engine.get_addr(), not on client addresses
        retrieved from RPC handles.
        """
        return _pymargo.addr2str(self._mid, self._hg_addr)

    def __eq__(self, other: 'Address'):
        """
        Checks for equality between two addresses.
        """
        return _pymargo.addr_cmp(self._mid, self._hg_addr, other._hg_addr)

    def copy(self):
        """
        Copies this Address object.
        """
        return Address(self._mid, _pymargo.addr_dup(self._mid, self._hg_addr))

    def shutdown(self):
        """
        Requests the remote Engine to shutdown.
        The user must have called enable_remote_shutdown on the remote Engine.
        """
        _pymargo.shutdown_remote_instance(self._mid, self._hg_addr)

    def get_internal_hg_addr(self):
        """
        Get the internal hg_addr handle.
        """
        return self._hg_addr

    @property
    def hg_addr(self):
        return self._hg_addr


def __Handler_get_Address(h):
    """
    This function gets the address of a the sender of a Handle.
    """
    mid = h._get_mid()
    addr = h._get_hg_addr()
    return Address(mid, addr, need_del=False).copy()


"""
Since the Handle class is fully defined in C++, the get_addr
function is added this way to return an Address object.
"""
setattr(_pymargo.Handle, "get_addr", __Handler_get_Address)


class Engine:

    class EngineLogger(Logger):

        def __init__(self, engine):
            self._engine = engine

        def trace(self, msg):
            _pymargo.trace(msg, mid=self._engine.mid)

        def debug(self, msg):
            _pymargo.debug(msg, mid=self._engine.mid)

        def info(self, msg):
            _pymargo.info(msg, mid=self._engine.mid)

        def warning(self, msg):
            _pymargo.warning(msg, mid=self._engine.mid)

        def error(self, msg):
            _pymargo.error(msg, mid=self._engine.mid)

        def critical(self, msg):
            _pymargo.critical(msg, mid=self._engine.mid)

        def set_logger(self, logger):
            _pymargo.set_logger(self._engine, logger)

        def set_log_level(self, log_level):
            _pymargo.set_log_level(self._engine._mid, log_level)

    def __init__(self, addr,
                 mode=server,
                 use_progress_thread=False,
                 num_rpc_threads=0,
                 options=""):
        """
        Constructor of the Engine class.
        addr : address of the Engine
        mode : pymargo.core.server or pymargo.core.client
        use_progress_thread : whether to use a progress execution stream or not
        num_rpc_threads : Number of RPC execution streams
        options : options dictionary (or serialized in json)
        """
        self._finalized = True
        if isinstance(options, dict):
            opt = json.dumps(options)
        else:
            opt = options
        self._mid = _pymargo.init(
            addr, mode, use_progress_thread, num_rpc_threads, opt)
        self._finalized = False
        self._logger = Engine.EngineLogger(self)

    def __del__(self):
        """
        Destructor. Will call finalize it has not been called yet.
        """
        if not self._finalized:
            self.finalize()

    def __enter__(self):
        """
        This method, together with __exit__, enable the "with" synthax for
        an Engine. For example:

        with Engine('tcp') as engine:
           ...
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        See __enter__.
        """
        if not self._finalized:
            self.finalize()

    def finalize(self):
        """
        Finalizes the Engine.
        """
        _pymargo.finalize(self._mid)
        self._finalized = True

    def wait_for_finalize(self):
        """
        Wait for the Engine to be finalize.
        """
        _pymargo.wait_for_finalize(self._mid)
        self._finalized = True

    @property
    def listening(self):
        """
        Returns whether the engine is listening for RPCs.
        """
        return _pymargo.is_listening(self._mid)

    def on_prefinalize(self, callable_obj):
        """
        Registers a callback (i.e. a function or an object with a
        __call__ method) to be called before the Engine is finalized
        and before the Mercury progress loop is terminated.
        """
        _pymargo.push_prefinalize_callback(self._mid, callable_obj)

    def on_finalize(self, callable_obj):
        """
        Registers a callback (i.e. a function or an object with
        a __call__ method) to be called before this Engine is finalized.
        """
        _pymargo.push_finalize_callback(self._mid, callable_obj)

    def enable_remote_shutdown(self):
        """
        Enables this Engine to be remotely shut down.
        """
        _pymargo.enable_remote_shutdown(self._mid)

    def register(self, rpc_name, obj=None, method_name=None, provider_id=0):
        """
        Registers an RPC handle. If the Engine is a client, the obj,
        method_name and provider_id arguments should be ommited. If the
        Engine is a server, obj should be the object instance from which to
        call the method represented by the method_name string, and provider_id
        should be the provider id at which this object is reachable.
        The object should inherite from the Provider class. rpc_name is the
        name of the RPC, to be used by clients when sending requests.
        """
        if (obj is None) and (method_name is None):
            return _pymargo.register_on_client(
                self._mid, rpc_name, provider_id)
        elif (obj is not None) and (method_name is not None):
            return _pymargo.register(
                self._mid, rpc_name, provider_id, obj, method_name)
        else:
            raise RuntimeError(
                'Both method name and object instance should be provided')

    def registered(self, rpc_name, provider_id=None):
        """
        Checks if an RPC with the given name is registered.
        Returns the corresponding RPC id if found, None otherwise.
        If provider_id is given, the returned RPC id will integrate it.
        """
        if provider_id is None:
            return _pymargo.registered(self._mid, rpc_name)
        else:
            return _pymargo.registered_provider(
                self._mid, rpc_name, provider_id)

    def deregister(self, rpc_id):
        """
        Deregisters an RPC.
        """
        _pymargo.deregister(self._mid, rpc_id)

    def disable_response(self, rpc_id, disable: bool = True):
        """
        Disable response for the specified RPC.
        """
        _pymargo.disable_response(self._mid, rpc_id, disable)

    def disabled_response(self, rpc_id):
        """
        Check if response is disabled for this RPC.
        """
        return _pymargo.disabled_response(self._mid, rpc_id)

    def lookup(self, straddr):
        """
        Looks up a remote Engine's address from a string and
        return an Address instance.
        """
        hg_addr = _pymargo.lookup(self._mid, straddr)
        return Address(self._mid, hg_addr)

    def addr(self):
        """
        Returns the Engine's address (Address instance).
        """
        hg_addr = _pymargo.addr_self(self._mid)
        return Address(self._mid, hg_addr)

    @property
    def address(self):
        """
        Returns the Engine's address (Address instance).
        """
        return self.addr()

    def create_handle(self, addr, rpc_id):
        """
        Creates an RPC Handle to be sent to a given address.
        """
        h = _pymargo.create(self._mid, addr._hg_addr, rpc_id)
        return h

    def create_bulk(self, array, mode):
        """
        Creates a bulk handle to expose the memory used by the provided array
        (which can be any python type that satisfies the buffer protocol,
        e.g. a bytearray or a numpy array, for instance).
        The array's memory must be contiguous.
        mode must be bulk.read_only, bulk.write_only, or bulk.read_write.
        Returns a Bulk object.
        """
        blk = _pymargo.bulk_create(self._mid, array, mode)
        return Bulk(self, blk)

    def transfer(self, op, origin_addr, origin_handle, origin_offset,
                 local_handle, local_offset, size):
        """
        Transfers data between Bulk handles.
        op : bulk.push or bulk.pull
        origin_addr : instance of Address of the origin Bulk handle
        origin_handle : remote bulk handle
        origin_offset : offset at the origin
        local_handle : Bulk handle representing local memory
        local_offset : offset in local memory
        size : size of data to transfer
        """
        _pymargo.bulk_transfer(
            self._mid, op, origin_addr._hg_addr, origin_handle._hg_bulk,
            origin_offset, local_handle._hg_bulk, local_offset, size)

    def get_internal_mid(self):
        """
        Returns the internal margo_instance_id.
        """
        return self._mid

    @property
    def mid(self):
        """
        Returns the internal margo_instance_id.
        """
        return self._mid

    @property
    def logger(self):
        """
        Returns a Logger instance that will redirect messages to the
        internal Margo instance.
        """
        return self._logger

    def set_remove(self, address: Address):
        """
        Hint that the address is no longer valid.
        """
        _pymargo.addr_set_remove(self._mid, address.hg_addr)


class Provider:
    """
    The Provider class represents an object for which some methods
    can be called remotely.
    """

    def __init__(self, engine, provider_id):
        """
        Constructor.
        engine : instance of Engine attached to this Provider
        provider_id : id at which this provider is reachable
        """
        self._engine = engine
        self._provider_id = provider_id

    def register(self, rpc_name, method_name):
        """
        Registers one of this object's methods to be used as an RPC handler.
        rpc_name : string to use by clients to identify this RPC
        method_name : string representation of the method to call
                      in this object.
        """
        return self._engine.register(
            rpc_name, self, method_name, self._provider_id)

    def registered(self, rpc_name):
        """
        Checks if an RPC with the provided name has been
        registered for this provider.
        """
        return self._engine.registered(rpc_name, self._provider_id)

    def get_provider_id(self):
        """
        Returns this provider's id.
        """
        return self._provider_id

    @property
    def provider_id(self):
        """
        Returns this provider's id.
        """
        return self._provider_id

    def get_engine(self):
        """
        Gets the Engine associated with this Provider.
        """
        return self._engine

    @property
    def engine(self):
        """
        Gets the Engine associated with this Provider.
        """
        return self._engine
