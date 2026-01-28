# 💰 Cost Estimation Analysis

This document provides a breakdown regarding the estimated costs for running the "Clinic Voice Assistant" project. The stack involves several usage-based AI services.

> **Note**: Prices are subject to change by providers. Estimates below are based on pricing as of January 2026.

## 1. Cost Breakdown by Service

### 🎤 Speech-to-Text (STT) - Deepgram
*   **Model**: `Nova-2`
*   **Pricing**: ~$0.0059 per minute (streaming).
*   **Unit**: Audio minutes streamed from user to agent.

### 🧠 Intelligence (LLM) - OpenAI
*   **Model**: `GPT-4o` (Standard Realtime/Chat usage)
*   **Pricing**:
    *   Input: $2.50 / 1M tokens
    *   Output: $10.00 / 1M tokens
*   **Estimate**: A 5-minute voice conversation typically consumes ~2k-4k tokens depending on verbosity.
    *   ~3k tokens ≈ $0.01 - $0.02 per conversation.

### 🗣️ Text-to-Speech (TTS) - Cartesia
*   **Model**: `Sonic` (Low latency)
*   **Pricing**:
    *   Tiered Subscription model (e.g., Startup Plan $39/mo for ~1.25M characters).
    *   Pay-as-you-go / Overage: Approx $0.03 per minute of generated audio (or ~$0.001 per request depending on length).
*   **Unit**: Characters converted to audio. A 5-minute conversation might have ~2 minutes of agent speech (~300 words ≈ 1,500 characters).

### 📹 Avatar - Beyond Presence
*   **Service**: Real-time Avatar
*   **Pricing**: Credit-based.
    *   **Managed Agents**: ~100 credits/min ≈ **$0.35 per minute** (Starter Plan rates).
    *   **S2V (Speech to Video)**: ~50 credits/min ≈ **$0.175 per minute**.
*   **Context**: This is likely the most expensive component per minute.

### 📡 Infrastructure - LiveKit Cloud
*   **Service**: Real-time WebRTC Transport
*   **Pricing**:
    *   Audio/Video session: ~$0.004 - $0.01 per participant/minute.
    *   Agent connection: $0.01 per minute.
*   **Estimate**: For a 1-on-1 call (User + Agent) + Avatar stream:
    *   Users: 2 (User + Avatar/Agent)
    *   Cost: ~$0.02 - $0.04 per minute.

### 🗄️ Database - Supabase
*   **Plan**: Free Tier (suitable for dev/demo).
*   **Pro**: $25/month for production scale.

---

## 2. Scenario Estimations

### 📉 Scenario A: Single 5-Minute Consultation
*A typical user calls to check appointments and book a slot.*

| Service | Usage Estimate | Approx Cost |
| :--- | :--- | :--- |
| **Beyond Presence** | 5 mins (Avatar video) | $1.75 |
| **Deepgram STT** | 2.5 mins (User speech) | $0.015 |
| **OpenAI LLM** | ~4k tokens | $0.02 |
| **Cartesia TTS** | 2.5 mins (Agent speech) | $0.075 |
| **LiveKit** | 5 mins x 2 participants | $0.15 |
| **Total** | | **~$2.01 per call** |

*> **Observation**: The visual avatar drives ~87% of the cost.*

### 📈 Scenario B: Monthly Operation (Standard Clinic)
*Assumption: 20 consultations per day x 22 working days = 440 calls/month.*
*Avg duration: 5 minutes.*

*   **Total Minutes**: 2,200 minutes.
*   **Avatar Cost**: $349 (Scale Plan - 200k fixed credits/mo) + mild overage or roughly **$770** if purely pay-as-you-go at Starter rates. *Scale plan is much more efficient ($349 covers ~2000 mins managed).*
*   **LLM/STT/TTS**: ~$120.
*   **LiveKit**: ~$80.

**Estimated Monthly Total**: **~$550 - $600** (using optimized subscriptions).

## 💡 Cost Optimization Tips
1.  **Avatar on Demand**: Only initialize the avatar (`init_avatar`) when necessary. Use voice-only for standard queries.
2.  **Commitment Plans**: Use Beyond Presence and Cartesia monthly plans rather than pay-as-you-go to reduce unit costs by 40-50%.
3.  **Model Selection**: Use `GPT-4o-mini` for simpler queries to cut LLM costs by 90%.
