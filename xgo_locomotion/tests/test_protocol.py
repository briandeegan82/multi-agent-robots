import numpy as np

from xgo_rl import protocol as P


def test_read_frame_matches_xgolib():
    # xgolib __read(0x50, 15): checksum 255 - (0x09 + 0x02 + 0x50 + 15) % 256
    assert P.encode_read(0x50, 15) == bytes([0x55, 0, 9, 2, 0x50, 15, 149, 0, 0xAA])


def test_write_frame_matches_xgolib():
    # xgolib __send("MOTOR_ANGLE", index=1, len=2) with values 128, 200
    data = [128, 200]
    chk = 255 - ((2 + 8) + 0 + 0x50 + sum(data)) % 256
    assert P.encode_write(0x50, data) == bytes([0x55, 0, 10, 0, 0x50, 128, 200, chk, 0, 0xAA])


def test_parser_handles_garbage_and_split_chunks():
    frames = P.encode(0x12, 0x50, bytes(range(15))) + P.encode(0x12, 0x65, bytes(24))
    stream = b"\x01\x55\xff" + frames[:7] + b"" + frames[7:30] + frames[30:]
    parser = P.FrameParser()
    out = []
    for i in range(0, len(stream), 5):
        out += parser.feed(stream[i : i + 5])
    assert [f.addr for f in out] == [0x50, 0x65]
    assert out[0].data == bytes(range(15))


def test_parser_rejects_bad_checksum():
    bad = bytearray(P.encode(0x12, 0x50, b"\x01\x02"))
    bad[-3] ^= 0xFF
    parser = P.FrameParser()
    assert parser.feed(bytes(bad)) == []
    assert parser.bad_frames >= 1


def test_imu_roundtrip():
    s = P.decode_imu(P.encode_imu((0.1, -0.2, 9.8), (10.0, -20.0, 30.0), (1.5, -2.5, 90.0)))
    np.testing.assert_allclose(s.accel, (0.1, -0.2, 9.8), atol=1e-3)
    np.testing.assert_allclose(s.gyro_dps, (10.0, -20.0, 30.0), atol=0.07)
    np.testing.assert_allclose(s.rpy_deg, (1.5, -2.5, 90.0), atol=1e-5)
