"""Read MINAS A6 servo amplifier info via MINAS standard protocol.

Communicate over RS485 to read amplifier software version and
model name. Factory defaults: Pr5.37=0 (MINAS standard protocol),
Pr5.30=2 (9600 bps).

Reference: MINAS A6 취급설명서(종합편) P.7-28 ~ P.7-41
"""

import serial
import time

PORT = "/dev/ttyUSB0"
BAUDRATE = 9600       # Pr5.30 factory default 2 = 9600 bps
SLAVE_ID = 1          # Pr5.31 axis number (factory default 1)
TIMEOUT = 2.0         # [sec] response wait time

# MINAS standard protocol handshake codes
ENQ = 0x05
EOT = 0x04
ACK = 0x06
NAK = 0x15


def calculate_checksum(data: bytes) -> int:
    """Return two's complement of the byte sum, masked to 8 bits."""
    return (-sum(data)) & 0xFF


def build_command_block(
        axis: int,
        command: int,
        mode: int,
        params: bytes = b""
) -> bytes:
    """Build a MINAS standard protocol data block.

    Block layout:
        N | axis | (mode<<4)|command | params... | checksum
    """
    param_count = len(params)
    cmd_mode = ((mode & 0x0F) << 4) | (command & 0x0F)
    block = bytes([param_count, axis, cmd_mode]) + params
    checksum = calculate_checksum(block)
    return block + bytes([checksum])


def send_and_receive(
        ser: serial.Serial,
        slave_id: int,
        block: bytes
) -> bytes | None:
    """Send a command block and return the response block.

    Execute the RS485 handshake sequence (P.7-33):
        host->amp: module_byte+ENQ, amp->host: EOT,
        host->amp: data block,      amp->host: ACK+ENQ,
        host->amp: module_byte+EOT, amp->host: response block,
        host->amp: ACK.

    Return the raw response bytes, or None on failure.
    """
    module_byte = 0x80 | (slave_id & 0x7F)
    ser.reset_input_buffer()

    # Handshake: send ENQ, wait for EOT
    ser.write(bytes([module_byte, ENQ]))

    start = time.time()
    eot_received = False
    while time.time() - start < TIMEOUT:
        data = ser.read(1)
        if data and data[0] == EOT:
            eot_received = True
            break
    if not eot_received:
        print("  No EOT response from amplifier.")
        return None

    # Send command block, wait for ACK and ENQ
    ser.write(block)

    ack_data = ser.read(2)
    if len(ack_data) < 1:
        print("  ACK response timeout.")
        return None
    if ack_data[0] == NAK:
        print("  Received NAK (data error).")
        return None
    if ack_data[0] != ACK:
        print(f"  Unexpected response: 0x{ack_data[0]:02X}")
        return None

    enq_received = (
        len(ack_data) >= 2 and ack_data[1] == ENQ
    )
    if not enq_received:
        start = time.time()
        while time.time() - start < TIMEOUT:
            data = ser.read(1)
            if data and data[0] == ENQ:
                enq_received = True
                break
    if not enq_received:
        print("  ENQ wait timeout.")
        return None

    # Grant transmission: send EOT, then receive response block
    host_module = 0x80  # host module ID = 0
    ser.write(bytes([host_module, EOT]))

    first_byte = ser.read(1)
    if not first_byte:
        print("  Response block receive timeout.")
        return None

    param_count = first_byte[0]
    # Remaining: axis(1) + cmd_mode(1) + params(N) + checksum(1)
    expected_remaining = param_count + 3
    remaining = ser.read(expected_remaining)
    if len(remaining) < expected_remaining:
        print(
            f"  Incomplete response"
            f" (expected: {expected_remaining},"
            f" received: {len(remaining)})."
        )
        return None

    response = first_byte + remaining

    # Verify checksum: all bytes should sum to 0 mod 256.
    if sum(response) & 0xFF != 0:
        print(f"  Checksum error (sum: 0x{sum(response) & 0xFF:02X}).")
        ser.write(bytes([NAK]))
        return None

    ser.write(bytes([ACK]))
    return response


def extract_params(response: bytes) -> tuple[bytes, int]:
    """Extract parameter bytes and error code from a response.

    Return a (params, error_code) tuple. The error code is the
    last parameter byte; bit 7 indicates an error.
    """
    param_count = response[0]
    params = response[3:3 + param_count]
    error_code = params[-1] if params else 0xFF
    return params, error_code


def read_software_version(
        ser: serial.Serial,
        slave_id: int
) -> str | None:
    """Read and return the amplifier software version string.

    Use command=0, mode=1. Version is BCD-encoded in two bytes:
    high=X0h, low=YZh -> "Ver.X.0YZ".
    """
    block = build_command_block(
        axis=slave_id, command=0, mode=1)
    response = send_and_receive(ser, slave_id, block)
    if response is None:
        return None

    params, error_code = extract_params(response)
    if error_code & 0x80:
        print(f"  Error code: 0x{error_code:02X}")
        return None

    if len(params) >= 3:
        ver_high = params[0]
        ver_low = params[1]
        major = (ver_high >> 4) & 0x0F
        minor_high = ver_high & 0x0F
        minor_low_tens = (ver_low >> 4) & 0x0F
        minor_low_ones = ver_low & 0x0F
        return (
            f"Ver.{major}"
            f".{minor_high}{minor_low_tens}{minor_low_ones}"
        )

    return None


def read_model_name(
        ser: serial.Serial,
        slave_id: int,
        mode: int
) -> str | None:
    """Read a 12-character ASCII model name from the amplifier.

    Use command=0 with the given mode (5=amp, 6=motor).
    """
    block = build_command_block(
        axis=slave_id, command=0, mode=mode)
    response = send_and_receive(ser, slave_id, block)
    if response is None:
        return None

    params, error_code = extract_params(response)
    if error_code & 0x80:
        print(f"  Error code: 0x{error_code:02X}")
        return None

    if len(params) >= 2:
        model_bytes = params[:-1]
        name = model_bytes.decode(
            "ascii", errors="replace"
        ).rstrip("\x00 *")
        return name if name else None

    return None


def main():
    """Read and display amplifier info over RS485."""
    print(f"Port: {PORT}")
    print(f"Baud rate: {BAUDRATE} bps")
    print(f"Slave ID (Pr5.31): {SLAVE_ID}")
    print(f"Protocol: MINAS standard (Pr5.37=0)")
    print(f"Frame: 8N1")
    print()

    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=TIMEOUT,
    )

    try:
        print("Reading amp model...")
        amp_model = read_model_name(ser, SLAVE_ID, mode=5)
        if amp_model:
            print(f"  Amp model: {amp_model}")
        else:
            print("  Amp model: read failed")

        print("Reading motor model...")
        motor_model = read_model_name(ser, SLAVE_ID, mode=6)
        if motor_model:
            print(f"  Motor model: {motor_model}")
        else:
            print("  Motor model: not registered or disconnected")

        print("Reading software version...")
        version = read_software_version(ser, SLAVE_ID)
        if version:
            print(f"  Software version: {version}")
        else:
            print("  Software version: read failed")

    finally:
        ser.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    main()
