# NGPC hello_link demo — MSYS2-bash friendly Makefile
# Requires THOME = <ngpcbins>/T900 (MSYS2 /x/ path style) in env
# and $THOME/BIN in PATH. See build.sh wrapper.

NAME := main
OUT  := bin

CC := cc900.exe
LD := tulink.exe
CONV := tuconv.exe
NGP := s242ngp.exe

CFLAGS := -c -O3

OBJS := main.rel library.rel core/rom/comms.rel

.PHONY: all clean
.SUFFIXES: .c .rel

all: $(OUT)/$(NAME).ngp

%.rel: %.c
	$(CC) $(CFLAGS) $< -o $@

$(NAME).abs: ngpc.lcf system.lib $(OBJS)
	$(LD) -la -o $(NAME).abs ngpc.lcf system.lib $(OBJS)

$(NAME).s24: $(NAME).abs
	$(CONV) -Fs24 $(NAME).abs

$(NAME).ngp: $(NAME).s24
	$(NGP) $(NAME).s24

$(OUT)/$(NAME).ngp: $(NAME).ngp
	@mkdir -p $(OUT)
	@mv -f $(NAME).ngp   $(OUT)/$(NAME).ngp
	@mv -f $(NAME).abs   $(OUT)/ 2>/dev/null || true
	@mv -f $(NAME).s24   $(OUT)/ 2>/dev/null || true
	@mv -f $(NAME).map   $(OUT)/ 2>/dev/null || true

clean:
	@bash -c "find . -name '*.rel' -delete 2>/dev/null; rm -rf $(OUT)"
