CC ?= cc
QCC ?= qcc
QNX_VARIANT ?= gcc_ntox86_64
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror

.PHONY: host qnx

host: timing-probe-host

qnx: timing-probe-qnx

timing-probe-host: probe.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

timing-probe-qnx: probe.c
	$(QCC) -V$(QNX_VARIANT) $(CPPFLAGS) $(CFLAGS) -o $@ $<
