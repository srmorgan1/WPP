"""Network security utilities for IP address validation and access control."""

import ipaddress
import logging
from typing import List

from wpp.config import get_allowed_networks, get_enable_network_restrictions

logger = logging.getLogger(__name__)


def is_ip_in_allowed_networks(client_ip: str, allowed_networks: List[str]) -> bool:
    """
    Check if a client IP address is within any of the allowed networks.

    Args:
        client_ip: The client IP address to check
        allowed_networks: List of allowed networks in CIDR notation

    Returns:
        True if the IP is in an allowed network, False otherwise
    """
    try:
        client_addr = ipaddress.ip_address(client_ip)
    except ValueError:
        logger.warning(f"Invalid IP address format: {client_ip}")
        return False

    for network_str in allowed_networks:
        try:
            network = ipaddress.ip_network(network_str, strict=False)
            if client_addr in network:
                logger.debug(f"IP {client_ip} is allowed (matches {network_str})")
                return True
        except ValueError:
            logger.warning(f"Invalid network format: {network_str}")
            continue

    logger.warning(f"IP {client_ip} is not in any allowed network")
    return False


def validate_client_ip(client_ip: str) -> bool:
    """
    Validate if a client IP address is allowed to access the server.

    Args:
        client_ip: The client IP address to validate

    Returns:
        True if access is allowed, False otherwise
    """
    if not get_enable_network_restrictions():
        logger.debug("Network restrictions are disabled")
        return True

    allowed_networks = get_allowed_networks()
    return is_ip_in_allowed_networks(client_ip, allowed_networks)


def get_client_ip_from_request(request) -> str:
    """
    Extract the client IP address from a FastAPI request.

    Handles various proxy headers and direct connections.

    Args:
        request: FastAPI request object

    Returns:
        The client IP address as a string
    """
    # Check for forwarded headers (common with proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        client_ip = forwarded_for.split(",")[0].strip()
        logger.debug(f"Using X-Forwarded-For IP: {client_ip}")
        return client_ip

    # Check for other proxy headers
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        logger.debug(f"Using X-Real-IP: {real_ip}")
        return real_ip

    # Fall back to direct client IP
    client_ip = request.client.host if request.client else "127.0.0.1"
    logger.debug(f"Using direct client IP: {client_ip}")
    return client_ip


def log_security_event(event_type: str, client_ip: str, details: str = ""):
    """
    Log security-related events.

    Args:
        event_type: Type of security event (e.g., "access_denied", "access_allowed")
        client_ip: The client IP address involved
        details: Additional details about the event
    """
    message = f"Security event: {event_type} from {client_ip}"
    if details:
        message += f" - {details}"

    if event_type == "access_denied":
        logger.warning(message)
    else:
        logger.info(message)