#include "core/rom/comms.h"

/* Direct call to beetle-ngp HLE handler at 0xFF2C86 / 0xFF2CB4.
 * B register (bank-3 offset 0x35) carries the data byte; the HLE also
 * mirrors status/byte into RAM 0x6BFC/0x6BFD for us (NGPC_LINK_MMIO=1 side-channel
 * — sidesteps ASM900 ambiguity on LD (mem24),W). The ROM reads those
 * RAM bytes via the globals declared in comms.h. */

volatile u8 g_comms_tx_byte;
volatile u8 g_comms_rx_byte;
volatile u8 g_comms_rx_status;

void ComCreateData(void)
{
	__ASM("	ld	B,(_g_comms_tx_byte)");
	__ASM("	call	0xFF2C86");
}

void ComGetData(void)
{
	__ASM("	call	0xFF2CB4");
	__ASM("	ld	(_g_comms_rx_byte),B");
}
