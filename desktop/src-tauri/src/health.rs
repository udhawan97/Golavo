//! Loopback port selection, per-launch token generation, and the readiness gate.
//!
//! These are deliberately dependency-light: a raw `TcpStream` health probe avoids
//! pulling an HTTP client into the shell. The sidecar's `/health` is exempt from
//! the token, but we send the token anyway so *every* request the shell makes
//! carries it (defence in depth, and it exercises the header path).

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::time::{Duration, Instant};

/// Ask the OS for a free TCP port on loopback, then release it. There is an
/// unavoidable (tiny) race between releasing it here and the sidecar binding it;
/// the bounded health gate below is what actually confirms the sidecar is up.
pub fn pick_free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

/// 256 bits of OS randomness, hex-encoded, minted fresh per launch.
pub fn generate_token() -> String {
    let mut buf = [0u8; 32];
    getrandom::getrandom(&mut buf).expect("OS RNG must be available");
    buf.iter().map(|byte| format!("{byte:02x}")).collect()
}

/// Poll `http://127.0.0.1:<port>/health` until it reports ok, or the timeout
/// elapses. Returns Ok(elapsed) on success.
pub fn wait_for_health(port: u16, token: &str, timeout: Duration) -> Result<Duration, String> {
    let started = Instant::now();
    let deadline = started + timeout;
    let addr: SocketAddr = format!("127.0.0.1:{port}")
        .parse()
        .map_err(|e| format!("bad loopback addr: {e}"))?;
    let request = format!(
        "GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nx-golavo-token: {token}\r\nConnection: close\r\n\r\n"
    );

    let mut last = String::from("no connection yet");
    while Instant::now() < deadline {
        match probe(&addr, &request) {
            Ok(true) => return Ok(started.elapsed()),
            Ok(false) => last = "sidecar responded but /health not ok".into(),
            Err(e) => last = e,
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    Err(format!(
        "sidecar /health not ready on 127.0.0.1:{port} within {timeout:?} ({last})"
    ))
}

/// Ask the sidecar to exit itself (token-gated POST /api/v1/shutdown). Used
/// before an update installs: killing the onefile BOOTLOADER alone leaves its
/// forked Python child running — only the sidecar can take down its whole tree.
#[cfg_attr(not(feature = "updater"), allow(dead_code))]
pub fn post_shutdown(port: u16, token: &str) -> Result<(), String> {
    let addr: SocketAddr = format!("127.0.0.1:{port}")
        .parse()
        .map_err(|e| format!("bad loopback addr: {e}"))?;
    let request = format!(
        "POST /api/v1/shutdown HTTP/1.1\r\nHost: 127.0.0.1\r\nx-golavo-token: {token}\r\n\
         Content-Length: 0\r\nConnection: close\r\n\r\n"
    );
    let mut stream =
        TcpStream::connect_timeout(&addr, Duration::from_secs(2)).map_err(|e| e.to_string())?;
    stream
        .set_read_timeout(Some(Duration::from_secs(3)))
        .map_err(|e| e.to_string())?;
    stream
        .write_all(request.as_bytes())
        .map_err(|e| e.to_string())?;
    // Best-effort read: the sidecar may exit before the response flushes.
    let mut response = String::new();
    let _ = stream.read_to_string(&mut response);
    Ok(())
}

fn probe(addr: &SocketAddr, request: &str) -> Result<bool, String> {
    let mut stream =
        TcpStream::connect_timeout(addr, Duration::from_secs(2)).map_err(|e| e.to_string())?;
    stream
        .set_read_timeout(Some(Duration::from_secs(3)))
        .map_err(|e| e.to_string())?;
    stream
        .write_all(request.as_bytes())
        .map_err(|e| e.to_string())?;
    let mut response = String::new();
    // `Connection: close` makes the server close after the body, so read-to-end
    // terminates cleanly.
    stream
        .read_to_string(&mut response)
        .map_err(|e| e.to_string())?;
    let status_ok = response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200");
    let body_ok = response.contains("\"status\":\"ok\"");
    Ok(status_ok && body_ok)
}
