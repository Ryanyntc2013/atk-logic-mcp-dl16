// Bounded DL16 PWM output sender (DL16-TASK-004 live tool).
//
// Sends only the documented PWM command (0x17) start/stop through the pinned
// core's framed command path. It is NOT a raw/vendor/firmware command tool: it
// accepts only a PWM channel (0..1), frequency (1..20e6 Hz) and duty (0..100%),
// and builds the fixed 9-byte / 1-byte payloads. Requires operator-approved
// loopback wiring; see docs/research/DL16-TASK-002-pwm-output.md.
#include "atkdl16/constants.h"
#include "atkdl16/device.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

using namespace atkdl16;

static constexpr uint64_t PWM_COUNTER_HZ = 200'000'000ULL;
static constexpr uint32_t PWM_FREQ_MIN = 1;
static constexpr uint32_t PWM_FREQ_MAX = 20'000'000;

static bool valid_channel(long ch) { return ch == 0 || ch == 1; }

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr,
                     "usage: dl16-pwm start <ch 0|1> <freq_hz 1..20000000> <duty_pct 0..100>\n"
                     "       dl16-pwm stop <ch 0|1>\n");
        return 2;
    }
    std::string action = argv[1];

    std::vector<uint8_t> payload;
    if (action == "start" && argc == 5) {
        long ch = std::strtol(argv[2], nullptr, 10);
        unsigned long freq = std::strtoul(argv[3], nullptr, 10);
        double duty = std::strtod(argv[4], nullptr);
        if (!valid_channel(ch) || freq < PWM_FREQ_MIN || freq > PWM_FREQ_MAX || duty < 0.0 || duty > 100.0) {
            std::fprintf(stderr, "invalid PWM arguments\n");
            return 2;
        }
        uint32_t period = static_cast<uint32_t>(std::floor(PWM_COUNTER_HZ / static_cast<double>(freq) + 0.5));
        uint32_t dcount = static_cast<uint32_t>(std::floor(period * duty / 100.0 + 0.5));
        payload.push_back(static_cast<uint8_t>((ch << 4) + 0x11));
        for (int i = 0; i < 4; ++i) {
            payload.push_back(static_cast<uint8_t>((period >> (8 * i)) & 0xFF));
        }
        for (int i = 0; i < 4; ++i) {
            payload.push_back(static_cast<uint8_t>((dcount >> (8 * i)) & 0xFF));
        }
    } else if (action == "stop" && argc == 3) {
        long ch = std::strtol(argv[2], nullptr, 10);
        if (!valid_channel(ch)) {
            std::fprintf(stderr, "invalid PWM channel\n");
            return 2;
        }
        payload.push_back(static_cast<uint8_t>((ch + 1) << 4));
    } else {
        std::fprintf(stderr, "bad arguments\n");
        return 2;
    }

    Device dev;
    auto err = dev.open();
    if (!err) {
        std::fprintf(stderr, "device open failed: %s\n", err.message.c_str());
        return 1;
    }
    auto werr = dev.transport().send_command(CommandCode::PWM, payload.data(), payload.size());
    dev.close();
    if (!werr) {
        std::fprintf(stderr, "PWM command failed: %s\n", werr.message.c_str());
        return 1;
    }

    std::printf("{\"ok\": true, \"action\": \"%s\", \"payload\": \"", action.c_str());
    for (uint8_t b : payload) {
        std::printf("%02x", b);
    }
    std::printf("\"}\n");
    return 0;
}
