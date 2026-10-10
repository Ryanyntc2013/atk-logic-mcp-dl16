#include "atkdl16/types.h"
int main() {
    using atkdl16::experimental_depth_ready;
    std::vector<uint8_t> channels{8,14};
    std::map<uint8_t,uint64_t> samples{{8,0},{14,0}}, offsets;
    if (experimental_depth_ready(true,true,true,samples,offsets,channels,200000)) return 1;
    samples[8]=200000; samples[14]=199999;
    if (experimental_depth_ready(true,true,true,samples,offsets,channels,200000)) return 2;
    samples[14]=200000;
    if (!experimental_depth_ready(true,true,true,samples,offsets,channels,200000)) return 3;
    if (experimental_depth_ready(false,true,true,samples,offsets,channels,200000)) return 4;
    if (experimental_depth_ready(true,false,true,samples,offsets,channels,200000)) return 5;
    if (experimental_depth_ready(true,true,false,samples,offsets,channels,200000)) return 6;
    offsets[8]=1;
    if (experimental_depth_ready(true,true,true,samples,offsets,channels,200000)) return 7;
    offsets[8]=200001;
    if (experimental_depth_ready(true,true,true,samples,offsets,channels,200000)) return 8;
    return 0;
}
