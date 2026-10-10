#include "atkdl16/types.h"
#include "atkdl16/json_util.h"
#include <iostream>
int main() {
    atkdl16::CaptureResult r;
    auto& d = r.diagnostics;
    d.observe_read(512);
    if (d.reads) return 1;
    d.enabled = true;
    d.observe_read(512); d.observe_read(4096);
    for (unsigned i=0;i<100;++i) d.observe_order(6);
    d.before_crop[8]=200000; d.after_crop[8]=0; d.offsets[8]=200000;
    if (d.reads!=2 || d.bytes!=4608 || d.short_reads!=1 || d.unaligned_bytes!=512
        || d.messages!=100 || d.first_orders.size()!=32 || d.orders[6]!=100) return 2;
    r.success=false;
    auto failed=atkdl16::serialize_capture_result_json(r, "");
    r.success=true;
    auto passed=atkdl16::serialize_capture_result_json(r, "");
    if (failed.find("dl16-rx-diagnostics/v1")==std::string::npos
        || passed.find("samples_before_crop")==std::string::npos) return 3;
    std::cout << failed << passed;
    return 0;
}
