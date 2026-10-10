#include "session_protocol.h"
#include <iostream>
#include <cassert>
#include <vector>
#include <cmath>
#include <limits>

int main() {
    using namespace atkdl16::session;

    // Test 1: valid PWM configure request parsing & exact vector check (1kHz/50% -> 11400d0300a0860100)
    {
        Value v;
        std::string err;
        Parser p(R"({"request_id":"req-1","command":"pwm","op":"configure","output":0,"frequency_hz":1000,"duty_percent":50.0})");
        if (!p.parse(v, err)) {
            std::cerr << "Test 1 parse failed: " << err << std::endl;
            return 1;
        }
        std::string op;
        int out = -1;
        int freq = 0;
        double duty = 0.0;
        if (!get_string(v, "op", op) || op != "configure") return 2;
        if (!get_integer(v, "output", out) || out != 0) return 3;
        if (!get_integer(v, "frequency_hz", freq) || freq != 1000) return 4;
        if (!get_number(v, "duty_percent", duty) || duty != 50.0) return 5;

        std::vector<uint8_t> payload;
        std::string p_err;
        if (!build_pwm_payload(op, out, freq, duty, payload, p_err)) return 6;
        if (payload.size() != 9) return 7;
        // Exact vector check against documented 1kHz/50% transaction
        const uint8_t expected_1k_50[9] = {0x11, 0x40, 0x0d, 0x03, 0x00, 0xa0, 0x86, 0x01, 0x00};
        for (size_t i = 0; i < 9; ++i) {
            if (payload[i] != expected_1k_50[i]) return 8;
        }
    }

    // Test 2: valid PWM stop request parsing & exact vector check
    {
        Value v;
        std::string err;
        Parser p(R"({"request_id":"req-2","command":"pwm","op":"stop","output":1})");
        if (!p.parse(v, err)) return 9;
        std::string op;
        int out = -1;
        if (!get_string(v, "op", op) || op != "stop") return 10;
        if (!get_integer(v, "output", out) || out != 1) return 11;

        std::vector<uint8_t> payload;
        std::string p_err;
        if (!build_pwm_payload(op, out, 0, 0.0, payload, p_err)) return 12;
        if (payload.size() != 1) return 13;
        if (payload[0] != 0x20) return 14; // (1 + 1) << 4
    }

    // Test 3: invalid parameters rejected (including NaN and inf)
    {
        std::vector<uint8_t> payload;
        std::string p_err;
        // Invalid output channel
        if (build_pwm_payload("configure", 2, 1000, 50.0, payload, p_err)) return 15;
        if (build_pwm_payload("stop", -1, 0, 0.0, payload, p_err)) return 16;
        // Invalid frequency (< 1 or > 20MHz)
        if (build_pwm_payload("configure", 0, 0, 50.0, payload, p_err)) return 17;
        if (build_pwm_payload("configure", 0, 20000001, 50.0, payload, p_err)) return 18;
        // Invalid duty (< 0, > 100, NaN, inf)
        if (build_pwm_payload("configure", 0, 1000, -1.0, payload, p_err)) return 19;
        if (build_pwm_payload("configure", 0, 1000, 100.1, payload, p_err)) return 20;
        if (build_pwm_payload("configure", 0, 1000, std::numeric_limits<double>::quiet_NaN(), payload, p_err)) return 21;
        if (build_pwm_payload("configure", 0, 1000, std::numeric_limits<double>::infinity(), payload, p_err)) return 22;
        if (build_pwm_payload("configure", 0, 1000, -std::numeric_limits<double>::infinity(), payload, p_err)) return 23;
        // Invalid op
        if (build_pwm_payload("unknown", 0, 1000, 50.0, payload, p_err)) return 24;
    }

    std::cout << "All session PWM codec tests passed." << std::endl;
    return 0;
}
