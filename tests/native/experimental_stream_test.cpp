#include "async_dispatcher.h"
#include <iostream>
using namespace atkdl16;
static int io_calls=0;
static size_t fail_write(const void* p,size_t s,size_t n,FILE* f) {return ++io_calls==2?0:std::fwrite(p,s,n,f);}
static int fail_flush(FILE* f) {return ++io_calls==2?-1:std::fflush(f);}
static int fail_close(FILE* f) {std::fclose(f);return -1;}
int main(int argc,char** argv) {
    if(argc<2 || argc>3)return 2;
    const std::string mode=argc==3?argv[2]:"normal";
    session::AsyncDispatcher dispatcher([](const std::string& s){std::cout<<s<<std::flush;});
    std::thread owner([&]{std::string line;
        while(dispatcher.next(line)) {
            session::Value req; std::string error,id,cmd;session::Parser p(line);p.parse(req,error);
            session::get_string(req,"request_id",id);session::get_string(req,"command",cmd);
            if(cmd=="stream_start") {
                CaptureConfig cfg;std::string directory;
                if(!session::stream_config(req,cfg,directory))return;
                try {
                size_t count=0;io_calls=0;
                session::StreamRawIo io;
                if(mode=="raw_write_error")io.write=fail_write;
                if(mode=="raw_flush_error")io.flush=fail_flush;
                if(mode=="raw_close_error")io.close=fail_close;
                auto observed=session::run_stream(cfg,argv[1],dispatcher.cancel,
                    [&](const std::vector<uint8_t>& f,int){std::vector<uint8_t> pc(f.size());convert_to_pc(f.data(),pc.data(),f.size());
                        if(mode=="send_error" && pc[9]==0x12)return false;
                        if(mode=="stop_error" && pc[9]==0x15)return false;
                        if(pc[9]==0x11 && pc[11]!=0)throw std::runtime_error("not Stream");return true;},
                    [&](uint8_t* data,size_t,size_t& n,int){
                        if(mode=="usb_error"){n=0;return Error{ErrorCode::UsbTransferError,"synthetic error"};}
                        if(mode=="short" || mode=="error_bytes"){n=1024;for(size_t i=0;i<n;++i)data[i]=static_cast<uint8_t>(i);return Error{mode=="short"?ErrorCode::Ok:ErrorCode::DeviceDisconnected,"synthetic"};}
                        std::vector<uint8_t> pc(2048,0);
                        // Actual RX parser packet: all16 source channel, retain AA data as ordinary samples.
                        if(mode=="metadata_error" && count==1) {
                            std::filesystem::remove(std::filesystem::path(argv[1])/"stream_meta.json");
                            std::filesystem::create_directory(std::filesystem::path(argv[1])/"stream_meta.json");
                        }
                        unsigned ch=count++%16;std::vector<uint8_t> packet{0x0a,1,6,0,static_cast<uint8_t>(ch),0,0x81,0xaa,0xaa,0xaa,0,0x0b};
                        if(mode=="order6")packet={0x0a,6,0,0,0,0x0b};
                        std::copy(packet.begin(),packet.end(),pc.begin());convert_to_device(pc.data(),data,pc.size());n=pc.size();
                        std::this_thread::sleep_for(std::chrono::milliseconds(2));return Error::ok();
                    },"SYNTHETIC_OFFLINE",&dispatcher.stream_progress,io);
                dispatcher.emit(session::response(id,session::stream_result(observed,argv[1])));
                } catch(const std::exception& e) {dispatcher.emit(session::response(id,"\"ok\":false,\"error_code\":\"STREAM_WRITE_ERROR\",\"data_integrity\":\"INCOMPLETE\",\"message\":\""+json_escape(e.what())+"\",\"raw_rx_log\":"+dispatcher.stream_progress.raw_json()));}
            } else if(cmd=="close") {dispatcher.emit(session::response(id,"\"ok\":true"));break;}
            else dispatcher.emit(session::error_response(id,"UNKNOWN_COMMAND","unsupported"));
        }
    });
    std::string line;while(std::getline(std::cin,line)){dispatcher.submit(line);if(dispatcher.closing.load())break;}
    dispatcher.finish();owner.join();return 0;
}
