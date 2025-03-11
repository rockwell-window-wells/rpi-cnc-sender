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

start_datetime = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))

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
    
# Set up serial connection
ports = list_ports.comports()
if ports:
    print(f'Ports available: {ports}')
    serial_port = ports[0].device
    dummy_mode = False
else:
    print('No serial ports available. Entering dummy mode')
    dummy_mode = True
    serial_port = '/dev/ttyUSB0'

baud_rate = 115200
gcode_file_path = config['set1_paths']
# gcode_file_path = config['gcode_file_path']

# Initialize the serial connection
if not dummy_mode:
    ser = serial.Serial(serial_port, baud_rate)
    print("Initializing serial connection")
else:
    ser = None
    print("Initializing serial connection (dummy mode)")
time.sleep(2)  # Wait for GRBL to initialize

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
    PROBING = "Probing"
    
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

def send_gcode(ser, command):
    """Send a G-code command and return response."""
    ser.write((command + '\n').encode())
    time.sleep(0.1)
    return ser.readlines()

def set_tool_length(dummy_mode):
    """Use a probe routine to set the tool length"""
    machine.transition(MachineState.PROBING)
    
    xprobe = -21.550
    yprobe = -350.500
    zprobestart = -50.000
    spoilboard_offset = -20.0
    
    if not dummy_mode:
        send_gcode(ser, "!")                                         # Immediate feed hold
        send_gcode(ser, "M5")                                        # Stop spindle
        send_gcode(ser, "G90")                                       # Absolute positioning
        send_gcode(ser, f"G0 X{xprobe} Y{yprobe} Z{zprobestart}")    # Move to probe ready position
        send_gcode(ser, "G91")                                       # Relative positioning
        probe_response = send_gcode(ser, "G38.2 Z-50 F100")          # Execute probing within 50 mm
        
        machine_position = send_gcode(ser, "?")
        
        
        
        
        
        # ser.write(b"!")  # Immediate feed hold
        # ser.flush()
        # ser.write(b"M5\n")  # Stop spindle
        # ser.flush()
        # ser.write(b"G90")   # Absolute positioning
        # ser.flush()
        # ser.write(f"G0 X{xprobe} Y{yprobe} Z{zprobestart}\n".encode())
        # ser.flush()
        # ser.write(b"G91")   # Relative positioning
        # ser.flush()
        # ser.write(b"G38.2 Z-50 F100")
        # ser.flush()
        
    

def pause_resume(dummy_mode):
    """Toggle pause and resume functionality."""
    if machine.get_state() == MachineState.RUNNING:
        machine.transition(MachineState.PAUSED)
        if not dummy_mode:
            ser.write(b"!") # GRBL pause command
            # machine_position = send_gcode("?")
            # status_label.config(text=f"{machine_position}", fg="black")
            # time.sleep(10)
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
        set1_button.grid_forget()
        set2_button.grid_forget()
        all_button.grid_forget()
    else:
        run_button.grid(row=0, column=0, padx=20)
        pause_button.grid(row=0, column=1, padx=20)
        stop_button.grid(row=1, column=0, padx=20)
        home_button.grid_forget() # Hide Home button when not in STOPPED state
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
                    
                    # if line.strip() and not line.startswith(';'):
                    #     # Send G-code line
                    #     ser.write(line.encode('utf-8'))
                    #     logging.info(f"Sent: {line.strip()}")
                        
                    #     while True:
                    #         # Wait for response
                    #         wait_time = 0.0
                    #         response = ser.readline().decode('utf-8').strip()
                    #         if response == 'ok':
                    #             # Proceed to next line
                    #             logging.info(f"Response: {response}")
                    #             break
                    #         elif response.startswith('error'):
                    #             logging.error(f"Response: {response}")
                    #             break
                    #         else:
                    #             time.sleep(0.05)
                    #             wait_time += 0.05
                    #             logging.info(f"Waiting for GRBL response for {wait_time} seconds...")
                    
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
