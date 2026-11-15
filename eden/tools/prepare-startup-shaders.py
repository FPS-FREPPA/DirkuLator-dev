"""Widen affinity only inside the pinned startup-cache compilation tasks."""
import re


def pipeline(text):
    begin = text.index('void PipelineCache::LoadDiskResources(')
    end = text.index('void PipelineCache::QueueVulkanPipelineCacheFlush()', begin)
    startup = text[begin:end]
    pattern = r'(workers\.QueueWork\(\[[^\n]+&state, &callback\]\(\) mutable \{)'
    startup, count = re.subn(pattern, r'\1\n            ::Eden::Performance::StartupShaderAffinity startup_affinity;', startup)
    if count != 2:
        raise RuntimeError(f'Expected exactly two startup shader tasks, found {count}')
    text = text[:begin] + startup + text[end:]
    anchor = '    return max_core_threads;\n#endif'
    if text.count(anchor) != 1:
        raise RuntimeError('Startup pipeline worker-count anchor changed')
    return text.replace(anchor, '    return ::Eden::Performance::StartupShaderWorkerCount(max_core_threads);\n#endif')
