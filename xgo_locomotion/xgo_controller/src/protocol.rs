//! XGO byte protocol: `0x55 0x00 LEN TYPE ADDR DATA.. CHK 0x00 0xAA`, LEN = len(DATA) + 8,
//! CHK = 255 - (LEN + TYPE + ADDR + sum(DATA)) % 256. Mirrors LuwuDynamics/xgo_doglib.

pub const TYPE_WRITE: u8 = 0x00;
pub const TYPE_READ: u8 = 0x02;
pub const ADDR_BATTERY: u8 = 0x01;
pub const ADDR_FIRMWARE: u8 = 0x07;
pub const ADDR_LOAD: u8 = 0x20;
pub const ADDR_ACTION: u8 = 0x3E;
pub const ADDR_MOTOR: u8 = 0x50;
pub const ADDR_RPY: u8 = 0x62;
pub const ADDR_IMU: u8 = 0x65;
pub const N_MOTOR_REGS: usize = 15;
pub const ACTION_RESET: u8 = 0xFF;
pub const LOAD_ALL: u8 = 0x00;
pub const UNLOAD_ALL: u8 = 0x01;

pub fn checksum(len: u8, ty: u8, addr: u8, data: &[u8]) -> u8 {
    let s: u32 = len as u32 + ty as u32 + addr as u32 + data.iter().map(|&b| b as u32).sum::<u32>();
    (255 - s % 256) as u8
}

pub fn encode(ty: u8, addr: u8, data: &[u8]) -> Vec<u8> {
    let len = (data.len() + 8) as u8;
    let mut f = vec![0x55, 0x00, len, ty, addr];
    f.extend_from_slice(data);
    f.extend_from_slice(&[checksum(len, ty, addr, data), 0x00, 0xAA]);
    f
}

pub fn encode_read(addr: u8, n: u8) -> Vec<u8> {
    encode(TYPE_READ, addr, &[n])
}

pub fn encode_write(addr: u8, data: &[u8]) -> Vec<u8> {
    encode(TYPE_WRITE, addr, data)
}

#[derive(Debug, Clone, PartialEq)]
pub struct Frame {
    pub ty: u8,
    pub addr: u8,
    pub data: Vec<u8>,
}

#[derive(Default)]
pub struct FrameParser {
    buf: Vec<u8>,
    pub bad_frames: usize,
}

impl FrameParser {
    pub fn feed(&mut self, chunk: &[u8]) -> Vec<Frame> {
        self.buf.extend_from_slice(chunk);
        let mut out = Vec::new();
        loop {
            let Some(start) = self.buf.windows(2).position(|w| w == [0x55, 0x00]) else {
                let keep = usize::from(self.buf.last() == Some(&0x55));
                let n = self.buf.len() - keep;
                self.buf.drain(..n);
                return out;
            };
            self.buf.drain(..start);
            if self.buf.len() < 3 {
                return out;
            }
            let len = self.buf[2] as usize;
            if len < 8 {
                self.bad_frames += 1;
                self.buf.drain(..1);
                continue;
            }
            if self.buf.len() < len {
                return out;
            }
            let (ty, addr) = (self.buf[3], self.buf[4]);
            let data = self.buf[5..len - 3].to_vec();
            let ok = self.buf[len - 2] == 0x00
                && self.buf[len - 1] == 0xAA
                && self.buf[len - 3] == checksum(len as u8, ty, addr, &data);
            if ok {
                out.push(Frame { ty, addr, data });
                self.buf.drain(..len);
            } else {
                self.bad_frames += 1;
                self.buf.drain(..1);
            }
        }
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct Imu {
    pub accel: [f64; 3],
    pub gyro_dps: [f64; 3],
    pub rpy_deg: [f64; 3],
}

/// 0x65 block: 6 x int16 LE (accel /16384*9.8, gyro /16.4 deg/s) + 3 x f32 LE (rpy deg).
pub fn decode_imu(d: &[u8]) -> Imu {
    let i16_at = |i: usize| i16::from_le_bytes([d[2 * i], d[2 * i + 1]]) as f64;
    let f32_at = |o: usize| f32::from_le_bytes([d[o], d[o + 1], d[o + 2], d[o + 3]]) as f64;
    Imu {
        accel: [0, 1, 2].map(|i| i16_at(i) / 16384.0 * 9.8),
        gyro_dps: [3, 4, 5].map(|i| i16_at(i) / 16.4),
        rpy_deg: [12, 16, 20].map(f32_at),
    }
}

pub fn decode_rpy(d: &[u8]) -> [f64; 3] {
    [0, 4, 8].map(|o| f32::from_le_bytes([d[o], d[o + 1], d[o + 2], d[o + 3]]) as f64)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn read_frame_matches_xgolib() {
        assert_eq!(
            encode_read(0x50, 15),
            vec![0x55, 0, 9, 2, 0x50, 15, 149, 0, 0xAA]
        );
    }

    #[test]
    fn parser_split_and_garbage() {
        let mut s = vec![1, 0x55, 0xFF];
        s.extend(encode(0x12, 0x50, &(0..15).collect::<Vec<u8>>()));
        s.extend(encode(0x12, 0x65, &[0; 24]));
        let mut p = FrameParser::default();
        let mut got = Vec::new();
        for c in s.chunks(5) {
            got.extend(p.feed(c));
        }
        assert_eq!(
            got.iter().map(|f| f.addr).collect::<Vec<_>>(),
            vec![0x50, 0x65]
        );
        assert_eq!(got[0].data, (0..15).collect::<Vec<u8>>());
    }

    #[test]
    fn parser_rejects_bad_checksum() {
        let mut f = encode(0x12, 0x50, &[1, 2]);
        let n = f.len();
        f[n - 3] ^= 0xFF;
        let mut p = FrameParser::default();
        assert!(p.feed(&f).is_empty());
        assert!(p.bad_frames >= 1);
    }

    #[test]
    fn imu_decode() {
        let mut d = Vec::new();
        for v in [0i16, 0, 16384, 164, -328, 0] {
            d.extend(v.to_le_bytes());
        }
        for v in [1.5f32, -2.5, 90.0] {
            d.extend(v.to_le_bytes());
        }
        let imu = decode_imu(&d);
        assert!((imu.accel[2] - 9.8).abs() < 1e-9);
        assert!((imu.gyro_dps[0] - 10.0).abs() < 1e-9 && (imu.gyro_dps[1] + 20.0).abs() < 1e-9);
        assert_eq!(imu.rpy_deg, [1.5, -2.5, 90.0]);
    }
}
