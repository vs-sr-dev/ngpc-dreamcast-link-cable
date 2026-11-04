#ifndef NGPC_LINK_COMMS_H
#define NGPC_LINK_COMMS_H

#include "ngpc.h"

extern volatile u8 g_comms_tx_byte;
extern volatile u8 g_comms_rx_byte;
extern volatile u8 g_comms_rx_status;

void ComCreateData(void);
void ComGetData(void);

#endif
