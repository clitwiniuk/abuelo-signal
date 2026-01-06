# Livermore Event-Driven Strategy (MidCap Proposal)

**Date Archived:** 2025-12-25
**Status:** Proposal / Future Idea

## Concept
An event-driven strategy inspired by Jesse Livermore's principles, focusing on "Concept -> Observation -> Pause -> Continuation" rather than immediate reaction. This approach aims to reduce noise and enter trades "late but correct".

## Core Principles
1.  **The Event Disparates Attention**: News/Catalysts are for classification, not validation.
2.  **Continuity Validates**: The trade is only valid if the move resumes after a natural pause.
3.  **Strict Selection**: MidCap universe only ($2B-$50B), high liquidity.

## The Livermore Pipeline (8 Steps)

### 🧱 STEP 0 — Universe Definition
*   **Market Cap**: $2B - $50B (avoid pseudo-smallcaps).
*   **Liquidity**: Minimum daily liquidity criteria.
*   **Safety**: No chronic dump history.

### 🔍 STEP 1 — Reaction Detection (Observation Only)
*   **Trigger**: Expansion of range, anomalous volume, speed.
*   **Action**: Mark as "UNDER OBSERVATION". DO NOT ENTER.
*   **Philosophy**: "First, I look."

### 🧠 STEP 2 — Event Classification
*   **Types**: Earnings, Guidance, M&A, Regulatory, Macro, Unknown.
*   **Role**: Contextualizes the move. "No news" is a valid (and often strong) catalyst.

### ⏳ STEP 3 — The Pause (Continuity Test)
*   **Condition**: The move must pause naturally.
*   **Validation**:
    *   Volume drops during pause.
    *   Price holds > 50-70% of the impulse.
    *   Minimum consolidation time (not just 1-2 candles).
*   **Fail**: If price breaks structure or volume remains high during drop -> DISCARD.

### 🔁 STEP 4 — Cross-Confirmation
*   **Peers**: Are other stocks in the sector moving?
*   **Indices**: Is the sector ETF confirming?

### 🎯 STEP 5 — The Entry ("Late but Correct")
*   **Trigger**: Breakout of the pause high or continuation after flag.
*   **Timing**: Non-reactive. Wait for the confirmation.

### 💰 STEP 6 — Management
*   **Stop**: Technical, clear, non-negotiable (e.g., low of the pause).
*   **Adding**: Only on confirmation (averaging up, never down).

## Implementation Architecture (Proposed)

### 1. Scanner (`MidCapDailyScanner`)
*   **Role**: Acts as the "Observation Engine".
*   **Changes**:
    *   Return candidates with status `OBSERVATION` if they meet Step 1 criteria but not yet Step 5.
    *   Filter based on strict Universe rules (Step 0).

### 2. State Machine Worker (`LivermoreMidCapWorker`)
*   **Role**: Tracks candidates through the phases: `Observation` -> `Pause` -> `Ready`.
*   **States**:
    *   `OBSERVATION`: Initial detection.
    *   `PAUSE`: Tracking volume decay and price hold.
    *   `ENTRY_READY`: Pause validated, waiting for trigger.
    *   `ACTIVE`: Position open.
*   **Persistence**: Needs to track state across scanner intervals (e.g., using a local JSON or DB).

### 3. Logic Differences vs Current `DailyPlays`
| Feature | Current `DailyPlays` | Livermore Proposal |
| :--- | :--- | :--- |
| **Trigger** | Immediate reaction to Gap/Volume | Breakout after a Pause |
| **News** | Can be a validator | Is just context |
| **Entry** | ASAP (capture the move) | Late (capture the trend) |
| **Stop** | Volatility based / tight | Technical / Structural |

## Metrics to Measure
*   % of events that reach "Continuation" phase.
*   Average time from Event to Entry.
*   Risk/Reward of "Late" entries vs "Early" entries.
