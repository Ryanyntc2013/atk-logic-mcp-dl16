// Internal opt-in evidence probe, NOT a capture API. No tail removal or completeness claim.
#include "atkdl16/capture.h"
#include "atkdl16/protocol.h"
#include "session_protocol.h"
#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>
#include <stdexcept>

using namespace atkdl16;
using Clock = std::chrono::steady_clock;
constexpr uint64_t RAW_CAP = 32ULL * 1024 * 1024;
static bool valid(const CaptureConfig& c, uint64_t cap) {
    const std::vector<uint64_t> rates{1000000,2000000,4000000,5000000,10000000,20000000};
    return c.mode == CaptureMode::Stream && !c.enable_rle && c.trigger.is_instantly &&
        c.trigger.triggers.empty() && c.trigger.position_percent == 0 &&
        c.threshold_voltage == 1.6 && c.enabled_channels == std::vector<uint8_t>({8,14}) &&
        std::find(rates.begin(),rates.end(),c.sample_rate)!=rates.end() &&
        c.duration_ms >= 1 && c.duration_ms <= 100 && cap >= 16 && cap <= RAW_CAP;
}
static int remaining(Clock::time_point end, int maximum) {
    auto n=std::chrono::duration_cast<std::chrono::milliseconds>(end-Clock::now()).count();
    return n<=0 ? 0 : static_cast<int>(std::min<int64_t>(n,maximum));
}
static uint64_t integer(const char* text) {
    std::string s(text); if(s.empty() || s.find_first_not_of("0123456789")!=std::string::npos) throw std::runtime_error("invalid integer");
    return std::stoull(s);
}
static std::vector<uint8_t> pwm_frame(int channel, bool stop) {
    std::vector<uint8_t> payload; std::string error;
    if(!session::build_pwm_payload(stop ? "stop" : "configure", channel,
                                  channel==0 ? 1000 : 2000, 50, payload, error))
        throw std::runtime_error(error);
    return build_device_frame(CommandCode::PWM,payload.data(),payload.size());
}
static void hex(std::ostream& out,const std::vector<uint8_t>& p) {
    static const char* digits="0123456789abcdef";
    for(auto b:p) out << digits[b>>4] << digits[b&15];
}
struct Evidence {
    std::array<std::ofstream,16> channels;
    std::array<uint64_t,16> bytes{};
    std::ofstream events;
    uint64_t payload_bytes=0, short_bytes=0, order6=0;
    bool ack=false;
    void message(const RxMessage& m) {
        if(m.type==RxMessageType::ChannelData) {
            auto p=RxParser::parse_channel_data(m,false);
            if(!p || p->channel_id>=16) throw std::runtime_error("invalid channel payload");
            if(p->data.size()>RAW_CAP-payload_bytes) throw std::runtime_error("channel payload cap");
            channels[p->channel_id].write(reinterpret_cast<const char*>(p->data.data()),p->data.size());
            channels[p->channel_id].flush();
            if(!channels[p->channel_id]) throw std::runtime_error("channel write failed");
            bytes[p->channel_id]+=p->data.size(); payload_bytes+=p->data.size();
        } else if(m.type==RxMessageType::TriggerOffset || m.type==RxMessageType::Ack || m.type==RxMessageType::Complete) {
            events << "{\"order\":" << static_cast<unsigned>(m.type) << ",\"payload_hex\":\"";
            hex(events,m.payload); events << "\"";
            if(auto p=RxParser::parse_trigger_offset(m,16,false)) {
                events << ",\"trigger_sample_offset\":" << p->trigger_sample_offset << ",\"channel_byte_counts\":[";
                for(size_t i=0;i<p->channel_byte_counts.size();++i) {if(i) events << ','; events << p->channel_byte_counts[i];}
                events << ']';
            }
            if(auto p=RxParser::parse_ack(m)) ack=ack || (p->command_code==0x12 && p->status==3);
            if(auto p=RxParser::parse_complete(m,false)) { ++order6; events << ",\"stream_capacity_exceeded\":" << (p->is_stream_capacity_exceeded?"true":"false"); }
            events << "}\n"; events.flush(); if(!events) throw std::runtime_error("event write failed");
        }
    }
};
static void tx_evidence(std::ostream& out, const char* kind, const std::vector<uint8_t>& frame) {
    std::vector<uint8_t> linear(frame.size());
    convert_to_pc(frame.data(),linear.data(),frame.size());
    out << "{\"kind\":\"" << kind << "\",\"authority\":\"HOST_CONSTRUCTED_NOT_BUS_OBSERVED\",\"transport_hex\":\"";
    hex(out,frame); out << "\",\"linear_hex\":\""; hex(out,linear);
    out << "\"}\n";
}
static void profile_evidence(std::ostream& out, const DeviceInfo& info) {
    out << "{\"kind\":\"device_profile\",\"authority\":\"CACHED_DEVICE_OPEN_QUERY_NOT_INDEPENDENT_VERIFICATION\",\"vid\":" << info.vid
        << ",\"pid\":" << info.pid << ",\"model_enum\":" << static_cast<int>(info.model)
        << ",\"model_name_hex\":\"";
    hex(out,std::vector<uint8_t>(info.model_name.begin(),info.model_name.end()));
    out << "\",\"usb_speed_enum\":" << static_cast<int>(info.usb_speed)
        << ",\"mcu_firmware_version\":" << info.mcu_firmware_version
        << ",\"fpga_firmware_version\":" << info.fpga_firmware_version
        << ",\"hardware_version\":" << info.hardware_version
        << ",\"device_level\":" << info.device_level << ",\"channel_count\":" << info.channel_count
        << ",\"zero_or_unknown_fields_are_not_verified\":true}\n";
}
static int self_test() {
    CaptureConfig c; c.mode=CaptureMode::Stream; c.enabled_channels={8,14}; c.trigger.is_instantly=true; c.trigger.position_percent=0;
    auto check=[](bool b){if(!b)throw std::runtime_error("self-test failed");};
    check(valid(c,RAW_CAP)); c.duration_ms=100;check(valid(c,16)); c.duration_ms=101;check(!valid(c,RAW_CAP));
    c.duration_ms=0;check(!valid(c,RAW_CAP)); c.duration_ms=20; c.sample_rate=20000001;check(!valid(c,RAW_CAP));
    c.sample_rate=20000000;check(!valid(c,RAW_CAP+1));check(!valid(c,15));
    c.enable_rle=true;check(!valid(c,RAW_CAP));c.enable_rle=false;c.mode=CaptureMode::Buffer;check(!valid(c,RAW_CAP));
    c.mode=CaptureMode::Stream;c.enabled_channels={8,14,0};check(!valid(c,RAW_CAP));c.enabled_channels={8,14};
    c.trigger.is_instantly=false;check(!valid(c,RAW_CAP));c.trigger.is_instantly=true;
    auto frame=build_parameter_setting_frame(c);std::vector<uint8_t> linear(frame.size());convert_to_pc(frame.data(),linear.data(),frame.size());
    check(linear[11]==0); check(linear[13]==6);check(c.total_samples()==400000);
    frame=build_simple_trigger_frame(c);linear.resize(frame.size());convert_to_pc(frame.data(),linear.data(),frame.size());
    check(linear[10]==10 && linear[15]==0xf0 && linear[18]==0xf0 && linear[19]==1);
    check(remaining(Clock::now()-std::chrono::milliseconds(1),10)==0);
    check(remaining(Clock::now()+std::chrono::seconds(1),10)==10);
    std::vector<uint8_t> payload; std::string error;
    check(!session::build_pwm_payload("start",0,1000,50,payload,error));
    check(error=="unknown op: start");
    for(int ch=0;ch<2;++ch) {
        frame=pwm_frame(ch,false);linear.resize(frame.size());convert_to_pc(frame.data(),linear.data(),frame.size());
        check(linear[9]==0x17 && linear[10]==10 && linear[11]==(ch==0?0x11:0x21));
        auto le32=[&](size_t index){uint32_t value=0;for(unsigned i=0;i<4;++i)value|=static_cast<uint32_t>(linear[index+i])<<(8*i);return value;};
        check(le32(12)==(ch==0?200000:100000));check(le32(16)==(ch==0?100000:50000));
        frame=pwm_frame(ch,true);linear.resize(frame.size());convert_to_pc(frame.data(),linear.data(),frame.size());
        check(linear[9]==0x17 && linear[10]==2 && linear[11]==(ch==0?0x10:0x20));
    }
    for(const auto& f : {build_parameter_setting_frame(c),build_simple_trigger_frame(c)}) {
        std::vector<uint8_t> pc(f.size()), back(f.size());
        convert_to_pc(f.data(),pc.data(),f.size());convert_to_device(pc.data(),back.data(),pc.size());check(back==f);
        auto crc=compute_crc32(pc.data()+9,static_cast<size_t>(pc[10])+1);
        const size_t footer=10+pc[10];check(pc[footer]==0x0b);
        for(unsigned i=0;i<4;++i)check(pc[footer+1+i]==static_cast<uint8_t>(crc>>(8*i)));
    }
    tx_evidence(std::cout,"parameter",build_parameter_setting_frame(c));
    tx_evidence(std::cout,"trigger",build_simple_trigger_frame(c));
    DeviceInfo fixture;fixture.model_name="synthetic\"fixture";profile_evidence(std::cout,fixture);
    std::cout << "SYNTHETIC_OFFLINE stream mode/bounds/deadline/frame tests passed; PWM configure/stop exact production helper contract passed; TX roundtrip/CRC passed\n"; return 0;
}
int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="--self-test") return self_test();
        if(argc!=6 || std::string(argv[1])!="--diagnostic-stream-opt-in") throw std::runtime_error("usage: --diagnostic-stream-opt-in ABS_NEW_DIRECTORY RATE_HZ DURATION_MS RAW_CAP_BYTES (fixed CH8/CH14,1.6V,PWM0=1kHz/PWM1=2kHz 50%)");
        CaptureConfig c;c.mode=CaptureMode::Stream;c.enabled_channels={8,14};c.trigger.is_instantly=true;c.trigger.position_percent=0;
        c.sample_rate=integer(argv[3]);c.duration_ms=integer(argv[4]);auto cap=integer(argv[5]);
        if(!valid(c,cap))throw std::runtime_error("diagnostic bounds rejected before Device/filesystem");
        auto dir=std::filesystem::u8path(argv[2]);if(!valid_raw_rx_path(argv[2]) || !std::filesystem::create_directory(dir)) throw std::runtime_error("requires new absolute local directory with existing parent");
        Evidence e;e.events.open(dir/"orders.jsonl",std::ios::binary);
        for(int ch=0;ch<16;++ch) e.channels[ch].open(dir/("channel_"+std::to_string(ch)+".packed"),std::ios::binary);
        if(!e.events)throw std::runtime_error("event open failed");for(auto& f:e.channels)if(!f)throw std::runtime_error("channel open failed");
        RawRxLog metadata;RawRxWriter raw(metadata);if(!raw.open((dir/"raw-rx.bin").u8string(),cap))throw std::runtime_error(metadata.error);
        Device device;auto opened=device.open();if(!opened)throw std::runtime_error("device open failed: "+opened.message);
        const auto parameter_frame=build_parameter_setting_frame(c), trigger_frame=build_simple_trigger_frame(c);
        bool stop_attempted=false,stop_ok=false,pwm0_stop=false,pwm1_stop=false;
        auto send=[&](const std::vector<uint8_t>& f,int timeout){if(timeout<=0)throw std::runtime_error("send deadline expired");auto r=device.transport().write_bulk(EP_BULK_OUT,f.data(),f.size(),timeout);if(!r)throw std::runtime_error(r.message);};
        std::string reason="DEADLINE";
        {
            struct Cleanup {
                Device& d;bool& attempted;bool& ok;bool& p0;bool& p1;
                ~Cleanup(){attempted=true;auto f=build_stop_frame();ok=static_cast<bool>(d.transport().write_bulk(EP_BULK_OUT,f.data(),f.size(),50));
                    for(int ch=0;ch<2;++ch){f=pwm_frame(ch,true);bool r=static_cast<bool>(d.transport().write_bulk(EP_BULK_OUT,f.data(),f.size(),50));(ch==0?p0:p1)=r;}}
            } cleanup{device,stop_attempted,stop_ok,pwm0_stop,pwm1_stop};
            try {
                profile_evidence(e.events,device.info());
                tx_evidence(e.events,"parameter",parameter_frame);tx_evidence(e.events,"trigger",trigger_frame);
                e.events.flush();if(!e.events)throw std::runtime_error("TX/profile evidence write failed");
                for(int ch=0;ch<2;++ch) send(pwm_frame(ch,false),50);
                send(parameter_frame,50);std::this_thread::sleep_for(std::chrono::milliseconds(30));
                const auto deadline=Clock::now()+std::chrono::milliseconds(100);
                send(trigger_frame,remaining(deadline,20));
                RxParser parser;std::vector<uint8_t> input(16384),converted(16384);
                while(int timeout=remaining(deadline,10)) {
                    // Reserve a whole framed read before USB; never discard a cap-overflowing read.
                    const auto available=cap-metadata.bytes_written;
                    if(available<=8){reason="RAW_CAP";break;}
                    size_t n=0;auto requested=static_cast<size_t>(std::min<uint64_t>(input.size(),available-8));
                    auto status=device.transport().read_bulk(EP_BULK_IN,input.data(),requested,n,timeout);
                    if(!raw.append(input.data(),n,status.code) || metadata.truncated)throw std::runtime_error("raw log failure");
                    const auto aligned=n/2048*2048;e.short_bytes+=n-aligned;
                    if(aligned){convert_to_pc(input.data(),converted.data(),aligned);parser.push_bytes(converted.data(),aligned);while(auto m=parser.pop_message())e.message(*m);}
                    if(!status){reason="USB_ERROR";break;}
                    if(e.order6){reason="ORDER6_OBSERVED";break;}
                }
                e.events << "{\"parser_pending_bytes\":" << parser.buffered_bytes() << ",\"desync_count\":" << parser.desync_count() << "}\n";
            } catch(const std::exception& ex){reason="ERROR";std::cerr << ex.what() << '\n';}
        }
        device.close();bool files_ok=raw.close();e.events.close();files_ok=files_ok && !e.events.fail();
        for(auto& f:e.channels){f.close();files_ok=files_ok && !f.fail();}
        std::ofstream summary(dir/"summary.json",std::ios::binary);
        summary << "{\"format\":\"dl16-stream-evidence/v1\",\"diagnostic_only\":true,\"data_integrity\":\"UNKNOWN\",\"tail_status\":\"UNKNOWN\",\"uncropped\":true,\"mode\":\"STREAM\",\"rle\":false,\"sample_rate_hz\":" << c.sample_rate << ",\"duration_ms\":" << c.duration_ms << ",\"requested_samples\":" << c.total_samples() << ",\"receive_deadline_ms\":100,\"channels\":[8,14],\"threshold_voltage\":1.6,\"pwm_hz\":[1000,2000],\"pwm_duty_pct\":50,\"reason\":\"" << reason << "\",\"raw_bytes\":" << metadata.bytes_written << ",\"raw_reads\":" << metadata.reads << ",\"short_unconverted_bytes\":" << e.short_bytes << ",\"order6_count\":" << e.order6 << ",\"trigger_ack\":" << (e.ack?"true":"false") << ",\"stop_attempted\":" << (stop_attempted?"true":"false") << ",\"stop_write_ok\":" << (stop_ok?"true":"false") << ",\"pwm_stop_ok\":" << (pwm0_stop&&pwm1_stop?"true":"false") << ",\"files_ok\":" << (files_ok?"true":"false") << ",\"actual_channel_payload_bytes\":[";
        for(int ch=0;ch<16;++ch){if(ch)summary << ',';summary << e.bytes[ch];}summary << "],\"valid_samples\":null}\n";summary.close();
        std::cout << "DIAGNOSTIC_ONLY UNKNOWN " << reason << '\n';
        return files_ok && !summary.fail() && stop_ok && pwm0_stop && pwm1_stop && reason!="ERROR" && reason!="USB_ERROR" ? 0:1;
    } catch(const std::exception& ex){std::cerr << ex.what() << '\n';return 2;}
}
