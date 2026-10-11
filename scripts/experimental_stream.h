#pragma once
#include "atkdl16/capture.h"
#include "atkdl16/protocol.h"
#include "atkdl16/incremental_packed_writer.h"
#include "session_protocol.h"
#include <atomic>
#include <chrono>
#include <thread>
#include <mutex>
#include <sstream>

namespace atkdl16::session {
inline bool stream_config(const Value& req, CaptureConfig& cfg, std::string& out) {
    int ms=0; double rate=0,threshold=0; std::string confirmation;
    auto opt=get(req,"experimental_opt_in");
    if(!opt || opt->kind!=Value::Kind::Boolean || !opt->boolean ||
       !get_string(req,"safety_confirmation",confirmation) || confirmation!="CONFIRMED_SAFE_WIRING_GUI_CLOSED" ||
       !parse_channels(req,cfg.enabled_channels) || cfg.enabled_channels.size()>2 ||
       !get_integer(req,"duration_ms",ms) || ms<1 || ms>30000 ||
       !get_number(req,"sample_rate_hz",rate) ||
       !get_number(req,"threshold_voltage",threshold) || threshold < -5 || threshold > 5 ||
       !get_string(req,"output_dir",out) || !valid_raw_rx_path(out) ||
       get(req,"mode") || get(req,"rle") || get(req,"trigger") || get(req,"raw_rx_path")) return false;
    const std::vector<double> rates{1000000,2000000,4000000,5000000,10000000,20000000};
    if(std::find(rates.begin(),rates.end(),rate)==rates.end()) return false;
    auto logging=get(req,"raw_rx_logging");
    bool enabled=false;
    if(logging) { if(logging->kind!=Value::Kind::Boolean)return false; enabled=logging->boolean; }
    int limit=33554432;
    if(get(req,"raw_rx_max_bytes") && (!enabled || !get_integer(req,"raw_rx_max_bytes",limit)))return false;
    if(limit<8 || limit>33554432)return false;
    cfg.raw_rx_path=enabled?(std::filesystem::u8path(out)/"rx.bin").u8string():"";
    cfg.raw_rx_max_bytes=enabled?limit:0;
    // All sixteen physical channels, plus bounded unknown extras, not selected-channel bandwidth.
    if(((static_cast<uint64_t>(rate)*ms/1000+7)/8)*16 + 1048576 + cfg.raw_rx_max_bytes > IncrementalPackedWriter::max_bytes) return false;
    cfg.mode=CaptureMode::Stream; cfg.enable_rle=false; cfg.sample_rate=static_cast<uint64_t>(rate);
    cfg.duration_ms=ms; cfg.threshold_voltage=threshold; cfg.trigger.is_instantly=true;
    cfg.trigger.position_percent=0; return true;
}
inline std::string stream_raw_json(const RawRxLog& d) {
    std::ostringstream s;
    s << "{\"schema\":\"dl16-raw-rx/v1\",\"completeness\":\"UNKNOWN\",\"enabled\":" << (d.enabled?"true":"false")
      << ",\"path\":\"" << json_escape(d.path) << "\",\"max_bytes\":" << d.max_bytes
      << ",\"bytes_written\":" << d.bytes_written << ",\"payload_bytes\":" << d.payload_bytes
      << ",\"observed_bytes\":" << d.observed_bytes << ",\"reads\":" << d.reads << ",\"records\":" << d.records
      << ",\"truncated\":" << (d.truncated?"true":"false") << ",\"closed\":" << (d.closed?"true":"false")
      << ",\"error\":\"" << json_escape(d.error) << "\"}";
    return s.str();
}
struct StreamProgress {
    mutable std::mutex raw_mutex;
    RawRxLog raw;
    void publish_raw(const RawRxLog& value) { std::lock_guard<std::mutex> lock(raw_mutex);raw=value; }
    std::string raw_json() const { std::lock_guard<std::mutex> lock(raw_mutex);return stream_raw_json(raw); }
    std::atomic<uint64_t> stored_bytes{0}, reads{0}, receive_elapsed_ns{0}, packed_write_elapsed_ns{0}, packed_flush_elapsed_ns{0};
    void reset() { publish_raw(RawRxLog{}); stored_bytes.store(0); reads.store(0); receive_elapsed_ns.store(0); packed_write_elapsed_ns.store(0); packed_flush_elapsed_ns.store(0); }
    std::string json() const {
        return "\"raw_rx_log\":"+raw_json()+","+ "\"stored_bytes\":"+std::to_string(stored_bytes.load())+",\"reads\":"+std::to_string(reads.load())+",\"receive_elapsed_ns\":"+std::to_string(receive_elapsed_ns.load())+",\"packed_write_elapsed_ns\":"+std::to_string(packed_write_elapsed_ns.load())+",\"packed_flush_elapsed_ns\":"+std::to_string(packed_flush_elapsed_ns.load());
    }
};
struct StreamRawIo {
    size_t (*write)(const void*,size_t,size_t,FILE*)=std::fwrite;
    int (*flush)(FILE*)=std::fflush;
    int (*close)(FILE*)=std::fclose;
};
struct StreamObservation {
    std::string reason{"DEADLINE"}, order3_hex;
    uint64_t stored_bytes=0, short_bytes=0, order6=0, reads=0;
    uint64_t receive_elapsed_ns=0, packed_write_elapsed_ns=0, packed_flush_elapsed_ns=0;
    RawRxLog raw_rx_log;
    bool ack=false, stop_ok=false;
};
// Same receive/storage/control loop in live owner and USB-free injected-transport tests.
template<class Send, class Read>
StreamObservation run_stream(const CaptureConfig& cfg, const std::string& directory,
                             std::atomic<bool>& cancel, Send send, Read read,
                             const std::string& evidence="UNKNOWN", StreamProgress* progress=nullptr, StreamRawIo io={}) {
    std::vector<unsigned> channels; for(unsigned ch=0;ch<16;++ch) channels.push_back(ch);
    IncrementalPackedWriter writer(std::filesystem::u8path(directory),channels,cfg.sample_rate,
                                   static_cast<unsigned>(cfg.duration_ms),evidence,
                                   IncrementalPackedWriter::max_bytes-1048576-cfg.raw_rx_max_bytes,true);
    StreamObservation result;
    RawRxWriter raw(result.raw_rx_log,io.write,io.flush,io.close);
    auto publish=[&] {
        result.stored_bytes=writer.total_bytes();
        result.packed_write_elapsed_ns=writer.write_elapsed_ns();
        result.packed_flush_elapsed_ns=writer.flush_elapsed_ns();
        if(progress) {
            progress->publish_raw(result.raw_rx_log);
            progress->reads.store(result.reads); progress->receive_elapsed_ns.store(result.receive_elapsed_ns);
            progress->packed_write_elapsed_ns.store(result.packed_write_elapsed_ns);
            progress->packed_flush_elapsed_ns.store(result.packed_flush_elapsed_ns);
            progress->stored_bytes.store(result.stored_bytes);
        }
    };
    try {
        if(!raw.open(cfg.raw_rx_path,cfg.raw_rx_max_bytes)) throw std::runtime_error("raw RX open failed");
        publish();
        if(cancel.load()) result.reason="CANCELLED";
        else {
            if(!send(build_parameter_setting_frame(cfg),50)) throw std::runtime_error("parameter write failed");
            std::this_thread::sleep_for(std::chrono::milliseconds(30));
            if(cancel.load()) result.reason="CANCELLED";
            else {
                if(!send(build_simple_trigger_frame(cfg),50)) throw std::runtime_error("trigger write failed");
                const auto end=std::chrono::steady_clock::now()+std::chrono::milliseconds(cfg.duration_ms);
                RxParser parser; std::array<uint8_t,16384> input{},linear{};
                while(!cancel.load()) {
                    auto remaining=std::chrono::duration_cast<std::chrono::milliseconds>(end-std::chrono::steady_clock::now()).count();
                    if(remaining<=0) break;
                    const auto receive_start=std::chrono::steady_clock::now();
                    size_t n=0; auto status=read(input.data(),input.size(),n,static_cast<int>(std::min<int64_t>(remaining,10)));
                    result.receive_elapsed_ns+=static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-receive_start).count());
                    ++result.reads; publish();
                    if(n>input.size()) throw std::runtime_error("invalid RX size");
                    if(!raw.append(input.data(),n,status.code)) throw std::runtime_error("raw RX record failed");
                    publish();
                    size_t aligned=n/2048*2048; result.short_bytes+=n-aligned;
                    if(n!=aligned) {result.reason="SHORT_RX";break;}
                    if(aligned) {
                        convert_to_pc(input.data(),linear.data(),aligned); parser.push_bytes(linear.data(),aligned);
                        while(auto m=parser.pop_message()) {
                            if(m->type==RxMessageType::ChannelData) {
                                auto p=RxParser::parse_channel_data(*m,false);
                                if(!p || p->channel_id>=16) throw std::runtime_error("invalid channel");
                                writer.append(p->channel_id,p->data.data(),p->data.size());
                                publish();
                            } else if(m->type==RxMessageType::TriggerOffset) {
                                if(m->payload.size()>256) throw std::runtime_error("order3 exceeds diagnostic bound");
                                static const char* digits="0123456789abcdef"; result.order3_hex.clear();
                                for(auto b:m->payload){result.order3_hex+=digits[b>>4];result.order3_hex+=digits[b&15];}
                            } else if(m->type==RxMessageType::Ack) {auto p=RxParser::parse_ack(*m);if(p)result.ack=result.ack||(p->command_code==0x12&&p->status==3);}
                            else if(m->type==RxMessageType::Complete) ++result.order6;
                        }
                    }
                    if(!status){result.reason="USB_ERROR";break;}
                    if(result.order6){result.reason="ORDER6_OBSERVED";break;}
                }
                if(cancel.load() && result.reason=="DEADLINE")result.reason="CANCELLED";
            }
        }
    } catch(const std::exception& e) {result.reason=std::string(e.what())=="packed byte cap reached"?"BYTE_CAP":"OWNER_ERROR";}
    try { result.stop_ok=send(build_stop_frame(),50); } catch(...) { result.stop_ok=false; }
    if(!raw.close()) result.reason="OWNER_ERROR";
    result.stored_bytes=writer.total_bytes();
    publish();
    writer.finish(result.reason);
    publish();
    std::ofstream meta(std::filesystem::u8path(directory)/"stream_rx_meta.json",std::ios::trunc);
    meta << "{\"data_integrity\":\"INCOMPLETE\",\"reason\":\"" << result.reason << "\",\"raw_rx_log\":" << stream_raw_json(result.raw_rx_log) << "}\n";
    meta.flush(); if(!meta)throw std::runtime_error("raw metadata write failed");
    meta.close();if(meta.fail())throw std::runtime_error("raw metadata close failed");
    return result;
}
inline std::string stream_result(const StreamObservation& r,const std::string& directory) {
    return "\"ok\":true,\"result\":{\"error_code\":\""+std::string(r.raw_rx_log.error.empty()?"INCOMPLETE_CAPTURE":"ARTIFACT_WRITE_ERROR")+"\",\"raw_rx_log\":"+stream_raw_json(r.raw_rx_log)+",\"success\":false,\"experimental\":true,\"mode\":\"STREAM\",\"data_integrity\":\"INCOMPLETE\",\"tail_status\":\"UNKNOWN\",\"analysis_ready\":false,\"valid_sample_count\":null,\"reason\":\""+r.reason+"\",\"stored_bytes\":"+std::to_string(r.stored_bytes)+",\"reads\":"+std::to_string(r.reads)+",\"receive_elapsed_ns\":"+std::to_string(r.receive_elapsed_ns)+",\"packed_write_elapsed_ns\":"+std::to_string(r.packed_write_elapsed_ns)+",\"packed_flush_elapsed_ns\":"+std::to_string(r.packed_flush_elapsed_ns)+",\"short_bytes\":"+std::to_string(r.short_bytes)+",\"order6_count\":"+std::to_string(r.order6)+",\"order3_raw_hex\":\""+r.order3_hex+"\",\"trigger_ack_received\":"+(r.ack?"true":"false")+",\"cleanup_stop_attempted\":true,\"cleanup_stop_ok\":"+(r.stop_ok?"true":"false")+",\"artifact_directory\":\""+json_escape(directory)+"\"}";
}
}
