TARGET = dc_link_probe.elf
OBJS = main.o

all: rm-elf $(TARGET) dc_link_probe.bin

include $(KOS_BASE)/Makefile.rules

clean: rm-elf
	-rm -f $(OBJS) dc_link_probe.bin dc_link_probe.bin.span

rm-elf:
	-rm -f $(TARGET)

$(TARGET): $(OBJS)
	kos-cc -o $(TARGET) $(OBJS)

# Raw binary for the serial loader, plus its load span (_end - 0x8c010000):
# KOS does not clear .bss, the loader zero-fills up to the span.
dc_link_probe.bin: $(TARGET)
	sh-elf-objcopy -O binary $(TARGET) $@
	echo $$(( 0x$$(sh-elf-nm $(TARGET) | awk '$$3 == "_end" { print $$1 }') - 0x8c010000 )) > $@.span
