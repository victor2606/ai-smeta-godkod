# n8n Construction Estimator Workflow - Optimization Guide

## Overview

This document explains the optimized n8n workflow architecture for the Construction Estimator AI Agent, based on 2025 best practices for n8n + LangChain + MCP integration.

## Architecture Decision: Single MCP Client vs Multiple

### ✅ Chosen Approach: Single MCP Client Node

**Rationale:**
1. **Cohesive Domain**: All 5 tools (`natural_search`, `quick_calculate`, `show_rate_details`, `compare_variants`, `find_similar_rates`) operate on the same database and share construction cost estimation domain knowledge
2. **Shared Context**: Tools work together in workflows (search → calculate → compare)
3. **Simplified Management**: Single connection point reduces complexity
4. **Performance**: Lower overhead than multiple MCP connections
5. **n8n Best Practice 2025**: "Start with all tools in a single workflow for quick setup and shared context"

### ❌ When NOT to Use Single Client

Split into multiple MCP Client nodes only when:
- Tools require different authentication credentials
- Individual tools consume excessive RAM (>500MB per tool)
- Tools need different rate limiting policies
- Tools connect to different MCP servers entirely
- Tool-specific error handling is required

Since all our tools are part of the same FastMCP server instance, splitting would add unnecessary complexity.

---

## Workflow Components

### 1. Chat Trigger
```json
{
  "type": "@n8n/n8n-nodes-langchain.chatTrigger",
  "webhookId": "construction-estimator-chat"
}
```

**Configuration**:
- Unique webhook ID for dedicated chat endpoint
- No additional options needed
- Handles incoming user messages

---

### 2. AI Agent Node

**Model Selection**: Claude 3.5 Sonnet (via OpenRouter)

**Why Claude 3.5 Sonnet?**
- **Best-in-class tool use**: Superior function calling accuracy (95%+ vs 85% for GPT-4)
- **Russian language excellence**: Native support for Cyrillic morphology
- **Long context**: 200K token window handles complex construction specs
- **Cost-effective**: Via OpenRouter ($3/M tokens vs $15/M for GPT-4)
- **Reasoning quality**: Better at multi-step calculations

**Alternative Models**:
- Budget: `mistralai/mistral-medium-3.1` (good Russian, cheaper)
- Premium: `anthropic/claude-opus-4` (highest quality, 2x cost)
- Speed: `google/gemini-2.0-flash-exp:free` (fast, free tier)

**Configuration**:
```json
{
  "model": "anthropic/claude-3.5-sonnet:beta",
  "options": {
    "maxTokens": 4096,
    "temperature": 0.3
  }
}
```

**Temperature**: 0.3 (low) for consistent, factual responses
- 0.0-0.3: Factual, deterministic (recommended for cost calculations)
- 0.4-0.7: Balanced creativity
- 0.8-1.0: Creative, unpredictable (NOT recommended)

---

### 3. Memory Component

**Type**: Window Buffer Memory

**Configuration**:
```json
{
  "sessionIdType": "customKey",
  "sessionKey": "={{ $json.sessionId }}",
  "contextWindowLength": 10
}
```

**Why Window Memory?**
- **Conversation continuity**: Remembers last 10 messages
- **Context-aware**: Understands follow-up questions like "а для 200 м²?"
- **Session isolation**: Different users don't share context
- **Memory-efficient**: Doesn't store entire conversation history

**Alternative**: `memoryBufferSummary` if conversations exceed 20 messages regularly

---

### 4. MCP Client Tool Node

**Configuration**:
```json
{
  "endpointUrl": "http://host.docker.internal:8002/sse",
  "serverTransport": "sse",
  "options": {
    "allowedTools": [
      "natural_search",
      "quick_calculate",
      "show_rate_details",
      "compare_variants",
      "find_similar_rates"
    ]
  }
}
```

**Key Settings**:
- **Transport**: SSE (Server-Sent Events) for HTTP-based streaming
- **Host**: `host.docker.internal` for Docker-to-host communication
- **Port**: 8002 (matches MCP server SSE endpoint)
- **Allowed Tools**: Explicit whitelist of 5 tools (security best practice)

**Security Notes**:
- Never expose MCP endpoint publicly without authentication
- Use `allowedTools` to limit attack surface
- Consider adding rate limiting for production

---

## System Prompt Optimization

### Structure

The system prompt follows the **RISEN Framework** adapted for construction cost estimation:

1. **Role**: "You are a professional construction cost estimator..."
2. **Instructions**: Detailed tool usage guidelines
3. **Steps**: Response strategies for each query type
4. **Examples**: Not included in system prompt (keep it concise)
5. **Notes**: Critical rules and error handling

### Prompt Optimization Techniques Applied

#### 1. Tool-First Instruction (Critical for n8n)
```
"ALWAYS use tools - never make up numbers or rate codes"
```
**Why**: n8n agents sometimes skip tool calls without explicit instruction, causing hallucinations

#### 2. Structured Decision Tree
```
Type 1: "Сколько стоит X?" → natural_search → quick_calculate
Type 2: "Цена за единицу?" → natural_search → extract cost_per_unit
...
```
**Why**: Reduces LLM decision paralysis, increases tool call accuracy

#### 3. Parameter Examples
```
natural_search("перегородки гипсокартон", unit_type="м2", limit=5)
```
**Why**: Shows exact parameter format, reduces malformed tool calls

#### 4. Formatting Rules
```
- Use thousands separator: "59 411 руб." not "59411"
- Round to 2 decimals
- Russian units: м², м³
```
**Why**: Consistent user experience, prevents formatting errors

#### 5. Error Handling Templates
```
- Rate not found → suggest similar terms
- Multiple matches → show top 3, ask clarification
```
**Why**: Graceful degradation, maintains user trust

### Prompt Length: 2,847 tokens

**Optimization Balance**:
- ✅ Detailed enough for accurate tool use
- ✅ Concise enough to leave room for user context
- ✅ Structured for quick LLM parsing
- ❌ NOT overwhelming (under 3,000 tokens is ideal)

---

## Tool Usage Patterns

### Pattern 1: Simple Search → Calculate
```
User: "Сколько стоит 100 м² перегородок?"
Agent:
  1. natural_search("перегородки")
  2. quick_calculate(best_match, 100)
  3. Format response
```

### Pattern 2: Code → Details
```
User: "Покажи детализацию 10-05-001-01"
Agent:
  1. show_rate_details("10-05-001-01", quantity=100)
  2. Format breakdown
```

### Pattern 3: Search → Compare → Recommend
```
User: "Что выгоднее для кровли 200 м²?"
Agent:
  1. natural_search("кровля", limit=5)
  2. compare_variants([code1, code2, code3], 200)
  3. find_similar_rates(cheapest_code)
  4. Recommend best option
```

### Pattern 4: Complex Multi-Step
```
User: "Рассчитай стоимость для проекта: 150 м² перегородок, 200 м² кровли"
Agent:
  1. natural_search("перегородки")
  2. quick_calculate(match1, 150)
  3. natural_search("кровля")
  4. quick_calculate(match2, 200)
  5. Sum totals
  6. Format itemized response
```

---

## Performance Optimization

### 1. Tool Call Minimization

**Problem**: Each tool call adds 2-5 seconds latency

**Solution**: Agent instructed to combine operations when possible

**Example**:
- ❌ Bad: `natural_search` → `quick_calculate` → `show_rate_details` (3 calls)
- ✅ Good: `quick_calculate` with auto-search (1 call)

### 2. Result Limits

**Configuration**:
- `natural_search`: Default limit=10 (user can override up to 100)
- `find_similar_rates`: Default limit=5 (max 20)

**Rationale**:
- Most users need top 3-5 results
- Large result sets slow LLM processing
- Can always expand if needed

### 3. Temperature Tuning

**Setting**: 0.3 (low)

**Impact**:
- Faster inference (less sampling)
- More consistent tool parameters
- Reduced hallucination risk

### 4. Max Tokens

**Setting**: 4096

**Rationale**:
- Most responses: 500-1500 tokens
- Buffer for complex multi-rate comparisons
- Prevents runaway generation costs

---

## Monitoring & Debugging

### Key Metrics to Track

1. **Tool Call Success Rate**: Should be >95%
   - Monitor for malformed parameters
   - Track "Rate not found" errors

2. **Average Response Time**: Target <10s end-to-end
   - Chat trigger → Agent → Tools → Response
   - Breakdown: Tool latency vs LLM inference

3. **Token Usage**: Monitor costs
   - Input: ~3000 tokens (system + history + user)
   - Output: ~1000 tokens average
   - Cost: ~$0.02 per interaction (Claude 3.5 Sonnet)

4. **Error Types**:
   - Invalid rate codes
   - Quantity validation errors
   - Database connection failures

### n8n Debugging Tips

**Enable Execution Logging**:
```
Settings → Workflows → Execution Data → Save execution data: Always
```

**View Tool Calls**:
1. Open workflow execution
2. Click AI Agent node
3. Check "Tool Calls" tab
4. Verify parameters passed to MCP

**Common Issues**:

| Issue | Cause | Solution |
|-------|-------|----------|
| "Tool not found" | MCP server down | Check `docker ps`, verify port 8002 |
| Empty results | FTS5 query too restrictive | Broaden search, remove filters |
| Timeout errors | Database lock | Check for long-running queries |
| Hallucinated numbers | Agent skipped tools | Add "ALWAYS use tools" to prompt |

---

## Deployment Checklist

### Local Development
- [ ] MCP server running on `localhost:8002`
- [ ] Database at `data/processed/estimates.db` (verify with `ls -lh`)
- [ ] n8n using `host.docker.internal` (if in Docker)
- [ ] OpenRouter API key configured
- [ ] Test query: "Сколько стоит 100 м² перегородок?"

### Production Deployment

#### Infrastructure
- [ ] MCP server in Docker container
- [ ] Health check endpoint `/health` responding
- [ ] Database backed up (automated daily backups)
- [ ] SSL/TLS for MCP endpoint (if exposed externally)

#### n8n Configuration
- [ ] Update `endpointUrl` to production MCP host
- [ ] Set up API authentication (if MCP exposed)
- [ ] Configure rate limiting
- [ ] Enable execution data retention (7 days minimum)

#### Monitoring
- [ ] Set up alerts for tool call failures
- [ ] Track daily token usage (cost management)
- [ ] Monitor average response time
- [ ] Log error patterns

#### Security
- [ ] MCP endpoint NOT publicly accessible (use VPN/firewall)
- [ ] API keys in n8n credentials (never in code)
- [ ] Database file permissions (read-only for MCP process)
- [ ] Rate limiting on chat trigger webhook

---

## Cost Analysis

### Per-Interaction Breakdown

**Assumptions**:
- Model: Claude 3.5 Sonnet via OpenRouter ($3/M input, $15/M output)
- Average interaction: 1 user message + 2 tool calls + 1 response

| Component | Tokens | Cost |
|-----------|--------|------|
| System prompt | 2,847 | $0.0085 |
| User message | 150 | $0.0005 |
| Memory context (10 msgs) | 2,000 | $0.0060 |
| Tool results (2 calls) | 500 | $0.0015 |
| **Total Input** | **5,497** | **$0.0165** |
| Agent response | 1,000 | $0.0150 |
| **Total** | **6,497** | **$0.0315** |

**Monthly Estimate** (1,000 interactions):
- Token cost: $31.50
- OpenRouter fee (10%): $3.15
- **Total**: ~$35/month

**Cost Optimization Tips**:
1. Switch to `mistralai/mistral-medium-3.1` → 60% cheaper (~$14/month)
2. Reduce system prompt by 30% → save $2.50/month
3. Implement caching for frequent queries → save 40-50%

---

## Alternative Architectures

### Multi-Agent Pattern (For Complex Projects)

If users need multi-step project estimation:

```
[User Input] → [Orchestrator Agent]
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
   [Search Agent] [Calc Agent] [Compare Agent]
        ↓             ↓             ↓
        └─────────────┼─────────────┘
                      ↓
            [Aggregator Agent] → [Response]
```

**When to use**:
- Multi-room projects with different materials
- Need for budget optimization across categories
- Complex error handling and retry logic

**Drawback**: 3-4x more complex, higher latency

---

## Versioning & Updates

### Workflow Version: 1.0 (Optimized)

**Changelog**:
- v1.0 (2025-10-21): Initial optimized version
  - Single MCP client architecture
  - Claude 3.5 Sonnet model
  - Comprehensive system prompt (2,847 tokens)
  - Window memory (10 messages)
  - 5 tools exposed

**Future Enhancements**:
- [ ] Add caching layer for frequent queries
- [ ] Implement streaming responses (real-time feedback)
- [ ] Add voice input/output support
- [ ] Create dashboard for usage analytics
- [ ] Multi-language support (English, Kazakh)

---

## Testing Scenarios

### Basic Functionality Tests

1. **Simple Search + Calculate**
   ```
   Input: "Сколько стоит 100 м² перегородок из ГКЛ?"
   Expected: Uses natural_search → quick_calculate
   Validation: Returns cost ~39,600 руб. (±10%)
   ```

2. **Direct Rate Code**
   ```
   Input: "Рассчитай 10-05-004-01 для 150 м²"
   Expected: Uses quick_calculate only
   Validation: Returns cost ~59,400 руб.
   ```

3. **Comparison**
   ```
   Input: "Сравни 10-05-004-01 и 10-05-004-02 для 200 м²"
   Expected: Uses compare_variants
   Validation: Shows table with difference_from_cheapest
   ```

4. **Alternative Search**
   ```
   Input: "Найди альтернативы для 10-05-004-01"
   Expected: Uses find_similar_rates
   Validation: Returns 5 similar rates sorted by cost
   ```

5. **Detailed Breakdown**
   ```
   Input: "Покажи детализацию 10-05-004-01 на 100 м²"
   Expected: Uses show_rate_details
   Validation: Returns breakdown with materials/labor/machinery
   ```

### Edge Cases

6. **Ambiguous Query**
   ```
   Input: "Сколько стоит перегородки?"
   Expected: Returns multiple options, asks for clarification
   ```

7. **Invalid Quantity**
   ```
   Input: "Рассчитай 10-05-004-01 для -50 м²"
   Expected: Returns error "Quantity must be > 0"
   ```

8. **Rate Not Found**
   ```
   Input: "Рассчитай 99-99-999-99"
   Expected: Returns error "Rate not found", suggests search
   ```

9. **Typo Tolerance**
   ```
   Input: "Гермитизация окан"
   Expected: FTS5 corrects to "герметизация окон", returns results
   ```

10. **Follow-up Context**
    ```
    User: "Сколько стоит 100 м² перегородок?"
    Agent: [Returns cost]
    User: "А для 200 м²?"
    Expected: Uses memory to apply 200 to same rate
    ```

---

## Conclusion

This optimized workflow provides:
- ✅ **Accuracy**: Tool-first approach prevents hallucinations
- ✅ **Performance**: Single MCP client, optimized prompts
- ✅ **Scalability**: Handles 1000+ interactions/month efficiently
- ✅ **Maintainability**: Clear architecture, comprehensive docs
- ✅ **Cost-effectiveness**: ~$0.03 per interaction

**Next Steps**:
1. Import `n8n-construction-estimator-optimized.json` into n8n
2. Configure OpenRouter credentials
3. Update MCP endpoint URL if needed
4. Test with provided scenarios
5. Monitor metrics and iterate

For questions or issues, refer to:
- System prompt: `N8N_AGENT_SYSTEM_PROMPT.md`
- Example queries: `docs/example_queries.md`
- MCP server docs: `docs/MCP_SERVER.md`
