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

# Disable logging for a cleaner testing output
from datetime import datetime, timedelta, timezone
import logging
from unittest import mock
from urllib.parse import urlparse

import requests

from apprise.utils.wkd import AppriseWKDController, AppriseWKDException

logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# AppriseWKDException
# ---------------------------------------------------------------------------


def test_wkd_exception_default_error_code():
    """AppriseWKDException uses error_code 610 by default."""
    exc = AppriseWKDException("something went wrong")
    assert exc.error_code == 610


# ---------------------------------------------------------------------------
# zb32_encode
# ---------------------------------------------------------------------------


def test_zb32_encode_all_zeros():
    """20 zero bytes encode to 32 'y' characters (index 0 of the alphabet)."""
    result = AppriseWKDController.zb32_encode(b"\x00" * 20)
    assert result == "y" * 32


def test_zb32_encode_all_ones():
    """20 0xFF bytes encode to 32 '9' characters (index 31 of the alphabet)."""
    result = AppriseWKDController.zb32_encode(b"\xff" * 20)
    assert result == "9" * 32


def test_zb32_encode_sha1_length():
    """SHA-1 digest (20 bytes) always produces exactly 32 z-base32 chars."""
    import hashlib

    digest = hashlib.sha1(b"test@example.com").digest()
    result = AppriseWKDController.zb32_encode(digest)
    assert len(result) == 32
    # All characters must belong to the z-base32 alphabet
    assert all(c in AppriseWKDController._ZB32 for c in result)


def test_zb32_encode_empty():
    """Empty input produces an empty string."""
    assert AppriseWKDController.zb32_encode(b"") == ""


def test_zb32_encode_single_byte():
    """Single byte (5 bits + 3 leftover bits) produces 2 characters."""
    # 0x00 = 00000 000  -> 'y' then 0x00 << 2 = 00000 -> 'y'
    result = AppriseWKDController.zb32_encode(b"\x00")
    assert len(result) == 2
    assert result[0] == "y"


def test_zb32_encode_known_vector():
    """Verify z-base32 encoding against independently computed single-byte
    reference values.

    These expected strings are derived from first principles: each 5-bit
    group maps directly to _ZB32[value], and leftover bits are
    left-aligned.  They do NOT call zb32_encode() to generate the
    expected string, so a regression in the alphabet or bit-shifting
    logic will cause at least one assertion to fail.

    0xf8 = 11111000:
      group1 (bits 0-4): 11111 = 31 -> '9'
      leftover (bits 5-7) << 2: 00000 = 0 -> 'y'
    0xa8 = 10101000:
      group1 (bits 0-4): 10101 = 21 -> 'i'
      leftover (bits 5-7) << 2: 00000 = 0 -> 'y'
    0x08 = 00001000:
      group1 (bits 0-4): 00001 = 1 -> 'b'
      leftover (bits 5-7) << 2: 00000 = 0 -> 'y'
    """
    assert AppriseWKDController.zb32_encode(b"\xf8") == "9y"
    assert AppriseWKDController.zb32_encode(b"\xa8") == "iy"
    assert AppriseWKDController.zb32_encode(b"\x08") == "by"


# ---------------------------------------------------------------------------
# wkd_urls
# ---------------------------------------------------------------------------


def test_wkd_urls_structure():
    """wkd_urls() returns properly formed subdomain and direct URLs."""
    sub, direct = AppriseWKDController.wkd_urls("user@example.com")

    assert sub.startswith("https://openpgpkey.example.com/")
    assert "/.well-known/openpgpkey/example.com/hu/" in sub
    assert "?l=user" in sub

    assert direct.startswith("https://example.com/")
    assert "/.well-known/openpgpkey/hu/" in direct
    assert "?l=user" in direct


def test_wkd_urls_case_normalised():
    """wkd_urls() produces the same hash and domain for differently-cased
    inputs, but preserves the original local-part case in ?l= (RFC 9080).

    The hash component uses the lower-cased local part (spec requirement),
    the domain is always lower-cased (URL canonicalisation), and the ?l=
    query parameter carries the unchanged original local part -- so two
    addresses that differ only in local-part capitalisation will share the
    same hash/path but differ in their ?l= value.
    """
    sub_upper, dir_upper = AppriseWKDController.wkd_urls("User@Example.COM")
    sub_lower, dir_lower = AppriseWKDController.wkd_urls("user@example.com")

    # Hash and domain parts must be identical
    assert sub_upper.split("?")[0] == sub_lower.split("?")[0]
    assert dir_upper.split("?")[0] == dir_lower.split("?")[0]

    # ?l= must carry the original (unchanged) local part
    assert "?l=User" in sub_upper
    assert "?l=user" in sub_lower

    # Domain is always lower-cased regardless of input
    assert "example.com" in sub_lower


def test_wkd_urls_l_param_preserves_original_case():
    """?l= carries the unchanged local-part per RFC 9080.

    The spec example: Joe.Doe@Example.ORG ->
      ?l=Joe.Doe  (original case, not lowercased)
    The hash is computed from the lowercased local part; only ?l= keeps
    the original capitalisation.
    """
    sub, direct = AppriseWKDController.wkd_urls("Joe.Doe@Example.ORG")
    assert "?l=Joe.Doe" in sub
    assert "?l=Joe.Doe" in direct
    # Domain part is always lowercased in the URL host
    assert urlparse(sub).hostname == "openpgpkey.example.org"
    assert urlparse(direct).hostname == "example.org"


def test_wkd_urls_local_part_encoded():
    """wkd_urls() percent-encodes special characters in the local part."""
    sub, direct = AppriseWKDController.wkd_urls("first+last@example.com")
    assert "first%2Blast" in sub
    assert "first%2Blast" in direct


def test_wkd_urls_no_at_sign():
    """wkd_urls() returns (None, None) for an address without '@'."""
    sub, direct = AppriseWKDController.wkd_urls("notanemail")
    assert sub is None
    assert direct is None


def test_wkd_urls_empty_string():
    """wkd_urls() returns (None, None) for an empty string."""
    sub, direct = AppriseWKDController.wkd_urls("")
    assert sub is None
    assert direct is None


def test_wkd_urls_empty_local():
    """wkd_urls() returns (None, None) when the local part is empty."""
    sub, direct = AppriseWKDController.wkd_urls("@example.com")
    assert sub is None
    assert direct is None


def test_wkd_urls_empty_domain():
    """wkd_urls() returns (None, None) when the domain is empty."""
    sub, direct = AppriseWKDController.wkd_urls("user@")
    assert sub is None
    assert direct is None


def test_wkd_urls_none_input():
    """wkd_urls() returns (None, None) for None input."""
    sub, direct = AppriseWKDController.wkd_urls(None)
    assert sub is None
    assert direct is None


def test_wkd_urls_non_string_input():
    """wkd_urls() returns (None, None) for non-string truthy inputs.

    Without the isinstance guard, ``"@" not in 123`` raises TypeError
    before the try/except block can handle it.
    """
    for bad in (123, 12.5, object(), ["user@example.com"]):
        sub, direct = AppriseWKDController.wkd_urls(bad)
        assert sub is None
        assert direct is None


def test_wkd_urls_ipv4_domain_rejected():
    """wkd_urls() returns (None, None) for emails with an IPv4 domain.

    WKD is defined for DNS hostnames only (RFC 9080).  Allowing IP
    literals as the domain creates an SSRF vector because WKD discovery
    turns recipient domains into outbound HTTPS requests.
    """
    for addr in (
        "user@127.0.0.1",
        "user@192.168.1.1",
        "user@10.0.0.1",
    ):
        sub, direct = AppriseWKDController.wkd_urls(addr)
        assert sub is None, f"Expected None for IP domain: {addr}"
        assert direct is None, f"Expected None for IP domain: {addr}"


def test_wkd_urls_lower_raises_attribute_error():
    """wkd_urls() returns (None, None) when email.split() raises.

    Covers the defensive except branch for string-like objects that pass
    the '@' membership check but fail during splitting.  (After the
    RFC 9080 case-preservation fix, split() is called before lower(), so
    breaking split() is what exercises this path.)
    """

    class BrokenStr(str):
        def split(self, *args, **kwargs):
            raise AttributeError("broken split")

    sub, direct = AppriseWKDController.wkd_urls(BrokenStr("user@example.com"))
    assert sub is None
    assert direct is None


def test_wkd_urls_domain_injection_rejected():
    """wkd_urls() returns (None, None) for emails whose domain contains
    characters that would rewrite the URL host.

    user@legit.com@attacker.test splits to domain='legit.com@attacker.test'
    which, when embedded in an HTTPS URL, sends the request to attacker.test
    with legit.com as URL credentials.  The is_hostname() guard rejects it.
    """
    for bad_email in (
        "user@example.com@attacker.test",
        "user@example.com/path",
        "user@example.com:8080",
        "user@example.com space",
    ):
        sub, direct = AppriseWKDController.wkd_urls(bad_email)
        assert sub is None, f"Expected None for domain injection: {bad_email}"
        assert direct is None, (
            f"Expected None for domain injection: {bad_email}"
        )


# ---------------------------------------------------------------------------
# AppriseWKDController.fetch -- happy path
# ---------------------------------------------------------------------------


def _make_resp(status_code, chunks=None, url=None):
    """Build a context-manager-compatible requests.Response mock.

    ``chunks`` is a list of byte strings that iter_content() will yield.
    Pass an empty list for an empty body.  Leave as None when the status
    code is non-200 and the body will never be consumed.
    ``url`` sets r.url (the final URL after any redirects).  When omitted
    the attribute is a MagicMock, which passes the HTTPS check because
    MagicMock().lower().startswith() is truthy.
    """
    resp = mock.MagicMock(status_code=status_code)
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    # Default to an empty headers dict so r.headers.get("Content-Length")
    # returns None; tests that need a specific header override this
    resp.headers = {}
    if url is not None:
        resp.url = url
    if chunks is not None:
        resp.iter_content.return_value = iter(chunks)
    return resp


@mock.patch("requests.get")
def test_fetch_subdomain_success(mock_get):
    """fetch() returns key bytes when the subdomain URL responds with 200."""
    # 0x99 is a valid old-format OpenPGP packet header byte (bit 7 set)
    key_bytes = b"\x99fake-openpgp-key-data"

    # Subdomain call succeeds; iter_content yields the key in one chunk
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[key_bytes])

    ctrl = AppriseWKDController()
    result = ctrl.fetch("user@example.com")

    assert result == key_bytes
    assert mock_get.call_count == 1


@mock.patch("requests.get")
def test_fetch_direct_fallback(mock_get):
    """fetch() tries the direct URL when the subdomain URL fails."""
    key_bytes = b"\x99another-fake-key"

    # Subdomain -> 404 (body never consumed), direct -> 200 with key bytes
    mock_get.side_effect = [
        _make_resp(404),
        _make_resp(requests.codes.ok, chunks=[key_bytes]),
    ]

    ctrl = AppriseWKDController()
    result = ctrl.fetch("user@example.com")

    assert result == key_bytes
    assert mock_get.call_count == 2


@mock.patch("requests.get")
def test_fetch_both_fail(mock_get):
    """fetch() returns None when both WKD URLs fail."""
    mock_get.return_value = _make_resp(404)

    ctrl = AppriseWKDController()
    result = ctrl.fetch("user@example.com")

    assert result is None
    assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# fetch -- cache behaviour
# ---------------------------------------------------------------------------


@mock.patch("requests.get")
def test_fetch_caches_result(mock_get):
    """A successful fetch is cached; subsequent calls skip the network."""
    key_bytes = b"\x99cached-key"
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[key_bytes])

    ctrl = AppriseWKDController()
    result1 = ctrl.fetch("user@example.com")
    result2 = ctrl.fetch("user@example.com")

    assert result1 == key_bytes
    assert result2 == key_bytes
    # Network only hit once
    assert mock_get.call_count == 1


@mock.patch("requests.get")
def test_fetch_cache_case_insensitive(mock_get):
    """Cache lookup normalises the email address."""
    key_bytes = b"\x99normalised-key"
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[key_bytes])

    ctrl = AppriseWKDController()
    ctrl.fetch("User@Example.COM")
    result = ctrl.fetch("user@example.com")

    assert result == key_bytes
    assert mock_get.call_count == 1


@mock.patch("requests.get")
def test_fetch_expired_cache_refetches(mock_get):
    """An expired cache entry triggers a new network request."""
    key_bytes = b"\x99refreshed-key"
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[key_bytes])

    ctrl = AppriseWKDController()

    # Seed the cache with an already-expired entry
    ctrl._cache["user@example.com"] = {
        "data": b"stale-key",
        "expires": datetime.now(timezone.utc) - timedelta(seconds=1),
    }

    result = ctrl.fetch("user@example.com")

    assert result == key_bytes
    assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# fetch -- invalid input
# ---------------------------------------------------------------------------


def test_fetch_no_at_sign():
    """fetch() returns None for an address without '@'."""
    ctrl = AppriseWKDController()
    assert ctrl.fetch("notanemail") is None


def test_fetch_empty_string():
    """fetch() returns None for an empty string."""
    ctrl = AppriseWKDController()
    assert ctrl.fetch("") is None


def test_fetch_none():
    """fetch() returns None when called with None."""
    ctrl = AppriseWKDController()
    assert ctrl.fetch(None) is None


def test_fetch_non_string_input():
    """fetch() returns None for non-string truthy inputs.

    Without the isinstance guard, ``"@" not in 123`` raises TypeError
    before the method can return None for invalid input.
    """
    ctrl = AppriseWKDController()
    for bad in (123, 12.5, object(), ["user@example.com"]):
        assert ctrl.fetch(bad) is None


def test_fetch_at_only():
    """fetch() returns None for '@' (empty local and empty domain).

    '@' passes the '@' membership check but wkd_urls() returns (None, None)
    because both local and domain parts are empty -- covers the guard at
    the second validation point inside fetch().
    """
    ctrl = AppriseWKDController()
    assert ctrl.fetch("@") is None


# ---------------------------------------------------------------------------
# _get -- response validation
# ---------------------------------------------------------------------------


@mock.patch("requests.get")
def test_get_non_200_returns_none(mock_get):
    """_get() returns None for any non-200 HTTP status."""
    for code in (301, 400, 403, 404, 500):
        mock_get.return_value = _make_resp(code)
        ctrl = AppriseWKDController()
        assert ctrl._get("https://example.com/key") is None


@mock.patch("requests.get")
def test_get_empty_body_returns_none(mock_get):
    """_get() returns None when the response body is empty."""
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[])
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") is None


@mock.patch("requests.get")
def test_get_empty_chunk_is_skipped(mock_get):
    """_get() skips empty bytestrings yielded by iter_content().

    Some HTTP adapters yield b"" sentinel chunks between real chunks;
    the in-loop ``if not chunk: continue`` guard must skip them so they
    do not corrupt the accumulated content or trigger a false empty-body
    result.
    """
    # Interleave an empty sentinel before a valid PGP binary chunk
    key_bytes = b"\x99" + b"\x00" * 8
    mock_get.return_value = _make_resp(
        requests.codes.ok, chunks=[b"", key_bytes]
    )
    ctrl = AppriseWKDController()
    result = ctrl._get("https://example.com/key")
    assert result == key_bytes


@mock.patch("requests.get")
def test_get_oversized_via_content_length_returns_none(mock_get):
    """_get() rejects early when Content-Length already exceeds the limit.

    iter_content() must not be called at all -- we detect the oversize
    from the header before reading any bytes.
    """
    ctrl = AppriseWKDController()
    resp = _make_resp(requests.codes.ok)
    resp.headers = {"Content-Length": str(ctrl.max_response_size + 1)}
    mock_get.return_value = resp
    assert ctrl._get("https://example.com/key") is None
    resp.iter_content.assert_not_called()


@mock.patch("requests.get")
def test_get_valid_content_length_within_limit_proceeds(mock_get):
    """_get() proceeds to read chunks when Content-Length is within the limit.

    This exercises the branch where content_length is not None and the
    parsed value does not exceed max_response_size.
    """
    key_bytes = b"\x99valid-key"
    resp = _make_resp(requests.codes.ok, chunks=[key_bytes])
    resp.headers = {"Content-Length": str(len(key_bytes))}
    mock_get.return_value = resp
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") == key_bytes


@mock.patch("requests.get")
def test_get_malformed_content_length_proceeds(mock_get):
    """_get() ignores a malformed Content-Length and reads chunks normally."""
    key_bytes = b"\x99valid-key"
    resp = _make_resp(requests.codes.ok, chunks=[key_bytes])
    resp.headers = {"Content-Length": "not-a-number"}
    mock_get.return_value = resp
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") == key_bytes


@mock.patch("requests.get")
def test_get_oversized_body_returns_none(mock_get):
    """_get() returns None when accumulated chunks exceed max_response_size."""
    ctrl = AppriseWKDController()
    # Single chunk one byte over the limit triggers the in-loop guard
    oversized = b"\x99" + b"x" * ctrl.max_response_size
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[oversized])
    assert ctrl._get("https://example.com/key") is None


@mock.patch("requests.get")
def test_get_non_pgp_body_returns_none(mock_get):
    """_get() returns None when the response body is not PGP data.

    A subdomain endpoint that is a parked domain or CDN may return HTTP
    200 with HTML content.  Without this guard, fetch() would cache the
    HTML bytes and never try the direct-method fallback URL.
    """
    for non_pgp in (
        b"<html><body>Not a key</body></html>",
        b"<!DOCTYPE html>",
        b"{}",
        b"Not PGP data",
    ):
        mock_get.return_value = _make_resp(requests.codes.ok, chunks=[non_pgp])
        ctrl = AppriseWKDController()
        assert ctrl._get("https://example.com/key") is None, (
            f"Expected None for non-PGP content: {non_pgp[:20]}"
        )


@mock.patch("requests.get")
def test_get_binary_pgp_packet_accepted(mock_get):
    """_get() accepts a response whose first byte has bit 7 set (OpenPGP
    binary packet format)."""
    # 0x99 is the old-format public-key packet header
    pgp_binary = b"\x99\x01\xd6" + b"\x00" * 100
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[pgp_binary])
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") == pgp_binary


@mock.patch("requests.get")
def test_get_ascii_armoured_key_accepted(mock_get):
    """_get() accepts ASCII-armoured PGP key material (starts with '-----')."""
    armoured = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n..."
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[armoured])
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") == armoured


@mock.patch("requests.get", side_effect=requests.RequestException("timeout"))
def test_get_request_exception_returns_none(mock_get):
    """_get() returns None when requests raises any RequestException."""
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") is None


@mock.patch("requests.get")
def test_get_stream_oserror_returns_none(mock_get):
    """_get() returns None when iter_content() raises OSError mid-stream.

    Covers disk-full, connection-reset, and other IO-level failures that
    surface after the HTTP headers have been received successfully.
    """
    resp = _make_resp(requests.codes.ok)
    resp.iter_content.side_effect = OSError("connection reset by peer")
    mock_get.return_value = resp
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") is None


@mock.patch("requests.get")
def test_get_stream_generic_exception_returns_none(mock_get):
    """_get() returns None when iter_content() raises an unexpected exception.

    Covers urllib3 IncompleteRead, read-timeout mid-stream, and any other
    exception not otherwise categorised.
    """
    resp = _make_resp(requests.codes.ok)
    resp.iter_content.side_effect = Exception("unexpected streaming error")
    mock_get.return_value = resp
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") is None


@mock.patch("requests.get")
def test_get_http_redirect_rejected(mock_get):
    """_get() returns None when a redirect lands on a non-HTTPS URL.

    A redirect from HTTPS to HTTP would expose key material to interception
    and break the WKD trust model.
    """
    resp = _make_resp(
        requests.codes.ok,
        chunks=[b"\x99key"],
        url="http://attacker.example.com/hu/abc",
    )
    mock_get.return_value = resp
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") is None


@mock.patch("requests.get")
def test_get_success_returns_bytes(mock_get):
    """_get() returns the response bytes on HTTP 200 with content."""
    payload = b"\x99\xaa\xbb\xcc"
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[payload])
    ctrl = AppriseWKDController()
    assert ctrl._get("https://example.com/key") == payload


# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------


def test_prune_removes_expired_entries():
    """prune() discards entries whose expiry has passed."""
    ctrl = AppriseWKDController()
    now = datetime.now(timezone.utc)

    ctrl._cache["expired@example.com"] = {
        "data": b"old",
        "expires": now - timedelta(seconds=1),
    }
    ctrl._cache["fresh@example.com"] = {
        "data": b"new",
        "expires": now + timedelta(seconds=3600),
    }

    ctrl.prune()

    assert "expired@example.com" not in ctrl._cache
    assert "fresh@example.com" in ctrl._cache


def test_prune_empty_cache():
    """prune() does not raise when the cache is empty."""
    ctrl = AppriseWKDController()
    ctrl.prune()  # must not raise
    assert ctrl._cache == {}


# ---------------------------------------------------------------------------
# Constructor defaults
# ---------------------------------------------------------------------------


def test_defaults():
    """AppriseWKDController initialises with expected default values."""
    ctrl = AppriseWKDController()
    assert ctrl.verify_certificate is True
    assert ctrl.request_timeout == (4, 4)
    assert ctrl.allow_redirects is True
    assert ctrl._cache == {}


def test_custom_timeout_and_verify():
    """Constructor stores custom timeout and verify_certificate values."""
    ctrl = AppriseWKDController(
        verify_certificate=False, request_timeout=(2, 10)
    )
    assert ctrl.verify_certificate is False
    assert ctrl.request_timeout == (2, 10)


def test_custom_allow_redirects():
    """Constructor stores a custom allow_redirects value."""
    ctrl = AppriseWKDController(allow_redirects=False)
    assert ctrl.allow_redirects is False


@mock.patch("requests.get")
def test_get_passes_verify_and_timeout(mock_get):
    """_get() forwards verify_certificate, request_timeout, allow_redirects,
    and stream=True to requests."""
    mock_get.return_value = _make_resp(requests.codes.ok, chunks=[b"\x99key"])
    ctrl = AppriseWKDController(
        verify_certificate=False, request_timeout=(1, 5), allow_redirects=False
    )
    ctrl._get("https://example.com/key")

    _, kwargs = mock_get.call_args
    assert kwargs["verify"] is False
    assert kwargs["timeout"] == (1, 5)
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
