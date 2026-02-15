# ReviewFirst - Language Specification (v0.1)

A compiled, review-first programming language designed for AI-authored code that humans can verify quickly.

This revision focuses on **readability as a hard constraint**. Anything that improves typing speed but harms auditability loses.

---

## 1. Design Goals

1. **Reviewability over writability**
2. **Small, structured files**
3. **Explicit effects**
4. **Errors are values**
5. **Deterministic compilation**
6. **Zero-AI runtime**
7. **AI learnability through a tiny set of canonical patterns**
8. **Readable diffs as a language feature**
9. **Narrative code: one screen, one thought**

---

## 2. Compilation Model and Runtime

### 2.1 Targets
- Native executable (default)
- Bytecode VM (optional future backend)

### 2.2 Zero-AI Runtime Requirement
- Execution never requires AI agents, prompts, model calls, or any runtime “agent interpreter.”

### 2.3 Forbidden Runtime Features (Core)
- no `eval` or runtime AST execution
- no reflective code injection
- no implicit dynamic code loading

Dynamic loading may exist only behind an explicit capability and `!{DynLoad}` effect (see §7.6).

### 2.4 Build Manifest
Builds emit a manifest with:
- compiler version, build mode
- dependency versions and hashes
- source hashes
- artifact hashes

---

## 3. Source Files, Units, and Layout

### 3.1 File = Unit = Skill Container
- One file defines exactly **one primary exported skill**.
- Helpers and tests may exist in the same file under enforced sections.

### 3.2 Mandatory Top-Level Sections
A file must contain top-level sections in this exact order:
1. `public:`
2. `private:`
3. optional `tests:`

Any top-level declaration outside these sections is a compile-time error.

### 3.3 Visibility Rules
- `pub` declarations are allowed only inside `public:`
- `private:` and `tests:` cannot contain `pub`

Violations are compile-time errors.

### 3.4 Ordering Rules Within Sections
Each section must order declarations:
1. `type`
2. `const`
3. `skill` / `fn` / test declarations

Within each category, declarations must be in **dependency order**:
- a declaration may reference only imported names or names declared later in the same section
- this enforces “reading flows downward”

### 3.5 File Size and Complexity Limits (Enforced)
Defaults (project may override only within bounded ranges):
- max file length: **300 lines** (override range 200–600)
- max public section length: **120 lines**
- max exports per file: **8**
- max top-level declarations per section: **25**
- max function length: **40 lines**
- max cyclomatic complexity per function: **10**
- max indentation depth per function: **2** (compile error at depth 3)
- max control-structure count per function: **3** (`if`, `match`, loops combined)

---

## 4. Formatting and Diff Readability

### 4.1 Canonical Formatting (Normative)
- `skillfmt` is normative: one canonical formatting for a given AST.
- Non-canonical formatting may be rejected by tooling/CI.

### 4.2 Stable Ordering to Reduce Diff Noise
The formatter and compiler enforce:
- imports grouped by layer and sorted
- record literals printed vertically when multi-field
- trailing commas in multiline structures to minimize diff churn

---

## 5. Readability-First Semantics

This section is new in v0.2 and is enforced at compile time.

### 5.1 No Clever Syntax (Small Surface Area)
The following are disallowed:
- ternary operator
- implicit truthiness (conditions must be `Bool`)
- implicit numeric widening/coercion
- implicit string coercion
- operator overloading (stdlib-only may exist, user code cannot define new operators)
- macro systems (non-goal)

Rationale: cleverness hides intent. Intent must be visible.

### 5.2 Explicit Mutation
- All variables are immutable by default.
- Mutation requires `mut`.
- In-place updates require explicit syntax (no hidden mutation via method calls).

### 5.3 Explicit World-Changing Operations
Side-effecting calls must be visually marked:
- inside `steps:` blocks, side effects use `do`:
  - `do db.insert(...)`
  - `do console.println(...)`

This provides scan-friendly “here’s where the world changes.”

### 5.4 Happy Path First
Within a function/skill:
- validation uses guard clauses (`check`) early
- the success path reads top-to-bottom
- no deep nesting for error handling

### 5.5 Structured Comments Only
To prevent AI comment spam:
- Freeform multi-paragraph comments are disallowed.
- Only these are allowed:
  - structured doc headers (see §8.2)
  - tagged inline notes: `NOTE:`, `WHY:`, `SECURITY:`, `TODO:`

Projects may allow more tags, but untagged commentary is rejected.

### 5.6 Chained Call Limit
To avoid unreadable pipelines:
- max chained access/calls per line: **2** dots (`a.b().c()` allowed, `a.b().c().d()` rejected)
- exception: builder patterns in tests (see §11.5)

---

## 6. Types

### 6.1 Primitives
`Int`, `Float`, `Bool`, `String`, `Bytes`, `Unit`

### 6.2 Compounds
- records: `{ field: Type, ... }`
- `List[T]`, `Map[K, V]`

### 6.3 ADTs
Sum types are supported and pattern matching is exhaustive by default.

---

## 7. Errors and Results

### 7.1 No Unchecked Exceptions
All failures are explicit via `Result[T, E]`.

### 7.2 Propagation
`?` propagates errors outward when type-compatible.

### 7.3 Error Mapping
Errors must be mapped explicitly via `.mapErr(...)` when changing error types.

---

## 8. Effects and Capabilities

### 8.1 Effects Declared in Signatures
Every function and skill declares an effect set: `!{...}`.

Examples:
- `!{}` (pure)
- `!{IO}`
- `!{Network, Time}`

### 8.2 Standard Effects
Canonical effects:
- `IO`, `FileRead`, `FileWrite`, `Network`, `Time`, `Random`, `Process`, `Python`, `DynLoad`

### 8.3 Capabilities
Effects are exercised via explicit capability parameters.

```skillscript
type Http = capability
  fn get(url: Url, timeoutMs: Int) -> Result[Bytes, HttpError] !{Network, Time}
````

### 8.4 Effect Checking

A function may only call operations whose effects are contained in its declared set.

### 8.5 Effect Minimization (Optional Project Policy)

Projects may enable:

* max effect set size per `pub skill` (default recommended: 3)
* banned effect combos (for example `Network` + `FileWrite`) unless explicitly justified

### 8.6 Restricted Dynamic Loading

Allowed only when:

* signature includes `!{DynLoad}`
* capability `DynLoader` is provided
* modules are allowlisted in the manifest

---

## 9. Skills

### 9.1 Skills Are the Export Unit

Only `pub skill` may be exported. Exporting arbitrary functions is disallowed.

### 9.2 Required Doc Header for `pub skill`

Every `pub skill` must include:

* `intent:` one sentence
* `inputs:` assumptions/constraints
* `errors:` enumerated
* `effects:` summary (must match signature)
* `requires:` (at least one, or `requires: none`)
* `ensures:` (at least one, or `ensures: none`)
* optional `security:`
* optional `complexity:`

The compiler validates presence and basic consistency.

### 9.3 Thin Public Skills

* `pub skill` must be short (max function length applies).
* Complexity must be pushed into private helpers.

### 9.4 Naming Rules (Enforced at Public Boundary)

* exported skills: `PascalCase` and verb-first (CreateUser, FetchJson)
* exported types: `PascalCase` noun-first (UserId, HttpError)
* exported constants: `SCREAMING_SNAKE_CASE`
* exported names may not contain junk tokens: `util`, `helper`, `misc`, `tmp`, `stuff`

  * violations are compile errors for exports

---

## 10. Control Flow and Narrative Constructs

### 10.1 `check` Guard Clauses

`check <Bool> else Err(...)` is the standard validation form.

Rules:

* conditions must be `Bool`
* `check` is allowed in normal bodies and in `steps:`

### 10.2 `steps:` Block (Narrative Flow)

A constrained linear block intended to keep AI-generated code readable.

Allowed statements inside `steps:`:

* `let`
* `check`
* direct calls
* `do <side-effect call>`
* `return`

Disallowed inside `steps:`:

* nested `if`, `match`, loops
* anonymous functions/lambdas

Branching must be extracted to named private helpers.

### 10.3 Pattern Matching

`match` must be exhaustive unless a project explicitly allows `_` cases.
If `_` is used, an inline `WHY:` tag is required.

---

## 11. Tests Specification (Readability-Focused)

### 11.1 Tests Section

Tests live only in `tests:`.

### 11.2 Mandatory AAA Structure

Every test must contain blocks in order:

1. `arrange:`
2. `act:`
3. `assert:`

### 11.3 No Assertions Outside `assert:`

* `expect` is allowed only inside `assert:`.
* `arrange:` and `act:` may not contain assertions.

### 11.4 Named Case Lists (Preferred for Many Cases)

Tables are not a core feature. Use named case lists.

### 11.5 Builder Exception for Chaining

Builder chaining is allowed in tests only, inside `arrange:`:

* max chain length in builders may be higher (project-configurable)
* builder types must be named `*Builder`

### 11.6 Snapshot Testing

* `expectSnapshot(name, value)`
* updating requires `--accept-snapshots`
* snapshot diffs must be review-friendly and size-bounded

### 11.7 Test Readability Limits (Enforced)

Defaults:

* max assertions per test: **25**
* max test length: **60 lines**
* max indentation depth: **2**
* max nesting structures: **2**

If exceeded, compiler suggests:

* convert to named cases
* use snapshot
* extract fixture builder

---

## 12. Modules and Imports

### 12.1 Imports Explicit

No implicit imports.

### 12.2 Import Hygiene

Projects choose one policy (compiler-enforced):

* acyclic module graph, or
* layered imports, or
* feature-folder boundary

Default recommendation: acyclic + feature-folder boundary.

---

## 13. Python Interoperability (Optional Feature)

### 13.1 Principle

SkillScript compiles normally. Python is reachable only through explicit interop boundaries.

### 13.2 Python Effect and Capability

Any Python call requires:

* `!{Python}` in signature
* a `Py` capability parameter
* recommended: allowlisted modules in manifest

### 13.3 Packaging

Build system pins Python/module versions and records them in the manifest.

---

## 14. Toolchain (Normative Commands)

* `skillc build <entry> -o <artifact>` emits executable + manifest
* `skillfmt` canonical formatter
* `skilllint` extra checks (some may be fatal by policy)
* `skillsplit` deterministic refactoring to enforce size limits

---

## 15. Compliance Summary (Compiler MUST Enforce)

The compiler must reject:

* code outside `public/private/tests`
* `pub` outside `public:`
* private declarations inside `public:`
* section order violations
* type/const/function ordering violations
* dependency-order violations
* disallowed clever syntax (ternary, truthiness, implicit coercions, etc.)
* indentation depth > 2
* excessive nesting or control-structure count
* effect misuse
* unhandled errors (no unchecked exceptions)
* file/function/test readability limit violations
* tests missing AAA blocks or placing assertions outside `assert:`
* forbidden runtime features (eval, reflective execution)

---

## 16. Minimal File Template (Normative Shape)

```skillscript
public:
  type ...
  const ...

  /// intent: ...
  /// inputs: ...
  /// errors: ...
  /// effects: ...
  /// requires: ...
  /// ensures: ...
  pub skill Primary(...) -> Result[..., ...] !{...} =
    steps:
      ...

private:
  type ...
  const ...
  fn helper(...) -> ... !{...} =
    ...

tests:
  test "...":
    arrange:
      ...
    act:
      ...
    assert:
      ...
```

---


```

## 17. POC Implementation in This Repository

This repository now contains a **first executable POC** for the spec above.

### Included files
- `tools/skillc.py`: a tiny `skillc` prototype compiler.
- `skillc`: shell wrapper to run the compiler.
- `examples/hello.skill`: minimal example app using the required section layout.

### Supported POC features
- `skillc build <entry> -o <artifact>` command shape from §14.
- validates top-level section order (`public:` then `private:` then optional `tests:`).
- validates required `pub skill` doc header fields from §9.2.
- supports `steps:` with `do console.println("...")` statements and `return`.
- generates a native executable by transpiling to C and compiling with `gcc`/`cc`.
- emits an artifact manifest JSON next to the binary.

### Build and run the example
```bash
./skillc build examples/hello.skill -o build/hello
./build/hello
```

Expected output:
```text
ReviewFirst POC is running
Hello from SkillScript v0.1
```
