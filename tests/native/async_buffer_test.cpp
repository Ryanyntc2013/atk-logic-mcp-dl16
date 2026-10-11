#include "async_dispatcher.h"
#include "atkdl16/sample_store.h"
#include "atkdl16/capture.h"
#include "atkdl16/json_util.h"
#include <chrono>
#include <iostream>
#include <thread>
using namespace atkdl16;
int main(int argc, char** argv) {
    if(argc==2 && std::string(argv[1])=="cancel-result") {
        if(incomplete_capture_error(true,false)!=ErrorCode::Ok ||
           incomplete_capture_error(false,true)!=ErrorCode::CaptureTimeout ||
           incomplete_capture_error(false,false)!=ErrorCode::CaptureTimeout) return 3;
        CaptureResult result;
        result.success=false; result.data_integrity=DataIntegrity::Incomplete;
        result.error_code=incomplete_capture_error(true,true);
        result.error_message="Capture was cancelled by user before completion";
        std::cout<<serialize_capture_result_json(result,"")<<std::endl;
        return result.error_code==ErrorCode::IncompleteCapture ? 0 : 4;
    }
    if(argc==3 && std::string(argv[1])=="artifact") {
        CaptureConfig config; config.enabled_channels={8}; config.async_buffer=true;
        SampleStore store(config); uint8_t bytes[2]={0x55,0xaa}; store.append_channel_data(8,bytes,2);
        CaptureResult result; result.requested_samples=100; result.data_integrity=DataIntegrity::Incomplete;
        return store.save_to_directory(argv[2],"partial",&result) ? 0 : 2;
    }
    // Actual production dispatcher, synthetic owner only: never instantiate Device.
    session::AsyncDispatcher dispatcher([](const std::string& text){std::cout<<text<<std::flush;});
    std::thread owner([&]{
        std::string line;
        while(dispatcher.next(line)) {
            session::Value req; std::string error,id,cmd;
            session::Parser parser(line); parser.parse(req,error);
            session::get_string(req,"request_id",id); session::get_string(req,"command",cmd);
            if(cmd=="hello") dispatcher.emit(session::response(id,"\"ok\":true,\"protocol\":1,\"commands\":[\"async_buffer_v1\"]"));
            else if(cmd=="capture") {
                auto start=std::chrono::steady_clock::now();
                while(!dispatcher.cancel.load() && std::chrono::steady_clock::now()-start<std::chrono::seconds(5))
                    std::this_thread::sleep_for(std::chrono::milliseconds(2));
                dispatcher.emit(session::response(id,"\"ok\":true,\"result\":{\"success\":false,\"data_integrity\":\"INCOMPLETE\",\"evidence_source\":\"SYNTHETIC_OFFLINE\",\"cancel_observed\":"+std::string(dispatcher.cancel.load()?"true":"false")+"}"));
            } else if(cmd=="close") {dispatcher.emit(session::response(id,"\"ok\":true"));break;}
            else dispatcher.emit(session::error_response(id,"UNKNOWN_COMMAND","unsupported"));
        }
    });
    std::string line;
    while(std::getline(std::cin,line)) {dispatcher.submit(line);if(dispatcher.closing.load())break;}
    dispatcher.finish(); owner.join(); return 0;
}
