import unittest
import os
import uuid
import time

import momento.simple_cache_client as simple_cache_client
import momento.errors as errors
from momento.cache_operation_responses import CacheGetStatus

_AUTH_TOKEN = os.getenv('TEST_AUTH_TOKEN')
_TEST_CACHE_NAME = os.getenv('TEST_CACHE_NAME')
_BAD_AUTH_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJpbnRlZ3JhdGlvbiIsImNwIjoiY29udHJvbC5jZWxsLWFscGhhLWRldi5wcmVwcm9kLmEubW9tZW50b2hxLmNvbSIsImMiOiJjYWNoZS5jZWxsLWFscGhhLWRldi5wcmVwcm9kLmEubW9tZW50b2hxLmNvbSJ9.gdghdjjfjyehhdkkkskskmmls76573jnajhjjjhjdhnndy"
_DEFAULT_TTL_SECONDS = 60


class TestMomento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _AUTH_TOKEN:
            raise RuntimeError(
                "Integration tests require TEST_AUTH_TOKEN env var; see README for more details."
            )
        if not _TEST_CACHE_NAME:
            raise RuntimeError(
                "Integration tests require TEST_CACHE_NAME env var; see README for more details."
            )

        # default client for use in tests
        cls.client = simple_cache_client.init(_AUTH_TOKEN, _DEFAULT_TTL_SECONDS)

        # ensure test cache exists
        try:
            cls.client.create_cache(_TEST_CACHE_NAME)
        except errors.AlreadyExistsError:
            # do nothing, cache already exists
            pass

    @classmethod
    def tearDownClass(cls):
        # close client
        cls.client._momento_async_client._control_client.close()
        cls.client._momento_async_client._data_client.close()

    # basic happy path test
    def test_create_cache_get_set_values_and_delete_cache(self):
        cache_name = str(uuid.uuid4())
        key = str(uuid.uuid4())
        value = str(uuid.uuid4())

        self.client.create_cache(cache_name)

        set_resp = self.client.set(cache_name, key, value)
        self.assertEqual(set_resp.value(), value)

        get_resp = self.client.get(cache_name, key)
        self.assertEqual(get_resp.status(), CacheGetStatus.HIT)
        self.assertEqual(get_resp.value(), value)

        get_for_key_in_some_other_cache = self.client.get(_TEST_CACHE_NAME, key)
        self.assertEqual(get_for_key_in_some_other_cache.status(), CacheGetStatus.MISS)

        self.client.delete_cache(cache_name)

    # init

    def test_init_throws_exception_when_client_uses_negative_default_ttl(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            simple_cache_client.init(_AUTH_TOKEN, -1)
        self.assertEqual('{}'.format(cm.exception), "TTL Seconds must be a non-negative integer")

    def test_init_throws_exception_for_non_jwt_token(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            simple_cache_client.init("notanauthtoken", _DEFAULT_TTL_SECONDS)
        self.assertEqual('{}'.format(cm.exception), "Invalid Auth token.")

    def test_init_throws_exception_when_client_uses_negative_request_timeout_ms(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            simple_cache_client.init(_AUTH_TOKEN, _DEFAULT_TTL_SECONDS, -1)
        self.assertEqual('{}'.format(cm.exception), "Request timeout must be greater than zero.")

    def test_init_throws_exception_when_client_uses_zero_request_timeout_ms(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            simple_cache_client.init(_AUTH_TOKEN, _DEFAULT_TTL_SECONDS, 0)
        self.assertEqual('{}'.format(cm.exception), "Request timeout must be greater than zero.")

    # create_cache

    def test_create_cache_throws_already_exists_when_creating_existing_cache(self):
        with self.assertRaises(errors.AlreadyExistsError):
            self.client.create_cache(_TEST_CACHE_NAME)

    def test_create_cache_throws_exception_for_empty_cache_name(self):
        with self.assertRaises(errors.BadRequestError):
            self.client.create_cache("")

    def test_create_cache_throws_validation_exception_for_null_cache_name(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.create_cache(None)
        self.assertEqual('{}'.format(cm.exception), "Cache name must be a non-empty string")

    def test_create_cache_with_bad_cache_name_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.create_cache(1)
        self.assertEqual('{}'.format(cm.exception), "Cache name must be a non-empty string")

    def test_create_cache_throws_authentication_exception_for_bad_token(self):
        with simple_cache_client.init(_BAD_AUTH_TOKEN,
                                      _DEFAULT_TTL_SECONDS) as simple_cache:
            with self.assertRaises(errors.AuthenticationError):
                simple_cache.create_cache(str(uuid.uuid4()))

    # delete_cache
    def test_delete_cache_succeeds(self):
        cache_name = str(uuid.uuid4())

        self.client.create_cache(cache_name)
        with self.assertRaises(errors.AlreadyExistsError):
            self.client.create_cache(cache_name)
        self.client.delete_cache(cache_name)
        with self.assertRaises(errors.NotFoundError):
            self.client.delete_cache(cache_name)

    def test_delete_cache_throws_not_found_when_deleting_unknown_cache(self):
        cache_name = str(uuid.uuid4())
        with self.assertRaises(errors.NotFoundError):
            self.client.delete_cache(cache_name)

    def test_delete_cache_throws_invalid_input_for_null_cache_name(self):
        with self.assertRaises(errors.InvalidArgumentError):
            self.client.delete_cache(None)

    def test_delete_cache_throws_exception_for_empty_cache_name(self):
        with self.assertRaises(errors.BadRequestError):
            self.client.delete_cache("")

    def test_delete_with_bad_cache_name_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.delete_cache(1)
        self.assertEqual('{}'.format(cm.exception), "Cache name must be a non-empty string")

    def test_delete_cache_throws_authentication_exception_for_bad_token(self):
        with simple_cache_client.init(_BAD_AUTH_TOKEN,
                                      _DEFAULT_TTL_SECONDS) as simple_cache:
            with self.assertRaises(errors.AuthenticationError):
                simple_cache.create_cache(str(uuid.uuid4()))

    # list_caches

    def test_list_caches_succeeds(self):
        cache_name = str(uuid.uuid4())

        caches = self.client.list_caches().caches()
        cache_names = [cache.name() for cache in caches]
        self.assertNotIn(cache_name, cache_names)

        try:
            self.client.create_cache(cache_name)

            list_cache_resp = self.client.list_caches()
            caches = list_cache_resp.caches()
            cache_names = [cache.name() for cache in caches]
            self.assertIn(cache_name, cache_names)
            self.assertIsNone(list_cache_resp.next_token())
        finally:
            self.client.delete_cache(cache_name)

    def test_list_caches_throws_authentication_exception_for_bad_token(self):
        with simple_cache_client.init(_BAD_AUTH_TOKEN,
                                      _DEFAULT_TTL_SECONDS) as simple_cache:
            with self.assertRaises(errors.AuthenticationError):
                simple_cache.list_caches()

    def test_list_caches_with_next_token_works(self):
        # skip until pagination is actually implemented, see
        # https://github.com/momentohq/control-plane-service/issues/83
        self.skipTest("pagination not yet implemented")

    # setting and getting

    def test_set_and_get_with_hit(self):
        key = str(uuid.uuid4())
        value = str(uuid.uuid4())

        set_resp = self.client.set(_TEST_CACHE_NAME, key, value)
        self.assertEqual(set_resp.value(), value)
        self.assertEqual(set_resp.value_as_bytes(), bytes(value, 'utf-8'))

        get_resp = self.client.get(_TEST_CACHE_NAME, key)
        self.assertEqual(get_resp.status(), CacheGetStatus.HIT)
        self.assertEqual(get_resp.value(), value)
        self.assertEqual(get_resp.value_as_bytes(), bytes(value, 'utf-8'))

    def test_set_and_get_with_byte_key_values(self):
        key = uuid.uuid4().bytes
        value = uuid.uuid4().bytes

        set_resp = self.client.set(_TEST_CACHE_NAME, key, value)
        self.assertEqual(set_resp.value_as_bytes(), value)

        get_resp = self.client.get(_TEST_CACHE_NAME, key)
        self.assertEqual(get_resp.status(), CacheGetStatus.HIT)
        self.assertEqual(get_resp.value_as_bytes(), value)

    def test_get_returns_miss(self):
        key = str(uuid.uuid4())

        get_resp = self.client.get(_TEST_CACHE_NAME, key)
        self.assertEqual(get_resp.status(), CacheGetStatus.MISS)
        self.assertEqual(get_resp.value_as_bytes(), None)
        self.assertEqual(get_resp.value(), None)

    def test_expires_items_after_ttl(self):
        key = str(uuid.uuid4())
        val = str(uuid.uuid4())
        with simple_cache_client.init(_AUTH_TOKEN,
                                      2) as simple_cache:
            simple_cache.set(_TEST_CACHE_NAME, key, val)

            self.assertEqual(simple_cache.get(_TEST_CACHE_NAME, key).status(), CacheGetStatus.HIT)

            time.sleep(4)
            self.assertEqual(simple_cache.get(_TEST_CACHE_NAME, key).status(), CacheGetStatus.MISS)

    def test_set_with_different_ttl(self):
        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())

        self.client.set(_TEST_CACHE_NAME, key1, "1", 2)
        self.client.set(_TEST_CACHE_NAME, key2, "2")

        self.assertEqual(self.client.get(_TEST_CACHE_NAME, key1).status(), CacheGetStatus.HIT)
        self.assertEqual(self.client.get(_TEST_CACHE_NAME, key2).status(), CacheGetStatus.HIT)

        time.sleep(4)
        self.assertEqual(self.client.get(_TEST_CACHE_NAME, key1).status(), CacheGetStatus.MISS)
        self.assertEqual(self.client.get(_TEST_CACHE_NAME, key2).status(), CacheGetStatus.HIT)

    # set

    def test_set_with_non_existent_cache_name_throws_not_found(self):
        cache_name = str(uuid.uuid4())
        with self.assertRaises(errors.NotFoundError):
            self.client.set(cache_name, "foo", "bar")

    def test_set_with_null_cache_name_throws_exception(self):
        cache_name = str(uuid.uuid4())
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.set(None, "foo", "bar")
        self.assertEqual('{}'.format(cm.exception), "Cache name must be a non-empty string")

    def test_set_with_empty_cache_name_throws_exception(self):
        cache_name = str(uuid.uuid4())
        with self.assertRaises(errors.BadRequestError) as cm:
            self.client.set("", "foo", "bar")
        self.assertEqual('{}'.format(cm.exception), "Cache header is empty")

    def test_set_with_null_key_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError):
            self.client.set(_TEST_CACHE_NAME, None, "bar")

    def test_set_with_null_value_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError):
            self.client.set(_TEST_CACHE_NAME, "foo", None)

    def test_set_negative_ttl_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.set(_TEST_CACHE_NAME, "foo", "bar", -1)
        self.assertEqual('{}'.format(cm.exception), "TTL Seconds must be a non-negative integer")

    def test_set_with_bad_cache_name_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.set(1, "foo", "bar")
        self.assertEqual('{}'.format(cm.exception), "Cache name must be a non-empty string")

    def test_set_with_bad_key_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.set(_TEST_CACHE_NAME, 1, "bar")
        self.assertEqual('{}'.format(cm.exception), "Unsupported type for key: <class 'int'>")

    def test_set_with_bad_value_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.set(_TEST_CACHE_NAME, "foo", 1)
        self.assertEqual('{}'.format(cm.exception), "Unsupported type for value: <class 'int'>")

    def test_set_throws_authentication_exception_for_bad_token(self):
        with simple_cache_client.init(_BAD_AUTH_TOKEN,
                                      _DEFAULT_TTL_SECONDS) as simple_cache:
            with self.assertRaises(errors.AuthenticationError):
                simple_cache.set(_TEST_CACHE_NAME, "foo", "bar")

    def test_set_throws_timeout_error_for_short_request_timeout(self):
        with simple_cache_client.init(_AUTH_TOKEN, _DEFAULT_TTL_SECONDS, request_timeout_ms=1) as simple_cache:
            with self.assertRaises(errors.TimeoutError):
                simple_cache.set(_TEST_CACHE_NAME, "foo", "bar")


    # get

    def test_get_with_non_existent_cache_name_throws_not_found(self):
        cache_name = str(uuid.uuid4())
        with self.assertRaises(errors.NotFoundError):
            self.client.get(cache_name, "foo")

    def test_get_with_null_cache_name_throws_exception(self):
        cache_name = str(uuid.uuid4())
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.get(None, "foo")
        self.assertEqual('{}'.format(cm.exception), "Cache name must be a non-empty string")

    def test_get_with_empty_cache_name_throws_exception(self):
        cache_name = str(uuid.uuid4())
        with self.assertRaises(errors.BadRequestError) as cm:
            self.client.get("", "foo")
        self.assertEqual('{}'.format(cm.exception), "Cache header is empty")

    def test_get_with_null_key_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError):
            self.client.get(_TEST_CACHE_NAME, None)

    def test_get_with_bad_cache_name_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.get(1, "foo")
        self.assertEqual('{}'.format(cm.exception), "Cache name must be a non-empty string")

    def test_get_with_bad_key_throws_exception(self):
        with self.assertRaises(errors.InvalidArgumentError) as cm:
            self.client.get(_TEST_CACHE_NAME, 1)
        self.assertEqual('{}'.format(cm.exception), "Unsupported type for key: <class 'int'>")

    def test_get_throws_authentication_exception_for_bad_token(self):
        with simple_cache_client.init(_BAD_AUTH_TOKEN,
                                      _DEFAULT_TTL_SECONDS) as simple_cache:
            with self.assertRaises(errors.AuthenticationError):
                simple_cache.get(_TEST_CACHE_NAME, "foo")

    def test_get_throws_timeout_error_for_short_request_timeout(self):
        with simple_cache_client.init(_AUTH_TOKEN, _DEFAULT_TTL_SECONDS, request_timeout_ms=1) as simple_cache:
            with self.assertRaises(errors.TimeoutError):
                simple_cache.get(_TEST_CACHE_NAME, "foo")


if __name__ == '__main__':
    unittest.main()
