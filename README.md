# MC Poker

This repository contains my experimental proof-of-concept code for controlling selected ZEN-Core synth parameters in Roland MC-101 and MC-707 grooveboxes using MIDI SysEx messages over serial port. Requires a hardware serial-to-MIDI converter.

Please see the updated version in my follow-up project:
https://github.com/Locriana/mctools_basic

Roland does not officially document SysEx parameter control for the MC-101 and MC-707 in the same way as for some other ZEN-Core instruments, but after some testing and reverse engineering I found that the MC grooveboxes do respond to Roland-style SysEx messages such as `Data Request 1` and `Data Set 1` / `DT1`.

The goal of this project is to document what I found and to share a starting point for further experiments.
My related YouTube video (what's going on in this repository) is here:
https://youtu.be/x_kHTL99cvk

Similar principles apply to communication over USB, but you just need a different interface software layer. I tested the Coarse Tune setting to +2 as in the video, but using the USB interface and Linux command line. I tried both Generic and Vendor driver setting on my MC-707 - and it worked in both cases. I use Linux (obviously ;)), so I tried it with the "amidi" command, like that (copied & pasted exactly from the terminal):

amidi -p hw:2,0,0 -t1 -d -S 'F0 41 10 00 00 00 5D 12 30 42 00 18 42 34 F7'

The "hw:2,0,0" is how my MC-707 was displayed after issuing the command:

amidi --list-devices

and the SysEx message contents was copied&pasted from the terminal running the mcpoker.py as in the video.

---

## What this project does

The current proof-of-concept script can:

- send raw MIDI SysEx data to Roland MC-101 and MC-707,
- request data from selected internal address ranges,
- receive and parse DT1 response messages,
- scan parts of the internal parameter address space,
- locate ZEN-Core tone descriptor blocks,
- read selected ZEN-Core tone data,
- modify selected ZEN-Core parameters,
- send a simple test note over MIDI.

At the moment this is not a complete editor. It is only an experimental tool that helped me confirm that external SysEx control of some ZEN-Core parameters is possible.

---

## Why I made this

I really like the Roland MC-707 and MC-101 grooveboxes, but editing ZEN-Core sounds directly on the device can be quite inconvenient.

For example:

- many parameters require menu diving,
- MC-101 editing is especially limited because of the small interface,
- some values require very precise knob movements,
- envelope and partial editing is not very comfortable,
- deeper sound design would be much easier with external hands-on control.

The idea behind this project is to explore whether it is possible to build an external controller or editor for the MC grooveboxes by using MIDI SysEx communication.

And yes - it looks like it is possible.

---

## Important disclaimer

Use this at your own risk.

This project is based on experimentation, reverse engineering, and comparison with MIDI implementation charts for other Roland instruments. It is not based on official MC-101 or MC-707 SysEx documentation.

I am sharing this as a proof of concept and as inspiration for further experiments.

Please keep in mind:

- this code is experimental,
- it may contain bugs,
- it is not optimized,
- it does not validate everything safely,
- it may send data directly to your instrument,
- you are responsible for anything you do with your gear.

If you break something, corrupt a project, overwrite a sound, or confuse your groovebox, please do not blame me.

---

## Tested devices

I tested this with:

- Roland MC-707
- Roland MC-101

Both devices responded to the tested SysEx messages in a very similar way. Later I had also found out that MV-1 also responds to SysEx but the bi-directional communication is only over USB.

An interesting observation is that the MC-101 appears to use a descriptor layout compatible with the MC-707, even though only tracks 1-4 are available for normal playback on the MC-101.

---

## Basic idea

Roland instruments that support SysEx parameter access usually organize their internal parameters in an address space.

Each readable or writable parameter has an address. SysEx messages can then be used to:

- request data from a given address,
- write data to a given address.

The MC-101 and MC-707 seem to use a similar mechanism internally.

The two most important message types are:

`Data Request 1` - used to read data from the instrument,

`Data Set 1` / `DT1` - used to write data or receive requested data.

---


## SysEx request message

A Roland-style data request message contains:

- SysEx start byte,
- Roland manufacturer ID,
- device ID,
- model ID,
- command byte,
- target address,
- requested data length,
- checksum,
- SysEx end byte.

The address tells the instrument where to read data from.

The length tells the instrument how much data should be returned.

In this proof-of-concept code, large request lengths are not fully implemented. The current implementation is enough for the experiments I needed, but it should be improved if you want to build a more complete tool.

<img width="857" height="539" alt="dreq" src="https://github.com/user-attachments/assets/7a6995ef-4f2a-4126-9378-a95413b7e47a" />

---

## SysEx write message / DT1

To write data to the instrument, Roland instruments commonly use a `Data Set 1` message, also known as `DT1`.

For `DT1`, the command byte is: 0x12

The message contains:

- target address,
- payload data,
- checksum.

Each following data byte is written to the next higher address.

The same `DT1` message format is also used by the instrument when it responds to a data request.

<img width="954" height="607" alt="dset" src="https://github.com/user-attachments/assets/ef83f830-f768-4f14-ac88-61ee0ba8d702" />

---

## Checksum

Roland SysEx messages use a checksum byte.

The checksum is calculated from the address and data bytes. In this project, the checksum function follows the method described in MIDI implementation charts for other Roland instruments that support SysEx communication.

If your checksum is wrong, the instrument will usually ignore the message.

---

## Descriptor layout observations

From my tests:

- each tone track has its own descriptor,
- each tone clip has its own descriptor,
- MC-707 has 8 tracks,
- each track can have 16 clip tone descriptors,
- there is also a separate track tone descriptor,
- this gives many possible ZEN-Core tone descriptor locations.

For the MC-707 this means: 8 tracks × 16 clip tones = 128 clip tone descriptors, plus separate descriptors for track tones.

The MC-101 seems to expose a similar descriptor structure, but only tracks 1–4 are normally usable on the device.

And the diagram of the ZEN-Core tone addresses, which I figured out, is shown below.
<img width="454" height="907" alt="address-map-only" src="https://github.com/user-attachments/assets/ea9f8415-79c7-48af-852a-407af34f7a49" />

---

## ZEN-Core tone descriptors

In the MC-101 and MC-707, ZEN-Core tone data appears to be stored in descriptor-like structures.

I refer to them as:

- `ZEN-Core tone descriptors`
- or `ZEN-Core sound descriptors`

This is not an official Roland name. It is just the term I use in this project.

In my tests, a large block of ZEN-Core tone descriptors starts around 0x30000000.

The exact organization may differ between Roland products, so documentation for other ZEN-Core instruments can be useful, but addresses should not be copied blindly.

<img width="1644" height="1021" alt="tone-desc" src="https://github.com/user-attachments/assets/3d0e8dca-1bc6-46f0-a290-5a70c014db54" />

---

