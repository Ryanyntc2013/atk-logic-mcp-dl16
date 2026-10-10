// Optional DL16-TASK-002 offline cross-check harness.
//
// Builds against the pinned GPL-3.0 C++ core (atkdl16_core) and dumps the same
// byte-level vectors as tests/protocol_reference.py, so a host can assert that
// the C++ backend and the independent Python reference agree byte-for-byte.
// It touches no USB device and no live backend.
#include "atkdl16/constants.h"
#include "atkdl16/protocol.h"
#include "atkdl16/rx_parser.h"
#include "atkdl16/types.h"

#include <cstdint>
#include <cstdio>
#include <optional>
#include <vector>

using namespace atkdl16;

static void print_hex(const std::vector<uint8_t>& v) {
    for (uint8_t b : v) {
        std::printf("%02x", b);
    }
}

static std::vector<uint8_t> deinterleave(const std::vector<uint8_t>& frame) {
    std::vector<uint8_t> raw(frame.size());
    convert_to_pc(frame.data(), raw.data(), frame.size());
    return raw;
}

// raw layout: [8x00][0x0A][code][len][payload...][0x0B][crc32]
static std::vector<uint8_t> payload_of(const std::vector<uint8_t>& frame) {
    auto raw = deinterleave(frame);
    size_t payload_len = static_cast<size_t>(raw[10]) - 1;
    return std::vector<uint8_t>(raw.begin() + 11, raw.begin() + 11 + payload_len);
}

static std::vector<uint8_t> make_rx(uint8_t order, const std::vector<uint8_t>& p) {
    std::vector<uint8_t> f;
    f.push_back(RX_FRAME_START);
    f.push_back(order);
    f.push_back(static_cast<uint8_t>(p.size() & 0xFF));
    f.push_back(static_cast<uint8_t>((p.size() >> 8) & 0xFF));
    f.insert(f.end(), p.begin(), p.end());
    f.push_back(RX_FRAME_SEP);
    f.push_back(RX_FRAME_END);
    return f;
}

int main() {
    const char* text = "123456789";
    std::printf("{\n");
    std::printf("  \"crc_123456789\": \"%08x\",\n", compute_crc32(reinterpret_cast<const uint8_t*>(text), 9));
    std::printf("  \"crc_empty\": \"%08x\",\n", compute_crc32(nullptr, 0));

    CaptureConfig tcfg;
    tcfg.enabled_channels = {0};
    tcfg.trigger.triggers = {ChannelTrigger{0, TriggerType::RisingEdge}};
    tcfg.trigger.is_instantly = false;
    auto trig = payload_of(build_simple_trigger_frame(tcfg));
    std::printf("  \"trigger_payload\": \"");
    print_hex(trig);
    std::printf("\",\n");

    CaptureConfig pcfg;
    pcfg.mode = CaptureMode::Buffer;
    pcfg.sample_rate = 20000000ULL;
    pcfg.duration_ms = 20;
    pcfg.threshold_voltage = 1.6;
    pcfg.enabled_channels = {0, 1};
    pcfg.trigger.position_percent = 9.0;
    pcfg.trigger.is_instantly = true;
    pcfg.enable_rle = false;
    auto par = payload_of(build_parameter_setting_frame(pcfg));
    std::printf("  \"parameter_payload\": \"");
    print_hex(par);
    std::printf("\",\n");

    std::vector<uint8_t> src(USB_BLOCK_SIZE);
    for (size_t i = 0; i < src.size(); ++i) {
        src[i] = static_cast<uint8_t>(i & 0xFF);
    }
    std::vector<uint8_t> bank(USB_BLOCK_SIZE);
    convert_to_device(src.data(), bank.data(), USB_BLOCK_SIZE);
    std::printf("  \"bank_transform_hex\": \"");
    print_hex(bank);
    std::printf("\",\n");

    auto gdf = build_get_device_data_frame();
    std::printf("  \"get_device_data_frame_hex\": \"");
    print_hex(gdf);
    std::printf("\",\n");

    // --- RX reassembly + order-3 parse cross-check ---
    std::vector<uint8_t> o3;
    o3.push_back(0);
    o3.push_back(0);
    for (int b = 0; b < 5; ++b) {
        o3.push_back(static_cast<uint8_t>((800ULL >> (8 * b)) & 0xFF));
    }
    for (int i = 0; i < 16; ++i) {
        uint64_t count = (i == 0 || i == 1) ? 128ULL : 0ULL;
        for (int b = 0; b < 5; ++b) {
            o3.push_back(static_cast<uint8_t>((count >> (8 * b)) & 0xFF));
        }
    }
    o3.push_back(0x01);  // RLE flags: exceed_capacity

    std::vector<uint8_t> stream;
    auto f1 = make_rx(1, {2, 0, 0xAA, 0xBB});
    auto f3 = make_rx(3, o3);
    auto f4 = make_rx(4, {0, 0, static_cast<uint8_t>(CommandCode::SimpleTrigger), 3});
    auto f6 = make_rx(6, {});
    for (auto* v : {&f1, &f3, &f4, &f6}) {
        stream.insert(stream.end(), v->begin(), v->end());
    }

    RxParser parser;
    parser.push_bytes(stream.data(), stream.size());
    std::vector<int> orders;
    std::optional<TriggerOffsetMsg> trigo;
    while (parser.has_message()) {
        auto m = parser.pop_message();
        if (!m) {
            break;
        }
        orders.push_back(static_cast<int>(m->type));
        if (m->type == RxMessageType::TriggerOffset) {
            trigo = RxParser::parse_trigger_offset(*m, 16, true);
        }
    }

    std::printf("  \"rx_orders\": [");
    for (size_t i = 0; i < orders.size(); ++i) {
        std::printf("%s%d", i ? ", " : "", orders[i]);
    }
    std::printf("],\n");
    std::printf("  \"rx_desync\": %zu,\n", parser.desync_count());
    if (trigo && trigo->channel_byte_counts.size() >= 2) {
        std::printf("  \"rx_trigger_offset\": %llu,\n",
                    static_cast<unsigned long long>(trigo->trigger_sample_offset));
        std::printf("  \"rx_counts_first2\": [%llu, %llu],\n",
                    static_cast<unsigned long long>(trigo->channel_byte_counts[0]),
                    static_cast<unsigned long long>(trigo->channel_byte_counts[1]));
        std::printf("  \"rx_exceed_capacity\": %s\n", trigo->exceed_capacity ? "true" : "false");
    } else {
        std::printf("  \"rx_trigger_offset\": null,\n"
                    "  \"rx_counts_first2\": null,\n"
                    "  \"rx_exceed_capacity\": null\n");
    }
    std::printf("}\n");
    return 0;
}
