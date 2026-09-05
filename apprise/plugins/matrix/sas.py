# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Handles opt-in SAS verification from another device for the same Matrix user.
# A completed exchange is remembered for the current identity.
# Cryptography lives in MatrixSASVerification; this module manages the events
# and stored trust state.
#
# Protocol reference:
# https://spec.matrix.org/v1.19/client-server-api/#key-verification-framework

from json import dumps
import math
from time import monotonic, time
import uuid

from .e2ee import MatrixSASVerification, verify_device_keys

# To-device event types exchanged during a SAS verification.
EVENT_REQUEST = "m.key.verification.request"
EVENT_READY = "m.key.verification.ready"
EVENT_START = "m.key.verification.start"
EVENT_ACCEPT = "m.key.verification.accept"
EVENT_CANCEL = "m.key.verification.cancel"
EVENT_KEY = "m.key.verification.key"
EVENT_MAC = "m.key.verification.mac"
EVENT_DONE = "m.key.verification.done"

# Keep the supported method aligned with the SAS responder.
SAS_METHOD = MatrixSASVerification.METHOD

# Ignore requests outside these age limits as stale or replayed.
REQUEST_MAX_PAST_MS = 10 * 60 * 1000
REQUEST_MAX_FUTURE_MS = 5 * 60 * 1000

# Bound identifiers before echoing, comparing, or hashing them.
MAX_ID_LEN = 512

# Bound the small key maps normally advertised by Matrix devices.
MAX_DEVICE_KEYS = 8

# SAS protocol responses should remain comfortably below this limit.
MAX_RESPONSE_BYTES = 1024 * 1024


def _valid_id(value):
    """Return whether a Matrix ID is a non-empty string within our limit."""
    return isinstance(value, str) and 0 < len(value) <= MAX_ID_LEN


# Matrix always includes to-device events, so exclude everything else.
# An empty room list avoids unnecessary nested filters and invalid limits.
SYNC_FILTER = dumps(
    {
        "presence": {"types": []},
        "account_data": {"types": []},
        "room": {"rooms": []},
    }
)

# Use this fallback when the configured read timeout is invalid.
FALLBACK_SYNC_POLL_MS = 2000

# Avoid near-instant polling when the configured timeout is very small.
MIN_SYNC_POLL_MS = 250


def _sync_poll_ms(plugin):
    """Return a safe polling interval based on the configured read timeout."""
    poll_ms = plugin.socket_read_timeout * 1000 / 2
    if not math.isfinite(poll_ms) or poll_ms <= 0:
        return FALLBACK_SYNC_POLL_MS

    return max(MIN_SYNC_POLL_MS, int(poll_ms))


def store_verified_binding(plugin):
    """Remember that the current custom E2EE identity completed SAS."""
    # Trust applies to the exact device and account recorded during setup.
    binding = plugin.store.get("e2ee_device_binding")
    if not binding:
        # Never create a trust marker without an identity to bind it to.
        return False

    # Use the normal cache lifetime so related identity records expire
    # together.
    return plugin.store.set(
        "e2ee_verified_binding",
        binding,
        expires=plugin.default_cache_expiry_sec,
    )


def refresh_verified_state(plugin):
    """Refresh the identity state needed to retain SAS trust.

    A changed device or E2EE account requires verification again. Other
    cached Matrix state is left untouched.
    """
    # Do not delay delivery while another verification holds the lock.
    if not plugin._autoverify_lock.acquire(blocking=False):
        return False
    try:
        # Load the identity that was originally verified.
        binding = plugin.store.get("e2ee_device_binding")
        if (
            not binding
            or plugin.store.get("e2ee_verified_binding") != binding
            or not plugin.user_id
            or not plugin.device_id
            or not plugin._e2ee_account
        ):
            # Missing or mismatched state requires verification again.
            return False

        # Confirm that the live account still matches the stored identity.
        if binding != plugin._e2ee_binding_key():
            return False

        # Limit identity writes and treat an invalid timestamp as missing.
        last_refreshed = plugin.store.get("e2ee_autoverify_refreshed_at", 0)
        if not isinstance(last_refreshed, (int, float)) or not math.isfinite(
            last_refreshed
        ):
            # Non-finite timestamps could suppress refreshes until expiration.
            last_refreshed = 0
        if (
            time() - last_refreshed
            < plugin.default_autoverify_refresh_interval_sec
        ):
            return True

        # Refresh identity records in order and stop after the first failure.
        if not plugin.store.set(
            "device_id",
            plugin.device_id,
            expires=plugin.default_cache_expiry_sec,
        ):
            return False

        if not plugin.store.set(
            "e2ee_account",
            plugin._e2ee_account.to_dict(),
            expires=plugin.default_cache_expiry_sec,
        ):
            return False

        if not plugin.store.set(
            "e2ee_device_binding",
            binding,
            expires=plugin.default_cache_expiry_sec,
        ):
            return False

        # Write the trust marker last. A partial refresh must fail closed
        # instead of extending trust without its complete bound identity.
        if not plugin.store.set(
            "e2ee_verified_binding",
            binding,
            expires=plugin.default_cache_expiry_sec,
        ):
            return False

        # A bookkeeping failure only causes another refresh sooner than
        # planned.
        plugin.store.set(
            "e2ee_autoverify_refreshed_at",
            time(),
            expires=plugin.default_cache_expiry_sec,
        )
        return True
    finally:
        plugin._autoverify_lock.release()


def auto_verify(plugin):
    """Automatically complete one same-user SAS verification for *plugin*.

    This is the entry point for the opt-in ``autoverify=yes`` bootstrap.
    """
    # Let one caller verify while concurrent callers continue delivery.
    if not plugin._autoverify_lock.acquire(blocking=False):
        return False

    try:
        # Reuse trust only when it belongs to the current stored identity.
        binding = plugin.store.get("e2ee_device_binding")
        if binding and plugin.store.get("e2ee_verified_binding") == binding:
            # Already verified for the current identity; nothing to do.
            return True

        if (
            not plugin.user_id
            or not plugin.device_id
            or not plugin._e2ee_account
        ):
            # Login and E2EE setup must finish before verification
            # can begin.
            return False

        # Delay retries only for the identity that just failed.
        if plugin.store.get("e2ee_autoverify_cooldown") == binding:
            return False

        # A fresh verifier owns all state for this single attempt.
        result = MatrixSASAutoVerifier(plugin).run()
        if not result:
            plugin.store.set(
                "e2ee_autoverify_cooldown",
                binding,
                expires=plugin.default_autoverify_retry_cooldown_sec,
            )

        return result
    finally:
        plugin._autoverify_lock.release()


class MatrixSASAutoVerifier:
    """Complete one same-user SAS verification.

    Each instance handles one transaction and is discarded afterward.
    """

    def __init__(self, plugin):
        """Bind this verifier to the owning NotifyMatrix instance."""
        self.plugin = plugin

        # No transaction exists until a valid request is accepted.
        self.active = None

        # Share one reliable deadline across every request in this attempt.
        self.deadline = monotonic() + plugin.default_autoverify_timeout_sec

    def _bounded_fetch(
        self, path, bound_sec=None, best_effort=False, **kwargs
    ):
        """Fetch within this verification attempt's remaining time.

        ``bound_sec`` can shorten a call. ``best_effort`` allows the final
        cancellation request after the deadline.
        """
        # Clamp to the configured budget and the remaining time in this
        # verification attempt.
        remaining = min(
            self.plugin.default_autoverify_timeout_sec,
            max(0.0, self.deadline - monotonic()),
        )
        if remaining <= 0 and not best_effort:
            # Do not start another request after the deadline.
            return (False, {}, None)
        if bound_sec is None:
            bound_sec = _sync_poll_ms(self.plugin) / 1000
        # Allow two seconds for network activity around the server wait.
        fetch_timeout = min(bound_sec, remaining) + 2
        kwargs.setdefault("timeout", (fetch_timeout, fetch_timeout))
        kwargs.setdefault("max_retry_wait", remaining)
        kwargs.setdefault("max_response_bytes", MAX_RESPONSE_BYTES)
        return self.plugin._fetch(path, **kwargs)

    def run(self):
        """Poll ``/sync`` until a SAS verification completes or expires."""
        self.plugin.logger.info(
            "Matrix E2EE: waiting up to %d seconds for a same-user "
            "SAS verification request.",
            self.plugin.default_autoverify_timeout_sec,
        )

        # Keep each poll below the configured socket read timeout.
        max_poll_ms = _sync_poll_ms(self.plugin)

        # The sync token prevents older events from being returned
        # repeatedly.
        since = None

        while monotonic() < self.deadline:
            # Cap the requested long poll by the time left in this attempt.
            remaining_ms = max(0, int((self.deadline - monotonic()) * 1000))
            poll_ms = min(max_poll_ms, remaining_ms)
            params = {
                "timeout": poll_ms,
                # Only to-device events are needed for verification.
                "filter": SYNC_FILTER,
                # Verification polling should not make the account look online.
                "set_presence": "offline",
            }
            if since:
                params["since"] = since

            # Verification events arrive through the normal Matrix sync feed.
            ok, response, _ = self._bounded_fetch(
                "/sync",
                bound_sec=poll_ms / 1000,
                params=params,
                method="GET",
            )
            if not ok or not isinstance(response, dict):
                # A failed sync ends this attempt without changing trust.
                return False

            # A missing sync token cannot be resumed safely and may cause a
            # tight loop of immediate responses.
            next_batch = response.get("next_batch")
            if not isinstance(next_batch, str) or not next_batch:
                return False
            since = next_batch

            # Treat malformed event containers as empty.
            to_device = response.get("to_device")
            events = (
                to_device.get("events")
                if isinstance(to_device, dict)
                else None
            )
            for event in events if isinstance(events, list) else []:
                try:
                    # A handler returns None while the transaction is
                    # still active.
                    result = self._handle_event(event)
                except (AttributeError, KeyError, TypeError, ValueError):
                    # Skip malformed events without interrupting delivery.
                    continue
                if result is not None:
                    return result
                if monotonic() >= self.deadline:
                    # Stop processing an oversized batch at the deadline.
                    break

        # Tell the peer when this verification attempt expires.
        return self._fail("m.timeout", "SAS verification timed out")

    def _handle_event(self, event):
        """Dispatch one ``/sync`` to-device event.

        Returns ``True``/``False`` when verification has reached a final
        outcome, or ``None`` to keep polling.
        """
        if not isinstance(event, dict):
            # Matrix events must be JSON objects.
            return None

        # Pull out the common fields before routing by event type.
        event_type = event.get("type")
        sender = event.get("sender")
        content = event.get("content", {})
        if sender != self.plugin.user_id or not isinstance(content, dict):
            # Auto-verification is intentionally same-user only.
            return None

        if event_type == EVENT_REQUEST:
            # A request may create the one active transaction.
            return self._handle_request(sender, content)

        # Remaining events must belong to the active transaction.
        transaction_id = content.get("transaction_id")
        if not self.active or transaction_id != self.active["transaction_id"]:
            # Ignore late events and events for other verification attempts.
            return None
        if sender != self.active["user_id"]:
            # Only the device owner that opened the transaction may
            # continue it.
            return None

        if event_type == EVENT_CANCEL:
            return self._handle_cancel(content)

        if event_type == EVENT_START:
            return self._handle_start(sender, content)

        sas = self.active.get("sas")
        if sas is None:
            # Key, MAC, and done events are invalid until SAS has started.
            return self._fail(
                "m.unexpected_message", "SAS verification has not started"
            )

        if event_type == EVENT_KEY:
            return self._handle_key(sas, sender, content)

        if event_type == EVENT_MAC:
            return self._handle_mac(sas, content)

        if event_type == EVENT_DONE:
            return self._handle_done(sas)

        # Ignore unrelated event types.
        return None

    def _handle_request(self, sender, content):
        """Handle ``m.key.verification.request``."""
        # Read the fields required to identify a fresh request.
        timestamp = content.get("timestamp")
        now_ms = int(time() * 1000)
        transaction_id = content.get("transaction_id")
        from_device = content.get("from_device")
        methods = content.get("methods")

        if (
            not isinstance(timestamp, int)
            or timestamp < now_ms - REQUEST_MAX_PAST_MS
            or timestamp > now_ms + REQUEST_MAX_FUTURE_MS
            or not _valid_id(transaction_id)
            or not _valid_id(from_device)
            or not isinstance(methods, list)
            or SAS_METHOD not in methods
        ):
            # Malformed or stale request; ignore and keep waiting.
            return None

        if self.active:
            same_device = (
                sender == self.active["user_id"]
                and from_device == self.active["device_id"]
            )
            if same_device and transaction_id == self.active["transaction_id"]:
                # Ignore an exact replay without cancelling our transaction.
                return None

            if same_device:
                # Matrix requires both attempts from the device to be ended.
                self._cancel(
                    "m.unexpected_message",
                    "A newer verification request superseded this one",
                )
                self.active = None

            # Reject the new request without disturbing another device.
            self._send_event(
                EVENT_CANCEL,
                sender,
                from_device,
                {
                    "transaction_id": transaction_id,
                    "code": "m.unexpected_message",
                    "reason": "Another verification is already active",
                },
            )
            return None

        peer_keys = self._peer_keys(sender, from_device)
        if not peer_keys:
            # Verification cannot continue without a valid peer device key.
            return False

        # Keep all details needed by the remaining events in one record.
        self.active = {
            "transaction_id": transaction_id,
            "user_id": sender,
            "device_id": from_device,
            "peer_keys": peer_keys,
            "sas": None,
            "peer_done": False,
        }

        # Tell the requesting device that this responder supports SAS.
        if not self._send_event(
            EVENT_READY,
            sender,
            from_device,
            {
                "transaction_id": transaction_id,
                "from_device": self.plugin.device_id,
                "methods": [SAS_METHOD],
            },
        ):
            return False

        return None

    def _handle_cancel(self, content):
        """Handle ``m.key.verification.cancel`` from the peer."""
        # Preserve the peer's reason to make failed attempts diagnosable.
        self.plugin.logger.warning(
            "Matrix E2EE SAS verification was cancelled: %s",
            content.get("reason") or "unspecified reason",
        )
        return False

    def _handle_start(self, sender, content):
        """Handle ``m.key.verification.start``."""
        if self.active.get("sas") is not None:
            # Reject a restart after committing to this transaction's key.
            return self._fail(
                "m.unexpected_message",
                "SAS verification was already started",
            )

        try:
            # Validate the proposal and prepare the matching acceptance event.
            sas = MatrixSASVerification(
                self.plugin.user_id,
                self.plugin.device_id,
                sender,
                self.active["device_id"],
                content,
            )
            accept = sas.accept_content()

        except (TypeError, ValueError):
            # Unsupported or malformed proposals end the transaction cleanly.
            return self._fail(
                "m.unknown_method", "Unsupported SAS verification parameters"
            )

        # Retain the state machine for the key and MAC events that follow.
        self.active["sas"] = sas
        if not self._send_event(
            EVENT_ACCEPT,
            sender,
            self.active["device_id"],
            accept,
        ):
            return False

        return None

    def _handle_key(self, sas, sender, content):
        """Handle ``m.key.verification.key``."""
        try:
            # Establish the shared secret and build this device's proof.
            sas.receive_key(content.get("key") or "")
            sas_code = sas.decimal_sas()
            key_content = sas.key_content()
            mac_content = sas.mac_content(
                self.plugin._e2ee_account.signing_key
            )

        except (TypeError, ValueError):
            # Reject public keys that cannot form a valid exchange.
            return self._fail("m.invalid_message", "Invalid SAS public key")

        # Apprise responds automatically, so confirm its logged code on the
        # other device before approving the verification there.
        self.plugin.logger.info(
            "Matrix E2EE SAS code (compare against your other device): "
            "%d-%d-%d",
            *sas_code,
        )

        # Both the public key and its MAC must reach the same peer device.
        device_id = self.active["device_id"]
        if not self._send_event(
            EVENT_KEY, sender, device_id, key_content
        ) or not self._send_event(EVENT_MAC, sender, device_id, mac_content):
            return False

        return None

    def _handle_mac(self, sas, content):
        """Handle ``m.key.verification.mac``."""
        try:
            # Confirm that the peer possesses the advertised device keys.
            sas.verify_peer_mac(content, self.active["peer_keys"])

        except (TypeError, ValueError):
            # Treat malformed and mismatched proofs as verification failures.
            return self._fail(
                "m.key_mismatch", "SAS device key MAC did not match"
            )

        # Our side is complete once the peer's proof is valid.
        if not self._send_event(
            EVENT_DONE,
            self.active["user_id"],
            self.active["device_id"],
            {"transaction_id": self.active["transaction_id"]},
        ):
            return False

        if self.active["peer_done"]:
            # Both devices are finished, so this identity may retain trust.
            # Verification succeeds only if its trust marker is saved.
            return store_verified_binding(self.plugin)

        return None

    def _handle_done(self, sas):
        """Handle ``m.key.verification.done``."""
        # The peer may finish before or after its MAC reaches us.
        self.active["peer_done"] = True
        if sas.state == "verified":
            # Save trust only after verifying the peer's MAC.
            return store_verified_binding(self.plugin)

        return None

    def _send_event(
        self, event_type, user_id, device_id, content, best_effort=False
    ):
        """Send one unencrypted SAS event to a specific Matrix device."""
        # A unique transaction path prevents repeated PUTs from colliding.
        path = "/sendToDevice/{}/{}".format(event_type, uuid.uuid4().hex)
        ok, _, _ = self._bounded_fetch(
            path,
            payload={"messages": {user_id: {device_id: content}}},
            method="PUT",
            best_effort=best_effort,
        )
        return ok

    def _cancel(self, code, reason):
        """Cancel the active SAS transaction on the peer device."""
        if not self.active:
            # There is no peer transaction to cancel yet.
            return False

        # Send the matching cancellation even when the deadline just passed.
        return self._send_event(
            EVENT_CANCEL,
            self.active["user_id"],
            self.active["device_id"],
            {
                "transaction_id": self.active["transaction_id"],
                "code": code,
                "reason": reason,
            },
            best_effort=True,
        )

    def _fail(self, code, reason):
        """Cancel the active transaction (if any) and report failure."""
        # Cancellation is best-effort; the local result remains a failure.
        self._cancel(code, reason)
        return False

    def _peer_keys(self, user_id, device_id):
        """Return validated device and advertised cross-signing keys."""
        # Ask only for the device involved in this verification.
        ok, response, _ = self._bounded_fetch(
            "/keys/query",
            payload={"device_keys": {user_id: [device_id]}},
        )
        if not ok or not isinstance(response, dict):
            # Missing keys leave no identity for the SAS proof to confirm.
            return None

        # Validate each server field before using the self-signed device key.
        device_keys = response.get("device_keys")
        user_devices = (
            device_keys.get(user_id) if isinstance(device_keys, dict) else None
        )
        device = (
            user_devices.get(device_id)
            if isinstance(user_devices, dict)
            else None
        )
        if not isinstance(device, dict) or not verify_device_keys(
            device, user_id, device_id
        ):
            return None

        # Device keys are mandatory; advertised master keys are optional.
        raw_keys = device.get("keys")
        keys = (
            dict(raw_keys)
            if isinstance(raw_keys, dict) and len(raw_keys) <= MAX_DEVICE_KEYS
            else {}
        )

        master_keys = response.get("master_keys")
        master_key = (
            master_keys.get(user_id) if isinstance(master_keys, dict) else None
        )
        if isinstance(master_key, dict):
            raw_master_keys = master_key.get("keys")
            if (
                isinstance(raw_master_keys, dict)
                and len(raw_master_keys) <= MAX_DEVICE_KEYS
            ):
                keys.update(raw_master_keys)

        return keys
