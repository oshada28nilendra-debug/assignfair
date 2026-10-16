# AssignFair

Offline lab-session allocation for teaching coordinators comparing capacity-constrained assignments with a simple greedy baseline. Input availability and ranked preferences; export assignments, unmet demand, capacity use and an HTML review report. No services, paid APIs or third-party Python packages.

## Run

Python 3.12+:

```sh
python assignfair.py examples/students.json --out output
python -m unittest discover -s tests -v
```

Open `output/index.html`; `output/report.json` contains full machine-readable evidence. Output directory must be new. The example is **hand-authored synthetic data**, not real student information. Existing example reports are in `evaluation/`.

## Input contract

JSON has `sessions` (session name → nonnegative integer capacity) and `students` (list of `id`, `available`, `preferences`). Student IDs are unique. Availability lists acceptable session names; preferences ranks every available session exactly once, best first. Empty lists mean the student cannot attend any session. Unknown sessions, duplicate IDs/list entries, missing rankings, negative or noninteger capacities are rejected. Zero-capacity sessions are valid and can expose conflicts. Session IDs represent distinct, nonoverlapping choices; no calendar parsing is performed.

## Precise objective

Lexicographically **maximize assigned student count first, then minimize the sum of zero-based preference ranks among assigned students**. First choice costs 0, second 1, etc. Each student receives at most one session. Only available sessions are eligible; capacity is never exceeded. Unassigned students contribute no preference cost, so cost totals must not be compared in isolation when assignment counts differ. The report only computes a cost reduction when counts match.

This is not a universal fairness objective. It does not optimize worst individual outcome, demographic equity, envy-freeness or rotation across semesters. Equal-cost optima may favor earlier input order. Results are deterministic for identical ordered input, but not invariant to reordering. Human review is required before adopting assignments; the tool never sends notifications or changes a university system.

## Architecture and algorithm

`assignfair.py` separates validation, optimization, greedy baseline, report assembly and HTML rendering. The flow graph connects source → students (capacity 1) → available sessions (capacity 1, rank cost) → sink (session capacity). Successive shortest augmenting paths use Bellman-Ford on the residual graph, including negative-cost reverse edges that allow earlier assignments to be rerouted. Augment until no path remains, producing maximum flow and minimum cost for that flow. Pure functions leave input unchanged.

The greedy baseline iterates students in input order and picks their first remaining available preference. It does not reroute earlier choices. The optimizer costs roughly O(FVE), with F at most the student count; graph storage is O(V+E). This simple implementation targets small cohorts, not large university-wide timetabling.

## Conflicts and unmet demand

Reports distinguish no available session, all eligible sessions having zero capacity, and capacity competition. These explain why a student is unassigned under the reported allocation; they are not minimal conflict sets or proof that a particular student must always be excluded. Unknown/mismatched input constraints fail validation rather than being silently ignored. Sessions list used versus configured capacity.

## Measured evaluation

On the four-student synthetic example, optimized allocation assigns 2 students with preference cost 1; greedy assigns 1 with cost 0. One student has only a zero-capacity option and one has no availability. Lower greedy cost here is not a better overall outcome because coverage is the primary objective.

An equal-coverage test assigns 2 students in both methods: optimized rank cost 1 versus greedy 2. Eight automated tests include 200 seeded four-student cases compared against independent exhaustive enumeration of all assignments, checking the full lexicographic objective, capacity feasibility, repeatability and input immutability. This is bounded correctness evidence, not a large-scale performance benchmark or a claim of user adoption. Tests also cover malformed data, empty cohorts, HTML escaping and CLI overwrite protection. HTML layout has not been visually verified in a browser.

## Trade-offs and limitations

One session per student, integer capacities and complete strict preference lists only. No ties, quotas, groups, multi-session dependencies, accommodations or timetable overlap constraints. Preferences are declared rather than inferred. Reports contain the supplied IDs and preferences-derived outcomes; use synthetic or appropriately handled data when sharing. JSON/HTML exports are local and need no network.

## Interview explanation

“I modeled allocation as min-cost maximum flow, used residual edges to undo greedy choices, and defined coverage before preference cost. I checked the solver against exhaustive search and made the limits of the fairness objective explicit.”
