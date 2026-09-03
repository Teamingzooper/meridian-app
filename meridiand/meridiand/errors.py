"""Turning device failures into sentences a person can act on.

Everything that goes wrong here has a physical cause: a cable is out, a phone is
locked, a setting is off. The library raises precise exceptions; this module maps
them to the one thing the user should go do about it.

Kept free of pymobiledevice3 imports at module scope so it stays importable — and
testable — without a device stack present.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceError(Exception):
    """A device failure paired with the action that resolves it."""

    code: str
    message: str
    #: True when retrying unchanged could plausibly succeed, e.g. a dropped cable.
    recoverable: bool = True

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "recoverable": self.recoverable}


# Matched against the exception's class name, so this table needs no imports and
# survives pymobiledevice3 reorganising its module layout between releases.
_BY_EXCEPTION_NAME: dict[str, tuple[str, str, bool]] = {
    "UserspaceTunnelUnavailableError": (
        "no_tunnel",
        "Couldn't open a tunnel to your iPhone. Unplug it, plug it back in, and tap Trust.",
        True,
    ),
    "TunneldConnectionError": (
        "engine_down",
        "Couldn't reach your iPhone through either tunnel. Reconnect the cable and try again.",
        True,
    ),
    "NoDeviceConnectedError": (
        "no_device",
        "No iPhone found. Connect it with a USB cable.",
        True,
    ),
    "DeviceNotFoundError": (
        "no_device",
        "No iPhone found. Connect it with a USB cable.",
        True,
    ),
    "ConnectionFailedError": (
        "no_device",
        "Lost the connection to your iPhone. Check the cable.",
        True,
    ),
    "DeveloperModeIsNotEnabledError": (
        "dev_mode_off",
        "Turn on Developer Mode: Settings › Privacy & Security › Developer Mode, "
        "then restart your iPhone.",
        False,
    ),
    "DeveloperModeError": (
        "dev_mode_off",
        "Your iPhone refused to enable Developer Mode. Turn it on in "
        "Settings › Privacy & Security, then restart the phone.",
        False,
    ),
    "DeviceHasPasscodeSetError": (
        "device_locked",
        "Unlock your iPhone, then try again.",
        True,
    ),
    "PasswordRequiredError": (
        "device_locked",
        "Unlock your iPhone, then try again.",
        True,
    ),
    "NotTrustedError": (
        "not_trusted",
        "Tap Trust on your iPhone, then try again.",
        True,
    ),
    "NotPairedError": (
        "not_trusted",
        "Tap Trust on your iPhone, then try again.",
        True,
    ),
    "PairingError": (
        "not_trusted",
        "Pairing with your iPhone failed. Unplug it, plug it back in, and tap Trust.",
        True,
    ),
    "DeveloperDiskImageNotFoundError": (
        "ddi_missing",
        "No developer disk image for this iOS version yet. Updating pymobiledevice3 usually fixes it.",
        False,
    ),
    "DeviceVersionNotSupportedError": (
        "unsupported_ios",
        "This iOS version doesn't support location simulation.",
        False,
    ),
    "UnsupportedCommandError": (
        "unsupported_ios",
        "This iOS version doesn't support location simulation.",
        False,
    ),
}

_FALLBACK = (
    "unknown",
    "Something went wrong talking to your iPhone. Unplug it, plug it back in, and try again.",
    True,
)


def classify(exc: BaseException) -> DeviceError:
    """Map any exception to a `DeviceError` carrying a next step.

    Walks the exception's real class hierarchy so subclasses inherit their
    parent's guidance, then falls back to the transport-level checks.
    """
    if isinstance(exc, DeviceError):
        return exc

    for klass in type(exc).__mro__:
        entry = _BY_EXCEPTION_NAME.get(klass.__name__)
        if entry is not None:
            return DeviceError(*entry)

    # A missing module means a broken build, not a device problem. Saying
    # "check the cable" here sends people to debug hardware that is working.
    if isinstance(exc, ImportError):
        missing = getattr(exc, "name", None) or "a component"
        return DeviceError(
            "incomplete_install",
            f"Meridian's helper is missing {missing}. "
            "Reinstall Meridian, or rebuild it if you are running from source.",
            False,
        )

    # Socket-level failures arrive as plain OSErrors with nothing else to go on.
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return DeviceError(
            "connection_lost",
            "Lost the connection to your iPhone. Check the cable and try again.",
            True,
        )

    return DeviceError(*_FALLBACK)


def no_device() -> DeviceError:
    return DeviceError("no_device", "No iPhone found. Connect it with a USB cable.", True)


def engine_down() -> DeviceError:
    return DeviceError(
        "engine_down",
        "Couldn't reach your iPhone through either tunnel. Reconnect the cable and try again.",
        True,
    )
