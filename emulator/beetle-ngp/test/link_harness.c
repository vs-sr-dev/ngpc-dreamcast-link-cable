/* Drives the patched core's link hooks directly, as the HLE BIOS would,
 * with NGPC_LINK_ROLE=client. Run by link_test.py, which plays the peer.
 *
 * Phase 1: no peer listening -- 200 comms calls must not block.
 * Phase 2: poll (10 ms apart) until a byte arrives, then send 0x99.
 * Phase 3: the peer goes away and comes back; poll until it sends again,
 *          then send 0x77.
 *
 * Exit code: 0 ok, 1 no byte received, 2 a comms call took over 100 ms. */
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <windows.h>

#define SLOW_CALL_MS 100.0

bool system_comms_read(uint8_t* buffer);
void system_comms_write(uint8_t data);

static double worst_ms = 0;

static double now_ms(void) {
   LARGE_INTEGER f, c;
   QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c);
   return (double)c.QuadPart * 1000.0 / (double)f.QuadPart;
}

static bool timed_read(uint8_t* b) {
   double t = now_ms();
   bool got = system_comms_read(b);
   double dt = now_ms() - t;
   if (dt > worst_ms) worst_ms = dt;
   return got;
}

static int wait_byte(const char* tag, double limit_ms) {
   uint8_t b;
   double t0 = now_ms();
   while (now_ms() - t0 < limit_ms) {
      if (timed_read(&b)) {
         printf("%s: got 0x%02x after %.0f ms\n", tag, b, now_ms() - t0);
         return b;
      }
      Sleep(10);
   }
   printf("%s: nothing after %.0f ms\n", tag, limit_ms);
   return -1;
}

int main(void) {
   uint8_t b;
   double t0 = now_ms();
   for (int i = 0; i < 200 && now_ms() - t0 < 20000; i++)
      timed_read(&b);
   printf("phase1: 200 calls with no peer took %.0f ms\n", now_ms() - t0);
   fflush(stdout);

   if (wait_byte("phase2", 8000) < 0) return 1;
   system_comms_write(0x99);
   fflush(stdout);

   if (wait_byte("phase3", 8000) < 0) return 1;
   system_comms_write(0x77);
   Sleep(300);

   printf("slowest comms call: %.1f ms (limit %.0f)\n", worst_ms, SLOW_CALL_MS);
   fflush(stdout);
   return worst_ms > SLOW_CALL_MS ? 2 : 0;
}
