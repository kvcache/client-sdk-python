from momento_wire_types.controlclient_pb2 import _CreateCacheRequest
from momento_wire_types.controlclient_pb2 import _DeleteCacheRequest
from momento_wire_types.controlclient_pb2 import _ListCachesRequest

from .._utilities._data_validation import _validate_cache_name
from ..cache_operation_responses import CreateCacheResponse
from ..cache_operation_responses import DeleteCacheResponse
from ..cache_operation_responses import ListCachesResponse

from .. import _cache_service_errors_converter
from .. import _momento_logger
from . import _scs_grpc_manager


class _ScsControlClient:
    """Momento Internal."""
    def __init__(self, auth_token, endpoint):
        self._grpc_manager = _scs_grpc_manager._ControlGrpcManager(
            auth_token, endpoint)

    async def create_cache(self, cache_name):
        _validate_cache_name(cache_name)
        try:
            _momento_logger.debug(f'Creating cache with name: {cache_name}')
            request = _CreateCacheRequest()
            request.cache_name = cache_name
            return CreateCacheResponse(await self._grpc_manager.async_stub().CreateCache(request))
        except Exception as e:
            _momento_logger.debug(
                f'Failed to create cache: {cache_name} with exception:{e}')
            raise _cache_service_errors_converter.convert(e) from None

    async def delete_cache(self, cache_name):
        _validate_cache_name(cache_name)
        try:
            _momento_logger.debug(f'Deleting cache with name: {cache_name}')
            request = _DeleteCacheRequest()
            request.cache_name = cache_name
            return DeleteCacheResponse(await self._grpc_manager.async_stub().DeleteCache(request))
        except Exception as e:
            _momento_logger.debug(
                f'Failed to delete cache: {cache_name} with exception:{e}')
            raise _cache_service_errors_converter.convert(e) from None

    async def list_caches(self, next_token=None):
        try:
            list_caches_request = _ListCachesRequest()
            list_caches_request.next_token = next_token if next_token is not None else ''
            return ListCachesResponse(await self._grpc_manager.async_stub().ListCaches(list_caches_request))
        except Exception as e:
            raise _cache_service_errors_converter.convert(e)

    async def close(self):
        await self._grpc_manager.close()
