cmake_minimum_required(VERSION 3.20)
project(dl16_vector_harness LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(MSVC)
    # Match the pinned core's static CRT (/MT).
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
endif()

get_filename_component(UP "${CMAKE_CURRENT_SOURCE_DIR}/../../external/ATK-Logic-Mcp" ABSOLUTE)
if(NOT EXISTS "${UP}/build/Release/atkdl16_core.lib")
    message(FATAL_ERROR "Pinned core not built. Run scripts/bootstrap-native.ps1 first.")
endif()

add_executable(dl16-vector-dump vector_dump.cpp)
target_include_directories(dl16-vector-dump PRIVATE
    "${UP}/core/include"
    "${UP}/third_party/libusb/include"
)
# protocol.cpp has no USB dependency, but link the (non-/GL) DLL import library so the
# harness builds on older local toolchains exactly like the main backend.
target_link_libraries(dl16-vector-dump PRIVATE
    "${UP}/build/Release/atkdl16_core.lib"
    "${UP}/third_party/libusb/VS2022/MS64/dll/libusb-1.0.lib"
    Advapi32
)

# USB-free aggregate/JSON seam: never opens a device.
add_executable(dl16-diagnostics-test diagnostics_test.cpp)
target_include_directories(dl16-diagnostics-test PRIVATE "${UP}/core/include")
target_link_libraries(dl16-diagnostics-test PRIVATE "${UP}/build/Release/atkdl16_core.lib")

# Bounded PWM output sender (DL16-TASK-004); drives approved loopback wiring only.
add_executable(dl16-pwm pwm_tool.cpp)
target_include_directories(dl16-pwm PRIVATE
    "${UP}/core/include"
    "${UP}/third_party/libusb/include"
)
target_link_libraries(dl16-pwm PRIVATE
    "${UP}/build/Release/atkdl16_core.lib"
    "${UP}/third_party/libusb/VS2022/MS64/dll/libusb-1.0.lib"
    Advapi32
)

# Bounded SimpleTrigger gating probe (DL16-TASK-010); operator-approved experiment.
add_executable(dl16-trigger trigger_tool.cpp)
target_include_directories(dl16-trigger PRIVATE
    "${UP}/core/include"
    "${UP}/third_party/libusb/include"
)
target_link_libraries(dl16-trigger PRIVATE
    "${UP}/build/Release/atkdl16_core.lib"
    "${UP}/third_party/libusb/VS2022/MS64/dll/libusb-1.0.lib"
    Advapi32
)
