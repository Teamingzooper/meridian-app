"""Tests for exception-to-guidance mapping."""
import pytest

from meridiand.errors import DeviceError, classify, engine_down, no_device


class FakeTunneldConnectionError(Exception):
    pass


FakeTunneldConnectionError.__name__ = "TunneldConnectionError"


def _named(name, base=Exception):
    """Build an exception class standing in for one of pymobiledevice3's."""
    return type(name, (base,), {})


class TestClassify:
    @pytest.mark.parametrize(
        "exc_name,expected_code",
        [
            ("TunneldConnectionError", "engine_down"),
            ("NoDeviceConnectedError", "no_device"),
            ("DeviceNotFoundError", "no_device"),
            ("DeveloperModeIsNotEnabledError", "dev_mode_off"),
            ("DeviceHasPasscodeSetError", "device_locked"),
            ("NotTrustedError", "not_trusted"),
            ("DeveloperDiskImageNotFoundError", "ddi_missing"),
            ("UnsupportedCommandError", "unsupported_ios"),
        ],
    )
    def test_maps_known_exceptions(self, exc_name, expected_code):
        assert classify(_named(exc_name)()).code == expected_code

    def test_unknown_exception_falls_back(self):
        assert classify(ValueError("???")).code == "unknown"

    def test_subclasses_inherit_their_parents_guidance(self):
        parent = _named("DeveloperModeIsNotEnabledError")
        child = _named("SomeNewerSubclass", parent)
        assert classify(child()).code == "dev_mode_off"

    def test_connection_errors_are_recognised_without_a_name_match(self):
        assert classify(ConnectionResetError()).code == "connection_lost"
        assert classify(TimeoutError()).code == "connection_lost"

    def test_passing_through_an_existing_device_error(self):
        original = DeviceError("custom", "Do the thing.", False)
        assert classify(original) is original


class TestGuidanceQuality:
    def test_every_message_is_a_complete_sentence(self):
        for exc_name in [
            "TunneldConnectionError",
            "NoDeviceConnectedError",
            "DeveloperModeIsNotEnabledError",
            "DeviceHasPasscodeSetError",
            "NotTrustedError",
        ]:
            message = classify(_named(exc_name)()).message
            assert message[0].isupper(), message
            assert message.rstrip().endswith((".", "!")), message

    def test_developer_mode_message_names_the_settings_path(self):
        message = classify(_named("DeveloperModeIsNotEnabledError")()).message
        assert "Developer Mode" in message
        assert "Settings" in message

    def test_unrecoverable_states_are_flagged(self):
        assert not classify(_named("DeveloperModeIsNotEnabledError")()).recoverable
        assert classify(_named("NoDeviceConnectedError")()).recoverable


class TestSerialisation:
    def test_as_dict_carries_the_full_triple(self):
        assert no_device().as_dict() == {
            "code": "no_device",
            "message": "No iPhone found. Connect it with a USB cable.",
            "recoverable": True,
        }

    def test_str_is_the_message(self):
        assert str(engine_down()) == engine_down().message


class TestConstructors:
    def test_no_device(self):
        assert no_device().code == "no_device"

    def test_engine_down(self):
        assert engine_down().code == "engine_down"
