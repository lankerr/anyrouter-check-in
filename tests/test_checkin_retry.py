from types import SimpleNamespace

from checkin import execute_check_in, is_transient_checkin_error


class FakeResponse:
	def __init__(self, status_code, payload=None, text=''):
		self.status_code = status_code
		self._payload = payload
		self.text = text

	def json(self):
		return self._payload


class FakeClient:
	def __init__(self, responses):
		self.responses = iter(responses)
		self.calls = 0

	def post(self, *_args, **_kwargs):
		self.calls += 1
		return next(self.responses)


def provider():
	return SimpleNamespace(domain='https://anyrouter.top', sign_in_path='/api/user/checkin')


def test_mysql_write_lock_is_transient():
	message = 'Error 1290: The MySQL server is running with the LOCK_WRITE_GROWTH option'
	assert is_transient_checkin_error(message)


def test_transient_failure_retries_then_succeeds(monkeypatch):
	monkeypatch.setenv('CHECKIN_MAX_ATTEMPTS', '3')
	monkeypatch.setenv('CHECKIN_RETRY_DELAY_SECONDS', '1')
	monkeypatch.setattr('checkin.time.sleep', lambda _seconds: None)
	client = FakeClient(
		[
			FakeResponse(200, {'code': 1, 'message': 'LOCK_WRITE_GROWTH'}),
			FakeResponse(200, {'code': 0, 'message': 'ok'}),
		]
	)

	assert execute_check_in(client, 'test-account', provider(), {}) is True
	assert client.calls == 2


def test_auth_failure_does_not_retry(monkeypatch):
	monkeypatch.setenv('CHECKIN_MAX_ATTEMPTS', '3')
	client = FakeClient([FakeResponse(200, {'code': 1, 'message': 'Unauthorized'})])

	assert execute_check_in(client, 'test-account', provider(), {}) is False
	assert client.calls == 1
