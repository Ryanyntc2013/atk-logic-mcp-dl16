#pragma once
#include "session_protocol.h"
#include <atomic>
#include <condition_variable>
#include <deque>
#include <functional>
#include <mutex>
#include <thread>

namespace atkdl16::session {
// Input/control thread never touches Device; the owner alone executes queued work.
class AsyncDispatcher {
    std::mutex mutex_, output_mutex_;
    std::condition_variable ready_;
    std::deque<std::string> queue_;
    std::function<void(const std::string&)> output_;
    bool ending_{false}, active_{false};
    std::string operation_, result_;
public:
    std::atomic<bool> cancel{false};
    std::atomic<bool> closing{false};
    explicit AsyncDispatcher(std::function<void(const std::string&)> output) : output_(output) {}
    void output(const std::string& text) { std::lock_guard<std::mutex> lock(output_mutex_); output_(text); }
    void submit(const std::string& line) {
        Value req; std::string error, id, cmd;
        Parser parser(line);
        if (!parser.parse(req,error) || !get_string(req,"request_id",id) || id.empty() || id.size()>128 || !get_string(req,"command",cmd)) {
            std::lock_guard<std::mutex> lock(mutex_);
            if(!active_ && queue_.size()<8) { queue_.push_back(line);ready_.notify_one(); }
            else output(error_response("","INVALID_REQUEST","invalid asynchronous request"));
            return;
        }
        std::unique_lock<std::mutex> lock(mutex_);
        if(cmd=="stream_start" || cmd=="stream_poll" || cmd=="stream_cancel") {
            lock.unlock(); output(error_response(id,"STREAM_TAIL_UNVERIFIED","live Stream unavailable: incremental writer foundation only")); return;
        }
        if(cmd=="capture_poll" || cmd=="capture_cancel") {
            std::string op;
            if(!get_string(req,"operation_id",op) || op!=operation_ || op.empty()) {
                lock.unlock(); output(error_response(id,"UNKNOWN_OPERATION","operation ID does not match")); return;
            }
            if(cmd=="capture_cancel" && active_) cancel.store(true);
            std::string fields="\"ok\":true,\"operation_id\":\""+json_escape(op)+"\",\"state\":\""+(active_?"running":"finished")+"\"";
            if(!active_ && !result_.empty()) fields+=",\"response\":"+result_;
            lock.unlock(); output(response(id,fields)); return;
        }
        if(cmd=="capture_start") {
            std::vector<uint8_t> channels; int duration=0, timeout=30; double rate=0; std::string trigger="immediate";
            bool valid=parse_channels(req,channels) && channels.size()<=2 && get_integer(req,"duration_ms",duration) && duration>0 && duration<=30000 && get_number(req,"sample_rate_hz",rate) && rate>=1000000 && rate<=20000000;
            if(get(req,"trigger")) valid=valid && get_string(req,"trigger",trigger) && trigger=="immediate";
            if(get(req,"trigger_timeout_sec")) valid=valid && get_integer(req,"trigger_timeout_sec",timeout) && timeout>=1 && timeout<=30;
            if(get(req,"mode") || get(req,"rle")) valid=false;
            if(!valid) { lock.unlock(); output(error_response(id,"INVALID_CAPTURE","async BUFFER requires <=2 channels, <=20MHz, <=30s, immediate trigger, no mode/RLE")); return; }
            if(active_ || !queue_.empty()) { lock.unlock(); output(error_response(id,"SESSION_BUSY","owner is busy")); return; }
            active_=true; cancel.store(false); operation_=id; result_.clear();
            std::string work=line;
            // Find the command member rather than another user string with this value.
            size_t key=0, at=std::string::npos;
            while((key=work.find("\"command\"",key))!=std::string::npos) {
                auto colon=work.find(':',key+9);
                if(colon!=std::string::npos) {
                    auto value=work.find_first_not_of(" \t\r\n",colon+1);
                    if(value!=std::string::npos && work.compare(value,15,"\"capture_start\"")==0) {at=value;break;}
                }
                key+=9;
            }
            if(at==std::string::npos) {active_=false;lock.unlock();output(error_response(id,"INVALID_CAPTURE","command must use literal JSON member spelling"));return;}
            work.replace(at,15,"\"capture\"");
            queue_.push_back(work); ready_.notify_one();
            lock.unlock(); output(response(id,"\"ok\":true,\"operation_id\":\""+json_escape(id)+"\",\"state\":\"running\"")); return;
        }
        if(active_) { lock.unlock(); output(error_response(id,"SESSION_BUSY","cancel/poll active BUFFER operation before control commands")); return; }
        if(queue_.size()>=8) { lock.unlock(); output(error_response(id,"SESSION_BUSY","control queue full")); return; }
        if(cmd=="close") closing.store(true);
        queue_.push_back(line); ready_.notify_one();
    }
    bool is_operation(const std::string& id) { std::lock_guard<std::mutex> lock(mutex_); return active_ && id==operation_; }
    bool next(std::string& line) {
        std::unique_lock<std::mutex> lock(mutex_);
        ready_.wait(lock,[&]{return ending_ || !queue_.empty();});
        if(queue_.empty()) return false;
        line=std::move(queue_.front()); queue_.pop_front(); return true;
    }
    void emit(const std::string& text) {
        Value value; std::string error,id; Parser parser(text);
        std::unique_lock<std::mutex> lock(mutex_);
        if(active_ && parser.parse(value,error) && get_string(value,"request_id",id) && id==operation_) {
            result_=text; while(!result_.empty() && (result_.back()=='\n'||result_.back()=='\r')) result_.pop_back();
            active_=false; return;
        }
        lock.unlock(); output(text);
    }
    void finish() { std::lock_guard<std::mutex> lock(mutex_); ending_=true; cancel.store(true); ready_.notify_all(); }
};
}
