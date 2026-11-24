import logging
import threading
import time

import requests

logger = logging.getLogger(__name__)

TOKEN_REFRESH_MARGIN_SECONDS = 60


class MpesaError(Exception):
    def __init__(self, message, status_code=502, error_code=None, response_description=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.response_description = response_description


class MpesaClient:
    def __init__(self, base_url, consumer_key, consumer_secret, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.timeout = timeout
        self._session = requests.Session()
        self._token = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    def get_access_token(self):
        with self._lock:
            if self._token and time.time() < self._token_expiry - TOKEN_REFRESH_MARGIN_SECONDS:
                return self._token
            try:
                response = self._session.get(
                    f"{self.base_url}/oauth/v1/generate",
                    params={"grant_type": "client_credentials"},
                    auth=(self.consumer_key, self.consumer_secret),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                self._token = data["access_token"]
                self._token_expiry = time.time() + int(data.get("expires_in", 3599))
            except (requests.RequestException, ValueError, KeyError) as exc:
                logger.error("Failed to generate MPESA access token: %s", exc)
                raise MpesaError("MPESA Authentication failed") from exc
            logger.info("MPESA Token generated successfully")
            return self._token

    def clear_access_token(self):
        with self._lock:
            self._token = None
            self._token_expiry = 0.0

    def generate_qr_code(self, payload, retry=True):
        token = self.get_access_token()
        try:
            response = self._session.post(
                f"{self.base_url}/mpesa/qrcode/v1/generate",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MpesaError(f"Could not reach MPESA: {exc}") from exc

        if response.status_code == 401 and retry:
            self.clear_access_token()
            return self.generate_qr_code(payload, retry=False)

        try:
            data = response.json()
        except ValueError:
            data = {}

        if not response.ok:
            raise MpesaError(
                data.get("errorMessage")
                or data.get("ResponseDescription")
                or f"MPESA request failed with status {response.status_code}",
                status_code=400 if response.status_code == 400 else 502,
                error_code=data.get("errorCode") or data.get("ResponseCode"),
                response_description=data.get("ResponseDescription"),
            )
        return data
