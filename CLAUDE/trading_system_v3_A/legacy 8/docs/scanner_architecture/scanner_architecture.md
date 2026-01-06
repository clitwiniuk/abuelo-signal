# Scanner Module Analysis & Architecture

This document provides a detailed analysis of the `scanner` module in `trading_system_v3`, specifically focusing on the `SmallcapDailyScanner` and its interaction with `IBKRNativeScanner`.

## 1. High-Level Architecture

The scanning system is designed as a two-layer architecture:

1.  **Orchestration Layer (`SmallcapDailyScanner`)**:
    *   Manages the business logic for finding trading opportunities.
    *   Handles news analysis (`CatalystAnalyzer`).
    *   Applies multi-strategy logic (finding Gaps, Volume Surges, Catalyst plays, etc. on the same ticker).
    *   Manages "Sticky Watchlists" and Temporal Re-analysis (cooldowns).
    *   **Goal**: Return high-quality `SmallcapPlay` objects to the trading engine.

2.  **Data Layer (`IBKRNativeScanner`)**:
    *   Direct interface with Interactive Brokers.
    *   Executes raw market scans (e.g., "Top % Gainers", "Most Active").
    *   Handles low-level data fetching (Price, Volume, Historical Bars).
    *   Manages subscriptions (`BatchPriceManager`) to ensure real-time data.
    *   **Goal**: Provide raw, enhanced market candidates.

## 2. Core Components

### A. SmallcapDailyScanner (`scanner/smallcap/smallcap_daily_scanner.py`)
The brain of the operation. It runs on a loop (externally controlled) and performs the following:
*   **Early Bird Qualifier**: Checks for opportunities during pre-market (8:00 - 9:30 AM).
*   **Multi-Track Analysis**: Analyzes a single ticker for *multiple* potential strategies simultaneously (e.g., a stock can be both a `GAP_BREAKOUT` and have `CATALYST_NEWS`).
*   **Parallelization**: Fetches news and 1-minute bars for all candidates in parallel to minimize latency.

### B. IBKRNativeScanner (`scanner/ibkr_native_scanner.py`)
The muscle. It replaces the old ProRealTime integration.
*   **Adaptive Caching**: Adjusts data refresh rates based on market activity.
*   **Rate & Error Handling**: Manages IBKR API limits (e.g., Pacing violations) by executing scans sequentially with delays, but fetching data in batches.

### C. OpportunityTracker (`scanner/opportunity_tracker.py`)
The memory.
*   Prevents spamming the same signal repeatedly.
*   Only allows re-sending a signal if substantial changes occur (e.g., Sentiment shift, 50% volume increase, Price breakout).

## 3. Detailed Workflow Diagram

The following Mermaid diagram illustrates the complete lifecycle of a scan iteration.

```mermaid
sequenceDiagram
    participant Orch as Orchestrator/Trader
    participant SDS as SmallcapDailyScanner
    participant EB as EarlyBirdQualifier
    participant INS as IBKRNativeScanner
    participant IB as IBKR API
    participant News as News/Catalyst System
    participant Filter as Multi-Track Analyzer

    Note over Orch, IB: Start of Scan Loop

    Orch->>SDS: scan_daily_plays()
    
    %% Phase 1: Early Bird (Pre-market)
    rect rgb(240, 248, 255)
    Note right of SDS: Phase 1: Pre-Market Check
    SDS->>EB: check_and_send_early_bird()
    alt Market Opening (9:30 AM)
        EB-->>SDS: Return Qualified Pre-market Plays
        SDS-->>Orch: Return Early Bird Plays (Immediate)
    end
    end

    %% Phase 2: IBKR Scanning
    rect rgb(255, 250, 240)
    Note right of SDS: Phase 2: Candidate Sourcing
    SDS->>INS: scan_daily_plays(max_results=50)
    INS->>IB: reqScannerSubscription (Seq)
    IB-->>INS: Raw Candidates
    INS->>IB: Fetch Price/Vol/Bars (Batched)
    INS-->>SDS: List[IBKRScanResult]
    end

    %% Phase 3: Watchlist & Cooldown
    SDS->>SDS: Update Sticky Watchlist & Incubator
    SDS->>SDS: Check Temporal Cooldowns
    Note right of SDS: Filter out recently processed tickers

    %% Phase 4: Multi-Track Analysis (Parallel)
    rect rgb(240, 255, 240)
    Note right of SDS: Phase 4: Parallel Analysis
    
    par Parallel Data Fetch
        SDS->>News: Fetch News (Batch)
        SDS->>IB: Fetch 1-min Bars (Batch)
    end

    loop For Each Candidate Ticker
        SDS->>Filter: Analyze Strategies
        
        Filter->>Filter: Check Catalyst (FinBERT)
        Filter->>Filter: Check Gap Breakout
        Filter->>Filter: Check Volume Surge
        Filter->>Filter: Check Short Squeeze
        Filter->>Filter: Check Intraday Mover
        
        opt If Promising but not Ready
            Filter->>SDS: Add to Incubator (Sticky Watchlist)
        end
    end
    end

    %% Phase 5: Result Generation
    SDS->>SDS: Create SmallcapPlay Objects
    SDS->>SDS: Sort by Quality Score
    SDS->>SDS: Update Session Stats

    SDS-->>Orch: List[SmallcapPlay]
```

## 4. Key Logic & Optimizations

### 1. Parallelization
The system heavily utilizes `asyncio.gather` in `_create_multi_track_opportunities` to fetch:
*   News headlines for all ~50 candidates at once.
*   One-minute historical bars for all candidates at once.
*   **Result**: Reduces analysis time from ~3 minutes to ~30 seconds.

### 2. Multi-Track Analysis
Instead of running separate scanners for "Gap Up" and "Volume Surge", the `IBKRNativeScanner` fetches a broad list of "Active & Moving" stocks. The `SmallcapDailyScanner` then checks each stock against **all** strategies.
*   *Example*: A stock found via "Most Active" scan can generate both a `VOLUME_SURGE` play and a `CATALYST_NEWS` play if it has breaking news.

### 3. "Sticky" Watchlist (Incubator)
If a stock looks interesting (e.g., Price > VWAP) but doesn't trigger a signal immediately, it is added to a local `sticky_watchlist`.
*   **Benefit**: Even if the stock drops out of IBKR's "Top 50" list on the next scan, the scanner *manually* fetches it (`fetch_specific_tickers`) to keep tracking it.

### 4. Implicit & Explicit Event Detection
*   **Explicit**: Uses FinBERT to find "FDA Approval" or "Merger" news.
*   **Implicit (Optional)**: Can detect "Events" purely based on price/volume anomalies if news is slow (`ImplicitEventDetector`).
