// SPDX-License-Identifier: GPL-3.0-or-later
#include "devices.h"
#include "preferences.h"
#include "run_summary.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <stdexcept>
#include <vector>
#include "common/logging.h"
#include "native_audio.hpp"
#include "audio_out_init.h"

namespace Eden {
using namespace AudioCore::Sink;
using namespace ps5::native_audio;

namespace {
// Microphone input is not captured on the PS5. Upstream's NullSinkStreamImpl returns an empty
// vector from ReleaseBuffer, and DeviceSession::ReleaseBuffer then copies buffer.size bytes from
// its data(), a null pointer, into guest memory: any game that opens AudioIn (for voice
// chat, for one) crashed on the AudioManager thread. Release silence of the requested length.
class SilentInputStream final : public SinkStream {
public:
    explicit SilentInputStream(Core::System& system) : SinkStream{system, StreamType::In} {}
    void AppendBuffer(SinkBuffer&, std::span<s16>) override {}
    std::vector<s16> ReleaseBuffer(u64 num_samples) override {
        return std::vector<s16>(num_samples, 0);
    }
};
} // namespace

AudioStream::AudioStream(Core::System& system, u32 channels, const std::string& name_, StreamType type)
    : SinkStream{system, type} {
    if (type == StreamType::In || (channels != 1 && channels != 2 && channels != 6))
        throw std::invalid_argument("Unsupported AudioOut stream format");
    name = name_;
    system_channels = channels;
    device_channels = 2;
    SetRingSize(4);
    if (!AudioOutReady()) throw std::runtime_error("sceAudioOutInit failed");
    handle = sceAudioOutOpen(0xff, 0, 0, kAudioOutGrain, kAudioOutRate, kAudioOutStereoS16);
    if (handle < 0) throw std::runtime_error("sceAudioOutOpen failed");
    std::array<int, 8> volumes;
    volumes.fill(AudioVolume(PreferencesFor(session_title.load())));
    if (sceAudioOutSetVolume(handle, 3, volumes.data()) < 0) {
        sceAudioOutClose(handle);
        handle = -1;
        throw std::runtime_error("sceAudioOutSetVolume failed");
    }
    try {
        worker = std::jthread([this](std::stop_token stop) {
            std::array<s16, kAudioOutGrain * 2> block{};
            std::unique_lock lock(mutex);
            // 0.67rc EDEN_AUDIO_OUT: how late this thread feeds the port. A 256-frame block lasts 5.33 ms,
            // so a gap between two sceAudioOutOutput returns of more than ~8 ms is an audible dropout the
            // render queue (EDEN_AUDIO_SINK) cannot see. Every 5 s: blocks, the longest gap, how many gaps
            // were over 8, 16 and 50 ms, and the longest render and output call.
            using Clock = std::chrono::steady_clock;
            auto last_return = Clock::now();
            auto window_start = last_return;
            u64 probe_blocks = 0, late8 = 0, late16 = 0, late50 = 0;
            double max_gap_ms = 0.0, max_render_ms = 0.0, max_output_ms = 0.0;
            int mix_peak = 0;          // 0.75rc: the loudest sample sent to the port in the window
            u64 silent_blocks = 0;     // blocks that were all zero
            auto ms = [](Clock::duration d) { return std::chrono::duration<double, std::milli>(d).count(); };
            while (!stop.stop_requested()) {
                const auto wait_begin = Clock::now();
                if (!wake.wait(lock, stop, [this] { return !IsPaused(); })) break;
                const auto render_begin = Clock::now();
                if (render_begin - wait_begin > std::chrono::milliseconds(30)) last_return = render_begin; // a pause, not a dropout
                ProcessAudioOutAndRender(block, kAudioOutGrain);
                const auto render_end = Clock::now();
                {
                    int block_peak = 0;
                    for (const s16 sample : block) block_peak = std::max(block_peak, sample < 0 ? -static_cast<int>(sample) : static_cast<int>(sample));
                    mix_peak = std::max(mix_peak, block_peak);
                    if (block_peak == 0) ++silent_blocks;
                }
                // AudioOut paces complete 256-frame, 48 kHz stereo blocks.
                in_flight = true;
                lock.unlock();
                const int result = sceAudioOutOutput(handle, block.data());
                const auto output_end = Clock::now();
                lock.lock();
                {
                    const double gap = ms(output_end - last_return);
                    last_return = output_end;
                    ++probe_blocks;
                    if (gap > 8.0) ++late8;
                    if (gap > 16.0) ++late16;
                    if (gap > 50.0) ++late50;
                    max_gap_ms = std::max(max_gap_ms, gap);
                    max_render_ms = std::max(max_render_ms, ms(render_end - render_begin));
                    max_output_ms = std::max(max_output_ms, ms(output_end - render_end));
                    if (output_end - window_start >= std::chrono::seconds(5)) {
                        std::fprintf(stderr,
                                     "EDEN_AUDIO_OUT name=%s blocks=%llu max_gap_ms=%.1f late8=%llu late16=%llu late50=%llu "
                                     "max_render_ms=%.1f max_output_ms=%.1f mix_peak=%d silent_blocks=%llu\n",
                                     name.c_str(), static_cast<unsigned long long>(probe_blocks), max_gap_ms,
                                     static_cast<unsigned long long>(late8), static_cast<unsigned long long>(late16),
                                     static_cast<unsigned long long>(late50), max_render_ms, max_output_ms, mix_peak,
                                     static_cast<unsigned long long>(silent_blocks));
                        RunSummary::Get().AddAudioOut(probe_blocks, late8, late16, late50, max_gap_ms);
                        window_start = output_end;
                        probe_blocks = late8 = late16 = late50 = 0;
                        max_gap_ms = max_render_ms = max_output_ms = 0.0;
                        mix_peak = 0;
                        silent_blocks = 0;
                    }
                }
                in_flight = false;
                wake.notify_all();
                if (result < 0) {
                    failed = true;
                    SignalPause();
                    LOG_ERROR(Audio_Sink, "PS5 AudioOut output failed");
                    break;
                }
                output_frames += kAudioOutGrain;
                for (std::size_t frame = 0; frame < kAudioOutGrain; ++frame)
                    nonzero_frames += block[frame * 2] != 0 || block[frame * 2 + 1] != 0;
            }
        });
    } catch (...) {
        sceAudioOutClose(handle);
        handle = -1;
        throw;
    }
}
AudioStream::~AudioStream() { Finalize(); }
void AudioStream::Start(bool) {
    std::scoped_lock lock(mutex);
    if (handle >= 0 && !failed) { paused = false; wake.notify_one(); }
}
void AudioStream::Stop() {
    SignalPause();
    std::unique_lock lock(mutex);
    wake.wait(lock, [this] { return !in_flight; });
}
void AudioStream::Finalize() {
    worker.request_stop();
    wake.notify_all();
    if (worker.joinable()) worker.join();
    std::scoped_lock lock(mutex);
    SignalPause();
    if (handle >= 0) {
        const int drain = sceAudioOutOutput(handle, nullptr);
        const int close = sceAudioOutClose(handle);
        LOG_INFO(Audio_Sink, "EDEN_AUDIO_PORT_CLOSED frames={} nonzero={} failed={} drain={} close={}",
                 output_frames, nonzero_frames, failed.load(), drain, close);
        handle = -1;
    }
}
void AudioStream::AppendBuffer(SinkBuffer& buffer, std::span<s16> samples) {
    std::scoped_lock lock(mutex); // Publish PCM and its descriptor before the consumer runs.
    if (buffer.frames == 0 || buffer.frames > 0x8000 || buffer.frames_played != 0 ||
        samples.size() != buffer.frames * system_channels)
        throw std::invalid_argument("Invalid PCM buffer dimensions");
    if (failed || handle < 0) throw std::runtime_error("AudioOut stream is unavailable");
    SinkStream::AppendBuffer(buffer, samples);
}
SinkStream* AudioSink::AcquireSinkStream(Core::System& system, u32 channels,
                                        const std::string& name, StreamType type) {
    system_channels = channels;
    // Microphone capture is outside this output adapter.
    SinkStreamPtr stream = type == StreamType::In ?
        SinkStreamPtr{std::make_unique<SilentInputStream>(system)} :
        SinkStreamPtr{std::make_unique<AudioStream>(system, channels, name, type)};
    stream->SetDeviceVolume(device_volume);
    stream->SetSystemVolume(system_volume);
    auto* result = stream.get();
    streams.push_back(std::move(stream));
    return result;
}
void AudioSink::CloseStream(SinkStream* stream) {
    std::erase_if(streams, [stream](const auto& item) { return item.get() == stream; });
}
void AudioSink::SetDeviceVolume(f32 value) {
    device_volume = std::clamp(value, 0.0f, 1.0f);
    for (auto& stream : streams) stream->SetDeviceVolume(device_volume);
}
void AudioSink::SetSystemVolume(f32 value) {
    system_volume = std::clamp(value, 0.0f, 1.0f);
    for (auto& stream : streams) stream->SetSystemVolume(system_volume);
}
}
