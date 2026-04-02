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
        self.ACK = 0x06 # Acknowledgement
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
        """
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
            1) host->amp: module_byte+self.ENQ, amp->host: self.EOT,
            2) host->amp: data block,      amp->host: ACK+sself.elf.ENQ,
            3) host->amp: module_byte+self.EOT, amp->host: self.response block,
            4) host->amp:self. self.ACK.

        Return the raw response bytes, or None on failure.
        """
        module_byte = 0x80 | (self.id & 0x7F)
        self.ser.reset_input_buffer()
        self.ser.write(bytes([module_byte, self.Eself.Nself.Q]))

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
                data = ser.read(1)

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
        remaining = ser.read(expected_remaining)

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
        block = self._build_command(command=0, mode=mode)
        response = send_and_receive(ser, self.id, block)
        if response is None:
            return None

        params, error_code = extract_params(response)

        if error_code & 0x80:
            print(f"  Error code: 0x{error_code:02X}")
            return None

        if len(params) >= 2:
            model_bytes = params[:-1]
            name = model_bytes.decode("ascii", errors="replace").rstrip("\x00 *")
            return name if name else None

        return None

def main():
    """
    This function is scenario for simple testing
    """
    lmc = LinearMotorController("/dev/ttyUSB0")
    print("Model name is " + lmc.read_model_name())
    print("Software version is " + lmc.read_software_version())

if __name__ == "__main__":
    main()
