/* dc_link_probe: serial link diagnostics for a real Dreamcast.
 *
 * Tests the cable path to the NGPC without a retail Dreamcast game. The
 * screen shows what the SCIF sees: raw bytes, error counters (framing errors
 * mean a wrong baud rate) and the CTS/RTS lines. Four modes, cycled with A:
 *
 *   SNIFF  only listens
 *   ECHO   sends every received byte back (loopback test from the PC)
 *   MF2K   answers like Millennium Fight 2000 on Download Stand By
 *   DM99   answers like KoF Dream Match 1999
 *
 * The MF2K/DM99 answers are the frames captured in captures/ (see
 * docs/PROTOCOL.md): acknowledgement, announce reply, echo of the data frame.
 *
 * The SCIF runs at 19200 8N1 like the NGPC BIOS (VECT_COMINIT). At that rate
 * about 32 bytes arrive per video frame, twice the 16-byte FIFO, so the FIFO
 * is polled all the time: between screen rows and while waiting for vblank.
 * Polled rather than interrupt driven because Flycast does not raise the SCIF
 * receive interrupt, and the same binary should run there.
 *
 * Loaded over the serial line by tools/dc_probe.py, so the banner below goes
 * out at the loader's 115200 before the switch to 19200.
 */
#include <kos.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <dc/scif.h>
#include <dc/biosfont.h>
#include <dc/video.h>
#include <dc/maple.h>
#include <dc/maple/controller.h>
#include <kos/dbgio.h>
#include <arch/timer.h>

#define PROBE_VERSION "v1"
#define LINK_BAUD     19200

/* SH7091 SCIF registers */
#define SCFTDR2 (*(volatile uint8_t  *)0xffe8000c)
#define SCFSR2  (*(volatile uint16_t *)0xffe80010)
#define SCFRDR2 (*(volatile uint8_t  *)0xffe80014)
#define SCFCR2  (*(volatile uint16_t *)0xffe80018)
#define SCFDR2  (*(volatile uint16_t *)0xffe8001c)
#define SCSPTR2 (*(volatile uint16_t *)0xffe80020)
#define SCLSR2  (*(volatile uint16_t *)0xffe80024)

#define SCFCR2_MCE   0x08   /* hardware flow control (RTS/CTS) */
#define SCFCR2_BASE  0x40   /* what scif_init() leaves: RX trigger 4 bytes */

/* SCSPTR2: RTSIO=bit7 RTSDT=bit6 CTSIO=bit5 CTSDT=bit4. Both lines active low. */
enum { RTS_DEFAULT, RTS_ASSERTED, RTS_RELEASED, RTS_COUNT };
static const uint16_t rts_sptr[RTS_COUNT] = { 0x00, 0x80, 0xC0 };
static const char *const rts_name[RTS_COUNT] = { "default", "asserted", "released" };

enum { MODE_SNIFF, MODE_ECHO, MODE_MF2K, MODE_DM99, MODE_COUNT };
static const char *const mode_name[MODE_COUNT] = { "SNIFF", "ECHO", "FAKE MF2K", "FAKE DM99" };

/* Captured Dreamcast-side frames (docs/PROTOCOL.md) */
static const uint8_t ACK_MF2K[23] = {
    0xFF, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1C,
    0x00, 0x00, 0x04, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x10, 0x00, 0xFF };
static const uint8_t ACK_DM99[23] = {
    0xFF, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x51,
    0x00, 0x00, 0x04, 0x00, 0x00, 0x47, 0x00, 0x00, 0x0A, 0x00, 0xFF };
static const uint8_t ANNOUNCE[16] = {
    0xFF, 0x00, 0x10, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00,
    0x01, 0x01, 0x00, 0xFF };
static const uint8_t ANNOUNCE_REPLY[17] = {
    0xFF, 0x00, 0x10, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00,
    0x00, 0x01, 0x01, 0x00, 0xFF };

/* ---- counters ---- */
static uint32_t n_fer, n_per, n_brk, n_orer;
static uint32_t n_rx, n_tx, n_outside, n_frames;
static uint16_t fcr_config = SCFCR2_BASE;

/* ---- receive: FIFO -> ring, polled ---- */
#define RXQ_SIZE 4096
static uint8_t rxq[RXQ_SIZE];
static int rxq_head, rxq_tail;

static void rx_poll(void) {
    uint16_t fsr = SCFSR2;

    /* FER and PER describe the byte at the head of the FIFO. */
    while (SCFDR2 & 0x1f) {
        fsr = SCFSR2;
        if (fsr & 0x08) n_fer++;
        if (fsr & 0x04) n_per++;
        int next = (rxq_head + 1) % RXQ_SIZE;
        uint8_t c = SCFRDR2;
        if (next != rxq_tail) {     /* full: drop */
            rxq[rxq_head] = c;
            rxq_head = next;
        }
    }
    if (fsr & 0x10) n_brk++;
    if (fsr & 0x93)
        SCFSR2 = 0xff6c;            /* clear ER, BRK, RDF, DR */
    if (SCLSR2 & 0x01) {
        n_orer++;
        SCLSR2 = 0;
    }
}

static int rx_byte(void) {
    if (rxq_tail == rxq_head) return -1;
    int c = rxq[rxq_tail];
    rxq_tail = (rxq_tail + 1) % RXQ_SIZE;
    return c;
}

/* ---- transmit queue, fed to the FIFO without blocking ---- */
#define TXQ_SIZE 1024
static uint8_t txq[TXQ_SIZE];
static int txq_head, txq_tail;

static int txq_pending(void) {
    return (txq_head - txq_tail + TXQ_SIZE) % TXQ_SIZE;
}

static void tx_queue(const uint8_t *p, int n) {
    while (n-- > 0) {
        int next = (txq_head + 1) % TXQ_SIZE;
        if (next == txq_tail) return;   /* full: drop */
        txq[txq_head] = *p++;
        txq_head = next;
    }
}

/* Moves queued bytes into the 16-byte FIFO. With MCE on and CTS released the
 * FIFO does not drain, and neither does the queue: that is the point. */
static void tx_pump(void) {
    while (txq_tail != txq_head && ((SCFDR2 >> 8) & 0x1f) < 16) {
        SCFTDR2 = txq[txq_tail];
        txq_tail = (txq_tail + 1) % TXQ_SIZE;
        n_tx++;
    }
    (void)SCFSR2;
    SCFSR2 = 0xff9f;    /* clear TEND, TDFE */
}

/* A reply frame must leave in one piece: MOTM may give up on a frame whose
 * bytes stop arriving before the closing FF. Pump until the queue is empty,
 * up to a timeout (a stalled CTS would otherwise hang us here). */
static void tx_drain(uint32_t timeout_ms) {
    uint64_t deadline = timer_ms_gettime64() + timeout_ms;
    while (txq_pending() > 0 && timer_ms_gettime64() < deadline) {
        rx_poll();
        tx_pump();
    }
}

/* vid_waitvbl() with the serial port serviced while it waits. */
static void wait_vbl_polling(void) {
    volatile uint32_t *vbl = (volatile uint32_t *)0xa05f810c;
    while (!(*vbl & 0x01ff)) { rx_poll(); tx_pump(); }
    while (*vbl & 0x01ff)    { rx_poll(); tx_pump(); }
}

/* ---- screen: fixed rows, opaque font, no clears needed ---- */
#define COLS   48
#define ROWS   18
#define ORG_X  32
#define ORG_Y  24

static void row(int r, const char *fmt, ...) {
    char buf[COLS + 1];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n < 0) n = 0;
    if (n > COLS) n = COLS;
    memset(buf + n, ' ', COLS - n);
    buf[COLS] = 0;
    rx_poll();
    bfont_draw_str(vram_s + (ORG_Y + r * 24) * 640 + ORG_X, 640, 1, buf);
}

/* ---- history of received bytes for the hex dump ---- */
#define HIST_ROWS 7
#define HIST_SIZE (HIST_ROWS * 16)
static uint8_t hist[HIST_SIZE];
static uint32_t hist_count;

/* ---- event log ---- */
#define LOG_LINES 4
static char log_lines[LOG_LINES][COLS + 1];

static void log_event(const char *fmt, ...) {
    va_list ap;
    memmove(log_lines[0], log_lines[1], sizeof(log_lines[0]) * (LOG_LINES - 1));
    va_start(ap, fmt);
    vsnprintf(log_lines[LOG_LINES - 1], COLS + 1, fmt, ap);
    va_end(ap);
}

/* ---- frame parser and the fake Dreamcast game ---- */
#define FRAME_MAX 64
static uint8_t frame[FRAME_MAX];
static int frame_len = -1;      /* -1: outside a frame */
#ifndef PROBE_START_MODE
#define PROBE_START_MODE MODE_SNIFF     /* -DPROBE_START_MODE=MODE_MF2K for Flycast tests */
#endif
static int mode = PROBE_START_MODE;

static void on_frame(const uint8_t *f, int len) {
    n_frames++;
    int fake = (mode == MODE_MF2K || mode == MODE_DM99);

    if (len == 18 && f[1] == 0x00 && f[2] == 0x31 && f[3] == 0x31) {
        if (fake) {
            tx_queue(mode == MODE_MF2K ? ACK_MF2K : ACK_DM99, 23);
            tx_drain(100);
        }
        log_event("REQUEST 18B%s", fake ? " -> ACK sent" : "");
        return;
    }
    if (len == 16 && memcmp(f, ANNOUNCE, 16) == 0) {
        if (fake) {
            tx_queue(ANNOUNCE_REPLY, 17);
            tx_drain(100);
        }
        log_event("ANNOUNCE 16B%s", fake ? " -> reply sent" : "");
        return;
    }
    if (len >= 19 && f[1] == 0x00 && f[2] == 0x10 && f[3] == 0x00 &&
        f[4] == 0x00 && f[5] == 0x02) {
        /* Checksum at offset 10: sum of offsets 11..end, minus the field
         * byte at 13. Points: 16-bit BE, offsets 21-22 (MF2K) or 15-16 (DM99). */
        uint8_t sum = 0;
        for (int i = 11; i < len - 1; i++) sum += f[i];
        sum -= f[13];
        int points = (len == 25) ? (f[21] << 8 | f[22])
                   : (len == 19) ? (f[15] << 8 | f[16]) : -1;
        if (fake) {
            tx_queue(f, len);   /* the Dreamcast game confirms by echoing */
            tx_drain(100);
        }
        log_event("DATA %dB pts %d chk %s%s", len, points,
                  sum == f[10] ? "OK" : "BAD", fake ? " -> echoed" : "");
        return;
    }
    log_event("frame %dB %02X %02X %02X %02X ...", len, f[1], f[2], f[3], f[4]);
}

static void parse_byte(uint8_t c) {
    if (frame_len < 0) {
        if (c == 0xFF) { frame[0] = c; frame_len = 1; }
        else n_outside++;
        return;
    }
    if (c == 0xFF && frame_len == 1)    /* FF FF: the second one opens */
        return;
    if (frame_len >= FRAME_MAX) {       /* runaway: resync on the next FF */
        log_event("frame over %d bytes, dropped", FRAME_MAX);
        frame_len = -1;
        return;
    }
    frame[frame_len++] = c;
    if (c == 0xFF) {
        on_frame(frame, frame_len);
        frame_len = -1;
    }
}

static void reset_counters(void) {
    n_fer = n_per = n_brk = n_orer = 0;
    n_rx = n_tx = n_outside = n_frames = 0;
    hist_count = 0;
    frame_len = -1;
    memset(log_lines, 0, sizeof(log_lines));
}

static void apply_lines(int mce, int rts) {
    fcr_config = SCFCR2_BASE | (mce ? SCFCR2_MCE : 0);
    SCFCR2 = fcr_config;
    SCSPTR2 = mce ? 0x00 : rts_sptr[rts];   /* MCE drives RTS itself */
}

int main(int argc, char **argv) {
    (void)argc; (void)argv;

    /* Still on the loader's 115200 console: say we are alive. */
    dbgio_printf("\n[PROBE] dc_link_probe " PROBE_VERSION " up, SCIF -> %d 8N1\n", LINK_BAUD);
    dbgio_flush();

    dbgio_dev_select("null");   /* nothing else may write to the link */
    scif_set_parameters(LINK_BAUD, 1);
    scif_init();
    scif_set_irq_usage(0);

    vid_set_mode(DM_640x480, PM_RGB565);
    memset(vram_s, 0, 640 * 480 * 2);

    int mce = 0, rts = RTS_ASSERTED, tests_sent = 0;
    uint32_t last_buttons = 0, burst_max = 0;
    apply_lines(mce, rts);
    reset_counters();

    for (;;) {
        maple_device_t *cont = maple_enum_type(0, MAPLE_FUNC_CONTROLLER);
        if (cont) {
            cont_state_t *st = (cont_state_t *)maple_dev_status(cont);
            if (st) {
                uint32_t edge = st->buttons & ~last_buttons;
                if (edge & CONT_A) {
                    mode = (mode + 1) % MODE_COUNT;
                    frame_len = -1;
                    log_event("mode -> %s", mode_name[mode]);
                }
                if (edge & CONT_X) { reset_counters(); burst_max = 0; }
                if (edge & CONT_Y) {
                    char msg[40];
                    int n = snprintf(msg, sizeof(msg), "DC>PC test %d\r\n", ++tests_sent);
                    tx_queue((const uint8_t *)msg, n);
                    log_event("sent test line %d", tests_sent);
                }
                if (edge & CONT_DPAD_UP)   { mce = !mce; apply_lines(mce, rts); }
                if (edge & CONT_DPAD_DOWN) { rts = (rts + 1) % RTS_COUNT; apply_lines(mce, rts); }
                last_buttons = st->buttons;
            }
        }

        uint32_t burst = 0;
        int c;
        rx_poll();
        while ((c = rx_byte()) >= 0) {
            n_rx++;
            burst++;
            hist[hist_count % HIST_SIZE] = (uint8_t)c;
            hist_count++;
            if (mode == MODE_ECHO) {
                uint8_t b = (uint8_t)c;
                tx_queue(&b, 1);
            }
            else {
                parse_byte((uint8_t)c);
            }
        }
        if (burst > burst_max) burst_max = burst;
        /* One FIFO per frame would echo at half the line rate. */
        tx_drain(txq_pending() > 0 ? 40 : 0);

        uint16_t sptr = SCSPTR2;
        int cts_low = !(sptr & 0x10);

        row(0,  "DC LINK PROBE " PROBE_VERSION "    mode: %s", mode_name[mode]);
        row(1,  "SCIF %d 8N1   MCE %s   RTS %s", LINK_BAUD, mce ? "ON " : "off",
            mce ? "(by MCE)" : rts_name[rts]);
        row(2,  "SCSPTR2 %04X  CTS pin %s", sptr, cts_low ? "LOW (asserted)" : "HIGH (released)");
        row(3,  "RX %-7lu TX %-7lu txq %-4d burst %lu", (unsigned long)n_rx,
            (unsigned long)n_tx, txq_pending(), (unsigned long)burst_max);
        row(4,  "ERR framing %lu parity %lu break %lu overrun %lu",
            (unsigned long)n_fer, (unsigned long)n_per, (unsigned long)n_brk,
            (unsigned long)n_orer);
        row(5,  "frames %lu   bytes outside frames %lu", (unsigned long)n_frames,
            (unsigned long)n_outside);

        /* Hex dump, oldest first; the newest byte is the last one shown. */
        uint32_t shown = hist_count < HIST_SIZE ? hist_count : HIST_SIZE;
        uint32_t first = hist_count - shown;
        for (int r = 0; r < HIST_ROWS; r++) {
            char line[COLS + 1];
            int p = 0;
            for (int i = 0; i < 16; i++) {
                uint32_t k = (uint32_t)(r * 16 + i);
                if (k < shown)
                    p += snprintf(line + p, sizeof(line) - p, "%02X ", hist[(first + k) % HIST_SIZE]);
            }
            line[p] = 0;
            row(6 + r, "%s", line);
        }

        for (int i = 0; i < LOG_LINES; i++)
            row(13 + i, "%s", log_lines[i]);

        row(17, "A mode X clear Y test UP mce DOWN rts");

        wait_vbl_polling();
    }

    return 0;
}
