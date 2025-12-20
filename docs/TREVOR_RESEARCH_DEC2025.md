# Trevor Nederlof's Big Code MCP Research (December 2025)

**Status:** Completed research. Tasks and findings guide Phase 2 implementation of CodeContextBench comparison framework.

**Note:** This research was conducted before Sourcegraph Deep Search MCP was a released feature. Testing was done exclusively on sourcegraph.sourcegraph.com.

**Original Notes:** Detailed running notes available at [Google Doc](https://docs.google.com/document/d/1DsmVoUbo4fl94VkhmcIE5jLSzz7SWowcVNMMyRADcy0/edit?usp=sharing)

---

## Research Target Repositories

| Repository | Size | Primary Languages |
|---|---|---|
| Firefox | 4.2 GB | JavaScript (29%), C++ (28%), HTML (22%), C (10%), Python (3%), Kotlin (3%) |
| TensorRT-LLM | 1.6 GB | Python (45%), C++ (43%), CUDA (10%) |
| Servo | 1.6 GB | Rust |
| Kubernetes | 1.4 GB | Go |
| PyTorch | 1.1 GB | Python (60%), C++ (32%), CUDA (3%) |
| VS Code | 1 GB | TypeScript (95%) |

---

## Key Findings

### Deep Search MCP Limitations

Initial testing used Sourcegraph Deep Search MCP, but encountered **consistent timeout issues (>2 minutes)** on larger codebases. This made it impractical for agent-based iteration.

**Solution:** Switched to full Sourcegraph MCP endpoint: `https://sourcegraph.sourcegraph.com/.api/mcp/v1`

This eliminated timeouts and provided better performance for agent-driven searches.

### The "Big Code" Problem

Early attempts to use real GitHub issues showed limited MCP value:
- PyTorch, Istio, oauth2-proxy: Both CC alone and CC+MCP produced similar (often incorrect) solutions
- **Root cause:** These issues were not "big code" problems—they didn't require broad architectural context

**Key insight:** MCP value emerges when agents face problems requiring:
- Broad codebase understanding (not narrow, localized fixes)
- Multiple modules, patterns, or systems at scale
- Architectural decisions that ripple across the codebase

### The Sourcegraph Prompt

Firefox's methodology inspired the core prompt added to all big code tasks:

**For single-repo large codebases:**
> "This repository is large. If a search spans more than a narrow, well-defined set of directories, you MUST use the Sourcegraph MCP search tools. Local grep or rg is only acceptable when tightly scoped."

**For multi-repo systems:**
> "This repository is part of a multi-repository codebase indexed in Sourcegraph. Any questions about other repositories MUST be answered using the Sourcegraph MCP search tools."

Without this prompt, Claude Code defaults to confident guessing and local-only search, missing critical context.

---

## Big Code Tasks with Demonstrated MCP Value

### 1. VS Code: Stale Diagnostics After Git Branch Switch

**Prompt:**
> "I'm seeing stale TypeScript diagnostics in the Problems panel after switching Git branches. Files that no longer have errors still show the old errors until I manually open each file and make an edit. It seems like the diagnostics pipeline only refreshes on in-editor changes and misses file-on-disk changes from Git operations.
>
> Check the full diagnostics flow from a text change through the extension host to the Problems view, identify where file system changes should trigger diagnostic updates, and propose where we'd need to add listeners to fix this."

**Task ID:** `big-code-vsc-001`

**MCP Impact:**
- ✅ Deep Search found actual existing mechanisms: `deleteAllDiagnosticsInFile`, file watchers, `onWillChange` listener
- ✅ Proposed modifications to real code paths
- ❌ Claude Code alone: Suggested partial duplicates of existing functionality

**Why it's big code:** Requires understanding the full diagnostic pipeline (text changes → extension host → Problems view), integrating across multiple modules.

---

### 2. Kubernetes: NoScheduleNoTraffic Taint Effect

**Prompt:**
> "Implement a new Node taint effect called NoScheduleNoTraffic that prevents new pods from being scheduled AND removes the node from Service EndpointSlices, but does NOT evict existing pods. This is different from NoSchedule (which doesn't affect traffic) and NoExecute (which evicts pods). Find all the places in the codebase where taint effects are evaluated and add support for this new effect."

**Task ID:** `big-code-k8s-001`

**MCP Impact:**
- ✅ Found all necessary locations: tests, utilities, settings, enforcement points
- ✅ Comprehensive understanding of taint effect architecture
- ❌ Claude Code alone: Missed critical areas, incomplete implementation coverage

**Why it's big code:** Taint effects are evaluated in many modules (scheduler, admission controller, endpoint slices). Requires finding all evaluation points across a 1.4GB codebase.

---

### 3. Servo: scrollend DOM Event Implementation

**Prompt:**
> "Add support for the scrollend DOM event in Servo. It should fire on scrollable elements and the window when scrolling stops, including for compositor-driven async scrolling.
>
> The event should debounce properly—multiple rapid scroll inputs should result in a single scrollend after movement stops. Don't fire if the scroll position didn't actually change.
>
> Add WPT tests covering wheel, keyboard, and programmatic scrolling (scrollTo)."

**Task ID:** `big-code-servo-001`

**MCP Impact:**
- ✅ Located all scroll event handlers across browser architecture
- ✅ Understood debouncing patterns already in use
- ✅ Found proper test integration points
- ❌ Claude Code alone: Missed some handlers, less comprehensive event system understanding

**Why it's big code:** Scroll handling is scattered across multiple modules (browser, compositor, DOM event system, etc.). Requires architectural understanding of how scrolling works across Servo's systems.

---

### 4. TensorRT-LLM: W4A8_MXFP4_INT8 Quantization Mode

**Prompt:**
> "Add support for a new quantization mode W4A8_MXFP4_INT8 — 4-bit MXFP4 weights with INT8 activations, targeting Blackwell GPUs. The CUDA kernels already exist on the C++ side; we just need to expose and plumb this through the Python/C++ stack.
>
> Follow the patterns used by W4A8_MXFP4_FP8 — find everywhere that mode is defined, parsed, validated, and used for kernel selection, then add the equivalent support for the INT8 variant. Make sure the Python and C++ quantization enums stay in sync.
>
> Unsupported combinations (certain attention backends, incompatible KV cache settings) should fail at build time with clear errors. Add tests to cover the new mode."

**Task ID:** `big-code-trt-001`

**MCP Impact:**
- ✅ Comprehensively found all locations: Python enums, C++ enums, kernel selection logic, validation, build-time checks
- ✅ Identified all unsupported combinations and validation points
- ✅ Found proper test patterns
- ❌ Claude Code alone: Missed many locations, incomplete enum sync, validation gaps

**Why it's big code:** Quantization modes are defined and used across Python/C++ boundary, kernel selection logic, build system, and tests. Requires understanding a complex cross-language system architecture.

---

## Multi-Repo MCP Value

Testing showed MCP is **critical** for multi-repo codebases and microservice architectures where:

### Temporalio (sdk-go + server)

**Without MCP:** Claude Code guessed at cross-repo interactions, was inaccurate
**With MCP:** Correctly traced API definitions, Go bindings, and server implementation

### microservices-demo (orders → payment service)

**Without MCP:** "Pretty useless" unless repos cloned locally. Heavy hallucination about API contracts.
**With MCP:** Correctly identified payment service endpoints, request format, decline conditions, and mismatches

**Key observation:** Claude Code will hallucinate confidently about unknown code. MCP prevents this by providing actual evidence.

---

## Implementation Implications for CodeContextBench

### Task Suite Design

The four big code tasks (VS Code, Kubernetes, Servo, TensorRT-LLM) are production-ready for MCP value measurement:

1. **All show clear MCP value** in Trevor's testing
2. **All are real, maintainable problems** (not synthetic)
3. **All require broad architectural understanding** (not narrow debugging)
4. **Clear success criteria** (tests, code changes, validation)

### Environment Setup

Based on Trevor's experience:

- ✅ **Use full MCP endpoint:** `https://sourcegraph.sourcegraph.com/.api/mcp/v1`
- ❌ **Do NOT use Deep Search MCP:** Timeouts on >2GB codebases
- ✅ **Inject Sourcegraph prompt:** Add to CLAUDE.md guidance files
- ❌ **Do NOT clone full repositories:** Use minimal workspace structure, let agents use MCP to understand code

### Measurement Expected Results

Trevor's qualitative observations suggest:

- **Big code tasks:** MCP agent should be more accurate (fewer incorrect assumptions) and more comprehensive
- **Token/step tradeoffs:** MCP may use more tokens (search overhead) but should find more correct locations
- **Multi-repo tasks:** MCP agent should be vastly superior (without it, agents hallucinate)

The 4 tasks above are designed to validate these hypotheses quantitatively.

---

## References

- **Original running notes:** [Google Doc with detailed testing methodology](https://docs.google.com/document/d/1DsmVoUbo4fl94VkhmcIE5jLSzz7SWowcVNMMyRADcy0/edit?usp=sharing)
- **Sourcegraph MCP Documentation:** [Sourcegraph MCP API](https://sourcegraph.com/docs/api/mcp)
- **Deep Search:** Not recommended for codebases >2GB due to timeout issues

---

## Historical Context

This research was conducted in December 2025 before Sourcegraph Deep Search MCP was released to general availability. All testing was on sourcegraph.sourcegraph.com. These findings informed the design of the CodeContextBench big code MCP comparison framework.
