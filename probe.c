#define _POSIX_C_SOURCE 200809L
#if defined(__QNXNTO__)
#define _QNX_SOURCE
#include <sys/neutrino.h>
#include <sys/syspage.h>
#include <sys/utsname.h>
#endif

#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define NS_PER_SECOND UINT64_C(1000000000)

static uint64_t number(const char *argument, uint64_t minimum, uint64_t maximum) {
    char *end;
    errno = 0;
    unsigned long long value = strtoull(argument, &end, 10);
    if (argument[0] < '0' || argument[0] > '9' || *end || errno ||
        value < minimum || value > maximum) {
        fprintf(stderr, "Invalid numeric argument: %s\n", argument);
        exit(EXIT_FAILURE);
    }
    return (uint64_t)value;
}

static uint64_t monotonic_ns(void) {
    struct timespec current;
    if (clock_gettime(CLOCK_MONOTONIC, &current) != 0) {
        perror("clock_gettime");
        exit(EXIT_FAILURE);
    }
    return (uint64_t)current.tv_sec * NS_PER_SECOND + (uint64_t)current.tv_nsec;
}

static void wait_until(uint64_t deadline) {
    uint64_t current = monotonic_ns();
    while (current < deadline) {
        uint64_t remaining = deadline - current;
        struct timespec interval = {
            .tv_sec = (time_t)(remaining / NS_PER_SECOND),
            .tv_nsec = (long)(remaining % NS_PER_SECOND),
        };
        if (nanosleep(&interval, NULL) != 0 && errno != EINTR) {
            perror("nanosleep");
            exit(EXIT_FAILURE);
        }
        current = monotonic_ns();
    }
}

int main(int argc, char **argv) {
    if (argc != 3 && argc != 5) {
        fprintf(stderr, "Usage: %s SAMPLES PERIOD_US [DELAY_AT_SAMPLE DELAY_US]\n", argv[0]);
        return EXIT_FAILURE;
    }
    uint64_t samples = number(argv[1], 1, 10000);
    uint64_t period = number(argv[2], 1, 1000000) * 1000;
    uint64_t injected_at = 0;
    uint64_t delay = 0;
    if (argc == 5) {
        injected_at = number(argv[3], 1, samples);
        delay = number(argv[4], 1, 1000000) * 1000;
    }

    const char *target = "posix-host";
    uint64_t counter_hz = 0;
#if defined(__QNXNTO__)
    struct utsname system;
    if (uname(&system) != 0) {
        perror("uname");
        return EXIT_FAILURE;
    }
    if (system.release[0] != '8' || system.release[1] != '.') {
        fprintf(stderr, "Expected QNX 8.x, got %s\n", system.release);
        return EXIT_FAILURE;
    }
    target = "qnx-8";
    counter_hz = SYSPAGE_ENTRY(qtime)->cycles_per_sec;
    if (counter_hz == 0) {
        fputs("QNX cycle counter frequency is unavailable\n", stderr);
        return EXIT_FAILURE;
    }
    uint64_t first_cycle = ClockCycles();
#endif

    printf("{\"version\":1,\"target\":\"%s\",\"counter_hz\":%" PRIu64
           ",\"samples\":%" PRIu64 ",\"period_ns\":%" PRIu64
           ",\"injected_at\":%" PRIu64 ",\"delay_ns\":%" PRIu64 "}\n",
           target, counter_hz, samples, period, injected_at, delay);
    uint64_t deadline = monotonic_ns();
    for (uint64_t sample = 1; sample <= samples; sample++) {
        deadline += period;
        wait_until(deadline);
        if (sample == injected_at) {
            wait_until(monotonic_ns() + delay);
        }
        uint64_t late_ns = monotonic_ns() - deadline;
        uint64_t cycles = 0;
#if defined(__QNXNTO__)
        cycles = ClockCycles() - first_cycle;
#endif
        printf("{\"sample\":%" PRIu64 ",\"late_ns\":%" PRIu64
               ",\"cycles\":%" PRIu64 "}\n", sample, late_ns, cycles);
    }
    return fflush(stdout) == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
