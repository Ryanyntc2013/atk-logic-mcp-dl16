#include "atkdl16/incremental_packed_writer.h"
#include "async_dispatcher.h"
#include <chrono>
#include <iostream>
#include <thread>
using namespace atkdl16;
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    std::string mode = argv[1];
    std::filesystem::path directory = argv[2];
    if (mode == "tail8" || mode == "tail12" || mode == "tail1") {
        try {
            IncrementalPackedWriter writer(directory,{8},1000000,1,"SYNTHETIC_OFFLINE");
            std::vector<uint8_t> bytes(125 + (mode == "tail8" ? 8 : mode == "tail12" ? 12 : 1),0x81);
            writer.append(8,bytes.data(),7);
            writer.append(8,bytes.data()+7,bytes.size()-7);
            writer.finish("TAIL_UNVERIFIED");
            return 0;
        } catch (...) { return 3; }
    }
    if (mode == "chunk") {
        try {
            IncrementalPackedWriter writer(directory,{8},20000000,30000,"SYNTHETIC_OFFLINE");
            uint8_t byte = 0x81;
            bool channel_rejected=false, size_rejected=false, closed_rejected=false;
            try { writer.append(14,&byte,1); } catch (const std::invalid_argument&) { channel_rejected=true; }
            try { writer.append(8,&byte,IncrementalPackedWriter::max_chunk+1); } catch (const std::invalid_argument&) { size_rejected=true; }
            writer.append(8,&byte,1);
            writer.finish("TAIL_UNVERIFIED");
            try { writer.append(8,&byte,1); } catch (const std::runtime_error&) { closed_rejected=true; }
            return channel_rejected && size_rejected && closed_rejected && writer.total_bytes()==1 ? 0 : 4;
        } catch (...) { return 3; }
    }
    if (mode == "invalid") {
        auto invalid = [&](std::vector<unsigned> channels, uint64_t rate, unsigned duration, uint64_t cap) {
            try { IncrementalPackedWriter writer(directory,channels,rate,duration,"SYNTHETIC_OFFLINE",cap); }
            catch (const std::invalid_argument&) { return !std::filesystem::exists(directory); }
            return false;
        };
        return invalid({0,1,2},1000000,1,1024) && invalid({0,0},1000000,1,1024) &&
               invalid({16},1000000,1,1024) && invalid({0},20000001,1,1024) &&
               invalid({0},1000000,30001,1024) && invalid({0},1000000,1,IncrementalPackedWriter::max_bytes+1) ? 0 : 4;
    }
    if (mode == "write" || mode == "cap" || mode == "abandon" || mode == "meta-error") {
        try {
            IncrementalPackedWriter writer(directory, {8,14}, 1000000, 1,
                                            "SYNTHETIC_OFFLINE", mode == "cap" ? 4 : 1024);
            uint8_t data[]{0x55,0xaa,0x81};
            writer.append(8, data, 3);
            if (mode == "abandon") return 0;
            if (mode == "meta-error") {
                std::filesystem::remove(directory / "stream_meta.json");
                std::filesystem::create_directory(directory / "stream_meta.json");
            }
            writer.append(14, data, 3);
            writer.finish("TAIL_UNVERIFIED");
            return 0;
        } catch (const std::exception& error) { std::cerr << error.what(); return 3; }
    }
    if (mode != "control") return 2;
    session::AsyncDispatcher dispatcher([](const std::string& text){std::cout<<text<<std::flush;});
    std::thread owner([&]{
        std::string line;
        while (dispatcher.next(line)) {
            session::Value req; std::string error,id,cmd;
            session::Parser parser(line); parser.parse(req,error);
            session::get_string(req,"request_id",id); session::get_string(req,"command",cmd);
            if (cmd == "hello") dispatcher.emit(session::response(id,"\"ok\":true,\"protocol\":1,\"commands\":[\"async_buffer_v1\"]"));
            else if (cmd == "capture") {
                try {
                    IncrementalPackedWriter writer(directory,{8,14},1000000,30000,"SYNTHETIC_OFFLINE");
                    std::array<uint8_t,4096> bytes{};
                    auto started = std::chrono::steady_clock::now();
                    while (!dispatcher.cancel.load() && std::chrono::steady_clock::now()-started < std::chrono::seconds(3)) {
                        writer.append(8,bytes.data(),bytes.size());
                        writer.append(14,bytes.data(),bytes.size());
                        std::this_thread::sleep_for(std::chrono::milliseconds(2));
                    }
                    writer.finish(dispatcher.cancel.load() ? "CANCELLED" : "TAIL_UNVERIFIED");
                    dispatcher.emit(session::response(id,"\"ok\":true,\"result\":{\"success\":false,\"data_integrity\":\"INCOMPLETE\",\"evidence_source\":\"SYNTHETIC_OFFLINE\",\"stored_bytes\":"+std::to_string(writer.total_bytes())+"}"));
                } catch (const std::exception&) {
                    dispatcher.emit(session::error_response(id,"WRITER_ERROR","incremental writer failed"));
                }
            } else if (cmd == "close") { dispatcher.emit(session::response(id,"\"ok\":true")); break; }
            else dispatcher.emit(session::error_response(id,"UNKNOWN_COMMAND","unsupported"));
        }
    });
    std::string line;
    while (std::getline(std::cin,line)) { dispatcher.submit(line); if(dispatcher.closing.load()) break; }
    dispatcher.finish(); owner.join(); return 0;
}
