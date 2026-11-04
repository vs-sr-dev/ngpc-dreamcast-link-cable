#include "ngpc.h"
#include "carthdr.h"
#include "library.h"
#include "core/rom/comms.h"

#define P1_PAL1       0
#define JOY_A         0x10

/* Side-channel from the patched beetle-ngp core (NGPC_LINK_MMIO=1): status (1=empty / 0=got byte)
 * and last received byte are mirrored into these RAM cells by the HLE. */
#define LINK_MMIO_STATUS (*(volatile u8*)0x6BFC)
#define LINK_MMIO_BYTE   (*(volatile u8*)0x6BFD)

void main(void)
{
	u8 joy_prev = 0;
	u8 joy_now;
	u8 pressed;
	u16 tx_count = 0;
	u16 rx_count = 0;

	InitNGPC();
	SetBackgroundColour(RGB(68, 68, 68));
	SysSetSystemFont();
	SetPalette(SCR_1_PLANE, P1_PAL1, 4,
	           RGB(15, 15, 15), RGB(15, 15, 15), RGB(15, 15, 15));

	LINK_MMIO_STATUS = 1; /* init as empty */
	LINK_MMIO_BYTE   = 0;

	while (1)
	{
		joy_now = JOYPAD;
		pressed = joy_now & ~joy_prev;
		joy_prev = joy_now;

		if (pressed & JOY_A)
		{
			g_comms_tx_byte = 0x42;
			ComCreateData();
			tx_count++;
		}

		ComGetData();
		if (LINK_MMIO_STATUS == 0)
			rx_count++;

		PrintHex(SCR_1_PLANE, P1_PAL1, 6, 8,  tx_count, 4);
		PrintHex(SCR_1_PLANE, P1_PAL1, 6, 9,  rx_count, 4);
		PrintHex(SCR_1_PLANE, P1_PAL1, 6, 11, LINK_MMIO_BYTE,   2);
		PrintHex(SCR_1_PLANE, P1_PAL1, 6, 12, LINK_MMIO_STATUS, 2);

		WaitVsync();
	}
}
