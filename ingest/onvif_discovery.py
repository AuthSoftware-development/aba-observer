"""ONVIF camera auto-discovery on local network.

Discovers ONVIF-compliant IP cameras and extracts their RTSP stream URLs.
Works with Axis, Hikvision, Dahua, Bosch, Hanwha, and other ONVIF cameras.
"""

import socket
import re
from xml.etree import ElementTree


# WS-Discovery probe message for ONVIF devices
PROBE_MESSAGE = '''<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
    <e:Header>
        <w:MessageID>uuid:84ede3de-7dec-11d0-c360-f01234567890</w:MessageID>
        <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
        <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
    </e:Header>
    <e:Body>
        <d:Probe>
            <d:Types>dn:NetworkVideoTransmitter</d:Types>
        </d:Probe>
    </e:Body>
</e:Envelope>'''


def discover_cameras(timeout: float = 3.0) -> list[dict]:
    """Discover ONVIF cameras on the local network via WS-Discovery.

    Returns list of discovered cameras with their addresses and capabilities.
    """
    cameras = []

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)

        # Send WS-Discovery probe to multicast address
        sock.sendto(PROBE_MESSAGE.encode(), ("239.255.255.250", 3702))

        while True:
            try:
                data, addr = sock.recvfrom(65535)
                camera = _parse_probe_response(data.decode(errors="ignore"), addr[0])
                if camera:
                    cameras.append(camera)
            except socket.timeout:
                break

        sock.close()
    except Exception as e:
        print(f"[onvif] Discovery error: {e}")

    return cameras


def _parse_probe_response(xml_data: str, source_ip: str) -> dict | None:
    """Parse a WS-Discovery probe response."""
    try:
        # Extract XAddrs (service URLs)
        xaddrs_match = re.search(r'<[^:]*XAddrs>([^<]+)</[^:]*XAddrs>', xml_data)
        scopes_match = re.search(r'<[^:]*Scopes>([^<]+)</[^:]*Scopes>', xml_data)

        xaddrs = xaddrs_match.group(1).strip() if xaddrs_match else ""
        scopes = scopes_match.group(1).strip() if scopes_match else ""

        # Extract device info from scopes
        name = ""
        hardware = ""
        for scope in scopes.split():
            if "name/" in scope.lower():
                name = scope.split("/")[-1]
            elif "hardware/" in scope.lower():
                hardware = scope.split("/")[-1]

        # Guess RTSP URL (common patterns)
        rtsp_urls = [
            f"rtsp://{source_ip}:554/stream1",
            f"rtsp://{source_ip}:554/Streaming/Channels/101",
            f"rtsp://{source_ip}:554/cam/realmonitor?channel=1&subtype=0",
        ]

        return {
            "ip": source_ip,
            "name": name or f"Camera at {source_ip}",
            "hardware": hardware,
            "onvif_url": xaddrs.split()[0] if xaddrs else f"http://{source_ip}:80/onvif/device_service",
            "rtsp_urls": rtsp_urls,
            "scopes": scopes,
        }
    except Exception:
        return None


def get_rtsp_url(onvif_url: str, username: str = "admin", password: str = "admin") -> str | None:
    """Try to get the actual RTSP URL from an ONVIF device.

    Note: Full ONVIF requires python-onvif-zeep. This is a simplified version
    that works with common camera URL patterns.
    """
    try:
        # Extract IP from ONVIF URL
        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', onvif_url)
        if not ip_match:
            return None
        ip = ip_match.group(1)

        # Try common RTSP patterns
        import cv2
        patterns = [
            f"rtsp://{username}:{password}@{ip}:554/stream1",
            f"rtsp://{username}:{password}@{ip}:554/Streaming/Channels/101",
            f"rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0",
            f"rtsp://{username}:{password}@{ip}:554/h264Preview_01_main",
            f"rtsp://{ip}:554/stream1",
        ]

        for url in patterns:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                cap.release()
                return url
            cap.release()

        return None
    except Exception:
        return None
