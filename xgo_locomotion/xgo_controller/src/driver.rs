//! XGO driver over any byte stream (UART via `serialport`, or a pty in tests).

use std::io::{ErrorKind, Read, Write};
use std::time::{Duration, Instant};

use crate::protocol::{self as p, FrameParser, Imu};

pub trait Port: Read + Write {
    fn clear_input(&mut self) {}
}

impl Port for Box<dyn serialport::SerialPort> {
    fn clear_input(&mut self) {
        let _ = self.clear(serialport::ClearBuffer::Input);
    }
}

pub fn open_serial(path: &str, baud: u32) -> anyhow::Result<Box<dyn serialport::SerialPort>> {
    Ok(serialport::new(path, baud)
        .timeout(Duration::from_millis(1))
        .open()?)
}

#[derive(Debug)]
pub struct Timeout(pub u8);

impl std::fmt::Display for Timeout {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "no reply for read 0x{:02X}", self.0)
    }
}

impl std::error::Error for Timeout {}

pub struct Driver<P: Port> {
    pub port: P,
    pub read_timeout: Duration,
    parser: FrameParser,
    pub bytes_tx: usize,
    pub bytes_rx: usize,
}

impl<P: Port> Driver<P> {
    pub fn new(port: P, read_timeout: Duration) -> Self {
        Self {
            port,
            read_timeout,
            parser: FrameParser::default(),
            bytes_tx: 0,
            bytes_rx: 0,
        }
    }

    fn send(&mut self, frame: &[u8]) -> anyhow::Result<()> {
        self.port.write_all(frame)?;
        self.port.flush()?;
        self.bytes_tx += frame.len();
        Ok(())
    }

    pub fn read_regs(&mut self, addr: u8, n: usize) -> anyhow::Result<Vec<u8>> {
        self.port.clear_input();
        self.parser = FrameParser::default();
        self.send(&p::encode_read(addr, n as u8))?;
        let deadline = Instant::now() + self.read_timeout;
        let mut buf = [0u8; 256];
        loop {
            match self.port.read(&mut buf) {
                Ok(k) if k > 0 => {
                    self.bytes_rx += k;
                    for f in self.parser.feed(&buf[..k]) {
                        if f.addr == addr && f.data.len() >= n {
                            return Ok(f.data[..n].to_vec());
                        }
                    }
                }
                Ok(_) => {}
                Err(e) if matches!(e.kind(), ErrorKind::TimedOut | ErrorKind::WouldBlock) => {}
                Err(e) => return Err(e.into()),
            }
            if Instant::now() >= deadline {
                return Err(Timeout(addr).into());
            }
        }
    }

    pub fn write_regs(&mut self, addr: u8, data: &[u8]) -> anyhow::Result<()> {
        self.send(&p::encode_write(addr, data))
    }

    pub fn read_firmware(&mut self) -> anyhow::Result<String> {
        let d = self.read_regs(p::ADDR_FIRMWARE, 10)?;
        Ok(String::from_utf8_lossy(&d)
            .trim_end_matches('\0')
            .to_string())
    }

    pub fn read_battery(&mut self) -> anyhow::Result<u8> {
        Ok(self.read_regs(p::ADDR_BATTERY, 1)?[0])
    }

    pub fn read_motors(&mut self, n: usize) -> anyhow::Result<Vec<u8>> {
        self.read_regs(p::ADDR_MOTOR, n)
    }

    pub fn write_motors(&mut self, first_register: usize, values: &[u8]) -> anyhow::Result<()> {
        self.write_regs(p::ADDR_MOTOR + first_register as u8, values)
    }

    pub fn read_imu(&mut self) -> anyhow::Result<Imu> {
        Ok(p::decode_imu(&self.read_regs(p::ADDR_IMU, 24)?))
    }

    pub fn read_rpy(&mut self) -> anyhow::Result<[f64; 3]> {
        Ok(p::decode_rpy(&self.read_regs(p::ADDR_RPY, 12)?))
    }

    pub fn reset(&mut self) -> anyhow::Result<()> {
        self.write_regs(p::ADDR_ACTION, &[p::ACTION_RESET])
    }

    pub fn load_all(&mut self) -> anyhow::Result<()> {
        self.write_regs(p::ADDR_LOAD, &[p::LOAD_ALL])
    }

    pub fn unload_all(&mut self) -> anyhow::Result<()> {
        self.write_regs(p::ADDR_LOAD, &[p::UNLOAD_ALL])
    }
}
