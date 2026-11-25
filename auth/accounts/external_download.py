import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings


class ExternalDownloadError(Exception):
    pass


class UnsafeRemoteAddress(ExternalDownloadError):
    pass


class ExternalFileTooLarge(ExternalDownloadError):
    pass


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, port, timeout):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def validate_archive_url(raw_url):
    parsed = urlsplit(raw_url)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not (host == "archive.org" or host.endswith(".archive.org"))
    ):
        raise UnsafeRemoteAddress("unsafe Internet Archive URL")
    return parsed


def resolve_public_address(host, port):
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ExternalDownloadError("Internet Archive DNS lookup failed") from exc
    addresses = sorted({record[4][0] for record in records})
    if not addresses:
        raise ExternalDownloadError("Internet Archive DNS lookup returned no addresses")
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise UnsafeRemoteAddress("Internet Archive host resolved to a non-public address")
    return addresses[0]


def open_archive_response(raw_url, deadline, max_redirects=5):
    current_url = raw_url
    for redirect_count in range(max_redirects + 1):
        parsed = validate_archive_url(current_url)
        port = parsed.port or 443
        address = resolve_public_address(parsed.hostname, port)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExternalDownloadError("Internet Archive download timed out")
        connection = PinnedHTTPSConnection(parsed.hostname, address, port, min(20, remaining))
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        try:
            connection.request(
                "GET",
                path,
                headers={"Accept": "audio/mpeg, audio/flac, application/octet-stream", "User-Agent": "WaveBox/1.0"},
            )
            response = connection.getresponse()
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            connection.close()
            raise ExternalDownloadError("Internet Archive download failed") from exc
        if response.status not in {301, 302, 303, 307, 308}:
            return connection, response
        location = response.getheader("Location")
        response.close()
        connection.close()
        if redirect_count == max_redirects or not location:
            raise ExternalDownloadError("unsafe or excessive Internet Archive redirects")
        current_url = urljoin(current_url, location)
    raise ExternalDownloadError("Internet Archive redirect limit exceeded")


def stream_archive_file(raw_url, destination, max_size):
    deadline = time.monotonic() + 120
    connection, response = open_archive_response(raw_url, deadline)
    try:
        if response.status != 200:
            raise ExternalDownloadError(f"Internet Archive returned status {response.status}")
        content_length = response.getheader("Content-Length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError as exc:
                raise ExternalDownloadError("Internet Archive returned an invalid file size") from exc
            if declared_size > max_size:
                raise ExternalFileTooLarge("file exceeds the download size limit")
        digest = hashlib.sha256()
        size = 0
        with Path(destination).open("wb") as output:
            while True:
                if time.monotonic() >= deadline:
                    raise ExternalDownloadError("Internet Archive download timed out")
                chunk = response.read1(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_size:
                    raise ExternalFileTooLarge("file exceeds the download size limit")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise ExternalDownloadError("Internet Archive returned an empty file")
        return digest.hexdigest(), size
    except (OSError, http.client.HTTPException) as exc:
        raise ExternalDownloadError("Internet Archive download was interrupted") from exc
    finally:
        response.close()
        connection.close()


def fetch_archive_item(identifier):
    query = urlencode({"identifier": identifier})
    target = f"{settings.MUSIC_API_URL.rstrip('/')}/api/external/internet-archive/files?{query}"
    request = Request(target, headers={"Accept": "application/json", "User-Agent": "WaveBox-auth/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read(2 * 1024 * 1024 + 1)
    except (HTTPError, URLError, OSError) as exc:
        raise ExternalDownloadError("Internet Archive metadata is unavailable") from exc
    if len(body) > 2 * 1024 * 1024:
        raise ExternalDownloadError("Internet Archive metadata response is too large")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ExternalDownloadError("Internet Archive metadata response is invalid") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise ExternalDownloadError("Internet Archive metadata response is invalid")
    return payload


def archive_download_url(identifier, file_name):
    if not isinstance(identifier, str) or not isinstance(file_name, str):
        raise UnsafeRemoteAddress("invalid Internet Archive file identifier")
    if not identifier or not file_name or any(character in file_name for character in "/\\\x00"):
        raise UnsafeRemoteAddress("invalid Internet Archive file identifier")
    return f"https://archive.org/download/{quote(identifier, safe='')}/{quote(file_name, safe='')}"
