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

# Internal opt-in Stream evidence probe; --self-test never constructs Device.
add_executable(dl16-stream-evidence stream_evidence.cpp)
target_include_directories(dl16-stream-evidence PRIVATE "${UP}/core/include" "${UP}/cli")
target_link_libraries(dl16-stream-evidence PRIVATE
    "${UP}/build/Release/atkdl16_core.lib"
    "${UP}/third_party/libusb/VS2022/MS64/dll/libusb-1.0.lib" Advapi32)
add_custom_command(TARGET dl16-stream-evidence POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${UP}/third_party/libusb/VS2022/MS64/dll/libusb-1.0.dll" "$<TARGET_FILE_DIR:dl16-stream-evidence>")

add_executable(dl16-incremental-writer-test incremental_writer_test.cpp)
target_include_directories(dl16-incremental-writer-test PRIVATE "${UP}/core/include" "${UP}/cli" "${CMAKE_CURRENT_SOURCE_DIR}/../../scripts")
target_link_libraries(dl16-incremental-writer-test PRIVATE "${UP}/build/Release/atkdl16_core.lib")

add_executable(dl16-async-buffer-test async_buffer_test.cpp)
target_include_directories(dl16-async-buffer-test PRIVATE "${UP}/core/include" "${UP}/cli" "${CMAKE_CURRENT_SOURCE_DIR}/../../scripts")
target_link_libraries(dl16-async-buffer-test PRIVATE "${UP}/build/Release/atkdl16_core.lib")

# USB-free aggregate/JSON seam: never opens a device.
add_executable(dl16-diagnostics-test diagnostics_test.cpp)
target_include_directories(dl16-diagnostics-test PRIVATE "${UP}/core/include")
target_link_libraries(dl16-diagnostics-test PRIVATE "${UP}/build/Release/atkdl16_core.lib")

add_executable(dl16-experimental-lifecycle-test experimental_lifecycle_test.cpp)
target_include_directories(dl16-experimental-lifecycle-test PRIVATE "${UP}/core/include")

# USB-free session protocol and PWM helper/codec test (DL16-TASK-032).
add_executable(dl16-session-pwm-test session_pwm_test.cpp)
target_include_directories(dl16-session-pwm-test PRIVATE
    "${UP}/core/include"
    "${UP}/cli"
)
target_link_libraries(dl16-session-pwm-test PRIVATE "${UP}/build/Release/atkdl16_core.lib")

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

# USB-free actual native file writer contracts (DL16-TASK-047).
add_executable(dl16-raw-rx-logging-test raw_rx_logging_test.cpp)
target_include_directories(dl16-raw-rx-logging-test PRIVATE "${UP}/core/include")
target_link_libraries(dl16-raw-rx-logging-test PRIVATE "${UP}/build/Release/atkdl16_core.lib")

# USB-free bounded raw RX offline replay tool (DL16-TASK-046).
add_executable(dl16-raw-rx-replay raw_rx_replay.cpp)
target_include_directories(dl16-raw-rx-replay PRIVATE "${UP}/core/include")
target_link_libraries(dl16-raw-rx-replay PRIVATE "${UP}/build/Release/atkdl16_core.lib")

add_executable(dl16-experimental-stream-test experimental_stream_test.cpp)
target_include_directories(dl16-experimental-stream-test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../../scripts" "${UP}/core/include" "${UP}/cli")
target_link_libraries(dl16-experimental-stream-test PRIVATE "${UP}/build/Release/atkdl16_core.lib")
