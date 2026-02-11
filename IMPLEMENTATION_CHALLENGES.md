# Terminal GPT: Implementation Challenges & Solutions

This document captures the five biggest technical challenges we faced while implementing tool calling functionality in Terminal GPT, and how we overcame them.

---

## Challenge 1: Tool Call Fragmentation in Streaming Responses

**The Problem**
When using Claude 3.5 Sonnet via OpenRouter with streaming enabled, tool calls don't arrive in a single complete chunk. Instead, they come fragmented across multiple SSE (Server-Sent Events) chunks:

```json
// Chunk 1: Just the function name
{"delta": {"tool_calls": [{"index": 0, "function": {"name": "list_directory"}}]}}

// Chunk 2: Partial arguments
{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{ \"path\": \"."}}]}}

// Chunk 3: Remaining arguments
{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"}"}}]}}
```

Our initial implementation treated each chunk independently, so we never reconstructed the complete tool call. The logs showed `has_tool_calls: false` even when Claude was trying to use tools.

**The Solution**
We implemented a `tool_call_buffers` dictionary that persists across streaming chunks:

```python
# Buffer for accumulating fragmented tool calls across chunks
tool_call_buffers: Dict[int, Dict[str, Any]] = {}

# Accumulate function name and arguments incrementally
if "tool_calls" in delta and delta["tool_calls"]:
    for tc in delta["tool_calls"]:
        idx = tc.get("index", 0)
        if idx not in tool_call_buffers:
            tool_call_buffers[idx] = {
                "id": tc.get("id", f"call_{idx}_{int(time.time() * 1000)}"),
                "type": "function",
                "function": {"name": "", "arguments": ""}
            }
        
        # Accumulate name and arguments
        fn = tc.get("function", {})
        if "name" in fn:
            tool_call_buffers[idx]["function"]["name"] = fn["name"]
        if "arguments" in fn:
            tool_call_buffers[idx]["function"]["arguments"] += fn["arguments"]
```

We only yield the complete accumulated tool calls when `finish_reason == "tool_calls"`.

**Key Insight**: Streaming tool calls require stateful accumulation - you can't process each chunk independently.

---

## Challenge 2: Missing Assistant Message with Tool Calls

**The Problem**
After implementing tool accumulation, tools were being called but Claude would ignore the results. The conversation would look like this:

```
User: "List my files"
→ Assistant: [calls list_directory]
→ Tool: [returns file list]
→ Assistant: "I'll check that for you" [tries to call list_directory AGAIN]
```

Claude was in a loop because it never "saw" that it had already called the tool. The OpenAI/Claude protocol requires a specific sequence:

1. Assistant emits `tool_calls`
2. **Assistant message with `tool_calls` is added to conversation**
3. Tool results are added with `tool_call_id` linking back to step 2
4. LLM continues

We were skipping step 2, so the tool results appeared orphaned in the conversation history.

**The Solution**
We now explicitly add an assistant message containing the `tool_calls` before adding tool results:

```python
# CRITICAL: First add assistant message with tool_calls to conversation
# This establishes the linkage for the tool results
assistant_tool_message = Message(
    role="assistant",
    content=full_response if full_response else None,
    tool_calls=tool_calls_found
)
conversation = conversation.add_message(assistant_tool_message)

# THEN execute tools and add results with tool_call_id linkage
for tool_result in tool_results:
    tool_message = Message(
        role="tool",
        content=tool_result["result"],
        name=tool_result["tool_name"],
        tool_call_id=tool_call_id  # Links back to assistant's tool_calls
    )
    conversation = conversation.add_message(tool_message)
```

**Key Insight**: The assistant must "own" its tool calls in the conversation history via the `tool_calls` field, and tool results must reference those calls via `tool_call_id`.

---

## Challenge 3: The Infinite Tool Loop

**The Problem**
Once tools started working, we hit a second classic agent bug: runaway tool loops. The behavior was:

```
User: "List my files"
→ Assistant: calls list_directory
→ Tool: returns results
→ Assistant: calls read_file on README.md
→ Tool: returns README contents
→ Assistant: calls read_file on another file
→ ...infinite loop...
```

Claude is extremely compliant and task-completion oriented. Once it sees tools helped, it assumes "the safest correct behavior is to keep calling tools until the task is fully complete." Unlike GPT-4, Claude does not self-terminate.

**The Solution**
We implemented a hard one-tool-cycle limit:

```python
async def _generate_assistant_response_stream(self, conversation: ConversationState):
    max_iterations = 3  # Reduced from 5
    current_iteration = 0
    has_completed_tool_cycle = False  # NEW: Track if we've done one cycle

    while current_iteration < max_iterations:
        current_iteration += 1

        # Enforce one tool cycle limit
        if has_completed_tool_cycle:
            logger.info("Tool cycle already completed, forcing final answer")
            tools = None  # Disable tools!
        else:
            tools = self._get_available_tools()
        
        # ... generate response ...
        
        if tool_calls_found:
            # ... execute tools ...
            has_completed_tool_cycle = True  # Mark cycle complete
            continue  # One more iteration for final answer (without tools)
```

After tools execute, we set `has_completed_tool_cycle = True`, which forces `tools = None` on the next iteration. Claude can then provide a final natural language answer but cannot call more tools.

**Key Insight**: Claude needs explicit permission to stop. Without the guardrail, it will tool-call indefinitely.

---

## Challenge 4: Exit/Farewell Intent Detection

**The Problem**
Even with the one-cycle limit, we had inappropriate tool calls:

```
User: "thanks, that's all I need, bye!"
→ Assistant: calls list_directory (WHY??)
```

The system prompt said "call tools when helpful," so Claude interpreted "bye" as "help the user by listing files before they go." The LLM was being invoked for messages that clearly signaled conversation termination.

**The Solution**
We added a terminal intent gate that short-circuits BEFORE any LLM call:

```python
# Terminal intents that should short-circuit tool calling
TERMINAL_INTENTS = {
    "quit", "exit", "bye", "goodbye", "thanks", "thank you",
    "no", "stop", "end", "close", "later", "see ya", "cya"
}

def is_terminal_intent(message: str) -> bool:
    normalized = message.lower().strip().rstrip("!.")
    if normalized in TERMINAL_INTENTS:
        return True
    # Handle phrases like "thanks a bunch", "thanks anyway"
    for intent in TERMINAL_INTENTS:
        if normalized.startswith(intent):
            return True
    return False

# In process_user_message_stream():
if is_terminal_intent(user_content):
    # Skip LLM entirely - return farewell immediately
    farewell = random.choice([
        "👋 Catch you later!",
        "No worries, talk soon!",
        "All good, see ya!",
        "Later! Hit me up if you need anything."
    ])
    yield {"content": farewell, ...}
    return  # Don't call LLM at all!
```

**Key Insight**: Don't waste LLM tokens on obvious exit intents. Detect them early and respond immediately.

---

## Challenge 5: Balancing Tool Eagerness vs Conversation Naturalness

**The Problem**
Our first attempt to fix over-tooling made the system prompt TOO aggressive:

```
"If a tool can help answer the request, YOU MUST call it"
```

This resulted in:
- "Hi" → calls calculator (thinks user might need math)
- "Goodbye" → calls list_directory ("helpful" before user leaves)
- "What can you do?" → calls every tool (show capabilities)

Then we went too far the other way - Claude wouldn't call tools even when obviously needed.

**The Solution**
We found the balance with a decision framework in the system prompt:

```markdown
## Tool Calling Instructions

**Decision Framework:**
1. Does the user NEED live/current data? → Call a tool
2. Can ONLY a tool provide this answer? → Call a tool  
3. Is this a casual chat/greeting/farewell? → Respond naturally, NO tool

**You MUST:**
- Call tools when they are REQUIRED to answer the request
- STOP after one tool cycle - respond naturally and wait for user

**You must NOT:**
- Call tools for greetings, goodbyes, thanks, or casual chat
- Repeat tool calls unless the user explicitly asks for more
- Keep calling tools after the request is satisfied
```

This gives Claude:
- Clear criteria for WHEN to use tools
- Explicit permission to stop (Claude needs this!)
- Clear prohibitions for casual conversation

**Key Insight**: Claude needs both positive rules ("do this") AND negative rules ("don't do this"), plus explicit permission to stop.

---

## Summary: What We Learned

| Challenge | Root Cause | Solution |
|-----------|-----------|----------|
| Fragmented tool calls | Treating streaming chunks independently | Stateful accumulation with buffers |
| Missing tool context | No assistant message with `tool_calls` | Explicit assistant message injection |
| Infinite loops | No limit on tool cycles per turn | `has_completed_tool_cycle` flag + tools=None |
| Exit intent mishandling | LLM invoked for farewells | Pre-LLM terminal intent detection |
| Tool over/under-use | Imbalanced system prompt | Decision framework + explicit stop permission |

## The Result

Before fixes:
```
User: "thanks bye" → calls list_directory (WRONG)
User: "list files" → calls list_directory → calls read_file → calls read_file... (INFINITE)
```

After fixes:
```
User: "thanks bye" → "👋 Catch you later!" (CORRECT - no tools)
User: "list files" → calls list_directory → natural response (CORRECT - single cycle)
User: "hello" → "Hey! What's up?" (CORRECT - natural chat)
```

---

*Document created: February 2026*
*Phase: Tool Calling Implementation*
*Status: ✅ All challenges resolved*
