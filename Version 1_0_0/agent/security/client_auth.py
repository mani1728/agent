# Path: Version 1_0_0/agent/security/client_auth.py

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import platform
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows environments
    winreg = None

try:
    from confluent_kafka import Consumer, KafkaException, Producer
except ImportError:  # pragma: no cover
    Consumer = None
    KafkaException = Exception
    Producer = None

try:
    from agent.infrastructure.config_manager import cfg
except ImportError:  # pragma: no cover
    from infrastructure.config_manager import cfg


logger = logging.getLogger(__name__)


IDENTITY_CACHE_FILE = Path(__file__).resolve().parents[1] / "agent_identity.json"


class ClientAuthError(RuntimeError):
    """Base error for client authentication failures."""


class ClientRegistrationError(ClientAuthError):
    """Raised when client registration fails."""


class ClientAuthenticationError(ClientAuthError):
    """Raised when authenticated communication cannot be prepared."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nonce() -> str:
    return uuid.uuid4().hex


def _read_machine_guid_windows() -> Optional[str]:
    """
    Read the Windows MachineGuid when available.

    This value is used only as one input to a locally generated stable
    client-id suggestion. It is never logged.
    """
    if winreg is None:
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")

        value = str(value).strip()
        return value or None
    except (OSError, FileNotFoundError):
        return None


def _stable_suggested_client_id() -> str:
    """
    Generate a deterministic client-id suggestion from machine-local data.

    The raw machine identifiers are never returned or logged.
    """
    machine_guid = _read_machine_guid_windows() or ""
    hostname = platform.node() or ""
    mac = f"{uuid.getnode():012x}"

    source = "|".join(
        (
            machine_guid,
            hostname,
            mac,
        )
    )

    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()

    return f"client-{digest[:16]}"


def _load_cached_identity(
    path: Path = IDENTITY_CACHE_FILE,
) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        logger.warning("Unable to load cached client identity")
        return {}


def _save_cached_identity(
    identity: Mapping[str, Any],
    path: Path = IDENTITY_CACHE_FILE,
) -> None:
    """
    Persist non-secret identity information and authentication material.

    The file is local to the agent and should be protected by the host OS.
    Sensitive values are never logged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(
                dict(identity),
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)

    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

        raise


class ClientAuth:
    """
    Legacy-compatible client registration and authentication manager.

    Responsibilities currently preserved from the legacy implementation:

    - client identity discovery/cache
    - Kafka registration
    - authentication-token cache
    - authenticated outgoing headers
    - optional HMAC signing
    - client heartbeat/status publishing
    - token-expiry checks

    This class intentionally retains Kafka integration for compatibility.
    A later migration phase can split registration/authentication from the
    Kafka transport without changing the external behavior.
    """

    def __init__(self, config: Any = None) -> None:
        self.config = config or cfg()

        self._conf_snapshot: dict[str, Any] = {}

        self._refresh_conf()

        self.client_meta: dict[str, Any] = {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "pid": os.getpid(),
        }

        self.client_tmp_id = str(uuid.uuid4())

        cached = _load_cached_identity()

        configured_client_id = self._conf(
            "client_id",
            default=None,
        )

        self.client_id = (
            str(cached.get("client_id")).strip()
            if cached.get("client_id")
            else None
        )

        if not self.client_id:
            self.client_id = (
                str(configured_client_id).strip()
                if configured_client_id
                else None
            )

        if not self.client_id:
            self.client_id = _stable_suggested_client_id()

        self.auth_token: Optional[str] = cached.get("auth_token")

        self.token_expires_at: Optional[str] = cached.get(
            "token_expires_at"
        )

        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None

        self._producer = self._create_producer()
        self._register_consumer = self._create_register_consumer()

        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _conf(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        current = self._conf_snapshot

        if key in current:
            return current[key]

        value = self.config

        for part in key.split("."):
            if isinstance(value, Mapping):
                value = value.get(part, default)
            else:
                try:
                    value = value.get(part, default)
                except AttributeError:
                    return default

        return value

    def _refresh_conf(self) -> None:
        try:
            data = getattr(self.config, "_data", None)

            if isinstance(data, Mapping):
                self._conf_snapshot = dict(data)
                return

            if isinstance(self.config, Mapping):
                self._conf_snapshot = dict(self.config)
                return

        except Exception:
            logger.debug(
                "Unable to refresh ClientAuth configuration",
                exc_info=True,
            )

        self._conf_snapshot = {}

    def _read_conf(self) -> dict[str, Any]:
        self._refresh_conf()

        kafka = self._conf("kafka", default={}) or {}
        auth = self._conf("auth", default={}) or {}
        client_auth = self._conf("client_auth", default={}) or {}

        topics = kafka.get("topics", {}) or {}

        return {
            "bootstrap_servers": kafka.get(
                "bootstrap_servers",
                "",
            ),
            "register_topic": topics.get(
                "register",
                "clients.register",
            ),
            "register_response_topic": topics.get(
                "register_responses",
                "clients.register.responses",
            ),
            "status_topic": topics.get(
                "status",
                "clients.status",
            ),
            "initial_client_id": kafka.get(
                "client_id"
            ),
            "heartbeat_interval": client_auth.get(
                "heartbeat_interval",
                client_auth.get("heartbeat", 15),
            ),
            "register_timeout": client_auth.get(
                "register_timeout",
                30,
            ),
            "token_margin": client_auth.get(
                "token_margin",
                120,
            ),
            "hmac_algorithm": client_auth.get(
                "hmac_algorithm",
                "sha256",
            ),
            "hmac_secret": client_auth.get(
                "hmac_secret"
            ),
            "kid": client_auth.get(
                "kid"
            ),
            "group_prefix": client_auth.get(
                "consumer_group_prefix",
                client_auth.get(
                    "group_prefix",
                    "mt5-service",
                ),
            ),
            "auth_token_required": auth.get(
                "token_required",
                False,
            ),
            "auth_header": auth.get(
                "header",
                "auth_token",
            ),
        }

    # ------------------------------------------------------------------
    # Kafka initialization
    # ------------------------------------------------------------------

    def _create_producer(self) -> Any:
        if Producer is None:
            return None

        conf = self._read_conf()

        kafka = self._conf("kafka", default={}) or {}
        producer_conf = kafka.get("producer", {}) or {}

        result: dict[str, Any] = {
            "bootstrap.servers": conf["bootstrap_servers"],
            "enable.idempotence": True,
            "acks": "all",
        }

        for source_key, kafka_key in (
            ("retries", "retries"),
            ("linger_ms", "linger.ms"),
            ("request_timeout_ms", "request.timeout.ms"),
        ):
            if source_key in producer_conf:
                result[kafka_key] = producer_conf[source_key]

        try:
            return Producer(result)
        except Exception:
            logger.exception("Unable to create ClientAuth Kafka producer")
            return None

    def _create_register_consumer(self) -> Any:
        if Consumer is None:
            return None

        conf = self._read_conf()

        kafka = self._conf("kafka", default={}) or {}

        group_prefix = conf["group_prefix"] or "mt5-service"

        consumer_conf = {
            "bootstrap.servers": conf["bootstrap_servers"],
            "group.id": (
                f"{group_prefix}.registration.{self.client_tmp_id}"
            ),
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }

        for source_key, kafka_key in (
            ("security_protocol", "security.protocol"),
            ("sasl_mechanism", "sasl.mechanisms"),
            ("sasl_username", "sasl.username"),
            ("sasl_password", "sasl.password"),
            ("session_timeout_ms", "session.timeout.ms"),
        ):
            value = kafka.get(source_key)
            if value is not None:
                consumer_conf[kafka_key] = value

        try:
            return Consumer(consumer_conf)
        except Exception:
            logger.exception(
                "Unable to create ClientAuth registration consumer"
            )
            return None

    # ------------------------------------------------------------------
    # Logging compatibility
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_log(
        message: str,
        *args: Any,
    ) -> None:
        logger.warning(message, *args)

    # ------------------------------------------------------------------
    # HMAC
    # ------------------------------------------------------------------

    def _make_signature(
        self,
        headers: Mapping[str, Any],
        body: Any,
    ) -> Optional[str]:
        conf = self._read_conf()

        secret = conf.get("hmac_secret")

        if not secret:
            return None

        algorithm = str(
            conf.get("hmac_algorithm") or "sha256"
        ).lower()

        allowed = {
            "sha256": hashlib.sha256,
            "sha384": hashlib.sha384,
            "sha512": hashlib.sha512,
        }

        digest = allowed.get(algorithm)

        if digest is None:
            raise ClientAuthenticationError(
                f"Unsupported HMAC algorithm: {algorithm}"
            )

        ordered_names = (
            "corr_id",
            "client_id",
            "priority",
            "ts",
            "nonce",
        )

        header_values = [
            str(headers.get(name, ""))
            for name in ordered_names
        ]

        body_text = json.dumps(
            body,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        )

        canonical = (
            "|".join(header_values)
            + "|"
            + body_text
        )

        signature = hmac.new(
            str(secret).encode("utf-8"),
            canonical.encode("utf-8"),
            digest,
        ).hexdigest()

        return signature

    # ------------------------------------------------------------------
    # Token
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_expiry(value: Any) -> Optional[float]:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()

        if not text:
            return None

        try:
            return float(text)
        except ValueError:
            pass

        try:
            normalized = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.timestamp()

        except ValueError:
            return None

    def _token_is_valid(self) -> bool:
        if not self.auth_token:
            return False

        expiry = self._parse_expiry(
            self.token_expires_at
        )

        if expiry is None:
            return True

        margin = float(
            self._read_conf().get(
                "token_margin",
                120,
            )
            or 120
        )

        return time.time() < (expiry - margin)

    def _refresh_token_if_needed(self) -> None:
        """
        Preserve the legacy token-refresh hook.

        The legacy implementation did not implement a separate refresh
        protocol; it only reported when the token was approaching expiry.
        """
        if not self.auth_token:
            return

        expiry = self._parse_expiry(
            self.token_expires_at
        )

        if expiry is None:
            return

        margin = float(
            self._read_conf().get(
                "token_margin",
                120,
            )
            or 120
        )

        if time.time() >= expiry - margin:
            logger.warning(
                "Client authentication token is near expiry"
            )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self) -> bool:
        """
        Register the client with the server.

        Cached, still-valid authentication is reused to preserve the
        legacy startup behavior.
        """
        with self._lock:
            self._refresh_conf_if_needed()

            if self._token_is_valid():
                self._start_heartbeat()
                return True

            if self._producer is None:
                raise ClientRegistrationError(
                    "Kafka producer is not available"
                )

            if self._register_consumer is None:
                raise ClientRegistrationError(
                    "Kafka registration consumer is not available"
                )

            conf = self._read_conf()

            correlation_id = str(uuid.uuid4())

            body = {
                "schema": "ClientRegisterV1",
                "client_tmp_id": self.client_tmp_id,
                "client_id": self.client_id,
                "client_meta": dict(self.client_meta),
                "timestamp": _utcnow_iso(),
            }

            headers = {
                "schema": "ClientRegisterV1",
                "corr_id": correlation_id,
                "client_tmp_id": self.client_tmp_id,
                "content_type": "application/json",
            }

            register_topic = conf["register_topic"]
            response_topic = conf["register_response_topic"]

            try:
                self._register_consumer.subscribe(
                    [response_topic]
                )

                # Warm-up poll before publishing registration.
                self._register_consumer.poll(0)

                payload = json.dumps(
                    body,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")

                kafka_headers = [
                    (
                        str(key),
                        str(value).encode("utf-8"),
                    )
                    for key, value in headers.items()
                ]

                self._producer.produce(
                    topic=register_topic,
                    key=self.client_tmp_id,
                    value=payload,
                    headers=kafka_headers,
                )

                self._producer.flush(
                    timeout=float(
                        conf["register_timeout"]
                    )
                )

                deadline = (
                    time.monotonic()
                    + float(conf["register_timeout"])
                )

                while time.monotonic() < deadline:
                    remaining = max(
                        0.0,
                        deadline - time.monotonic(),
                    )

                    message = self._register_consumer.poll(
                        min(1.0, remaining)
                    )

                    if message is None:
                        continue

                    if message.error():
                        continue

                    response = self._parse_registration_response(
                        message
                    )

                    if not response:
                        continue

                    response_corr_id = (
                        response.get("corr_id")
                        or response.get("correlation_id")
                    )

                    response_tmp_id = (
                        response.get("client_tmp_id")
                    )

                    if (
                        response_corr_id
                        and response_corr_id != correlation_id
                    ):
                        continue

                    if (
                        response_tmp_id
                        and response_tmp_id != self.client_tmp_id
                    ):
                        continue

                    if response.get("status") in (
                        "error",
                        "failed",
                    ):
                        raise ClientRegistrationError(
                            "Client registration was rejected"
                        )

                    self._apply_registration_response(
                        response
                    )

                    self._start_heartbeat()

                    return True

            except ClientRegistrationError:
                raise
            except Exception as exc:
                raise ClientRegistrationError(
                    "Client registration failed"
                ) from exc
            finally:
                try:
                    self._register_consumer.unsubscribe()
                except Exception:
                    pass

            raise ClientRegistrationError(
                "Client registration timed out"
            )

    def _parse_registration_response(
        self,
        message: Any,
    ) -> Optional[dict[str, Any]]:
        try:
            raw = message.value()

            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            if isinstance(raw, str):
                data = json.loads(raw)
            elif isinstance(raw, Mapping):
                data = dict(raw)
            else:
                return None

            return data if isinstance(data, dict) else None

        except (UnicodeDecodeError, ValueError, TypeError):
            logger.warning(
                "Unable to parse client registration response"
            )
            return None

    def _apply_registration_response(
        self,
        response: Mapping[str, Any],
    ) -> None:
        client_id = (
            response.get("client_id")
            or response.get("assigned_client_id")
        )

        auth_token = (
            response.get("auth_token")
            or response.get("token")
        )

        expires_at = (
            response.get("expires_at")
            or response.get("token_expires_at")
            or response.get("expires")
        )

        if client_id:
            self.client_id = str(client_id)

        if auth_token:
            self.auth_token = str(auth_token)

        self.token_expires_at = (
            str(expires_at)
            if expires_at is not None
            else self.token_expires_at
        )

        if not self.auth_token:
            raise ClientRegistrationError(
                "Registration response did not contain an authentication token"
            )

        identity = {
            "client_id": self.client_id,
            "auth_token": self.auth_token,
            "token_expires_at": self.token_expires_at,
        }

        try:
            _save_cached_identity(identity)
        except OSError:
            logger.warning(
                "Unable to persist client identity cache"
            )

    def _refresh_conf_if_needed(self) -> None:
        self._refresh_conf()

    @property
    def inbox_topic(self) -> str:
        return f"cmd.{self.client_id}"

    # ------------------------------------------------------------------
    # Outgoing authenticated headers
    # ------------------------------------------------------------------

    def build_outgoing_headers(
        self,
        *,
        corr_id: Optional[str] = None,
        priority: Optional[int] = None,
        ordering_scope: Optional[str] = None,
        ttl_ms: Optional[int] = None,
        body: Any = None,
        extra_headers: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, bytes]:
        with self._lock:
            if not self.client_id:
                raise ClientAuthenticationError(
                    "Client ID is not available"
                )

            if not self.auth_token:
                raise ClientAuthenticationError(
                    "Authentication token is not available"
                )

            self._refresh_conf_if_needed()
            self._refresh_token_if_needed()

            if not self._token_is_valid():
                raise ClientAuthenticationError(
                    "Authentication token is expired or near expiry"
                )

            conf = self._read_conf()

            correlation_id = corr_id or str(uuid.uuid4())

            plain: dict[str, Any] = {
                "schema": "AuthenticatedMessageV1",
                "client_id": self.client_id,
                "corr_id": correlation_id,
                "ts": str(int(time.time())),
                "nonce": _nonce(),
            }

            if priority is not None:
                plain["priority"] = priority

            if ordering_scope is not None:
                plain["ordering_scope"] = ordering_scope

            if ttl_ms is not None:
                plain["ttl_ms"] = ttl_ms

            signature = self._make_signature(
                plain,
                body,
            )

            if signature:
                plain["sig"] = signature

            plain["auth_token"] = self.auth_token

            kid = conf.get("kid")
            if kid:
                plain["kid"] = str(kid)

            plain["sig_alg"] = str(
                conf.get(
                    "hmac_algorithm",
                    "sha256",
                )
            )

            result: dict[str, bytes] = {
                key: str(value).encode("utf-8")
                for key, value in plain.items()
            }

            result["content_type"] = (
                b"application/json"
            )

            if extra_headers:
                for key, value in extra_headers.items():
                    if value is None:
                        continue

                    result[str(key)] = str(value).encode(
                        "utf-8"
                    )

            return result

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _start_heartbeat(self) -> None:
        with self._lock:
            if (
                self._heartbeat_thread is not None
                and self._heartbeat_thread.is_alive()
            ):
                return

            self._heartbeat_stop.clear()

            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name="client-auth-heartbeat",
                daemon=True,
            )

            self._heartbeat_thread.start()

    def stop(self) -> None:
        self._heartbeat_stop.set()

        thread = self._heartbeat_thread

        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)

        self._heartbeat_thread = None

        if self._register_consumer is not None:
            try:
                self._register_consumer.close()
            except Exception:
                logger.debug(
                    "Unable to close registration consumer",
                    exc_info=True,
                )

        if self._producer is not None:
            try:
                self._producer.flush(timeout=5.0)
            except Exception:
                logger.debug(
                    "Unable to flush ClientAuth producer",
                    exc_info=True,
                )

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.is_set():
            try:
                self._refresh_conf_if_needed()

                conf = self._read_conf()

                status = {
                    "schema": "ClientStatusV1",
                    "client_id": self.client_id,
                    "status": "ready",
                    "timestamp": _utcnow_iso(),
                    "hostname": self.client_meta.get(
                        "hostname"
                    ),
                }

                if self.auth_token:
                    status_headers = self.build_outgoing_headers(
                        corr_id=str(uuid.uuid4()),
                        body=status,
                        extra_headers={
                            "schema": "ClientStatusV1",
                        },
                    )
                else:
                    status_headers = {
                        "schema": b"ClientStatusV1",
                    }

                if self._producer is not None:
                    payload = json.dumps(
                        status,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")

                    kafka_headers = [
                        (key, value)
                        for key, value in status_headers.items()
                    ]

                    self._producer.produce(
                        topic=conf["status_topic"],
                        key=self.client_id,
                        value=payload,
                        headers=kafka_headers,
                    )

                    self._producer.flush(timeout=5.0)

            except Exception:
                logger.exception(
                    "Client heartbeat failed"
                )

            interval = float(
                self._read_conf().get(
                    "heartbeat_interval",
                    15,
                )
                or 15
            )

            self._heartbeat_stop.wait(
                max(1.0, interval)
            )


__all__ = [
    "ClientAuth",
    "ClientAuthError",
    "ClientAuthenticationError",
    "ClientRegistrationError",
]