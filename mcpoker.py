#!/usr/bin/python3

import serial
import sys
import termios
import fcntl
import os
from time import sleep
import csv

arg_list = sys.argv[1:]
print('arg list:',arg_list)
arg_dict=[]

for a in arg_list:
  s=a.split('=')
  arg_dict.append({s[0]:s[1]})

def get_value_by_key(dict_list,key):
  for entry in dict_list:
    v = entry.get(key)
    if v is not None:
      return v
  return None

print(f'arg_dict: {arg_dict}')

out_file_name = get_value_by_key(arg_dict,'out')
model_name = get_value_by_key(arg_dict,'model')
start_address_str = get_value_by_key(arg_dict,'start')
end_address_str = get_value_by_key(arg_dict,'end')
serial_str = get_value_by_key(arg_dict,'serial')

if serial_str is None: serial_str = '/dev/ttyUSB0'

if out_file_name is None: out_file_name = 'default.csv'

if start_address_str is None:
  start_address = 0x30000000
else:
  start_address = int(start_address_str,16)

if end_address_str is None:
  end_address = 0x40000000
else:
  end_address = int(end_address_str,16)


# MC-101 ID=5E 03, MC-707 ID=5D 03
# we assume the MC-707 as default
model_id = 0x5D

# add support for more if needed
if model_name is not None:
  model_name = model_name.lower()
  print(f'model name lowercase: {model_name}')
  if model_name == 'mc101' or model_name == 'mc-101':
    model_id = 0x5E
  elif model_name == 'mc707' or model_name == 'mc-707':
    model_id = 0x5D
  else:
    print('Unsupported model name, please specify MC-101 or MC-707, using model ID for MC-707')
    

track = 1
clip = 1
base_address = 0x30000000

print(f'model_id = {model_id:02X}')
print(f'output file name: {out_file_name}')
print(f'poke start address hex: {start_address:08X}')
print(f'poke end address hex: {end_address:08X}')
print(f'general operation track/clip/base_address T={track}, C={clip}, Base=0x{base_address:08X}')
print(f'serial port: {serial_str}')

port = serial.Serial(serial_str, baudrate=31250, timeout=3.0)




def init_nonblocking_input():
    fd = sys.stdin.fileno()

    # Save the original terminal settings
    original_termios = termios.tcgetattr(fd)
    new_termios = termios.tcgetattr(fd)

    # Turn off canonical mode and echo
    new_termios[3] &= ~(termios.ICANON | termios.ECHO)
    termios.tcsetattr(fd, termios.TCSANOW, new_termios)

    # Set stdin to non-blocking
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    return original_termios

def restore_input(original_termios):
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSANOW, original_termios)

def read_key():
    try:
        return sys.stdin.read(1)
    except IOError:
        return None



# sends a list of values (int)
# through the serial port
# represented by the object port
def midi_tx(data):
  arr = bytes(data)
  port.write(data)
  port.flush()


rxbuf = []

# an example of a data packet
# data = [0xF0, 0x41, 0x10, 0x00,0x00,0x00,0x5D, 0x11, 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x4, 0x00, 0xF7]

def intlist_to_hex_str(intlist):
  return f"{' '.join(f'{n:02X}' for n in intlist)}"

def limit_to_printable_ascii(i):
  if i >= 0x20 and i < 0x7F:
    return i
  else:
    return ord('.')

def intlist_to_str(intlist):
  return f"{''.join(f'{chr(limit_to_printable_ascii(n))}' for n in intlist)}"


# basic reception function
# please be aware that it is just a test function
# it doesn't really parse the received data
# it doesn't even handle the MIDI state machines
# (it just filters out F8 and FE)
# so errors happen sometimes if for example
# more than one messages is received from the MIDI serial port
def roland_response_wait(t=0.5):
  rxbuf = []
  sleep(t)
  while port.in_waiting > 0:
    rxed_b = port.read()
    rxed = int.from_bytes(rxed_b,byteorder='little')
    # ignore timing messages
    if rxed == 0xF8: continue
    if rxed == 0xFE: continue
    rxbuf.append(rxed)
  if( len(rxbuf) > 0 ):
    print(f"response raw: {' '.join(f'{n:02X}' for n in rxbuf)}")
    print(f"   response len={len(rxbuf)}")
  else:
    print("no response")
    return []
  if( len(rxbuf) < 14 ):
    print(f"response too short: {len(rxbuf)}")
    print(f"  contents: {intlist_to_hex_str(rxbuf)}")
    return []
  
  outbuf = []
  try:
    for i in range(12,len(rxbuf)-2):
      outbuf.append(rxbuf[i])
    print(f"extracted response: {intlist_to_hex_str(outbuf)}")
    print(f"   len={len(outbuf)}")
  except:
    print(f"exception happens")
  return outbuf
  
# computes checksum according to the documentation
# substitutes the checksum byte in the provided input buffer data_in
# returns the input buffer but with the checksum added @ [len-2]
def compute_checksum(data_in):
  try:
    if(len(data_in) < 14):
      print(f"compute_checksum: too short, len={ len(data_in) }")
      return data_in
    s = 0
    checksum_idx = len(data_in)-2
    for idx in range(8,checksum_idx):
      s += data_in[idx]
    remainder = s % 128
    checksum = 128 - remainder
    data_in[checksum_idx] = checksum
  except Exception as e:
    print(f'compute_checksum exception: {str(e)}')
  return data_in

# This is a rather raw request function to read the internal params
# I used it to create dumps
# The return data is not handled in any way
# The count parameter (i.e. the requested data length to be returned)
# is very poorly supported, so just don't use anything
# longer than 127 bytes, so that you don't exceed
# the maximum value of 127 allowed as MIDI data
# The musical instruments just don't use addresses with
# the bytes > 127, so you are safe as long as you provide
# a valid address
def roland_request(address, count):
  rq = [0xF0, 0x41, 0x10, 0x00,0x00,0x00,model_id, 0x11,\
    (address >> 24)&0xFF,(address >> 16)&0xFF,(address >> 8)&0xFF,address&0xFF,\
    0,0,0,count&0xFF,\
    0x00, 0xF7]
  rq = compute_checksum(rq)
  print(f"request raw:  {intlist_to_hex_str(rq)}")
  midi_tx(rq)
  return rq


def rq1_read_param(address,count=1):
  print(f'rq1_read_param 0x{address:08X}, count {count:02X}')
  roland_request(address,count)
  response = roland_response_wait(0.4)
  
  if len(response) < count: return None
  
  value = None
  
  if count == 1:
    value = response[0]
  elif count == 2:
    value = ((response[0]&0xF)<<4) | (response[1]&0xF)
  elif count == 4:
    value = ((response[0]&0xF)<<12) | ((response[1]&0xF)<<8) | ((response[2]&0xF)<<4) | (response[3]&0xF)
  else:
    value = None
  
  return value



def dt1_set_param(address,value,size):
  dt = [0xF0, 0x41, 0x10, 0x00,0x00,0x00,model_id, 0x12,\
    (address >> 24)&0xFF,(address >> 16)&0xFF,(address >> 8)&0xFF,address&0xFF]
  if size == 1:
    dt.append(value&0x7F)
  elif size == 2:
    dt.append( (value>>4) & 0x0F )
    dt.append( value & 0x0F )
  elif size == 4:
    dt.append( (value>>12) & 0x0F )
    dt.append( (value>>8) & 0x0F )
    dt.append( (value>>4) & 0x0F )
    dt.append( value & 0x0F )
  else:
    print('unsupported size param, use 1, 2, or 4')
    return
  dt.append(0x00) # a byte for the checksum
  dt.append(0xF7) # end of sysex
  dt = compute_checksum(dt)
  midi_tx(dt)
  print(f'sent the value {value}=0x{value:02X} of size {size} to address 0x{address:08X}')
  print(f'     set raw: {intlist_to_hex_str(dt)}')


# reads current value of coarse tune (offset 0x18),
# modifies it by integer value given in step parameter
# checks the range
# writes it back to the register
# provide base address of the sound descriptor for a slected clip/track
def coarse_tune_rmw(sound_base_address, step):
  print(f'Coarse tune {step:+}')
  coarse_tune_offset = 0x0018
  #read
  coarse_tune = rq1_read_param(sound_base_address+coarse_tune_offset,1)
  if coarse_tune is None:
    print('rq1_read_param returned None, exit')
    return False
  #modify
  coarse_tune += step
  #check
  if coarse_tune > 112: coarse_tune = 112
  if coarse_tune < 16: coarse_tune = 16
  #write the modified value
  dt1_set_param(sound_base_address+coarse_tune_offset,coarse_tune,1)
  return True

# this example writes an index of a waveform to a selected partial of a z-core tone
# choose the partial in the range of 1 to 4
# it works only with clips that use a PCM waveform (not e.g. virtual analog)
# 
def example_partial_wave_l(sound_base_address,partial,step):
  print(f'Setting partial {partial} waweform L, step={step:+}')
  partial_idx = partial - 1
  # basic input checks
  if partial_idx < 0: partial_idx = 0
  if partial_idx > 3: partial_idx = 3
  # offsets from midi impl. docs
  partial_offset = [0x2000,0x2100,0x2200,0x2300]
  partial_wave_number_l_offset = 0x20
  # read
  partial_waveform_idx = rq1_read_param(sound_base_address+partial_offset[partial_idx]+partial_wave_number_l_offset,4)
  # modify
  partial_waveform_idx += step
  #check
  if partial_waveform_idx > 16383: partial_waveform_idx = 16383
  #write back
  dt1_set_param(sound_base_address+partial_offset[partial_idx]+partial_wave_number_l_offset,partial_waveform_idx,4)
  

# if you don't specify clip, you get the base address for the track sound
# -- the same if you specify clip number out of 1-16 range
# otherwise specify a clip number between 1 and 16 for a given track
def get_base_address(track,clip=None):
  number_of_clips = 16
  
  # 16 clip sounds + 1 track sound
  sounds_in_track = number_of_clips + 1 
  
  #editing the track sound which is represented as if it was clip #17
  if clip is None or clip >= sounds_in_track or clip < 1:
    clip = sounds_in_track
  
  clip_idx = 0
  
  #input check and pre-processing
  if track < 1: track = 1
  if track > 8: track = 8
  
  # this many bytes is between adjacent base addresses
  # of the zen core tones
  # this is also the number tone structs are aligned
  tone_alignment = 0x20000
  
  #base addresses of the 8 tracks
  mc_track_base = \
    [0x30000000, 0x30220000, 0x30440000, 0x30660000,\
     0x31080000, 0x312A0000, 0x314C0000, 0x316E0000]
  
  # arrays don't start at one :P
  track_idx = track - 1
  clip_idx = clip - 1
  
  result = mc_track_base[track_idx] + tone_alignment * clip_idx
  if clip == sounds_in_track:
    print(f'Selecting trk={track} @ base_address=0x{result:08X}')
  else:
    print(f'Selecting trk={track}, clip={clip} @ base_address=0x{result:08X}')
  return result



# An example of a reg dump procedure
# I leave it as is
# it's super dirty but it worked for me to figure out the address map
# it creates and updates a simple CSV file if the the script could read the data
def dump(start_address,end_address,out_file_name):
  print('starting register dump procedure...')
  address_l = 0x0000;
  address_h_start = start_address >> 16
  address_h_end = end_address >> 16
  print(f'address_h_start=0x{address_h_start:08X}, address_h_end=0x{address_h_end:08X}')
  
  # I thought it may be convenient to divide the address
  # into two halves (high and low) as they are usually divided in instruments' memory maps
  # this way you can modify this func to scan just a couple of address
  # at the beginning of each large section - it was really useful for me :)
  for address_h in range (address_h_start,address_h_end):
    empty_count = 0
    empty_count_max = 0x2
    for address_l_16 in range(0x0,0x3):
      address_l = address_l_16 << 4;
      address = address_h << 16 | address_l
      
      # MIDI doesn't allow sending data with the MSB set
      # as they would modify the internal state machine
      # so let's reduce some options:
      if address & 0x80808080 != 0: continue
      
      size = 16
      print(f'---> poking up to {size} bytes from address 0x{address:08X}, empty_count=0x{empty_count:04X} of 0x{empty_count_max:04X}')
      rq = roland_request(address,size)
      result = roland_response_wait(0.2)
      result_len = len(result)
      #result_len is zero if a location is empty
      if result_len > 0:
        empty_count = 0
        address_hex = f'{address:08X}'
        print(f'got response from {address_hex}, len {result_len}')
        value_list = str(intlist_to_hex_str(result))
        ascii_interp = str(intlist_to_str(result))
        line = [[address_hex,result_len,value_list,ascii_interp]]
        print(f'line to write: {line}')
        with open( out_file_name, 'a', newline='') as csvfile:
          writer = csv.writer(csvfile)
          writer.writerows(line)
      else:
        empty_count+=1
        if empty_count > empty_count_max:
          print('too many empty spaces, nothing to see here, moving on...')
          break
      if address_l == 0 and result_len == 0:
        break
      sleep(0.2)


def tx_program_change(channel,program):
  if channel < 1: channel = 1
  if channel > 16: channel = 16
  channel = channel - 1
  channel = channel & 0xF
  if program < 0: program = 0
  program = program & 0x7F
  ctrl_change_status = 0xC0 | channel
  control_change = [ctrl_change_status,program]
  print(f'MIDI Program Change: {intlist_to_hex_str(control_change)}')
  midi_tx(control_change)


print("Press a key to perform an action (q or ctrl+C to quit)...")
print("Read the source code to figure out which to press ;)")

track = 1
clip = 1
size = 1
offset = 0
value = 0
get_base_address(track,clip)
# activate clip
tx_program_change(track,clip-1)

original_settings = init_nonblocking_input()
try:
  while True:
    if port.in_waiting > 0:
      rxed_b = port.read()
      rxed = int.from_bytes(rxed_b,byteorder='little')
      if rxed == 0xF8: continue
      if rxed == 0xFE: continue
      print(f"rxed: {rxed:X}")
      rxbuf.append(rxed)
    key = read_key()
    if key:
        print(f"Key pressed: {repr(key)}")
        if key == 'q':
        
        # navigation between tracks and clips to edit: w/a/s/d
        # these only set the base address of a zen-core tone in the MC
        # but they don't interact with with the instrument
        # you can modify clip or track sounds even when other clips are selected/playing
          break
        if key == 'w':  #set value of zero to activate track sound edit
          if clip > 0: clip -= 1
          base_address = get_base_address(track,clip)
          tx_program_change(track,clip-1)
        if key == 's':
          if clip < 17: clip += 1
          base_address = get_base_address(track,clip)
          tx_program_change(track,clip-1)
        if key == 'a':
          if track > 1:
            track -= 1
          else:
            print('first track')
          base_address = get_base_address(track,clip)
          tx_program_change(track,clip-1)
        if key == 'd':
          if track < 8:
            track += 1
          else:
            print('last track')
          base_address = get_base_address(track,clip)
          tx_program_change(track,clip-1)
        
        #examples of parameters modification
        if key == 'r':
          coarse_tune_rmw(base_address,1)
        if key == 'f':
          coarse_tune_rmw(base_address,-1)
        if key == 't':
          example_partial_wave_l(base_address,2,1)
        if key == 'g':
          example_partial_wave_l(base_address,2,-1)
            
        #simple tests if it works:
        #the sysex to read info about the instrument
        if key == 'i':
          data = [0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]
          midi_tx(data)
        #play the 0x40 note for one second on MIDI channel=current track
        if key == 'n':
          print('playing a note...')
          data = [0x90+track-1,0x40,0x70]
          midi_tx(data)
          sleep(1)
          data = [0x80+track-1,0x40,0x40]
          midi_tx(data)
          print('note off')
        
        # call the dump procedure
        if key == '^':
          dump(start_address,end_address,out_file_name)
        
        # the code below can be used for own expermients
        # use at your own risk - no checks, just raw read-write
        
        # set global variables: offset and size of data
        # for own experiments with read-write of the registers
        if key == '[':
          if offset < 0x10000: offset += 1
          print(f'offset set to {offset:02X}')
        if key == ']':
          if offset > 0: offset -= 1
          print(f'offset set to {offset:02X}')
        if key == '{':
          if size < 32: size += 1
          print(f'size set to {size}')
        if key == '}':
          if size > 1: size -= 1
          print(f'size set to {size}')
        
        #space: read a value from the instrument
        if key == ' ':
          address = base_address + offset
          value = rq1_read_param(address,size)
          if value is not None:
            print(f'value read: {value}')
          else:
            print('no valid response received')
            
        #increment the value by one and write it back
        if key == '+':
          address = base_address + offset
          value += 1
          print(f'write @ addr={address:08X}, value={value:02X}')
          dt1_set_param(address,value,size)
        
        #decrement the value by one and write it back
        if key == '-':
          address = base_address + offset
          value -= 1
          print(f'write @ addr={address:08X}, value={value:02X}')
          dt1_set_param(address,value,size)

          
finally:
    restore_input(original_settings)
    print("\n\nExit")


