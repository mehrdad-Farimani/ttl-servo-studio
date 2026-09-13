import time, unittest
from ttl_servo_studio._vendor.scservo_sdk import scscl, COMM_RX_CORRUPT


class Protocol(unittest.TestCase):
    def test_scs_big_endian_position_packet(self):
        sdk = scscl(None)
        out = []
        sdk.writeTxRx = lambda *args: out.append(args)
        sdk.WritePos(1, 511, 1500, 100)
        self.assertEqual(out, [(1, 42, 6, [1, 255, 5, 220, 0, 100])])

    def test_malformed_length_terminates(self):
        class Port:
            is_using = True

            def __init__(self):
                self.end = time.monotonic() + 0.02
                self.data = bytearray([255, 255, 1, 0, 0, 0])

            def isPacketTimeout(self):
                return time.monotonic() > self.end

            def readPort(self, n):
                out = self.data[:n]
                del self.data[:n]
                return out

        port = Port()
        packet, result = scscl(port).rxPacket()
        self.assertEqual(result, COMM_RX_CORRUPT)
        self.assertFalse(port.is_using)


if __name__ == "__main__":
    unittest.main()
