// trace_comms_mame.cmd
// MAME debugger script — trace NGPC BIOS comms vector hits and TMP95C061 serial MMIO writes.
// Decides: does the ROM use SDK BIOS vectors (BIOS-HLE path)
//          or does it poke the TLCS-900H UART registers directly (MAME transplant path)?
//
// Load with: mame ngpc -cart <your MOTM .ngc> -debug -debugscript tools/trace/trace_comms_mame.cmd
//
// The breakpoints use action "{ ... ; g }" so they log and resume automatically
// without pausing the emulator. Output goes to the MAME debugger console window.

// ============================================================
// BIOS comms vectors (from OpenEmu/NeoPop-Core/biosHLE.c:449-640)
// If ANY of these fires during link-menu navigation → BIOS path.
// ============================================================
bpset ff2c86,1,{ printf "[BIOS] VECT_COMCREATEDATA @ pc=%X",pc; g }
bpset ff2cb4,1,{ printf "[BIOS] VECT_COMGETDATA @ pc=%X",pc; g }
bpset ff2d27,1,{ printf "[BIOS] VECT_COMONRTS @ pc=%X",pc; g }
bpset ff2d33,1,{ printf "[BIOS] VECT_COMOFFRTS @ pc=%X",pc; g }
bpset ff2d3a,1,{ printf "[BIOS] VECT_COMSENDSTATUS @ pc=%X",pc; g }
bpset ff2d4e,1,{ printf "[BIOS] VECT_COMRECIVESTATUS @ pc=%X",pc; g }
bpset ff2d6c,1,{ printf "[BIOS] VECT_COMCREATEBUFDATA @ pc=%X",pc; g }
bpset ff2d85,1,{ printf "[BIOS] VECT_COMGETBUFDATA @ pc=%X",pc; g }

// ============================================================
// TMP95C061 serial MMIO watchpoints (from MAME tmp95c061.cpp:1131-1216)
// Serial register range on TMP95C061 internal I/O page.
// SC0BUF=0x50, SC1BUF=0x51 (approximate — MAME stubs return 0 on read, fake INT on write).
// If these fire WITHOUT BIOS vectors firing → register-level poke path.
// ============================================================
wpset 50,1,w,1,{ printf "[SER] W SC0BUF <- %02X @ pc=%X",wpdata,pc; g }
wpset 51,1,w,1,{ printf "[SER] W SC1BUF <- %02X @ pc=%X",wpdata,pc; g }
wpset 52,1,w,1,{ printf "[SER] W SC0CR <- %02X @ pc=%X",wpdata,pc; g }
wpset 53,1,w,1,{ printf "[SER] W SC1CR <- %02X @ pc=%X",wpdata,pc; g }
wpset 54,1,w,1,{ printf "[SER] W SC0MOD <- %02X @ pc=%X",wpdata,pc; g }
wpset 55,1,w,1,{ printf "[SER] W SC1MOD <- %02X @ pc=%X",wpdata,pc; g }
wpset 56,1,w,1,{ printf "[SER] W BR0CR <- %02X @ pc=%X",wpdata,pc; g }
wpset 57,1,w,1,{ printf "[SER] W BR1CR <- %02X @ pc=%X",wpdata,pc; g }
wpset 50,1,r,1,{ printf "[SER] R SC0BUF @ pc=%X",pc; g }
wpset 51,1,r,1,{ printf "[SER] R SC1BUF @ pc=%X",pc; g }

// Start execution.
printf "[trace_comms] armed: 8 BIOS breakpoints + 10 serial watchpoints. Navigate to link menu."
g
