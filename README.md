# MC Poker

An experimental proof-of-concept script for interacting with MC-101 and MC-707 ZEN-Core synth engine using MIDI System Exclusive (SysEx) messages over serial port. Requires a hardware serial-to-midi converter.

My related YouTube video (what's going on in this repository) is here:
https://youtu.be/x_kHTL99cvk

Similar principles apply to communication over USB, but you just need a different interface software layer. I tested the Coarse Tune setting to +2 as in the video, but using the USB interface and Linux command line. I tried both Generic and Vendor driver setting on my MC-707 - and it worked in both cases. I use Linux (obviously ;)), so I tried it with the "amidi" command, like that (copied & pasted exactly from the terminal):

amidi -p hw:2,0,0 -t1 -d -S 'F0 41 10 00 00 00 5D 12 30 42 00 18 42 34 F7'

The "hw:2,0,0" is how my MC-707 was displayed after issuing the command:

amidi --list-devices

and the SysEx message contents was copied&pasted from the terminal running the mcpoker.py as in the video.

And the diagram of the ZEN-Core tone addresses, which I figured out, is shown below.
<img width="454" height="907" alt="address-map-only" src="https://github.com/user-attachments/assets/ea9f8415-79c7-48af-852a-407af34f7a49" />
