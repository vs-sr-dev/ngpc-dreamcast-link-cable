#include <kos.h>
#include <stdio.h>
#include <stdint.h>
#include <dc/scif.h>
#include <dc/biosfont.h>
#include <dc/video.h>
#include <dc/maple.h>
#include <dc/maple/controller.h>

static void draw_text(uint16_t *fb, int x, int y, const char *s) {
    bfont_draw_str(fb + y * 640 + x, 640, 1, s);
}

static void clear_fb(uint16_t *fb, uint16_t color) {
    for (int i = 0; i < 640 * 480; i++) fb[i] = color;
}

int main(int argc, char **argv) {
    vid_set_mode(DM_640x480, PM_RGB565);
    scif_init();
    scif_set_irq_usage(0);

    uint16_t *fb = vram_s;
    int last_rx = -1;
    int tx_count = 0;
    int rx_count = 0;
    uint32_t last_buttons = 0;
    char line[96];

    for (;;) {
        maple_device_t *cont = maple_enum_type(0, MAPLE_FUNC_CONTROLLER);
        if (cont) {
            cont_state_t *st = (cont_state_t *)maple_dev_status(cont);
            if (st) {
                uint32_t edge = st->buttons & ~last_buttons;
                if (st->buttons & CONT_START) break;
                if (edge & CONT_A) { scif_write(0x42); scif_flush(); tx_count++; }
                if (edge & CONT_B) { scif_write(0xAB); scif_flush(); tx_count++; }
                if (edge & CONT_X) { scif_write(0xC5); scif_flush(); tx_count++; }
                last_buttons = st->buttons;
            }
        }

        int c;
        while ((c = scif_read()) >= 0) {
            last_rx = c & 0xff;
            rx_count++;
        }

        clear_fb(fb, 0x001F);

        draw_text(fb, 16, 16,  "NGPC <-> DREAMCAST  LINK  BRIDGE  DEMO");
        draw_text(fb, 16, 48,  "A / B / X -> send 0x42 / 0xAB / 0xC5");
        draw_text(fb, 16, 72,  "START -> exit");

        snprintf(line, sizeof(line), "TX count: %d", tx_count);
        draw_text(fb, 16, 128, line);

        snprintf(line, sizeof(line), "RX count: %d", rx_count);
        draw_text(fb, 16, 152, line);

        if (last_rx < 0) {
            draw_text(fb, 16, 176, "last rx: -- (none yet)");
        } else {
            char pretty = (last_rx >= 32 && last_rx < 127) ? (char)last_rx : '.';
            snprintf(line, sizeof(line), "last rx: 0x%02X  ('%c')", last_rx, pretty);
            draw_text(fb, 16, 176, line);
        }

        vid_waitvbl();
    }

    return 0;
}
