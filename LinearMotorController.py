import serial
import time

class LinearMotorController():

    def __init__(self, port: str):
        """
        This funtion initialize serial and connection parameters. In this config, we use 8N1 and MINAS stardard.
        """
        self.ser = serial.Serial(port=port, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=2)
        self.id = 1

        self.ENQ = 0x05 # Enquiry
        self.EOT = 0x04 # End of transmission
        self.ACK = 0x06 # Acknowledgement1
        self.NAK = 0x15 # Negative acknowledgement

    def _build_command(self, command: int, mode: int, params: bytes = b"") -> bytes: # empty bytes
        """
        This funtion build a MINAS standard protocol data block. Axis is 1

        Block layout:
            0x00 | 0x01 | (mode<<4) | command | params | checksum
        """
        param_count = len(params)
        mode_command = ((mode & 0x0F) << 4) | (command & 0x0F) # Mapping mode and command
        block = bytes([param_count, 1, mode_command]) + params

        checksum = sum(block)
        checksum_tc= -sum(block) # complement 
        checksum_tc_mask= -sum(block) & 0xFF # masking

        return block + bytes([checksum_tc_mask])

    def _extract_params(self, response: bytes) -> tuple[bytes, int]:
        """1
        This funtion extract parameter bytes and error code from a response. 
        """
        param_count = response[0]
        params = response[3:3 + param_count]
        error_code = params[-1] if params else 0xFF

        return params, error_code

    def _send_and_receive(self, block: bytes) -> bytes | None:
        """
        This function send a command block and return the response block.

        Execute the RS485 handshake sequence
            1) host->amp: module_byte+ENQ, amp->host: EOT,
            2) host->amp: data block,      amp->host: ACK+ENQ,
            3) host->amp: module_byte+EOT, amp->host: response block,
            4) host->amp: ACK.

        Return the raw response bytes, or None on failure.
        """
        module_byte = 0x80 | (self.id & 0x7F)
        self.ser.reset_input_buffer()
        self.ser.write(bytes([module_byte, self.ENQ]))

        start = time.time()
        eot_received = False

        while time.time() - start < 2:
            data = self.ser.read(1)

            if data and data[0] == self.EOT:
                eot_received =True

                break

        if not eot_received:
            print(" No EOT response from amplifier.")
            return None

        self.ser.write(block)

        ack_data = self.ser.read(2)
        if len(ack_data) < 1:
            print("ACK response timeout.")
            
            return None

        if ack_data[0] == self.NAK:
            print("Received NAK (data error).")

            return None

        if ack_data[0] != self.ACK:
            print(f"Unexpected response: 0x{ack_data[0]:02X}")
            
            return None

        enq_received = (len(ack_data) >= 2 and ack_data[1] == self.ENQ)

        if not enq_received:
            start = time.time()

            while time.time() - start < 2:
                data = self.ser.read(1)

                if data and data[0] == self.ENQ:
                    enq_received = True

                    break

        if not enq_received:
            print("ENQ wait timeout.")

            return None

        self.ser.write(bytes([0x80, self.EOT]))

        first_byte = self.ser.read(1)

        if not first_byte:
            print("Response block receive timeout.")

            return None

        param_count = first_byte[0]
        expected_remaining = param_count + 3
        remaining = self.ser.read(expected_remaining)

        if len(remaining) < expected_remaining:
            print(
                f"  Incomplete response"
                f" (expected: {expected_remaining},"
                f" received: {len(remaining)})."
            )

            return None

        response = first_byte + remaining

        if sum(response) & 0xFF != 0:
            print(f"  Checksum error (sum: 0x{sum(response) & 0xFF:02X}).")
            self.ser.write(bytes([self.NAK]))
            
            return None

        self.ser.write(bytes([self.ACK]))

        return response

    def read_software_version(self) -> str | None:
        """
        This function read and return the amplifier software version string.

        Use command=0, mode=1. Version is BCD-encoded in two bytes:
        high=X0h, low=YZh -> "Ver.X.0YZ".
        """
        block = self._build_command(command=0, mode=1)
        response = self._send_and_receive(block)

        if response is None:
            return None

        params, error_code = self._extract_params(response)

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

    def read_model_name(self) -> str | None:
        """
        This function read a 12-character ASCII model name from the amplifier.

        Use command=0 with the given mode (5=amp, 6=motor).
        """
        block = self._build_command(command=0, mode=5)
        response = self._send_and_receive(block)
        if response is None:
            return None

        params, error_code = self._extract_params(response)

        if error_code & 0x80:
            print(f"  Error code: 0x{error_code:02X}")
            return None

        if len(params) >= 2:
            model_bytes = params[:-1]
            name = model_bytes.decode("ascii", errors="replace").rstrip("\x00 *")
            return name if name else None

        return None

    def read_feedback_pulse_position(self) -> int | None:
        """
        This function read the current feedback pulse counter position.

        Use command=2, mode=2. The value represents absolute position from the power-on origin: negative for reverse, positive for forward.
        """
        block = self._build_command(command=2, mode=2)
        response = self._send_and_receive(block)
        if response is None:
            return None

        params, error_code = self._extract_params(response)
        if error_code & 0x80:
            print(f"  Error code: 0x{error_code:02X}")
            return None

        if len(params) >= 5:
            # 4-byte little-endian signed integer (L, H order)
            position = int.from_bytes(
                params[0:4], byteorder="little", signed=True
            )
            return position

        return None

    def _acquire_execution_rights(self) -> bool:
        """Acquire execution rights for parameter writes.

        Use command=1, mode=7 with param=0x01 (acquire).
        Must be called before writing parameters. Release
        with _release_execution_rights() when done.
        """
        block = self._build_command(
            command=1, mode=7, params=bytes([0x01])
        )
        response = self._send_and_receive(block)
        if response is None:
            return False

        params, error_code = self._extract_params(response)
        if error_code & 0x80:
            print(f"  Execution rights acquire failed: "
                  f"0x{error_code:02X}")
            return False
        return True

    def _release_execution_rights(self) -> bool:
        """Release execution rights after parameter writes.

        Use command=1, mode=7 with param=0x00 (release).
        """
        block = self._build_command(
            command=1, mode=7, params=bytes([0x00])
        )
        response = self._send_and_receive(block)
        if response is None:
            return False

        params, error_code = self._extract_params(response)
        if error_code & 0x80:
            print(f"  Execution rights release failed: "
                  f"0x{error_code:02X}")
            return False
        return True

    def _write_parameter(
            self, category: int, number: int, value: int
    ) -> bool:
        """Write a single parameter value (command=7, mode=1).

        Temporarily change a parameter in RAM. Use EEPROM write
        (mode=2) to persist. Value is sent as signed 32-bit
        little-endian.
        """
        value_bytes = value.to_bytes(
            4, byteorder="little", signed=True
        )
        param_data = bytes([category, number]) + value_bytes
        block = self._build_command(
            command=7, mode=1, params=param_data
        )
        response = self._send_and_receive(block)
        if response is None:
            return False

        params, error_code = self._extract_params(response)
        if error_code & 0x80:
            print(f"  Parameter write failed: "
                  f"0x{error_code:02X}")
            return False
        return True

    def _read_parameter(
            self, category: int, number: int
    ) -> int | None:
        """Read a single parameter value (command=7, mode=0).

        Return the 32-bit signed value, or None on error.
        """
        param_data = bytes([category, number])
        block = self._build_command(
            command=7, mode=0, params=param_data
        )
        response = self._send_and_receive(block)
        if response is None:
            return None

        params, error_code = self._extract_params(response)
        if error_code & 0x80:
            print(f"  Parameter read failed: "
                  f"0x{error_code:02X}")
            return None

        if len(params) >= 5:
            value = int.from_bytes(
                params[0:4], byteorder="little", signed=True
            )
            return value
        return None

    def move_speed(self, speed: int, duration: float) -> bool:
        """Run the motor at a given speed for a duration.

        Set internal speed command (Pr3.04), wait, then stop.
        Require Pr0.01=1 (speed control, saved in EEPROM)
        and SRV-ON from hardware X4 connector.

        speed -- speed in r/min (positive=forward, negative=reverse)
        duration -- run time in seconds
        """
        if not self._acquire_execution_rights():
            return False

        try:
            self._write_parameter(3, 4, speed)
            print(f"  Running at {speed} r/min"
                  f" for {duration}s...")
            time.sleep(duration)
            self._write_parameter(3, 4, 0)
        finally:
            self._release_execution_rights()

        return True

    def move_relative(self, pulse_offset: int,
                      speed: int = 50,
                      tolerance: int = 500,
                      timeout: float = 10.0) -> int | None:
        """Move the motor by pulse_offset from current position.

        Set internal speed via Pr3.04 and monitor feedback
        pulses until the target is reached within tolerance.
        Require Pr0.01=1 (speed control) and SRV-ON.

        pulse_offset -- displacement in encoder pulses
        speed -- speed in r/min (1~500, sign auto-set)
        tolerance -- acceptable error in pulses
        timeout -- maximum wait time in seconds

        Return the final position, or None on failure.
        """
        start_pos = self.read_feedback_pulse_position()
        if start_pos is None:
            return None

        target = start_pos + pulse_offset
        direction = 1 if pulse_offset > 0 else -1
        abs_speed = min(abs(speed), 500)
        print(f"  Start={start_pos}, Target={target}")

        if not self._acquire_execution_rights():
            return None

        try:
            self._write_parameter(3, 4, direction * abs_speed)

            start_time = time.time()
            while time.time() - start_time < timeout:
                current = self.read_feedback_pulse_position()
                if current is None:
                    break

                remaining = (target - current) * direction
                # Stop when reached or passed the target.
                if remaining <= tolerance:
                    break

                time.sleep(0.01)

            self._write_parameter(3, 4, 0)
        finally:
            self._release_execution_rights()

        time.sleep(0.3)
        final = self.read_feedback_pulse_position()
        print(f"  Final={final}")
        return final


def main():
    """
    This function is scenario for simple testing
    """
    lmc = LinearMotorController("/dev/ttyUSB0")

    model = lmc.read_model_name()
    print(f"Model name is {model}")

    version = lmc.read_software_version()
    print(f"Software version is {version}")

    pulse_position = lmc.read_feedback_pulse_position()
    print(f"Feedback pulse position is {pulse_position}")

    print("\n--- Motor move test ---")

    while True:
        print("Moving +5000 pulses...")
        lmc.move_relative(40000, speed=100)
        print("Moving -5000 pulses...")
        time.sleep(1)


        lmc.move_relative(-40000, speed=100)
        final = lmc.read_feedback_pulse_position()
        print(f"Final position: {final}")
        time.sleep(1)


if __name__ == "__main__":
    main()