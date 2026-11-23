"""
Circuit-AI Robot Driver (Dum-E)
===============================
Handles physical Serial communication with the robotic arm.
"""

import time
import logging

# Mock Serial for when hardware isn't connected
class MockSerial:
    def __init__(self, port, baud):
        self.is_open = True
        print(f"[Dum-E Driver] Connecting to {port} at {baud}...")

    def write(self, data: bytes):
        print(f"[Dum-E Driver] >> SENT: {data.decode().strip()}")

    def readline(self) -> bytes:
        return b"ok\n"

    def close(self):
        print("[Dum-E Driver] Disconnected.")

class RobotDriver:
    def __init__(self, port="/dev/ttyUSB0", baud=115200):
        try:
            import serial
            self.conn = serial.Serial(port, baud, timeout=1)
        except ImportError:
            logging.warning("PySerial not found, using Mock Driver.")
            self.conn = MockSerial(port, baud)
        except Exception as e:
            logging.warning(f"Hardware connection failed: {e}. Using Mock Driver.")
            self.conn = MockSerial(port, baud)

    def send_gcode(self, gcode_line: str):
        """Sends a single G-Code command and waits for ack"""
        if not gcode_line.strip() or gcode_line.startswith(";"):
            return # Skip comments/empty
        
        cmd = f"{gcode_line}\n".encode('utf-8')
        self.conn.write(cmd)
        
        # Simple ack logic (Marlin usually sends 'ok')
        # In production, we'd have a timeout loop here
        time.sleep(0.01) 
        response = self.conn.readline().decode().strip()
        # logging.info(f"RECV: {response}")
        return response

    def run_program(self, gcode_program: str):
        """Streams a full program to the robot"""
        lines = gcode_program.split('\n')
        print(f"[Dum-E Driver] Starting Program ({len(lines)} lines)...")
        
        for line in lines:
            self.send_gcode(line)
            
        print("[Dum-E Driver] Program Complete.")

    def emergency_stop(self):
        """Hardware Kill Switch"""
        print("[Dum-E Driver] !!! EMERGENCY STOP TRIGGERED !!!")
        self.conn.write(b"M112\n") # Marlin Emergency Stop
        self.conn.close()

if __name__ == "__main__":
    driver = RobotDriver()
    driver.send_gcode("G28 ; Home All")
    driver.send_gcode("G0 X10 Y10 Z5")
