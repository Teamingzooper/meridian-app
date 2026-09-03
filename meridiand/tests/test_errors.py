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


class TestNoDeviceGuidance:
    """An unplugged phone must not be reported as a tunnel or engine fault."""

    def test_message_names_the_cable_not_the_tunnel(self):
        message = no_device().message
        assert "USB" in message or "cable" in message
        assert "tunnel" not in message.lower()

    def test_it_is_recoverable(self):
        assert no_device().recoverable


class TestIncompleteInstall:
    """A packaging mistake once surfaced as 'check your cable'. Never again."""

    def test_a_missing_module_is_not_blamed_on_the_device(self):
        error = classify(ModuleNotFoundError("No module named 'prompt_toolkit'",
                                             name="prompt_toolkit"))
        assert error.code == "incomplete_install"
        assert "cable" not in error.message.lower()
        assert "unplug" not in error.message.lower()

    def test_it_names_the_missing_module(self):
        error = classify(ModuleNotFoundError("nope", name="prompt_toolkit"))
        assert "prompt_toolkit" in error.message

    def test_it_survives_an_importerror_with_no_name(self):
        assert classify(ImportError("something went wrong")).code == "incomplete_install"

    def test_it_is_not_recoverable_by_retrying(self):
        assert not classify(ImportError("x", name="y")).recoverable
