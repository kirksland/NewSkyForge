## Feature Pipeline Diagrams (2026-03-13)

### 1) High-Level Architecture (Hub-First Dispatch)
```mermaid
flowchart TD
    State["Viewer State / Orchestrator"]
    Ctx["ToolContext / Runtime Data + Services"]
    Hub["FeatureHub / Dispatcher"]
    F1[HoverGadgetFeature]
    F2[AstarTurnFeature]
    F3[TransversalLoopFeature]
    Preview["PreviewService / Draw Channels"]

    State -->|creates| Ctx
    State -->|instantiates| Hub
    Hub -->|owns| F1
    Hub -->|owns| F2
    Hub -->|owns| F3
    F1 -->|writes| Ctx
    F2 -->|reads/writes| Ctx
    F3 -->|reads/writes| Ctx
    Ctx -->|service| Preview
    F2 -->|draws via| Preview
    F3 -->|draws via| Preview
```

### 2) Event Flow (Mouse Event + Payload)
```mermaid
sequenceDiagram
    participant State
    participant Hub
    participant Hover as HoverFeature
    participant Astar as AstarFeature
    participant LoopF as LoopFeature
    participant Ctx as ToolContext

    State->>Ctx: ensure_geo / ensure_mesh
    State->>Hover: on_mouse_event
    Hover->>Ctx: set_service("hover", payload)
    State->>Astar: on_mouse_event
    Astar->>Ctx: read_service("hover")
    Astar-->>State: payload?
    State->>LoopF: on_mouse_event
    LoopF->>Ctx: read_service("hover")
    LoopF-->>State: payload?
    State->>Ctx: set_service("selection_payload", payload)
```

### 3) Services as "Boxes" (Context Services)
```mermaid
flowchart LR
    subgraph Ctx[ToolContext.services]
        HoverBox["hover"]
        HitBox["hit"]
        PreviewBox["preview"]
        PayloadBox["selection_payload"]
    end

    HoverFeature -- writes --> HoverBox
    HitFeature -. optional .-> HitBox
    PreviewFeature -- writes --> PreviewBox
    AstarFeature -- reads --> HoverBox
    LoopFeature -- reads --> HoverBox
    State -- writes --> PayloadBox
```

### 4) PreviewService Channels as "Lenses"
```mermaid
flowchart TD
    Preview[PreviewService]
    subgraph Channels["Named Channels (Drawables)"]
        C1["astar_preview (line)"]
        C2["astar_committed (line)"]
        C3["loop_preview (line)"]
        C4["loop_committed (line)"]
        C5["hover_edge (line)"]
        C6["hover_point (point)"]
        C7["hover_face (face)"]
    end

    Preview --> C1
    Preview --> C2
    Preview --> C3
    Preview --> C4
    Preview --> C5
    Preview --> C6
    Preview --> C7
```

### 5) provides / requires Dependency Ordering
```mermaid
flowchart LR
    Hover[HoverGadgetFeature\nprovides: hover]
    Astar[AstarTurnFeature\nrequires: hover]
    Loop[TransversalLoopFeature\nrequires: hover]
    Move[HoverMoveFeature\nrequires: hover, edit_geo, tool_mode]
    Draw[HoverDrawFeature\nrequires: hover, edit_geo, preview, tool_mode]
    Preview[PreviewFeature\nprovides: preview]

    Hover --> Astar
    Hover --> Loop
    Hover --> Move
    Hover --> Draw
    Preview --> Draw
```
