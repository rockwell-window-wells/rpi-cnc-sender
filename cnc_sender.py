#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 11 10:49:28 2024

@author: Ryan.Larson
"""

import tkinter as tk
import serial
from serial.tools import list_ports
import time
import threading
import pickle
from queue import Queue
from enum import Enum
import logging
import datetime
import re

start_datetime = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))

old_tool_z = None

# Logging setup
logging.basicConfig(
    filename=f"logs/{start_datetime}.log",
    encoding="utf-8",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    style="%",
    datefmt="%Y-%m-%d %H:%M:%S"
    )

with open('config.pkl', 'rb') as f:
    config = pickle.load(f)
    
baud_rate = 115200
gcode_file_path = config['set1_paths']

# Set up serial connection
ports = list_ports.comports()
# if ports:
#     print(f'Ports available: {ports}')
#     serial_port = ports[0].device
#     dummy_mode = False
print(f'Ports available: {ports}')
if ports:
    serial_port = ports[0].device
    try:
        ser = serial.Serial(serial_port, baud_rate, timeout=1)
        dummy_mode = False
        print("Serial connection established.")
    except serial.SerialException:
        print("Error: Unable to open serial connection. Entering dummy mode.")
        dummy_mode = True
        ser = None
else:
    print('No serial ports available. Entering dummy mode')
    dummy_mode = True
    serial_port = '/dev/ttyUSB0'
time.sleep(2)   # Wait for GRBL to initialize

# gcode_file_path = config['gcode_file_path']

# # Initialize the serial connection
# if not dummy_mode:
#     ser = serial.Serial(serial_port, baud_rate)
#     print("Initializing serial connection")
# else:
#     ser = None
#     print("Initializing serial connection (dummy mode)")
# time.sleep(2)  # Wait for GRBL to initialize

# Send an initial command to wake up GRBL
if not dummy_mode:
    ser.write(b"\r\n\r\n")
    print("Sending command to wake GRBL")    
    time.sleep(2)
    ser.flushInput()

class MachineState(Enum):
    READY = "Ready"
    RUNNING = "Running"
    PAUSED = "Paused"
    STOPPED = "Stopped"
    PROBING1 = "Probing Step 1"
    PROBING2 = "Probing Step 2"
    
class Machine:
    def __init__(self):
        self.state = MachineState.READY
    
    def transition(self, new_state):
        logging.info(f"State changed from {self.state} to {new_state}")
        self.state = new_state
        print(f"State changed to {self.state.value}")
        
    def get_state(self):
        return self.state
    
# Initialize machine object
machine = Machine()

def exit_fullscreen(event=None):
    root.attributes('-fullscreen', False)  # Exit full-screen

def send_gcode_and_wait(command, wait_for_response=True, probing=False):
    """Send a G-code command and wait for a meaningful response if required."""
    global ser
    logging.info(f"About to write serial command {command}")
    ser.write((command + "\n").encode())  # Send command
    logging.info(f"Sent serial command {command}")
    time.sleep(0.1)  # Give GRBL a moment to process

    if not wait_for_response:
        return []

    response = []
    while True:
        line = ser.readline().decode().strip()  # Read line-by-line
        if line:
            response.append(line)
            if probing:
                if "PRB" in line:
                    break
            else:
                if "ok" in line or "error" in line or "ALARM" in line or "PRB" in line:
                    break  # Stop when we get a final response (ok, error, probe data, alarm)
    
    return response

def get_z_position(response):
    for line in response:
        if "PRB" in line:
            match = re.search(r"PRB:[-?\d.]+,[-?\d.]+,([-?\d.]+)", line)
            if match:
                    z_position = float(match.group(1))
                    print(f"Confirmed probe hit at Z: {z_position:.4f} mm")
                    return z_position
    return None

def probe_tool():
    """Probes the tool and returns its Z position."""
    global ser
    # Probe downward (adjust Z depth and feed rate as needed)
    logging.info("About to attempt to send probe command.")
    response = send_gcode_and_wait("G38.2 Z-50 F200", probing=True)
    logging.info("Sent probe command")
    print(f"First probe response: {response}")
    
    z_position = get_z_position(response)
    
    # Back off and touch off probe again with a slower feed rate
    response = send_gcode_and_wait("G0 Z10")
    print(f"Backing off response: {response}")
    response = send_gcode_and_wait("G38.2 Z-50 F100", probing=True)
    print(f"Second probe response: {response}")
    
    z_position = get_z_position(response)
    return z_position

def apply_tool_offset(reference_z):
    """Probes the new tool and applies compensation based on reference Z."""
    global ser
    new_tool_z = probe_tool()
    
    if new_tool_z is None:
        print("Error: Could not retrieve new tool Z position.")
        return
    
    # Compute tool length difference
    offset = reference_z - new_tool_z
    print(f"Tool length difference: {offset:.4f} mm")

    # Apply compensation (G43 H1 can be used for tool length offsets)
    send_gcode_and_wait(f"G43 Z{offset:.4f}")  # Apply tool offset

    print("Tool length compensation applied.")

def probe_old_tool(dummy_mode):
    """Use a probe routine to get the current tool length"""
    global old_tool_z
    machine.transition(MachineState.PROBING1)
    
    xprobe = -21.550
    yprobe = -350.500
    zprobestart = -50.000
    spoilboard_offset = -20.0
    
    xtoolchange = -100.000
    ytoolchange = -250.000
    ztoolchange = 0.000
    
    if not dummy_mode:
        logging.info("Attempting to start first probe for tool change")
        send_gcode_and_wait("!")                         # Immediate feed hold
        logging.info("Sent feed hold command")
        send_gcode_and_wait("M5")                        # Stop spindle
        logging.info("Sent stop spindle command")
        send_gcode_and_wait("G90")                       # Absolute positioning
        logging.info("Set absolute positioning")
        send_gcode_and_wait(f"G0 X{xprobe} Y{yprobe}")   # Move to probe ready position
        logging.info("Sent Gcode to move to probe XY position")
        send_gcode_and_wait("G91")                       # Relative positioning
        logging.info("Set relative positioning")
        
        old_tool_z = probe_tool()
        
        # Move the toolhead to the tool change position
        send_gcode_and_wait("G90")
        send_gcode_and_wait(f"G0 X{xtoolchange} Y{ytoolchange} Z{ztoolchange}")
        
        # Pause and wait for the user to change the tool
        send_gcode_and_wait("!")
    else:
        print("Moving to probe position...")
        print("Probing old tool...")
        print("Old tool z at -85.0 mm")
        
    machine.transition(MachineState.PROBING2)
    update_button_visibility()
    root.update_idletasks()
    
def probe_new_tool(dummy_mode):
    """Use a probe routine to get the new tool length"""
    global old_tool_z
    global ser
    xprobe = -21.550
    yprobe = -350.500
    
    if not dummy_mode:
        send_gcode_and_wait("!")                         # Immediate feed hold
        send_gcode_and_wait("M5")                        # Stop spindle
        send_gcode_and_wait("G90")                       # Absolute positioning
        send_gcode_and_wait(f"G0 X{xprobe} Y{yprobe}")   # Move to probe ready position
        send_gcode_and_wait("G91")                       # Relative positioning
        
        apply_tool_offset(old_tool_z)
        time.sleep(5)
        ser.write(b"$H\n") # GRBL home command
    else:
        print("Probing new tool...")
        print("Applying tool offset...")
        print("Homing...")
        
    machine.transition(MachineState.READY)
    update_button_visibility()
    root.update_idletasks()

def pause_resume(dummy_mode):
    """Toggle pause and resume functionality."""
    if machine.get_state() == MachineState.RUNNING:
        machine.transition(MachineState.PAUSED)
        if not dummy_mode:
            ser.write(b"!") # GRBL pause command
        status_label.config(text=f"{machine.state.name}", fg="black")
        pause_button.config(text="Resume", bg="blue", activebackground="blue")
    elif machine.get_state() == MachineState.PAUSED:
        machine.transition(MachineState.RUNNING)
        if not dummy_mode:
            ser.write(b"~")     # GRBL resume command
        status_label.config(text=f"{machine.state.name}", fg="black")
        pause_button.config(text="Pause", bg="orange", activebackground="orange")
    update_button_visibility()
    root.update_idletasks()

def stop_program(dummy_mode):
    """Send the GRBL stop program command."""
    machine.transition(MachineState.STOPPED)

    if not dummy_mode:
        ser.write(b"!")  # Immediate feed hold
        ser.flush()
        ser.write(b"M5\n")  # Stop spindle
        ser.flush()
        ser.write(b"\x18\n")  # GRBL reset
        ser.flush()
        ser.reset_input_buffer()
        ser.reset_output_buffer()

    status_label.config(text=f"{machine.state.name}", fg="black")
    update_button_visibility()
    pause_button.config(text="Pause", bg="orange", activebackground="orange")
    root.update_idletasks()

def home_machine(dummy_mode):
    """Send the GRBL home command."""
    if not dummy_mode:
        ser.write(b"$H\n") # GRBL home command
        ser.flush()
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    machine.transition(MachineState.READY)
    status_label.config(text=f"{machine.state.name}", fg="black")
    update_button_visibility() # Ensure the Home button is hidden after homing
    root.update_idletasks()
    
    # Re-enable the Set 1/Set 2 buttons
    set1_button.config(state="normal")
    set2_button.config(state="normal")
    
def choose_set1_paths():
    """Choose which toolpaths to run."""
    global gcode_file_path
    gcode_file_path = config['set1_paths']
    
    # Toggle button state
    if machine.state is not MachineState.RUNNING:
        logging.info("Toolpath selection: SET 1")
        set1_button.config(relief="sunken", bg="green", fg="white")
        set2_button.config(relief="raised", bg="lightgray", fg="black")
        all_button.config(relief="raised", bg="lightgray", fg="black")
    
def choose_set2_paths():
    """Choose which toolpaths to run."""
    global gcode_file_path
    gcode_file_path = config['set2_paths']
  
    # Toggle button state
    if machine.state is not MachineState.RUNNING:
        logging.info("Toolpath selection: SET 2")
        set2_button.config(relief="sunken", bg="green", fg="white")
        set1_button.config(relief="raised", bg="lightgray", fg="black")
        all_button.config(relief="raised", bg="lightgray", fg="black")

def choose_all_paths():
    """Choose which toolpaths to run."""
    global gcode_file_path
    gcode_file_path = config['all_paths']

    # Toggle button state
    if machine.state is not MachineState.RUNNING:
        logging.info("Toolpath selection: ALL")
        all_button.config(relief="sunken", bg="green", fg="white")
        set1_button.config(relief="raised", bg="lightgray", fg="black")
        set2_button.config(relief="raised", bg="lightgray", fg="black")
    
def update_button_visibility():
    """Update the visibility of the Home button based on the machine state."""
    if machine.get_state() == MachineState.STOPPED:
        run_button.grid_forget()
        pause_button.grid_forget()
        stop_button.grid_forget()
        home_button.grid(row=1, column=1, padx=10, pady=20) # Show Home button
        tool_change_1_button.grid_forget()
        tool_change_2_button.grid_forget()
        set1_button.grid_forget()
        set2_button.grid_forget()
        all_button.grid_forget()
    elif machine.get_state() == MachineState.PROBING2:
        run_button.grid_forget()
        pause_button.grid_forget()
        stop_button.grid_forget()
        home_button.grid_forget()
        tool_change_1_button.grid_forget()
        tool_change_2_button.grid(row=1, column=1, padx=10, pady=20)
        set1_button.grid_forget()
        set2_button.grid_forget()
        all_button.grid_forget()
    else:
        run_button.grid(row=0, column=0, padx=20)
        pause_button.grid(row=0, column=1, padx=20)
        stop_button.grid(row=1, column=0, padx=20)
        home_button.grid_forget() # Hide Home button when not in STOPPED state
        tool_change_1_button.grid(row=1, column=1, padx=20)
        tool_change_2_button.grid_forget()
        set1_button.grid(row=0, column=0, padx=10)
        set2_button.grid(row=0, column=1, padx=10)
        all_button.grid(row=0, column=2, padx=10)


def run_gcode(dummy_mode):
    """Send Gcode commands from the file to the CNC router."""
    def gcode_thread():
        def send_line(line):
            #if line.strip() and not line.startswith(';'):
            if line.strip():
                # Send G-code line
                ser.write(line)
                logging.info(f"Sent: {line.strip()}")
                
                while True:
                    # Wait for response
                    wait_time = 0.0
                    response = ser.readline().decode('utf-8').strip()
                    if response == 'ok':
                        # Proceed to next line
                        logging.info(f"Response: {response}")
                        break
                    elif response.startswith('error'):
                        logging.error(f"Response: {response}")
                        break
                    else:
                        time.sleep(0.05)
                        wait_time += 0.05
                        logging.info(f"Waiting for GRBL response for {wait_time} seconds...")
        
        try:
            logging.info("TOOLPATH START")
            root.after(0, lambda: [set1_button.config(state="disabled"), set2_button.config(state="disabled"), all_button.config(state="disabled")])
            # Unlock the machine
            if not dummy_mode:
                # ser.write(b"$H\n") # Home the machine
                send_line(b"$H\n")
                ser.flush()   
            status_label.config(text=f"{machine.state.name}", fg="black")
            current_line = None
        
            with open(gcode_file_path, 'r') as file:
                for i,line in enumerate(file):
                    if machine.get_state() == MachineState.STOPPED:
                        return
                    
                    # Store the current line to allow resuming from this point
                    current_line = line
                    
                    # Pause the loop if machine is paused
                    first_iteration = True
                    while machine.get_state() == MachineState.PAUSED:
                        if current_line:
                            if first_iteration:
                                status_label.config(text=f"Paused on line {i+1}: {current_line}", fg="black")
                                logging.info(f"Paused on line {i+1}: {current_line}")
                                first_iteration = False
                            time.sleep(0.1)
                            if machine.get_state() == MachineState.RUNNING:
                                status_label.config(text=f"Resumed on line {i+1}: {current_line}", fg="black")
                                logging.info(f"Resumed on line {i+1}: {current_line}")
                                break   # Exit the while loop when the machine resumes
                    
                    # Quick check for mismatch in what gets sent to the buffer
                    if current_line != line:
                        logging.error("Current line does not equal the line getting sent to the buffer")
                    
                    send_line(line.encode('utf-8'))
                    
            if machine.get_state() == MachineState.RUNNING:
                if not dummy_mode:
                    # ser.write(b"M5\n") # Stop spindle
                    send_line(b"M5\n") # Stop spindle
                    ser.flush()
                    # ser.write(b"$H\n") # Home the machine
                    send_line(b"$H\n") # Home the machine
                    ser.flush()
                    send_line(b"\x18\n") # GRBL reset
                    ser.flush()
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    status_label.config(text=f"{machine.state.name}", fg="black")
                else:
                    status_label.config(text=f"{machine.state.name}", fg="black")

        except FileNotFoundError:
            status_label.config(text=f'Error: File not found at {gcode_file_path}')
            logging.exception(f"Error: File not found at {gcode_file_path}")
        except Exception as e:
            status_label.config(text=f'Error reading file: {e}')
            logging.exception(f"Error reading file: {e}")
        finally:
            root.update_idletasks()
            root.after(0, lambda: [set1_button.config(state="normal"), set2_button.config(state="normal"), all_button.config(state="normal")])
            if machine.get_state() == MachineState.STOPPED:
                logging.info("Ending toolpath due to Stop")
            else:
                logging.info("TOOLPATH COMPLETE")
                time.sleep(2)
                ser.flush()
            machine.transition(MachineState.READY)
            status_label.config(text=f"{machine.state.name}", fg="black")
    
    ser.flush()
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    machine.transition(MachineState.RUNNING)
    update_button_visibility()
    threading.Thread(target=gcode_thread, daemon=True).start()
    
# GUI setup
root = tk.Tk()
root.title("Material Test Sample CNC Controller")

root.geometry("")
root.resizable(False, False)

# Frame for the buttons, making them left and right aligned
button_frame = tk.Frame(root)
button_frame.pack(expand=True, padx=10, pady=10)  # Add space above buttons for layout

# Run Button
run_button = tk.Button(
    button_frame,
    text="Run",
    command=lambda: run_gcode(dummy_mode),
    font=('Helvetica', 18, "bold"),
    width=20,
    height=5,)
run_button.grid(row=0, column=0, padx=20)  # Padding for spacing

# Pause/Resume Button
pause_button = tk.Button(
    button_frame,
    text="Pause",
    command=lambda: pause_resume(dummy_mode),
    font=('Helvetica', 18),
    width=20,
    height=5,
    bg="orange",
    fg="black"
)
pause_button.grid(row=0, column=1, padx=20)

# Stop button
stop_button = tk.Button(
    button_frame,
    text="Stop",
    command=lambda: stop_program(dummy_mode),
    font=('Helvetica', 18),
    width=20,
    height=5,
    bg="red",
    fg="white"
)
stop_button.grid(row=1, column=0, padx=20)

# Home button
home_button = tk.Button(
    button_frame,
    text="Home",
    command=lambda: home_machine(dummy_mode),
    font=('Helvetica', 18),
    width=20,
    height=5,
    bg="blue",
    fg="white"
)
home_button.grid(row=1, column=1, padx=20)

# Tool change step 1 button
tool_change_1_button = tk.Button(
    button_frame,
    text="Tool Change",
    command=lambda: probe_old_tool(dummy_mode),
    font=('Helvetica', 18),
    width=20,
    height=5,
)
tool_change_1_button.grid(row=1, column=1, padx=20)

# Tool change step 2 button
tool_change_2_button = tk.Button(
    button_frame,
    text="Probe New Tool",
    command=lambda: probe_new_tool(dummy_mode),
    font=('Helvetica', 18),
    width=20,
    height=5,
)
tool_change_2_button.grid(row=1, column=1, padx=20)


button_frame.grid_propagate(True)

# Frame for Set 1 and Set 2 buttons
set_button_frame = tk.Frame(root)
set_button_frame.pack(pady=5)  # Add small space between this frame and button_frame

# Set 1 Button
set1_button = tk.Button(
    set_button_frame,
    text="Set 1",
    command=lambda: choose_set1_paths(),
    font=('Helvetica', 12),
    width=10,
    height=2,
)
set1_button.grid(row=0, column=0, padx=10)

# Set 2 Button
set2_button = tk.Button(
    set_button_frame,
    text="Set 2",
    command=lambda: choose_set2_paths(),
    font=('Helvetica', 12),
    width=10,
    height=2,
)
set2_button.grid(row=0, column=1, padx=10)

# All Button
all_button = tk.Button(
    set_button_frame,
    text="All",
    command=lambda: choose_all_paths(),
    font=('Helvetica', 12),
    width=10,
    height=2,
)
all_button.grid(row=0, column=2, padx=10)

set1_button.config(relief="sunken", bg="green", fg="white")
set2_button.config(relief="raised", bg="lightgray", fg="black")
all_button.config(relief="raised", bg="lightgray", fg="black")

update_button_visibility()

# Status label to display the current line being sent
status_label = tk.Label(root, text="", font=('Helvetica', 12))
status_label.config(text=f"{machine.state.name}", fg="black")
status_label.pack(pady=20)

root.after(100, lambda: root.attributes('-fullscreen', True))
root.bind("<Escape>", exit_fullscreen)
root.mainloop()
