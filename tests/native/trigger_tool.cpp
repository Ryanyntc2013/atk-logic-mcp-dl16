// DL16-TASK-010: bounded SimpleTrigger gating probe (9B vs 10B payload).
//
// Sends ParameterSetting then a SimpleTrigger with a SELECTABLE payload layout,
// reads RX for a bounded window, and reports whether the capture completed and
// how long it took. This is a controlled, operator-approved experiment to decide
// whether the 9-byte (CPP/VENDOR) or 10-byte (LHX) simple-trigger payload actually
// gates acquisition. It sends Stop on exit and never touches firmware/driver.
#include "atkdl16/constants.h"
#include "atkdl16/device.h"
#include "atkdl16/protocol.h"
#include "atkdl16/rx_parser.h"
#include "atkdl16/types.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>
#include <vector>

using namespace atkdl16;

static bool has(const std::vector<uint8_t>& v, int x) {
    for (uint8_t e : v) {
        if (e == x) return true;
    }
    return false;
}

static void set_nibble(uint8_t& b, bool even, TriggerType t) {
    uint8_t en = even ? 0x80 : 0x08;
    b |= en;
    switch (t) {
        case TriggerType::RisingEdge:  b |= even ? 0x10 : 0x01; break;
        case TriggerType::FallingEdge: b |= even ? 0x20 : 0x02; break;
        case TriggerType::HighLevel:   b |= even ? 0x40 : 0x04; break;
        case TriggerType::LowLevel:    break;
        case TriggerType::DoubleEdge:  b |= even ? 0x30 : 0x03; break;
        default:                       b |= even ? 0x70 : 0x07; break;
    }
}

static std::vector<uint8_t> pair_bytes(const std::vector<uint8_t>& enabled, int trig_ch,
                                       TriggerType trig_type, bool immediate) {
    std::vector<uint8_t> out;
    for (int i = 0; i < 16; i += 2) {
        uint8_t b = 0;
        if (has(enabled, i)) {
            set_nibble(b, true, (i == trig_ch && !immediate) ? trig_type : TriggerType::None);
        }
        if (has(enabled, i + 1)) {
            set_nibble(b, false, (i + 1 == trig_ch && !immediate) ? trig_type : TriggerType::None);
        }
        out.push_back(b);
    }
    return out;
}

int main(int argc, char** argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: dl16-trigger <9b|10b> <channel 0..15> "
                             "<rising|falling|high|low|none> [timeout_ms=5000] [sample_rate_hz=20000000]\n");
        return 2;
    }
    std::string variant = argv[1];
    int channel = std::atoi(argv[2]);
    std::string edge = argv[3];
    int timeout_ms = (argc >= 5) ? std::atoi(argv[4]) : 5000;
    uint64_t rate = (argc >= 6) ? std::strtoull(argv[5], nullptr, 10) : 20'000'000ULL;
    if (variant != "9b" && variant != "10b") {
        std::fprintf(stderr, "variant must be 9b or 10b\n");
        return 2;
    }
    bool immediate = (edge == "none");
    TriggerType tt = TriggerType::None;
    if (edge == "rising") tt = TriggerType::RisingEdge;
    else if (edge == "falling") tt = TriggerType::FallingEdge;
    else if (edge == "high") tt = TriggerType::HighLevel;
    else if (edge == "low") tt = TriggerType::LowLevel;
    else if (!immediate) {
        std::fprintf(stderr, "edge must be rising/falling/high/low/none\n");
        return 2;
    }

    Device dev;
    Error err;
    for (int attempt = 0; attempt < 6; ++attempt) {
        err = dev.open();
        if (err) break;
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
    }
    if (!err) {
        std::fprintf(stderr, "open failed: %s\n", err.message.c_str());
        return 1;
    }

    CaptureConfig cfg;
    cfg.mode = CaptureMode::Buffer;
    cfg.sample_rate = rate;
    cfg.duration_ms = 20;
    cfg.threshold_voltage = 1.6;
    cfg.enabled_channels = {static_cast<uint8_t>(channel)};
    cfg.trigger.position_percent = 50.0;
    cfg.trigger.is_instantly = immediate;
    if (!immediate) {
        cfg.trigger.triggers = {ChannelTrigger{static_cast<uint8_t>(channel), tt}};
    }

    dev.wake_fpga();
    dev.flush_buffers();
    auto param = build_parameter_setting_frame(cfg);
    auto werr = dev.transport().write_bulk(EP_BULK_OUT, param.data(), param.size(), 200);
    if (!werr) {
        std::fprintf(stderr, "ParameterSetting failed: %s\n", werr.message.c_str());
        dev.close();
        return 1;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(30));

    std::vector<uint8_t> payload = pair_bytes(cfg.enabled_channels, channel, tt, immediate);
    if (variant == "9b") {
        payload.push_back(immediate ? 1 : 0);          // VENDOR/CPP 9-byte
    } else {
        payload.push_back(0x00);                       // LHX/HUGEL 10-byte collect type
        payload.push_back(0x00);
    }
    auto trig = build_device_frame(CommandCode::SimpleTrigger, payload.data(), payload.size());
    werr = dev.transport().write_bulk(EP_BULK_OUT, trig.data(), trig.size(), 200);
    if (!werr) {
        std::fprintf(stderr, "SimpleTrigger failed: %s\n", werr.message.c_str());
        dev.close();
        return 1;
    }

    RxParser parser;
    std::vector<uint8_t> raw(READ_TRANSFER_BUFFER_SIZE);
    std::vector<uint8_t> conv(READ_TRANSFER_BUFFER_SIZE);
    bool ack = false, offset = false, complete = false;
    auto start = std::chrono::steady_clock::now();
    int order4_status = -1;
    while (std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::steady_clock::now() - start).count() < timeout_ms) {
        size_t actual = 0;
        auto rerr = dev.transport().read_bulk(EP_BULK_IN, raw.data(), raw.size(), actual, 200);
        if (!rerr && rerr.code == ErrorCode::DeviceDisconnected) break;
        if (actual >= USB_BLOCK_SIZE) {
            size_t aligned = (actual / USB_BLOCK_SIZE) * USB_BLOCK_SIZE;
            if (conv.size() < aligned) conv.resize(aligned);
            convert_to_pc(raw.data(), conv.data(), aligned);
            parser.push_bytes(conv.data(), aligned);
            while (parser.has_message()) {
                auto m = parser.pop_message();
                if (!m) break;
                if (m->type == RxMessageType::Ack) {
                    auto a = RxParser::parse_ack(*m);
                    if (a && a->command_code == static_cast<uint8_t>(CommandCode::SimpleTrigger)) {
                        ack = true;
                        order4_status = a->status;
                    }
                } else if (m->type == RxMessageType::TriggerOffset) {
                    offset = true;
                } else if (m->type == RxMessageType::Complete) {
                    complete = true;
                }
            }
            if (complete) break;
        }
    }
    long elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - start).count();

    auto stop = build_stop_frame();
    dev.transport().write_bulk(EP_BULK_OUT, stop.data(), stop.size(), 100);
    dev.close();

    std::printf("{\"variant\": \"%s\", \"channel\": %d, \"edge\": \"%s\", "
                "\"completed\": %s, \"elapsed_ms\": %ld, \"ack\": %s, \"order4_status\": %d, "
                "\"trigger_offset\": %s, \"complete\": %s}\n",
                variant.c_str(), channel, edge.c_str(), complete ? "true" : "false",
                elapsed, ack ? "true" : "false", order4_status,
                offset ? "true" : "false", complete ? "true" : "false");
    return 0;
}
