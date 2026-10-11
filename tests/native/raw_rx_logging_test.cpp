#include "atkdl16/capture.h"
#include "atkdl16/json_util.h"
#include <fstream>
#include <iostream>
#include <iterator>
using namespace atkdl16;
static int calls=0;
static size_t broken_write(const void* p,size_t s,size_t n,FILE* f) {
    return ++calls==2 ? 0 : std::fwrite(p,s,n,f);
}
static int broken_flush(FILE* f) { return ++calls==2 ? -1 : std::fflush(f); }
static int broken_close(FILE* f) { std::fclose(f); return -1; }
int main(int argc,char** argv) {
    if(argc!=2) return 1;
    auto base=std::filesystem::absolute(argv[1]);
    uint8_t bytes[]={0,10,255,11};
    RawRxLog disabled;
    { RawRxWriter w(disabled); if(!w.open("",32)||!w.append(bytes,4,ErrorCode::Ok)||!w.close()) return 2; }
    if(disabled.reads||disabled.bytes_written||disabled.enabled) return 3;
    RawRxLog exact;
    auto path=base.string()+"-exact.bin";
    { RawRxWriter w(exact); if(!w.open(path,28)||!w.append(bytes,4,ErrorCode::Ok)||!w.append(nullptr,0,ErrorCode::CaptureTimeout)||!w.close()) return 4; }
    std::ifstream in(path,std::ios::binary); std::string data((std::istreambuf_iterator<char>(in)),{});
    if(data.size()!=28||data.substr(0,8)!="DL16RX01"||static_cast<unsigned char>(data[8])!=4||data.substr(16,4)!=std::string(reinterpret_cast<char*>(bytes),4)||!exact.closed||exact.records!=2) return 5;
    RawRxLog collision; {RawRxWriter w(collision); if(w.open(path,28)||collision.error.empty()) return 6;}
    RawRxLog capped; {RawRxWriter w(capped); if(!w.open(base.string()+"-cap.bin",19)||!w.append(bytes,4,ErrorCode::Ok)||!w.append(bytes,4,ErrorCode::Ok)||!w.close()) return 7;}
    if(!capped.truncated||capped.bytes_written!=8||capped.records||capped.observed_bytes!=8||capped.reads!=2) return 8;
    for(int mode=0;mode<3;++mode) {
        calls=0; RawRxLog failed;
        RawRxWriter w(failed,mode==0?broken_write:std::fwrite,mode==1?broken_flush:std::fflush,mode==2?broken_close:std::fclose);
        if(!w.open(base.string()+"-fail"+std::to_string(mode)+".bin",32)) return 9;
        bool appended=w.append(bytes,4,ErrorCode::Ok); bool closed=w.close();
        if((mode<2&&appended)||closed||failed.error.empty()) return 10;
    }
    RawRxLog invalid; {RawRxWriter w(invalid);if(w.open("relative.bin",32))return 11;}
    RawRxLog missing; {RawRxWriter w(missing);if(w.open((base/"missing"/"file.bin").string(),32))return 12;}
    RawRxLog over; {RawRxWriter w(over);if(w.open(base.string()+"-over.bin",33554433))return 13;}
    CaptureResult r;r.raw_rx_log=capped;
    auto json=serialize_capture_result_json(r,"");
    if(json.find("\"truncated\":true")==std::string::npos||json.find("\"completeness\":\"UNKNOWN\"")==std::string::npos)return 14;
    std::cout<<"PASS: disabled, exact records, collision, truncation, write/flush/close failure, invalid path/limit, metadata\n";
}
