# Complexity Reduction - Phase 2 Roadmap

## Executive Summary

**Phase 1 Achievements:**
- 10 functions refactored from F/E/D to A/B/C grade
- 73% average complexity reduction  
- 12 helper modules created
- Zero breaking changes

**Phase 2 Scope:**
- 27 functions identified with complexity > 20 (D/E/F grades)
- 1 function already refactored in Phase 2 (collect_links: 33 → 2)
- 26 functions remaining

---

## Remaining Functions by Priority

### Tier 1: Critical (F + High E-grade) - 5 functions

| Function | File | CC | Grade | Priority |
|----------|------|----|----|----------|
| `_worker_process` | cli/batch.py | 44 | F | 🔴 Highest |
| `run_batch_with_cfg` | ui/batch_runner.py | 39 | E | 🔴 Critical |
| `consolidate_and_report` | cli/reporting.py | 32 | E | 🔴 High |
| `split_doc_header` | dou_utils/text_cleaning.py | 31 | E | 🔴 High |
| `collect_open_list_options` | dou_utils/dropdowns/strategies.py | 31 | E | 🔴 High |
| `EditionRunnerService.run` | dou_utils/services/edition_runner_service.py | 31 | E | 🔴 High |

**Estimated Impact:** 6 functions × avg 30% improvement = High ROI

**Recommended Approach:**
- `_worker_process`: Complete existing partial refactoring (batch_worker.py, batch_job.py)
- `run_batch_with_cfg`: Extract UI state management, subprocess execution, result aggregation
- `consolidate_and_report`: Extract file loading, enrichment, bulletin generation  
- `split_doc_header`: Extract document type detection, header extraction, fallback logic
- `collect_open_list_options`: Extract dropdown opening strategies, option collection
- `EditionRunnerService.run`: Extract parallel/sequential execution, result aggregation

---

### Tier 2: High Impact D-grade (26-30) - 9 functions

| Function | File | CC | Focus Area |
|----------|------|----|------------|
| `_execute_plan` | ui/batch_executor.py | 30 | UI execution |
| `_read_dropdown_options_async` | cli/plan_live_async.py | 29 | Async dropdown |
| `build_plan_live_async` | cli/plan_live_async.py | 29 | Async plan building |
| `aggregate_outputs_by_plan` | cli/reporting.py | 29 | Aggregation |
| `main` | ui/eagendas_collect_subprocess.py | 29 | Subprocess main |
| `_select_by_text_async` | cli/plan_live_async.py | 28 | Async selection |
| `render_hierarchy_selector` | ui/eagendas_ui.py | 27 | UI rendering |
| `select_option_robust` | dou_utils/selection/helpers.py | 27 | Robust selection |
| `main_async` | ui/dou_collect_parallel.py | 26 | Async main |

**Pattern:** Heavy use of async/await, multiple retry strategies, UI state management

**Recommended Approach:**
- Extract retry strategies into `async_retry_helpers.py`
- Extract UI state management into `ui_state_helpers.py`  
- Extract option selection patterns into `option_selection_helpers.py`

---

### Tier 3: Medium D-grade (21-25) - 11 functions

| Function | File | CC | Category |
|----------|------|----|----------|
| `render_plan_editor_table` | ui/plan_editor.py | 24 | UI rendering |
| `_filter_opts` | cli/plan_live.py | 24 | Filtering |
| `filter_options` | dou_utils/core/option_filter.py | 24 | Core filtering |
| `_summarize_item_fixed` | dou_utils/bulletin_patch.py | 23 | Summarization |
| `filter_opts` | mappers/pairs_mapper.py | 23 | Mapping |
| `find_dropdown_by_id_or_label` | mappers/pairs_mapper.py | 23 | Mapping |
| `select_by_text_or_attrs` | mappers/pairs_mapper.py | 23 | Mapping |
| `render_plan_discovery` | ui/plan_editor.py | 22 | UI rendering |
| `map_pairs` | mappers/pairs_mapper.py | 21 | Mapping |
| `render_lista_manager` | ui/eagendas_ui.py | 21 | UI rendering |
| `render_execution_section` | ui/eagendas_ui.py | 21 | UI rendering |

**Pattern:** UI rendering, filtering, mapping - often with nested conditionals

**Recommended Approach:**
- Group mapper functions → `pairs_mapper_helpers.py`
- Group UI functions → `plan_editor_helpers.py`, `eagendas_ui_helpers.py`
- Consolidate filtering logic → `filter_helpers.py`

---

## Refactoring Strategies by Pattern

### Pattern 1: Async/Await Heavy Functions
**Examples:** `build_plan_live_async`, `_read_dropdown_options_async`, `_select_by_text_async`

**Strategy:**
```python
# Before: Mixed async logic
async def build_plan_live_async(...):
    # setup
    # error handling
    # retry logic
    # cleanup
    pass

# After: Separated concerns
from .async_helpers import (
    setup_async_context,
    execute_with_retry,
    cleanup_async_context
)

async def build_plan_live_async(...):
    ctx = await setup_async_context(...)
    result = await execute_with_retry(ctx, ...)
    await cleanup_async_context(ctx)
    return result
```

### Pattern 2: UI Rendering Functions
**Examples:** `render_plan_editor_table`, `render_hierarchy_selector`, `render_lista_manager`

**Strategy:**
```python
# Before: Monolithic rendering
def render_plan_editor_table(...):
    # state management
    # data loading
    # UI component creation
    # event handlers
    pass

# After: Component-based
from .ui_helpers import (
    load_plan_data,
    create_table_components,
    attach_event_handlers
)

def render_plan_editor_table(...):
    data = load_plan_data(...)
    components = create_table_components(data, ...)
    attach_event_handlers(components, ...)
    return components
```

### Pattern 3: Filtering/Mapping Functions
**Examples:** `filter_opts`, `map_pairs`, `find_dropdown_by_id_or_label`

**Strategy:**
```python
# Before: Nested conditionals
def filter_opts(opts, ...):
    results = []
    for opt in opts:
        if cond1:
            if cond2:
                if cond3:
                    results.append(transform(opt))
    return results

# After: Pipeline with predicates
from .filter_helpers import (
    create_filter_pipeline,
    sentinel_predicate,
    transform_option
)

def filter_opts(opts, ...):
    pipeline = create_filter_pipeline(
        predicates=[sentinel_predicate, ...],
        transformer=transform_option
    )
    return pipeline(opts)
```

### Pattern 4: Service Runner Functions  
**Examples:** `EditionRunnerService.run`, `_execute_plan`, `run_batch_with_cfg`

**Strategy:**
```python
# Before: Mixed execution modes
def run(self, ...):
    if parallel:
        # parallel execution logic
    else:
        # sequential execution logic
    # result aggregation
    pass

# After: Strategy pattern
from .execution_strategies import (
    ParallelExecutor,
    SequentialExecutor,
    ResultAggregator
)

def run(self, ...):
    executor = ParallelExecutor() if parallel else SequentialExecutor()
    results = executor.execute(...)
    return ResultAggregator().aggregate(results)
```

---

## Estimated Timeline

### Week 1: Tier 1 (Critical F/E-grade)
- Day 1-2: Complete `_worker_process` refactoring
- Day 3: `run_batch_with_cfg` + `consolidate_and_report`
- Day 4: `split_doc_header` + `collect_open_list_options`
- Day 5: `EditionRunnerService.run` + testing

### Week 2: Tier 2 (High D-grade)
- Day 1-2: Async functions (3 functions in plan_live_async.py)
- Day 3: Aggregation + execution (`aggregate_outputs_by_plan`, `_execute_plan`)
- Day 4: UI + selection (`render_hierarchy_selector`, `select_option_robust`)
- Day 5: Subprocess mains + testing

### Week 3: Tier 3 (Medium D-grade)  
- Day 1-2: Mapper functions (4 functions in pairs_mapper.py)
- Day 3: UI rendering (5 functions across plan_editor.py, eagendas_ui.py)
- Day 4: Filtering consolidation (3 filter functions)
- Day 5: Final testing, documentation, code review

---

## Success Metrics

### Phase 2 Target Goals
- ✅ Reduce 26 remaining D/E/F functions to C or better
- ✅ Achieve 70%+ average complexity reduction across all Phase 2 functions
- ✅ Create 8-10 new focused helper modules
- ✅ Maintain zero breaking changes
- ✅ Keep all import tests passing

### Overall Project Goals (Phase 1 + 2)
- ✅ Reduce repository average complexity from B (6.28) to B+ (≤5.5)
- ✅ Eliminate all F-grade functions (complexity > 40)
- ✅ Reduce E-grade functions (31-40) by 80%+
- ✅ Reduce D-grade functions (21-30) by 70%+
- ✅ 37 functions refactored total
- ✅ 20+ helper modules created

---

## Risk Mitigation

### High Risk Areas
1. **Async functions in plan_live_async.py** - Complex interdependencies
   - Mitigation: Create comprehensive async test suite first
   
2. **UI rendering functions** - Streamlit state management
   - Mitigation: Extract state management, test in isolation
   
3. **Mapper functions** - Used across multiple CLI commands
   - Mitigation: Ensure backward compatibility, extensive integration testing

### Testing Strategy
1. **Unit tests** for each new helper module
2. **Integration tests** for refactored functions
3. **Smoke tests** for critical paths (batch execution, plan building)
4. **Regression tests** using existing test suite

---

## Next Steps

1. ✅ **Complete Phase 2 analysis** (Done)
2. ⏳ **Begin Tier 1 refactoring** - Start with `_worker_process`
3. ⏳ **Create helper modules** for each pattern identified
4. ⏳ **Execute refactoring** in priority order
5. ⏳ **Comprehensive testing** after each batch
6. ⏳ **Documentation update** with final metrics

---

## Conclusion

Phase 1 demonstrated the viability and impact of systematic complexity reduction:
- 10 functions: 73% average reduction
- F-grade → A/B/C grade successfully
- Zero breaking changes maintained

Phase 2 will eliminate the remaining technical debt in 26 functions, bringing the entire repository to maintainable complexity levels and positioning the codebase for long-term sustainability.

**Total Impact (Phase 1 + 2):**
- 37 functions refactored
- ~70-75% average complexity reduction
- 20+ focused, testable helper modules
- Dramatically improved maintainability and testability
