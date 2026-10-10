# Agent D review workspace

Created 2026-10-10. Source: ../workspace/d/projects and ../souls/d.md.

## Agent D
The Inventor is a configured resident using the shared Python controller. Its identity encourages open-ended invention, experiments, and a linked wiki. The controller supplies model calls, bounded tools, durable memory, budget accounting, and a Linux sandbox. Agent D is not a separate application implementation.

## Projects
- Code Symphony: Python source -> approximate function complexity metrics -> musical parameters -> synthesized WAV plus JSON. It explores whether listening can help code review; producing audio does not prove that people can identify code issues by ear.
- Smell Genome: functions -> complexity and heuristic smell traits -> compact encodings -> comparisons, history, drift alerts, clustering, and function lineage. An additional Python/JavaScript/Java analyzer and port-kinship score compare profiles across languages. Similarity is not proof of common ancestry, correctness, or maintenance risk.
- Inventor Foundations: an introductory README, not an executable project.

## Preliminary findings from source inspection
- No top-level dependency or packaging manifests were found in the two code project roots.
- Code Symphony recognizes ordinary FunctionDef nodes but omits AsyncFunctionDef. Walking entire function subtrees can attribute nested-function decisions to outer functions.
- Smell Genome CLI silently skips SyntaxError in directory scans and returns an empty genome for some invalid inputs.
- Cross-language analyze_repo catches every Exception and continues; missing parsers or other failures can look like successful partial/empty analysis.
- Main Smell Genome CLI uses the Python analyzer; cross-language port analysis is a separate module.
- Agent D reports 18 Code Symphony tests and 49 Smell Genome tests passing. These are its claims, not independently reproduced results.
- External examples demonstrate processing real code; they do not establish broadly accurate health or ancestry judgments. Weights selected on the showcased port pairs need evaluation on held-out pairs.

## Next build and verification work
1. Copy authored code and tests into a dated snapshot, excluding caches, generated outputs, and third-party scratch checkouts; record hashes.
2. Review execution paths and dependencies; create isolated reproducible environments and package manifests.
3. Reproduce existing suites and both CLIs end to end; preserve raw results.
4. Independently probe async/nested functions, invalid input, parser failures, determinism, and history handling.
5. Fix reproduced defects in the review copies and rerun relevant checks.
6. Deliver runnable projects, sample outputs, commands, and an evidence-based report.

Status: initial explanation and inspection complete; no project code executed or build/test results independently verified yet.
