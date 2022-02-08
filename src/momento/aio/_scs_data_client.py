from typing import Union, Optional
import concurrent.futures
from momento_wire_types.cacheclient_pb2 import _GetRequest
from momento_wire_types.cacheclient_pb2 import _SetRequest

from .. import cache_operation_responses as cache_sdk_resp
from .. import _cache_service_errors_converter
from .. import _momento_logger
from . import _scs_grpc_manager
from .._utilities._data_validation import (
    _as_bytes,
    _validate_ttl,
    _make_metadata,
    _validate_cache_name,
    _validate_multi_op_list,
)

_DEFAULT_DEADLINE_SECONDS = 5.0  # 5 seconds


class _ScsDataClient:
    """Internal"""

    def __init__(
            self,
            auth_token: str,
            endpoint: str,
            default_ttl_seconds: int,
            operation_timeout_ms: Optional[int],
    ):
        self._default_deadline_seconds = (
            _DEFAULT_DEADLINE_SECONDS
            if not operation_timeout_ms
            else operation_timeout_ms / 1000.0
        )
        self._grpc_manager = _scs_grpc_manager._DataGrpcManager(auth_token, endpoint)
        _validate_ttl(default_ttl_seconds)
        self._default_ttlSeconds = default_ttl_seconds

    async def set(
            self,
            cache_name: str,
            key: str,
            value: Union[str, bytes],
            ttl_seconds: Optional[int],
    ) -> cache_sdk_resp.CacheSetResponse:
        _validate_cache_name(cache_name)
        try:
            _momento_logger.debug(f"Issuing a set request with key {key}")
            item_ttl_seconds = (
                self._default_ttlSeconds if ttl_seconds is None else ttl_seconds
            )
            _validate_ttl(item_ttl_seconds)
            set_request = _SetRequest()
            set_request.cache_key = _as_bytes(key, "Unsupported type for key: ")
            set_request.cache_body = _as_bytes(value, "Unsupported type for value: ")
            set_request.ttl_milliseconds = item_ttl_seconds * 1000
            response = await self._grpc_manager.async_stub().Set(
                set_request,
                metadata=_make_metadata(cache_name),
                timeout=self._default_deadline_seconds,
            )
            _momento_logger.debug(f"Set succeeded for key: {key}")
            return cache_sdk_resp.CacheSetResponse(response, set_request.cache_body)
        except Exception as e:
            _momento_logger.debug(f"Set failed for {key} with response: {e}")
            raise _cache_service_errors_converter.convert(e)

    async def m_set(self, cache_name, set_operations):
        _validate_multi_op_list(set_operations)
        _validate_cache_name(cache_name)
        try:
            request_promises = set()
            for val in set_operations:
                item_ttl_seconds = (
                    self._default_ttlSeconds if 'ttl_seconds' not in val else val['ttl_seconds']
                )
                _validate_ttl(item_ttl_seconds)
                set_request = _SetRequest()
                set_request.cache_key = _as_bytes(val['key'], 'Unsupported type for key: ')
                set_request.cache_body = _as_bytes(val['value'], 'Unsupported type for value: ')
                set_request.ttl_milliseconds = item_ttl_seconds * 1000
                request_promises.add(self._grpc_manager.async_stub().Set(
                    set_request,
                    metadata=_make_metadata(cache_name)
                ))

            concurrent.futures.as_completed(request_promises)

            _momento_logger.debug(f'mSet succeeded')
            return cache_sdk_resp.CacheMultiSetResponse

        except Exception as e:
            _momento_logger.debug(f'mSet failed with response: {e}')
            return cache_sdk_resp.CacheMultiSetResponse()  # mSet never fails always return ok

    async def get(self, cache_name, key):
        _validate_cache_name(cache_name)
        try:
            _momento_logger.debug(f"Issuing a get request with key {key}")
            get_request = _GetRequest()
            get_request.cache_key = _as_bytes(key, "Unsupported type for key: ")
            response = await self._grpc_manager.async_stub().Get(
                get_request,
                metadata=_make_metadata(cache_name),
                timeout=self._default_deadline_seconds,
            )
            _momento_logger.debug(f"Received a get response for {key}")
            return cache_sdk_resp.CacheGetResponse(response)
        except Exception as e:
            _momento_logger.debug(f"Get failed for {key} with response: {e}")
            raise _cache_service_errors_converter.convert(e)

    async def m_get(self, cache_name, get_operations):
        _validate_multi_op_list(get_operations)
        _validate_cache_name(cache_name)
        try:
            rsp_promises = set()
            for val in get_operations:
                get_request = _GetRequest()
                get_request.cache_key = _as_bytes(val['key'], 'Unsupported type for key: ')
                rsp_promises.add(self._grpc_manager.async_stub().Get(
                    get_request,
                    metadata=_make_metadata(cache_name)
                ))

            responses = []
            for pending_response in rsp_promises:
                # await one at a time to keep ordered for user
                completed_request = await pending_response
                # Receive the returned result of current user
                responses.append(cache_sdk_resp.CacheGetResponse(completed_request))

            _momento_logger.debug(f'mGet succeeded')

            return cache_sdk_resp.CacheMultiGetResponse(responses)
        except Exception as e:
            _momento_logger.debug(f'mSet failed with response: {e}')
            raise _cache_service_errors_converter.convert(e)

    async def close(self) -> None:
        await self._grpc_manager.close()
