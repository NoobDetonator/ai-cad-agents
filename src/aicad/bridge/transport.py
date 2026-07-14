from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import hmac
import ipaddress
import json
import math
import secrets
import socket
import socketserver
import struct
from threading import Thread
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError

from aicad.bridge.protocol import (
    BridgeError,
    BridgeErrorCode,
    BridgeProtocolError,
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
    BridgeTransportRequest,
)


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_MESSAGE_BYTES = 1024 * 1024
_FRAME_HEADER = struct.Struct("!I")


class BridgeTransportError(ConnectionError):
    """Raised when a local bridge connection or frame is invalid."""


def create_session_token() -> str:
    """Create a high-entropy credential that is safe to use for one GUI session."""

    return secrets.token_urlsafe(32)


def _validate_loopback_host(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("The bridge host must be an IP loopback address.") from exc
    if not address.is_loopback or address.version != 4:
        raise ValueError("The bridge host must be an IPv4 loopback address.")


def _validate_session_token(session_token: str) -> None:
    if not isinstance(session_token, str) or len(session_token) < 32:
        raise ValueError("The bridge session token must contain at least 32 characters.")


def _validate_transport_limits(timeout: float, max_message_bytes: int) -> None:
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout <= 0
    ):
        raise ValueError("The bridge timeout must be positive and finite.")
    if isinstance(max_message_bytes, bool) or not isinstance(max_message_bytes, int):
        raise ValueError("The bridge message limit must be an integer.")
    if max_message_bytes < 256:
        raise ValueError("The bridge message limit must be at least 256 bytes.")
    if max_message_bytes > 16 * 1024 * 1024:
        raise ValueError("The bridge message limit cannot exceed 16 MiB.")


@dataclass(frozen=True, slots=True)
class BridgeEndpoint:
    host: str
    port: int
    session_token: str = field(repr=False)

    def __post_init__(self) -> None:
        _validate_loopback_host(self.host)
        if (
            isinstance(self.port, bool)
            or not isinstance(self.port, int)
            or not 1 <= self.port <= 65535
        ):
            raise ValueError("The bridge port must be between 1 and 65535.")
        _validate_session_token(self.session_token)


def _receive_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise BridgeTransportError("The bridge connection closed mid-frame.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _reject_non_finite_json(value: str) -> None:
    raise ValueError(f"Non-finite JSON value is not allowed: {value}")


def _receive_json_object(
    connection: socket.socket,
    max_message_bytes: int,
) -> dict[str, Any]:
    header = _receive_exact(connection, _FRAME_HEADER.size)
    (message_size,) = _FRAME_HEADER.unpack(header)
    if message_size == 0 or message_size > max_message_bytes:
        raise BridgeTransportError("The bridge frame size is invalid.")
    encoded = _receive_exact(connection, message_size)
    try:
        payload = json.loads(
            encoded.decode("utf-8"),
            parse_constant=_reject_non_finite_json,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise BridgeTransportError("The bridge frame is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise BridgeTransportError("The bridge frame must contain a JSON object.")
    return payload


def _send_json_object(
    connection: socket.socket,
    payload: Mapping[str, Any],
    max_message_bytes: int,
) -> None:
    try:
        encoded = json.dumps(
            dict(payload),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BridgeTransportError(
            "The bridge response is not JSON serializable."
        ) from exc
    if not encoded or len(encoded) > max_message_bytes:
        raise BridgeTransportError("The bridge frame size is invalid.")
    connection.sendall(_FRAME_HEADER.pack(len(encoded)) + encoded)


@dataclass(frozen=True, slots=True)
class TcpBridgeClient:
    endpoint: BridgeEndpoint
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES

    def __post_init__(self) -> None:
        _validate_transport_limits(self.timeout, self.max_message_bytes)

    def request(self, request: BridgeTransportRequest) -> BridgeResponse:
        envelope = {
            "authorization": self.endpoint.session_token,
            "request": request.model_dump(mode="json"),
        }
        try:
            with socket.create_connection(
                (self.endpoint.host, self.endpoint.port),
                timeout=self.timeout,
            ) as connection:
                connection.settimeout(self.timeout)
                _send_json_object(connection, envelope, self.max_message_bytes)
                payload = _receive_json_object(connection, self.max_message_bytes)
        except BridgeTransportError:
            raise
        except (OSError, TimeoutError) as exc:
            raise BridgeTransportError(
                "The local bridge connection failed or timed out."
            ) from exc

        try:
            response = BridgeResponse.model_validate(payload)
        except ValidationError as exc:
            raise BridgeTransportError(
                "The local bridge returned an invalid response."
            ) from exc
        if response.request_id != request.request_id:
            raise BridgeTransportError("The bridge response request ID does not match.")
        return response


RequestHandler = Callable[[Mapping[str, Any]], BridgeResponse]


class _ThreadingTcpServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    owner: LocalTcpBridgeServer


class _BridgeSocketHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = cast(_ThreadingTcpServer, self.server)
        server.owner._handle_connection(cast(socket.socket, self.request))


class LocalTcpBridgeServer:
    """Authenticated local transport that never executes CAD work itself."""

    def __init__(
        self,
        request_handler: RequestHandler,
        *,
        host: str = LOOPBACK_HOST,
        port: int = 0,
        session_token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
    ) -> None:
        _validate_loopback_host(host)
        if (
            isinstance(port, bool)
            or not isinstance(port, int)
            or not 0 <= port <= 65535
        ):
            raise ValueError("The bridge port must be between 0 and 65535.")
        token = session_token if session_token is not None else create_session_token()
        _validate_session_token(token)
        _validate_transport_limits(timeout, max_message_bytes)

        self._request_handler = request_handler
        self._host = host
        self._port = port
        self._session_token = token
        self._timeout = timeout
        self._max_message_bytes = max_message_bytes
        self._server: _ThreadingTcpServer | None = None
        self._thread: Thread | None = None

    @property
    def is_running(self) -> bool:
        return (
            self._server is not None
            and self._thread is not None
            and self._thread.is_alive()
        )

    @property
    def endpoint(self) -> BridgeEndpoint:
        if self._server is None:
            raise RuntimeError("The local bridge server has not been started.")
        host, port = self._server.server_address
        return BridgeEndpoint(str(host), int(port), self._session_token)

    def start(self) -> BridgeEndpoint:
        if self._server is not None:
            raise RuntimeError("The local bridge server is already running.")
        server = _ThreadingTcpServer((self._host, self._port), _BridgeSocketHandler)
        server.owner = self
        thread = Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.05},
            name="aicad-local-bridge",
            daemon=True,
        )
        self._server = server
        self._thread = thread
        thread.start()
        return self.endpoint

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=self._timeout)
            if thread.is_alive():
                raise RuntimeError("The local bridge server did not stop cleanly.")
        self._server = None
        self._thread = None

    def __enter__(self) -> LocalTcpBridgeServer:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _handle_connection(self, connection: socket.socket) -> None:
        connection.settimeout(self._timeout)
        try:
            envelope = _receive_json_object(connection, self._max_message_bytes)
            request_payload = envelope.get("request")
            if not isinstance(request_payload, dict):
                raise BridgeTransportError("The bridge request payload is missing.")
            request_id = UUID(str(request_payload.get("request_id")))

            authorization = envelope.get("authorization")
            if not isinstance(authorization, str) or not hmac.compare_digest(
                authorization,
                self._session_token,
            ):
                response = BridgeResponse(
                    request_id=request_id,
                    status=BridgeResponseStatus.REJECTED,
                    error=BridgeError(
                        code=BridgeErrorCode.UNAUTHORIZED,
                        message="The bridge session token is invalid.",
                    ),
                )
            else:
                response = self._dispatch(request_id, request_payload)
            _send_json_object(
                connection,
                response.model_dump(mode="json"),
                self._max_message_bytes,
            )
        except (BridgeTransportError, OSError, TimeoutError, ValueError):
            return

    def _dispatch(
        self,
        request_id: UUID,
        request_payload: Mapping[str, Any],
    ) -> BridgeResponse:
        try:
            response = self._request_handler(request_payload)
            if response.request_id != request_id:
                raise ValueError("The handler returned a mismatched request ID.")
            return response
        except BridgeProtocolError as exc:
            return BridgeResponse(
                request_id=request_id,
                status=BridgeResponseStatus.REJECTED,
                error=exc.error,
            )
        except Exception:
            return BridgeResponse(
                request_id=request_id,
                status=BridgeResponseStatus.FAILED,
                error=BridgeError(
                    code=BridgeErrorCode.EXECUTION_ERROR,
                    message="The bridge request failed.",
                ),
            )
