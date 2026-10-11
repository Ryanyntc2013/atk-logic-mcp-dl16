#pragma once
#include "atkdl16/capture.h"
#include "atkdl16/protocol.h"
#include "atkdl16/incremental_packed_writer.h"
#include "session_protocol.h"
#include <atomic>
#include <chrono>
#include <thread>

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
    // All sixteen physical channels, plus bounded unknown extras, not selected-channel bandwidth.
    if(((static_cast<uint64_t>(rate)*ms/1000+7)/8)*16 + 1048576 > IncrementalPackedWriter::max_bytes) return false;
    cfg.mode=CaptureMode::Stream; cfg.enable_rle=false; cfg.sample_rate=static_cast<uint64_t>(rate);
    cfg.duration_ms=ms; cfg.threshold_voltage=threshold; cfg.trigger.is_instantly=true;
    cfg.trigger.position_percent=0; return true;
}
struct StreamObservation {
    std::string reason{"DEADLINE"}, order3_hex;
    uint64_t stored_bytes=0, short_bytes=0, order6=0, reads=0;
    bool ack=false, stop_ok=false;
};
// Same receive/storage/control loop in live owner and USB-free injected-transport tests.
template<class Send, class Read>
StreamObservation run_stream(const CaptureConfig& cfg, const std::string& directory,
                             std::atomic<bool>& cancel, Send send, Read read,
                             const std::string& evidence="UNKNOWN") {
    std::vector<unsigned> channels; for(unsigned ch=0;ch<16;++ch) channels.push_back(ch);
    IncrementalPackedWriter writer(std::filesystem::u8path(directory),channels,cfg.sample_rate,
                                   static_cast<unsigned>(cfg.duration_ms),evidence,
                                   IncrementalPackedWriter::max_bytes-1048576,true);
    StreamObservation result;
    try {
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
                    size_t n=0; bool ok=read(input.data(),input.size(),n,static_cast<int>(std::min<int64_t>(remaining,10)));
                    ++result.reads;
                    if(n>input.size()) throw std::runtime_error("invalid RX size");
                    size_t aligned=n/2048*2048; result.short_bytes+=n-aligned;
                    if(n!=aligned) {result.reason="SHORT_RX";break;}
                    if(aligned) {
                        convert_to_pc(input.data(),linear.data(),aligned); parser.push_bytes(linear.data(),aligned);
                        while(auto m=parser.pop_message()) {
                            if(m->type==RxMessageType::ChannelData) {
                                auto p=RxParser::parse_channel_data(*m,false);
                                if(!p || p->channel_id>=16) throw std::runtime_error("invalid channel");
                                writer.append(p->channel_id,p->data.data(),p->data.size());
                            } else if(m->type==RxMessageType::TriggerOffset) {
                                if(m->payload.size()>256) throw std::runtime_error("order3 exceeds diagnostic bound");
                                static const char* digits="0123456789abcdef"; result.order3_hex.clear();
                                for(auto b:m->payload){result.order3_hex+=digits[b>>4];result.order3_hex+=digits[b&15];}
                            } else if(m->type==RxMessageType::Ack) {auto p=RxParser::parse_ack(*m);if(p)result.ack=result.ack||(p->command_code==0x12&&p->status==3);}
                            else if(m->type==RxMessageType::Complete) ++result.order6;
                        }
                    }
                    if(!ok){result.reason="USB_ERROR";break;}
                    if(result.order6){result.reason="ORDER6_OBSERVED";break;}
                }
                if(cancel.load())result.reason="CANCELLED";
            }
        }
    } catch(const std::exception& e) {result.reason=std::string(e.what())=="packed byte cap reached"?"BYTE_CAP":"OWNER_ERROR";}
    result.stop_ok=send(build_stop_frame(),50);
    result.stored_bytes=writer.total_bytes();
    writer.finish(result.reason);
    return result;
}
inline std::string stream_result(const StreamObservation& r,const std::string& directory) {
    return "\"ok\":true,\"result\":{\"success\":false,\"experimental\":true,\"mode\":\"STREAM\",\"data_integrity\":\"INCOMPLETE\",\"tail_status\":\"UNKNOWN\",\"analysis_ready\":false,\"valid_sample_count\":null,\"reason\":\""+r.reason+"\",\"stored_bytes\":"+std::to_string(r.stored_bytes)+",\"short_bytes\":"+std::to_string(r.short_bytes)+",\"order6_count\":"+std::to_string(r.order6)+",\"order3_raw_hex\":\""+r.order3_hex+"\",\"trigger_ack_received\":"+(r.ack?"true":"false")+",\"cleanup_stop_attempted\":true,\"cleanup_stop_ok\":"+(r.stop_ok?"true":"false")+",\"artifact_directory\":\""+json_escape(directory)+"\"}";
}
}
