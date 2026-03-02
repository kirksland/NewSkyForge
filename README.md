
<img src="config/icons/newForge4-white.svg" alt="SkyForge Icon" width="500">
# SkyForge

**Development Architecture for Advanced Houdini Tools**

SkyForge is a structured development framework built on top of **SideFX Houdini**, designed to support the creation of complex, interactive, and technically robust tools.

It is not a replacement for Houdini’s native toolset.  
Houdini already provides a complete and powerful environment.

SkyForge exists to address a different problem:

> How do you design advanced, user-friendly, technically controlled tools inside Houdini without fighting architectural limitations?

---

## Why This Architecture Exists

When developing advanced modeling or topology-driven tools in Houdini, several structural challenges appear:

- Some viewport UX behaviors are not exposed through Python.
- Certain internal selection and traversal mechanisms are not accessible.
- SOP networks are extremely powerful, but complex interactive tools quickly become difficult to maintain.
- Mixing interaction logic, geometry processing, and state management leads to fragile systems.

SkyForge was created to impose structure where ad-hoc scripting becomes limiting.

The goal is not to replace Houdini.

The goal is to build **a clear, layered development architecture on top of it.**

---

## Architectural Philosophy

SkyForge enforces strict separation of concerns through distinct layers.

### 1 — Interaction Layer
Python Viewer States are responsible only for:

- Input handling
- Gesture logic
- Viewport feedback
- Tool state management

This layer does not perform heavy geometry logic.
It orchestrates behavior.

---

### 2 — Core Logic Layer
A dedicated Python / C++ module handles:

- Deterministic topology logic
- Reusable data structures
- Explicit traversal systems
- Algorithmic building blocks
- Operations independent from UI

This layer is interaction-agnostic.
It defines rules, not interface.

---

### 3 — Execution Layer (SOP / HDK)
Geometry mutation and processing are handled through:

- Modular SOP blocks
- Custom HDK nodes when required
- Controlled caching strategies
- Explicit data flow between operations

This layer executes.  
It does not decide.

---

## Design Intent

SkyForge aims to make advanced tool development:

- Modular
- Predictable
- Testable
- Maintainable
- Extensible

It provides:

- A reusable core module
- A consistent interaction architecture
- A structured way to build HDAs
- A disciplined development methodology

The modeling and retopology tools built on top of this architecture are applications of the framework — not its definition.

---

## Scope

SkyForge is:

- A development architecture
- A technical R&D framework
- A structured environment for building interactive tools
- A long-term experimentation platform

It is not:

- A replacement for native Houdini workflows
- A monolithic production pipeline
- A feature-driven tool pack

It is a foundation for controlled, high-level tool engineering inside Houdini.

---

## Current Phase

Architecture stabilization and refinement:

- Core module consolidation
- Viewer State framework consistency
- Modular SOP execution patterns
- Internal documentation and structural validation

High-level tools will continue to evolve on top of this base.