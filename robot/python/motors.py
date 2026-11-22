"""Wheel commands. The sketch receives ``setMotorSpeed(right, left)``."""

from __future__ import annotations


class ListMotors:
    """Records commands. Used when the Bridge is not on this machine."""

    def __init__(self):
        self.commands: list[tuple[int, int]] = []

    def send(self, right: int, left: int):
        pair = (int(right), int(left))
        self.commands.append(pair)
        return pair

    def close(self):
        return None


class BridgeMotors:
    def __init__(self):
        from arduino.app_utils import Bridge

        self._bridge = Bridge
        self._error = None

    def send(self, right: int, left: int):
        pair = (int(right), int(left))
        try:
            self._bridge.call("setMotorSpeed", pair[0], pair[1])
        except Exception as exc:
            text = f"setMotorSpeed failed: {exc}"
            if text != self._error:
                print(text)
                self._error = text
            return None
        self._error = None
        return pair

    def close(self):
        self.send(0, 0)


def open_motors(dry: bool = False):
    if dry:
        return ListMotors()
    try:
        return BridgeMotors()
    except ImportError:
        print("bridge: マイコンへは送らない（この機械には App Lab の Bridge が無い）")
        return ListMotors()
