"""Save every /overhead_camera frame (rgb8) as PNG named by sim time; pure-Python PNG writer."""
import sys, os, zlib, struct
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)

def png(path, w, h, data, step):
    raw = b"".join(b"\x00" + data[y * step:y * step + 3 * w] for y in range(h))
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

class Saver(Node):
    def __init__(self):
        super().__init__("frame_saver")
        self.create_subscription(Image, "/overhead_camera", self.cb, 2)
    def cb(self, m):
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        png(os.path.join(OUT, f"t{t:07.2f}.png"), m.width, m.height, bytes(m.data), m.step)

rclpy.init(); rclpy.spin(Saver())
