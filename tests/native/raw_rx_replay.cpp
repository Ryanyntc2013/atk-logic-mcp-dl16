#include "atkdl16/protocol.h"
#include "atkdl16/rx_parser.h"
#include "atkdl16/constants.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cstdint>
#include <algorithm>
#include <array>
#include <stdexcept>

constexpr size_t MAX_RAW_BYTES = 32 * 1024 * 1024;
constexpr size_t MAX_FRAGMENT_BYTES = 65536;

using namespace atkdl16;

static void print_usage(const char* prog) {
    std::cerr << "Usage: " << prog << " [--raw <raw.bin>] [--frag-size <N>] [--json]\n"
              << "Options:\n"
              << "  --raw <path>        Path to raw binary RX capture file\n"
              << "  --frag-size <N>     Maximum feed fragment (0..65536; 0/default: one 2048-byte bank)\n"
              << "  --json              Output machine-readable JSON result summary\n";
}

int main(int argc, char* argv[]) {
    std::string raw_path;
    size_t frag_size = 2048;
    bool json_output = false;

    bool fragment_set = false;
    try {
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--raw" && i + 1 < argc && raw_path.empty()) {
                raw_path = argv[++i];
                if (raw_path.empty() || raw_path.front() == '-') {
                    throw std::invalid_argument("invalid --raw path");
                }
            } else if (arg == "--frag-size" && i + 1 < argc && !fragment_set) {
                const std::string value = argv[++i];
                if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos) {
                    throw std::invalid_argument("fragment size must be an unsigned decimal integer");
                }
                const auto parsed = std::stoull(value);
                if (parsed > MAX_FRAGMENT_BYTES) {
                    throw std::invalid_argument("fragment size exceeds 65536 bytes");
                }
                frag_size = parsed == 0 ? USB_BLOCK_SIZE : static_cast<size_t>(parsed);
                fragment_set = true;
            } else if (arg == "--json" && !json_output) {
                json_output = true;
            } else if ((arg == "--help" || arg == "-h") && argc == 2) {
                print_usage(argv[0]);
                return 0;
            } else {
                throw std::invalid_argument("unknown, duplicate or missing CLI argument: " + arg);
            }
        }
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << "\n";
        return 1;
    }

    if (raw_path.empty()) {
        std::cerr << "Error: --raw <path> is required.\n";
        print_usage(argv[0]);
        return 1;
    }

    std::ifstream in(raw_path, std::ios::binary);
    if (!in) {
        std::cerr << "Error: cannot open file " << raw_path << "\n";
        return 1;
    }

    in.seekg(0, std::ios::end);
    const auto file_size = in.tellg();
    if (file_size <= 0 || file_size > static_cast<std::streamoff>(MAX_RAW_BYTES)) {
        std::cerr << "Error: raw file must contain 1..33554432 bytes\n";
        return 1;
    }
    const size_t total_bytes = static_cast<size_t>(file_size);
    if (total_bytes % USB_BLOCK_SIZE != 0) {
        std::cerr << "Error: unaligned raw tail; only complete 2048-byte banks can be converted\n";
        return 1;
    }
    in.seekg(0, std::ios::beg);
    const size_t aligned_bytes = total_bytes;
    std::array<uint8_t, USB_BLOCK_SIZE> raw_bytes{};
    std::array<uint8_t, USB_BLOCK_SIZE> converted_bytes{};
    RxParser parser;
    std::vector<int> first_orders;
    uint64_t order_counts[16] = {0};
    uint64_t total_messages = 0;
    bool trigger_ack = false;
    bool trigger_offset_rec = false;
    bool complete_rec = false;

    // Convert one bank at a time; drain messages after every bounded feed.
    for (size_t bank = 0; bank < total_bytes; bank += USB_BLOCK_SIZE) {
        if (!in.read(reinterpret_cast<char*>(raw_bytes.data()), USB_BLOCK_SIZE)) {
            std::cerr << "Error: raw file changed or read failed\n";
            return 1;
        }
        convert_to_pc(raw_bytes.data(), converted_bytes.data(), USB_BLOCK_SIZE);
        size_t offset = 0;
        while (offset < converted_bytes.size()) {
            const size_t chunk = std::min(frag_size, converted_bytes.size() - offset);
            parser.push_bytes(converted_bytes.data() + offset, chunk);
            offset += chunk;

            while (parser.has_message()) {
                auto msg_opt = parser.pop_message();
                if (!msg_opt) break;
                const auto& msg = *msg_opt;
                int ord = static_cast<int>(msg.type);
                total_messages++;
                if (ord >= 0 && ord < 16) {
                    order_counts[ord]++;
                }
                if (first_orders.size() < 32) {
                    first_orders.push_back(ord);
                }

                switch (msg.type) {
                    case RxMessageType::TriggerOffset: {
                        trigger_offset_rec = true;
                        break;
                    }
                    case RxMessageType::Ack: {
                        auto ack = RxParser::parse_ack(msg);
                        if (ack && ack->command_code == static_cast<uint8_t>(CommandCode::SimpleTrigger)) {
                            if (ack->status == 3) trigger_ack = true;
                        }
                        break;
                    }
                    case RxMessageType::Complete: {
                        complete_rec = true;
                        break;
                    }
                    default:
                        break;
                }
            }
        }
    }

    if (in.peek() != std::char_traits<char>::eof()) {
        std::cerr << "Error: raw file grew during replay\n";
        return 1;
    }

    if (json_output) {
        std::cout << "{\n"
                  << "  \"evidence_source\": \"OFFLINE_REPLAY\",\n"
                  << "  \"input_provenance\": \"UNKNOWN\",\n"
                  << "  \"data_integrity\": \"UNKNOWN\",\n"
                  << "  \"capture_completeness\": \"UNKNOWN\",\n"
                  << "  \"buffered_bytes\": " << parser.buffered_bytes() << ",\n"
                  << "  \"total_raw_bytes\": " << total_bytes << ",\n"
                  << "  \"aligned_bytes\": " << aligned_bytes << ",\n"
                  << "  \"unaligned_tail_bytes\": " << (total_bytes - aligned_bytes) << ",\n"
                  << "  \"total_messages\": " << total_messages << ",\n"
                  << "  \"desync_count\": " << parser.desync_count() << ",\n"
                  << "  \"trigger_ack_received\": " << (trigger_ack ? "true" : "false") << ",\n"
                  << "  \"trigger_offset_received\": " << (trigger_offset_rec ? "true" : "false") << ",\n"
                  << "  \"capture_complete_received\": " << (complete_rec ? "true" : "false") << ",\n"
                  << "  \"first_orders\": [";
        for (size_t i = 0; i < first_orders.size(); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << first_orders[i];
        }
        std::cout << "],\n  \"order_counts\": {\n";
        bool first_entry = true;
        for (int i = 0; i < 16; ++i) {
            if (order_counts[i] > 0) {
                if (!first_entry) std::cout << ",\n";
                first_entry = false;
                std::cout << "    \"" << i << "\": " << order_counts[i];
            }
        }
        std::cout << "\n  }\n}\n";
    } else {
        std::cout << "Replay complete:\n"
                  << "  Raw bytes:       " << total_bytes << "\n"
                  << "  Messages parsed: " << total_messages << "\n"
                  << "  Desync count:    " << parser.desync_count() << "\n"
                  << "  Trigger ACK:     " << (trigger_ack ? "yes" : "no") << "\n"
                  << "  Trigger offset:  " << (trigger_offset_rec ? "yes" : "no") << "\n"
                  << "  Complete:        " << (complete_rec ? "yes" : "no") << "\n";
    }

    return 0;
}
