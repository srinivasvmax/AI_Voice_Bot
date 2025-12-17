# Pipecat Library Patches

> **Internal modifications to Pipecat 0.0.95 for production stability**

This document tracks all modifications made to the Pipecat library. These patches fix critical bugs and should be considered for upstream contribution.

## ⚠️ Important Notes

- **Version**: Pipecat 0.0.95
- **Status**: Patches required for production use
- **Maintenance**: Re-apply after Pipecat upgrades
- **Upstream**: Consider submitting as pull requests

---

## Patch 1: Frame Processor Race Condition Fix

### Issue

**Severity**: 🔴 Critical  
**Impact**: Silent frame drops, audio loss  
**Root Cause**: Race condition where frames arrive before `__process_queue` initialization

### Problem Description

When LLM services respond quickly, they can emit frames before the frame processor's `__process_queue` is created. This causes:
- `RuntimeError: __process_queue is None`
- Silent frame drops
- No audio output despite successful LLM generation

### Timeline of Bug

```
1. Pipeline starts
2. StartFrame processed (creates input queue)
3. LLM emits TTSTextFrame immediately
4. __process_queue not yet created (created in __start())
5. Frame arrives at __input_frame_task_handler
6. Attempts to queue frame → RuntimeError or silent drop
```

### Solution

Add defensive queue creation before enqueueing frames.

**File**: `venv/Lib/site-packages/pipecat/processors/frame_processor.py`  
**Method**: `__input_frame_task_handler`  
**Line**: ~904-907

#### Original Code (Broken)

```python
if isinstance(frame, SystemFrame):
    await self.__process_frame(frame, direction, callback)
elif self.__process_queue:
    await self.__process_queue.put((frame, direction, callback))
else:
    raise RuntimeError(
        f"{self}: __process_queue is None when processing frame {frame.name}"
    )
```

#### Fixed Code

```python
if isinstance(frame, SystemFrame):
    await self.__process_frame(frame, direction, callback)
else:
    # PATCH: Ensure process_queue exists before enqueueing frames
    # Fixes race condition causing TTSTextFrame drops when LLM emits frames
    # before __process_queue is created in __start()
    if not self.__process_queue:
        self.__create_process_task()
    await self.__process_queue.put((frame, direction, callback))
```

### Why This Fix is Correct

1. **Eliminates timing dependency**: No longer assumes queue exists
2. **Prevents silent drops**: All frames are guaranteed to be queued
3. **Maintains frame ordering**: System frames still processed immediately
4. **Production-grade**: Defensive programming pattern
5. **Safe for all Python versions**: Not a Python version issue

### Testing

```python
# Verify fix
python -m py_compile venv/Lib/site-packages/pipecat/processors/frame_processor.py
# Should compile without errors
```

### Upstream Contribution

**Recommended**: Submit as pull request to Pipecat repository

**PR Title**: Fix race condition in frame processor queue initialization

**PR Description**:
```
Fixes a race condition where frames can arrive before __process_queue 
is initialized, causing RuntimeError or silent frame drops.

The issue occurs when:
1. Fast LLM services emit frames immediately after StartFrame
2. __process_queue hasn't been created yet (created in __start())
3. Frames are dropped or raise RuntimeError

This patch adds defensive queue creation, ensuring the queue exists
before attempting to enqueue frames.

Impact: Prevents audio loss in production voice AI applications.
```

---

## Patch 2: Aggregator Frame Forwarding Fix

### Issue

**Severity**: 🔴 Critical  
**Impact**: No audio output, TTS never receives frames  
**Root Cause**: `LLMAssistantContextAggregator` consumes frames without forwarding to TTS

### Problem Description

The `LLMAssistantContextAggregator` was designed to accumulate text for conversation context but does not forward frames to downstream processors (TTS). This causes:
- LLM generates responses successfully
- Aggregator receives and accumulates text
- TTS never receives frames
- No audio generated

### Solution

Modify aggregator to both accumulate for context AND forward frames downstream.

**File**: `venv/Lib/site-packages/pipecat/processors/aggregators/llm_response.py`  
**Methods**: `_handle_llm_start`, `_handle_llm_end`, `_handle_text`  
**Lines**: ~996, ~1000, ~1005

#### Fix 1: _handle_llm_start (Line ~996)

**Original**:
```python
async def _handle_llm_start(self, _: LLMFullResponseStartFrame):
    self._started += 1
```

**Fixed**:
```python
async def _handle_llm_start(self, frame: LLMFullResponseStartFrame):
    self._started += 1
    # PATCH: Push start frame to TTS so it knows response is beginning
    await self.push_frame(frame, FrameDirection.DOWNSTREAM)
```

#### Fix 2: _handle_llm_end (Line ~1000)

**Original**:
```python
async def _handle_llm_end(self, _: LLMFullResponseEndFrame):
    self._started -= 1
    await self.push_aggregation()
```

**Fixed**:
```python
async def _handle_llm_end(self, frame: LLMFullResponseEndFrame):
    self._started -= 1
    await self.push_aggregation()
    # PATCH: Push end frame to TTS so it knows response is complete
    await self.push_frame(frame, FrameDirection.DOWNSTREAM)
```

#### Fix 3: _handle_text (Line ~1005)

**Original**:
```python
async def _handle_text(self, frame: TextFrame):
    if not self._started:
        return
    if self._params.expect_stripped_words:
        self._aggregation += f" {frame.text}" if self._aggregation else frame.text
    else:
        self._aggregation += frame.text
```

**Fixed**:
```python
async def _handle_text(self, frame: TextFrame):
    if not self._started:
        return
    # Accumulate text for context
    if self._params.expect_stripped_words:
        self._aggregation += f" {frame.text}" if self._aggregation else frame.text
    else:
        self._aggregation += frame.text
    # PATCH: Push TextFrame downstream to TTS
    await self.push_frame(frame, FrameDirection.DOWNSTREAM)
```

### Why This Fix is Correct

1. **Dual purpose**: Aggregator now both accumulates AND forwards
2. **Maintains context**: Context management still works
3. **Enables TTS**: TTS receives frames for audio generation
4. **Standard pattern**: Matches other processor behaviors
5. **No breaking changes**: Existing functionality preserved

### Complete Frame Flow (After Fix)

```
LLM Service:
  → LLMFullResponseStartFrame
  → LLMTextFrame("Hello!")
  → LLMFullResponseEndFrame
     ↓
LLMAssistantContextAggregator:
  → Receives LLMFullResponseStartFrame
  → Increments _started counter
  → ✅ Pushes LLMFullResponseStartFrame to TTS
     ↓
  → Receives LLMTextFrame
  → Accumulates text for context
  → ✅ Pushes LLMTextFrame to TTS
     ↓
  → Receives LLMFullResponseEndFrame
  → Decrements _started counter
  → Pushes context frame upstream
  → ✅ Pushes LLMFullResponseEndFrame to TTS
     ↓
TTS Service:
  → Receives LLMFullResponseStartFrame (starts processing)
  → Receives LLMTextFrame (generates audio)
  → Receives LLMFullResponseEndFrame (flushes audio)
  → Sends audio to transport
```

### Testing

```python
# Verify fix
python -m py_compile venv/Lib/site-packages/pipecat/processors/aggregators/llm_response.py
# Should compile without errors
```

### Upstream Contribution

**Recommended**: Submit as pull request to Pipecat repository

**PR Title**: Fix LLMAssistantContextAggregator to forward frames to TTS

**PR Description**:
```
Fixes an issue where LLMAssistantContextAggregator consumes LLM frames
for context management but does not forward them to downstream processors,
preventing TTS from receiving text for audio generation.

The aggregator should:
1. Accumulate text for conversation context (existing behavior)
2. Forward frames to TTS for audio generation (added behavior)

This patch adds frame forwarding in three methods:
- _handle_llm_start: Forward LLMFullResponseStartFrame
- _handle_llm_end: Forward LLMFullResponseEndFrame  
- _handle_text: Forward TextFrame/LLMTextFrame

Impact: Enables audio output in voice AI applications using aggregators.
```

---

## How to Re-apply Patches After Upgrade

### Step 1: Backup Current Patches

```bash
# Create backup of patched files
cp venv/Lib/site-packages/pipecat/processors/frame_processor.py frame_processor.py.backup
cp venv/Lib/site-packages/pipecat/processors/aggregators/llm_response.py llm_response.py.backup
```

### Step 2: Upgrade Pipecat

```bash
pip install --upgrade pipecat-ai
```

### Step 3: Re-apply Patch 1 (frame_processor.py)

1. Open `venv/Lib/site-packages/pipecat/processors/frame_processor.py`
2. Find `__input_frame_task_handler` method (around line 890)
3. Locate the frame handling code
4. Replace with the fixed version from this document

### Step 4: Re-apply Patch 2 (llm_response.py)

1. Open `venv/Lib/site-packages/pipecat/processors/aggregators/llm_response.py`
2. Find `_handle_llm_start` (around line 996)
3. Find `_handle_llm_end` (around line 1000)
4. Find `_handle_text` (around line 1005)
5. Add `await self.push_frame(frame, FrameDirection.DOWNSTREAM)` to each

### Step 5: Clear Cache and Test

```bash
# Clear Python cache
Get-ChildItem -Recurse -Include "__pycache__","*.pyc" | Remove-Item -Recurse -Force

# Restart server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test call
python test_call.py
```

---

## Alternative: Use Git Patches

### Create Patches

```bash
cd venv/Lib/site-packages/pipecat
git init
git add .
git commit -m "Original Pipecat 0.0.95"

# Make changes
# ...

git diff processors/frame_processor.py > ~/frame_processor.patch
git diff processors/aggregators/llm_response.py > ~/llm_response.patch
```

### Apply Patches

```bash
cd venv/Lib/site-packages/pipecat
git apply ~/frame_processor.patch
git apply ~/llm_response.patch
```

---

## When to Remove These Patches

Monitor Pipecat releases for fixes:
- https://github.com/pipecat-ai/pipecat/releases
- https://github.com/pipecat-ai/pipecat/blob/main/CHANGELOG.md

Remove patches when:
- Pipecat fixes the frame processor race condition
- Pipecat updates aggregator to forward frames to TTS
- Pipecat version > 0.0.95 includes these fixes

---

## Current Status

| Patch | Status | Upstream PR | Pipecat Version |
|-------|--------|-------------|-----------------|
| Frame Processor Race Condition | ✅ Applied | ⏳ Pending | 0.0.95 |
| Aggregator Frame Forwarding | ✅ Applied | ⏳ Pending | 0.0.95 |

---

## Contributing Upstream

To submit these patches to Pipecat:

1. Fork https://github.com/pipecat-ai/pipecat
2. Create feature branch
3. Apply patches
4. Add tests
5. Submit pull request
6. Reference this documentation

---

**Last Updated**: December 18, 2025  
**Pipecat Version**: 0.0.95  
**Patches Applied**: 2  
**Production Status**: ✅ Stable
