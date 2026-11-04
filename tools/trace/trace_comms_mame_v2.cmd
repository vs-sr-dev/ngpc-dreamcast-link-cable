// trace_comms_mame_v2.cmd — MOTM link handshake RE via MAME debugger.
//
// Final clean version (MAME 0.287 TLCS-900H syntax):
//   register: xssp  (System Stack Pointer, 32-bit)
//   memory:   d@(xssp)  (dword at SP = return address pushed by CALL)
//
// Load with:
//   mame ngpc -cart "...motm.ngc" -debug -debugscript "..." -debuglog
//
// With -debuglog, all printf output is written to debug.log alongside
// the MAME executable, so we can read it after the session regardless
// of how fast the debugger console is scrolling.

// ============================================================
// BIOS comms vectors + caller PC (in cart ROM, 0x200000-0x3FFFFF range)
// ============================================================
bpset ff2bbd,1,{ printf "[BIOS] VECT_COMINIT          caller=%08X",d@(xssp); g }
bpset ff2c0c,1,{ printf "[BIOS] VECT_COMSENDSTART     caller=%08X",d@(xssp); g }
bpset ff2c44,1,{ printf "[BIOS] VECT_COMRECIVESTART   caller=%08X",d@(xssp); g }
bpset ff2c86,1,{ printf "[BIOS] VECT_COMCREATEDATA    caller=%08X",d@(xssp); g }
bpset ff2cb4,1,{ printf "[BIOS] VECT_COMGETDATA       caller=%08X",d@(xssp); g }
bpset ff2d27,1,{ printf "[BIOS] VECT_COMONRTS         caller=%08X",d@(xssp); g }
bpset ff2d33,1,{ printf "[BIOS] VECT_COMOFFRTS        caller=%08X",d@(xssp); g }
bpset ff2d3a,1,{ printf "[BIOS] VECT_COMSENDSTATUS    caller=%08X",d@(xssp); g }
bpset ff2d4e,1,{ printf "[BIOS] VECT_COMRECIVESTATUS  caller=%08X",d@(xssp); g }
bpset ff2d6c,1,{ printf "[BIOS] VECT_COMCREATEBUFDATA caller=%08X",d@(xssp); g }
bpset ff2d85,1,{ printf "[BIOS] VECT_COMGETBUFDATA    caller=%08X",d@(xssp); g }

// Serial MMIO -- SC0BUF TX watchpoint DISABLED for this run (too noisy;
// we already know MOTM spams 0x92 in tight polling loop on MAME's stub UART).

// Start emulation.
printf "[trace_v2] armed: 11 BIOS BPs. Output also in debug.log via -debuglog."
g
